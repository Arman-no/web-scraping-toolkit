"""
Download Instagram reels/posts and transcribe their audio locally.

Usage:
    uv run python transcribe_reel.py <reel_url_or_shortcode> [more ...] [--model tiny|base|small|medium|large-v3]

Pipeline:
    1. instaloader downloads each video logged-out. Only reels Instagram refuses to logged-out
       visitors (18+ or login-only accounts) are retried with the owner's Chrome session cookie,
       in one paced batch (see LOGIN FALLBACK below). Rare by design.
    2. faster-whisper transcribes it locally on CPU (no GPU/CUDA required).
    3. Only transcript text is printed to stdout -- whisper's per-segment progress log is written
       to a .log file instead, so a caller reading this script's output doesn't pay for that noise.

Output files land in ./downloads/<shortcode>/:
    <shortcode>.mp4        the video
    <shortcode>.txt        the transcript
    <shortcode>.caption.txt the post caption (logged-in fetches)
    <shortcode>.log        whisper's verbose per-segment log (ignore unless debugging)
"""

import argparse
import datetime
import json
import random
import re
import sys
import time
from pathlib import Path

import instaloader
from faster_whisper import WhisperModel

DOWNLOAD_DIR = Path(__file__).parent / "downloads"

# ---- LOGIN FALLBACK (2026-10-04; pacing from FinanceAdvisorAgent reports/Instagram reel fetch pacing.md)
# Only for reels Instagram hides from logged-out visitors (e.g. "People under 18 can't see this
# content"). The owner pastes ONLY the `sessionid` cookie value from Chrome DevTools
# (Application > Cookies > https://www.instagram.com) into SESSION_FILE; Chrome's app-bound cookie
# encryption makes reading it automatically need admin rights, so we don't. The value is never
# printed, logged or committed. Research behind the pacing: instaloader's own limits never bind at
# 5-10 reels; 2026 flags come from bursts, fixed intervals, restarts, fresh logins, VPNs, parallel
# use and fingerprint mismatch, not from volume. So:
#   - logged-out first, always; the cookie only after a login-required refusal
#   - ONE instaloader instance for the whole batch, test_login() once, Chrome's User-Agent
#   - random 45-150 s between logged-in reels, plus 60-120 s extra one time in five (7 reels ~10-15 min)
#   - instaloader's own per-request jitter stays on; iphone endpoint off (half the API calls)
#   - at most 30 logged-in reels a day; the first 401/429/checkpoint/challenge stops the batch for 24 h
SESSION_DIR = Path.home() / ".config" / "ig-session"
SESSION_FILE = SESSION_DIR / "sessionid.txt"
STATE_FILE = SESSION_DIR / "state.json"
MAX_PER_DAY = 30
CHROME_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
             "Chrome/154.0.0.0 Safari/537.36")  # the browser the cookie came from (Chrome 154)
LOGIN_HINTS = ("login", "log in", "fetching post metadata failed", "401", "403", "unavailable", "redirected")
BLOCK_HINTS = ("429", "401", "too many", "checkpoint", "challenge", "suspicious", "please wait", "feedback_required")


def extract_shortcode(url_or_code: str) -> str:
    """Accepts a full instagram.com/reel/<code>/ URL or a bare shortcode."""
    match = re.search(r"instagram\.com/(?:reel|p|tv)/([A-Za-z0-9_-]+)", url_or_code)
    return match.group(1) if match else url_or_code.strip("/")


def _state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(st: dict) -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(st), encoding="utf-8")


def check_allowed() -> None:
    st, now = _state(), time.time()
    if st.get("blocked_until", 0) > now:
        sys.exit(f"Logged-in fetches paused for {(st['blocked_until'] - now) / 3600:.1f} h more (Instagram pushed back).")
    if st.get("day") == datetime.date.today().isoformat() and st.get("count", 0) >= MAX_PER_DAY:
        sys.exit(f"Daily limit of {MAX_PER_DAY} logged-in reels reached; try again tomorrow.")


def human_gap(first: bool) -> None:
    """Random, human-like pause before a logged-in fetch (never a fixed interval)."""
    wait = random.uniform(5, 15) if first else random.uniform(45, 150)
    if not first and random.random() < 0.2:
        wait += random.uniform(60, 120)
    print(f"  waiting {wait:.0f} s (human pacing)...", file=sys.stderr)
    time.sleep(wait)


def record_fetch(blocked: bool = False) -> None:
    st, today = _state(), datetime.date.today().isoformat()
    if st.get("day") != today:
        st.update(day=today, count=0)
    st["count"] = st.get("count", 0) + 1
    if blocked:
        st["blocked_until"] = time.time() + 24 * 3600
    _save_state(st)


def make_loader(dest: Path, logged_in: bool = False) -> instaloader.Instaloader:
    loader = instaloader.Instaloader(
        dirname_pattern=str(dest),
        filename_pattern="{shortcode}",
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        post_metadata_txt_pattern="{caption}" if logged_in else "",
        quiet=True,
        **({"user_agent": CHROME_UA, "iphone_support": False} if logged_in else {}),
    )
    if logged_in:
        sid = SESSION_FILE.read_text(encoding="utf-8").strip()
        loader.context._session.cookies.set("sessionid", sid, domain=".instagram.com")
        user = loader.test_login()          # once per batch
        if not user:
            sys.exit("The saved sessionid is no longer valid; copy a fresh one from Chrome.")
        loader.context.username = user
    return loader


def download_reel(shortcode: str, dest: Path, loader: instaloader.Instaloader | None = None) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    loader = loader or make_loader(dest)
    loader.dirname_pattern = str(dest)
    post = instaloader.Post.from_shortcode(loader.context, shortcode)
    loader.download_post(post, target=dest)
    caption = dest / f"{shortcode}.txt"          # instaloader's caption file; the transcript reuses this name
    if caption.exists():
        caption.replace(dest / f"{shortcode}.caption.txt")

    video_path = dest / f"{shortcode}.mp4"
    if not video_path.exists():
        raise FileNotFoundError(
            f"Expected {video_path} after download -- instaloader's naming may "
            f"have differed; check {dest} for the actual file."
        )
    return video_path


def transcribe(video_path: Path, model_size: str, log_path: Path) -> str:
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(video_path), beam_size=5)

    lines = []
    with open(log_path, "w", encoding="utf-8") as log:
        log.write(f"language={info.language} probability={info.language_probability:.2f}\n")
        for seg in segments:
            log.write(f"[{seg.start:6.1f}s -> {seg.end:6.1f}s] {seg.text}\n")
            lines.append(seg.text.strip())

    return " ".join(lines).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="+", help="Reel URLs or bare shortcodes (a batch runs in one process)")
    parser.add_argument(
        "--model",
        default="small",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help="Whisper model size (default: small -- good accuracy/speed balance on CPU)",
    )
    args = parser.parse_args()

    gated, results = [], {}
    for target in args.targets:                      # 1. logged-out first, for every reel
        shortcode = extract_shortcode(target)
        print(f"Downloading {shortcode}...", file=sys.stderr)
        try:
            results[shortcode] = download_reel(shortcode, DOWNLOAD_DIR / shortcode)
        except Exception as e:
            if not any(h in str(e).lower() for h in LOGIN_HINTS):
                raise
            gated.append(shortcode)

    if gated:                                        # 2. the rare logged-in fallback, paced
        if not SESSION_FILE.exists():
            sys.exit(f"{', '.join(gated)} need a login (18+ or login-only account). To allow the rare logged-in "
                     f"fallback, paste your Instagram `sessionid` cookie value into {SESSION_FILE} and rerun.")
        check_allowed()
        loader = make_loader(DOWNLOAD_DIR, logged_in=True)
        for k, shortcode in enumerate(gated):
            check_allowed()
            human_gap(first=k == 0)
            print(f"Logged-in fetch {k + 1}/{len(gated)}: {shortcode}", file=sys.stderr)
            try:
                results[shortcode] = download_reel(shortcode, DOWNLOAD_DIR / shortcode, loader=loader)
                record_fetch()
            except Exception as e:
                blocked = any(h in str(e).lower() for h in BLOCK_HINTS)
                record_fetch(blocked=blocked)
                print(("Instagram pushed back; batch stopped, logged-in fetches paused for 24 h. " if blocked
                       else f"Logged-in fetch of {shortcode} failed: ") + type(e).__name__, file=sys.stderr)
                if blocked:
                    break

    for shortcode, video_path in results.items():    # 3. transcribe locally
        print(f"Transcribing {shortcode} with '{args.model}' model...", file=sys.stderr)
        dest = video_path.parent
        text = transcribe(video_path, args.model, dest / f"{shortcode}.log")
        (dest / f"{shortcode}.txt").write_text(text, encoding="utf-8")
        # Only transcript text goes to stdout -- this is what a caller should read.
        print(f"=== {shortcode} ===\n{text}" if len(args.targets) > 1 else text)


if __name__ == "__main__":
    main()

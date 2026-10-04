"""
Download an Instagram reel/post and transcribe its audio locally.

Usage:
    uv run python transcribe_reel.py <reel_url_or_shortcode> [--model tiny|base|small|medium|large-v3]

Pipeline:
    1. instaloader downloads the video, logged-out. Only if Instagram refuses that (18+ or
       otherwise login-only accounts) does it retry ONCE with the owner's Chrome session cookie,
       under human-like pacing (see LOGIN FALLBACK below). Rare by design.
    2. faster-whisper transcribes it locally on CPU (no GPU/CUDA required).
    3. Only the final transcript text is printed to stdout -- whisper's
       per-segment progress log is written to a .log file instead, so a
       caller reading this script's output doesn't pay for that noise.

Output files land in ./downloads/<shortcode>/:
    <shortcode>.mp4        the video
    <shortcode>.txt        the transcript
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

# ---- LOGIN FALLBACK (added 2026-10-04) ---------------------------------------------------
# Only for reels Instagram hides from logged-out visitors (e.g. "People under 18 can't see
# this content"). The owner pastes ONLY the `sessionid` cookie value from Chrome DevTools
# (Application > Cookies > https://www.instagram.com) into SESSION_FILE. Chrome's app-bound
# cookie encryption makes reading it automatically need admin rights, so we don't.
# The value is never printed, logged or committed. Pacing keeps the account unremarkable:
#   - logged-out first, always; the cookie is used only after a login-required refusal
#   - random 20-60 s pause before each logged-in fetch
#   - at least a random 3-6 min gap between logged-in fetches, at most 10 per day
#   - only the one post (video + caption): no profile browsing, likes or follows
#   - any rate limit / checkpoint / challenge -> no logged-in fetches for 24 h
SESSION_DIR = Path.home() / ".config" / "ig-session"
SESSION_FILE = SESSION_DIR / "sessionid.txt"
STATE_FILE = SESSION_DIR / "state.json"
MAX_PER_DAY = 10
LOGIN_HINTS = ("login", "log in", "fetching post metadata failed", "401", "403", "unavailable", "redirected")
BLOCK_HINTS = ("429", "too many", "checkpoint", "challenge", "suspicious", "please wait")


def _state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(st: dict) -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(st), encoding="utf-8")


def humanized_gate() -> None:
    """Wait (or refuse) so logged-in fetches look like a person watching the odd reel."""
    st, now = _state(), time.time()
    if st.get("blocked_until", 0) > now:
        hrs = (st["blocked_until"] - now) / 3600
        sys.exit(f"Logged-in fetches paused for {hrs:.1f} h more (Instagram pushed back earlier).")
    today = datetime.date.today().isoformat()
    if st.get("day") == today and st.get("count", 0) >= MAX_PER_DAY:
        sys.exit(f"Daily limit of {MAX_PER_DAY} logged-in reels reached; try again tomorrow.")
    gap = random.uniform(180, 360)
    wait = max(0.0, st.get("last", 0) + gap - now) + random.uniform(20, 60)
    print(f"Login-only reel: waiting {wait:.0f} s before a logged-in fetch (human pacing)...", file=sys.stderr)
    time.sleep(wait)


def record_fetch(blocked: bool = False) -> None:
    st, today = _state(), datetime.date.today().isoformat()
    if st.get("day") != today:
        st.update(day=today, count=0)
    st["count"] = st.get("count", 0) + 1
    st["last"] = time.time()
    if blocked:
        st["blocked_until"] = time.time() + 24 * 3600
    _save_state(st)


def extract_shortcode(url_or_code: str) -> str:
    """Accepts a full instagram.com/reel/<code>/ URL or a bare shortcode."""
    match = re.search(r"instagram\.com/(?:reel|p|tv)/([A-Za-z0-9_-]+)", url_or_code)
    return match.group(1) if match else url_or_code.strip("/")


def download_reel(shortcode: str, dest: Path, sessionid: str | None = None) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    loader = instaloader.Instaloader(
        dirname_pattern=str(dest),
        filename_pattern="{shortcode}",
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        post_metadata_txt_pattern="",
        quiet=True,
    )
    if sessionid:
        loader.context._session.cookies.set("sessionid", sessionid, domain=".instagram.com")
        user = loader.test_login()
        if not user:
            raise RuntimeError("The saved sessionid is no longer valid; copy a fresh one from Chrome.")
        loader.context.username = user
    post = instaloader.Post.from_shortcode(loader.context, shortcode)
    loader.download_post(post, target=dest)

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
    parser.add_argument("target", help="Reel URL or bare shortcode")
    parser.add_argument(
        "--model",
        default="small",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help="Whisper model size (default: small -- good accuracy/speed balance on CPU)",
    )
    args = parser.parse_args()

    shortcode = extract_shortcode(args.target)
    dest = DOWNLOAD_DIR / shortcode

    print(f"Downloading {shortcode}...", file=sys.stderr)
    try:
        video_path = download_reel(shortcode, dest)
    except Exception as e:
        msg = str(e).lower()
        if not any(h in msg for h in LOGIN_HINTS):
            raise
        if not SESSION_FILE.exists():
            sys.exit(f"{shortcode} needs a login (18+ or login-only account). To allow the rare logged-in "
                     f"fallback, paste your Instagram `sessionid` cookie value into {SESSION_FILE} and rerun.")
        humanized_gate()
        sid = SESSION_FILE.read_text(encoding="utf-8").strip()
        try:
            video_path = download_reel(shortcode, dest, sessionid=sid)
            record_fetch()
        except Exception as e2:
            blocked = any(h in str(e2).lower() for h in BLOCK_HINTS)
            record_fetch(blocked=blocked)
            sys.exit(("Instagram pushed back; logged-in fetches paused for 24 h. " if blocked else "Logged-in fetch failed: ")
                     + type(e2).__name__)

    print(f"Transcribing with '{args.model}' model...", file=sys.stderr)
    transcript_path = dest / f"{shortcode}.txt"
    log_path = dest / f"{shortcode}.log"
    text = transcribe(video_path, args.model, log_path)
    transcript_path.write_text(text, encoding="utf-8")

    # Only the transcript text goes to stdout -- this is what a caller should read.
    print(text)


if __name__ == "__main__":
    main()

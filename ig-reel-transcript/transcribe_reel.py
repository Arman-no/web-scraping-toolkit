"""
Download an Instagram reel/post and transcribe its audio locally.

Usage:
    .venv\\Scripts\\python.exe transcribe_reel.py <reel_url_or_shortcode> [--model tiny|base|small|medium|large-v3]

Pipeline:
    1. instaloader downloads the video (logged-out, public posts only).
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
import re
import sys
from pathlib import Path

import instaloader
from faster_whisper import WhisperModel

DOWNLOAD_DIR = Path(__file__).parent / "downloads"


def extract_shortcode(url_or_code: str) -> str:
    """Accepts a full instagram.com/reel/<code>/ URL or a bare shortcode."""
    match = re.search(r"instagram\.com/(?:reel|p|tv)/([A-Za-z0-9_-]+)", url_or_code)
    return match.group(1) if match else url_or_code.strip("/")


def download_reel(shortcode: str, dest: Path) -> Path:
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
    video_path = download_reel(shortcode, dest)

    print(f"Transcribing with '{args.model}' model...", file=sys.stderr)
    transcript_path = dest / f"{shortcode}.txt"
    log_path = dest / f"{shortcode}.log"
    text = transcribe(video_path, args.model, log_path)
    transcript_path.write_text(text, encoding="utf-8")

    # Only the transcript text goes to stdout -- this is what a caller should read.
    print(text)


if __name__ == "__main__":
    main()

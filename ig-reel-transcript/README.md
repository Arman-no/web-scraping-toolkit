# ig-reel-transcript

Downloads a public Instagram reel (via `instaloader`, logged-out) and
transcribes its audio locally (via `faster-whisper`, CPU, no GPU/CUDA
needed, no external API, nothing uploaded anywhere).

## Setup

### Fresh clone

```
python -m venv .venv
.venv\Scripts\pip.exe install -r requirements.txt
```

`faster-whisper` decodes audio itself via the bundled `av` (PyAV) library --
no system ffmpeg required. The Whisper model weights download on first run
(cached under your user profile afterward).

### This machine

Already installed in `.venv` (Python 3.13, `instaloader`, `faster-whisper`).
Nothing else to do.

## Usage

```
.venv\Scripts\python.exe transcribe_reel.py https://www.instagram.com/reel/SHORTCODE/
```

or with a bare shortcode:

```
.venv\Scripts\python.exe transcribe_reel.py SHORTCODE
```

Optional model size (`tiny`/`base`/`small`/`medium`/`large-v3`), default `small`:

```
.venv\Scripts\python.exe transcribe_reel.py SHORTCODE --model base
```

Only the final transcript text prints to stdout -- that's what should get
read into an LLM's context, not the whisper run log. Output lands in
`downloads/<shortcode>/`:
- `<shortcode>.mp4` -- the video
- `<shortcode>.txt` -- the transcript (same text as stdout)
- `<shortcode>.log` -- whisper's per-segment timestamped log (debugging only)

## Reality check

- **Public posts only.** Logged-out `instaloader` can't reach anything behind
  a login wall, which is most of Instagram's own recommendation/explore
  surface -- it works for a direct reel link you already have.
- **No native Instagram captions exist to scrape.** Even reels that show
  on-screen auto-captions don't expose them as a fetchable text asset --
  transcription always happens via Whisper here, there's no shortcut.
- **Model size tradeoff:** `tiny`/`base` are near-instant on a laptop CPU but
  less accurate; `small` (the default) is the practical balance; `medium`/
  `large-v3` are noticeably slower on CPU-only hardware (no CUDA GPU here)
  and only worth it for something like heavy accents or background noise.
- **Rate limits:** Instagram will start throttling/blocking an IP that hits
  it too often in a short window. Fine for occasional single-reel pulls;
  don't loop this over dozens of URLs back-to-back without adding delay.

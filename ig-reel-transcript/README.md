# ig-reel-transcript

Downloads a public Instagram reel (via `instaloader`, logged-out) and
transcribes its audio locally (via `faster-whisper`, CPU, no GPU/CUDA
needed, no external API, nothing uploaded anywhere).

## Setup

A [uv](https://docs.astral.sh/uv/) project: dependencies are in `pyproject.toml`,
and the exact tested versions are in `uv.lock`.

```
uv sync                      # creates .venv with the locked versions
```

`faster-whisper` decodes audio itself via the bundled `av` (PyAV) library --
no system ffmpeg required. The Whisper model weights download on first run
(cached under your user profile afterward).

## Usage

```
uv run python transcribe_reel.py https://www.instagram.com/reel/SHORTCODE/
```

or with a bare shortcode:

```
uv run python transcribe_reel.py SHORTCODE
```

Optional model size (`tiny`/`base`/`small`/`medium`/`large-v3`), default `small`:

```
uv run python transcribe_reel.py SHORTCODE --model base
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

## 18+ / login-only reels (rare fallback)

Some accounts hide their reels from logged-out visitors ("People under 18 can't see this content").
The tool always tries logged-out first. Only when Instagram refuses does it retry once with your
own Instagram session, and only if you have saved it:

1. In Chrome, logged in, open instagram.com, press F12, go to Application > Cookies >
   https://www.instagram.com, and copy the **Value** of `sessionid`.
2. Paste only that value into `%USERPROFILE%\.config\ig-session\sessionid.txt` (outside every repo).

Chrome's app-bound cookie encryption means reading cookies automatically would need admin rights,
so the tool deliberately uses this one pasted cookie instead. The value is never printed, logged or
committed.

Human-like pacing (so the account stays unremarkable): a random 20-60 s pause before each
logged-in fetch, at least a random 3-6 min gap between logged-in fetches, at most 10 per day, only
the requested post (no browsing, likes or follows), and a 24 h stop if Instagram rate-limits or asks
for a checkpoint. State lives in `%USERPROFILE%\.config\ig-session\state.json`.

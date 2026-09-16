# web-scraping-toolkit — Specification

Status: stable, low-change. Describes the repository as it actually is, not a
roadmap. Last verified against the tree on 2026-09-16.

---

## 1. Purpose and scope

Two small, self-contained command-line tools for retrieving web content that a
plain HTTP request cannot obtain:

1. **`scrapling-scraper/`** — pages that refuse or defeat a plain fetch: bot
   walls, Cloudflare interstitials, and client-side-rendered apps whose real
   content is not in the served HTML.
2. **`ig-reel-transcript/`** — Instagram reels and video posts, which expose no
   fetchable caption track, so the text has to be produced by transcribing the
   audio.

Both exist because an LLM agent's built-in `WebFetch`-style tool fails on these
two classes of target: the first returns an empty shell or a 403, the second
has no text to return at all.

**In scope:** local, operator-driven retrieval of individual URLs, and
extraction of a compact text representation from them.

**Out of scope:** crawling, scheduling, queueing, proxy rotation, retries,
authentication to any site, bulk collection, and any form of dataset building.
None of that exists here, and none of it is planned. This is a manual tool
reached for one URL at a time.

---

## 2. Which tool to use

| Situation | Tool |
|---|---|
| A plain fetch returns the content you need | Neither — use the plain fetch |
| Empty shell, JS-rendered SPA, 403, Cloudflare/bot page | `scrapling-scraper` |
| Page needs clicks, scrolling, or waiting on dynamic content | `scrapling-scraper`, `DynamicFetcher` |
| You need what was *said* in an Instagram reel/post/video | `ig-reel-transcript` |
| You need a YouTube transcript | Neither — YouTube exposes a caption track; fetch that |

Within `scrapling-scraper` the rule is to escalate, not to start at the top:
`Fetcher` (no browser) → `StealthyFetcher` (real browser, fingerprint
spoofing) → `DynamicFetcher` (full automation). Each rung costs more time and
more resources than the one below it.

---

## 3. Architecture

```
web-scraping-toolkit/
├── LICENSE
├── README.md
├── docs/SPEC.md
├── scrapling-scraper/          # tool 1 — its own venv, requirements, README
│   ├── README.md
│   ├── example.py
│   └── requirements.txt
└── ig-reel-transcript/         # tool 2 — its own venv, requirements, README
    ├── README.md
    ├── requirements.txt
    └── transcribe_reel.py
```

There is no shared package, no common library, and no top-level `setup.py`.
The two tools share nothing but the repository that holds them.

### Why each tool gets its own virtualenv

This is the one structural decision in the repo, and it is deliberate:

- **The dependency sets have nothing in common and are both heavy.**
  `scrapling[fetchers]` resolves to ~22 packages and its install step then
  downloads Playwright browser binaries (hundreds of MB). `faster-whisper`
  pulls a native inference stack — `ctranslate2`, `onnxruntime`, `numpy`, and
  `av` with bundled FFmpeg libraries. A single shared venv would force anyone
  who wants one tool to install the other's entire stack.
- **Failure isolation.** Upgrading Scrapling (which tracks browser-automation
  internals and moves fast) cannot break the transcriber, and vice versa. Each
  tool can be deleted, rebuilt, or pinned to a different Python without
  touching the other.
- **Unambiguous invocation.** Every documented command calls a venv's
  interpreter by absolute path (`.venv\Scripts\python.exe script.py`). Nothing
  is ever "activated", so there is no PATH state to get wrong — which matters
  most when the caller is an agent rather than a human, since the agent cannot
  see which environment a previous shell left behind.

The cost is duplicated disk and two install steps instead of one. For two
tools that are run occasionally and by hand, that is the cheaper trade.

---

## 4. Tool 1 — `scrapling-scraper`

A thin, self-contained install of [Scrapling](https://github.com/D4Vinci/Scrapling)
plus a worked example. The repository contributes no scraping logic of its
own; the value is the pinned-down environment, the escalation ladder, and the
convention of extracting text rather than HTML.

### 4.1 Interface

`example.py` is a **smoke test and usage reference, not a CLI**. It takes no
arguments and accepts no input. Running it performs a plain `Fetcher.get()`
against `https://example.com` and prints the HTTP status and page title. Its
remaining sections — stealth fetching, markdown extraction, CSS selection —
are present as commented reference code.

The real interface is the Python API you write against in your own script:

| Call | Behaviour |
|---|---|
| `Fetcher.get(url)` | Plain HTTP request, no browser. Fastest; try first. |
| `StealthyFetcher.fetch(url, headless=True)` | Real browser with anti-fingerprinting. For bot walls and JS-rendered content. |
| `DynamicFetcher` | Full Playwright automation — clicks, scrolling, waits. |

Response object, as used in `example.py`:

- `page.status` — HTTP status code.
- `page.css("selector::text").extract_first()` / `.extract()` — targeted extraction.
- `page.markdown()` — compact whole-page text.

**Convention:** pass `page.markdown()` or a `page.css(...)` result into an
LLM's context, never the raw HTML. Compact extraction is the entire reason to
reach for this over a plain fetch; handing back raw HTML discards the benefit.

### 4.2 Outputs and exit codes

`example.py` writes to stdout only and creates no files. It defines no exit
codes of its own, so it inherits Python's defaults:

| Code | Meaning |
|---|---|
| `0` | Ran to completion |
| `1` | Uncaught exception — traceback on stderr |

### 4.3 Failure modes

No error handling is implemented; every failure surfaces as a traceback and
exit `1`.

- **Network failure or DNS error** — raised from the underlying HTTP client.
- **Browser binaries missing** — `StealthyFetcher`/`DynamicFetcher` fail if
  `scrapling install` was never run after `pip install`. This is the most
  common setup mistake.
- **Target still blocks the stealth fetcher.** Anti-bot systems change; a
  fetcher that worked last month may return a challenge page today. A `200`
  carrying a challenge page is *not* an error and will not raise — inspect the
  content, do not trust the status code alone.
- **Site requires login.** Out of scope; nothing here authenticates.

### 4.4 Dependencies and their roles

`requirements.txt` declares exactly one line: `scrapling[fetchers]`. It is
unpinned, so the resolved set moves with upstream. Resolved at the time of
writing (22 packages):

| Package | Role |
|---|---|
| `scrapling` | The library itself — fetchers, parsing, extraction |
| `playwright`, `patchright` | Browser automation; `patchright` is the stealth-patched fork |
| `browserforge`, `apify_fingerprint_datapoints` | Generated browser fingerprints and their datasets |
| `curl_cffi` | HTTP client with TLS/JA3 fingerprint impersonation |
| `lxml`, `cssselect`, `w3lib` | HTML parsing, CSS-selector translation, URL/markup helpers |
| `Protego` | robots.txt parser (present in the tree — see §8) |
| `orjson`, `msgspec` | Fast JSON/struct serialisation |
| `tld` | Top-level-domain lookups |
| `cffi`, `pycparser`, `greenlet`, `pyee`, `anyio`, `certifi`, `idna`, `click`, `typing_extensions` | Transitive support libraries |

`scrapling install` additionally downloads Chromium and WebKit binaries. Those
are third-party browser builds fetched at setup time; they are not
redistributed by this repository.

### 4.5 Setup and usage

```
cd scrapling-scraper
python -m venv .venv
.venv\Scripts\pip.exe install -r requirements.txt
.venv\Scripts\scrapling.exe install      # downloads Chromium/WebKit binaries
.venv\Scripts\python.exe example.py      # smoke test
```

Upgrading:

```
.venv\Scripts\pip.exe install --upgrade scrapling
.venv\Scripts\scrapling.exe install      # re-sync browser binaries after upgrade
```

---

## 5. Tool 2 — `ig-reel-transcript`

Downloads a public Instagram reel or video post and transcribes its audio
locally. No API key, no cloud service, nothing uploaded anywhere: the audio
and the resulting text never leave the machine.

### 5.1 Interface

```
.venv\Scripts\python.exe transcribe_reel.py <target> [--model SIZE]
```

**Inputs**

| Argument | Required | Accepted values |
|---|---|---|
| `target` | yes | A full URL matching `instagram.com/{reel,p,tv}/<shortcode>`, or a bare shortcode |
| `--model` | no | `tiny`, `base`, `small` (default), `medium`, `large-v3` |

Target parsing is a single regex against the `reel`/`p`/`tv` URL forms. Any
input that does not match is stripped of surrounding slashes and used as a
shortcode verbatim — so a malformed URL is not rejected up front, it fails
later at download with a not-found error.

**Outputs** — written to `downloads/<shortcode>/` next to the script:

| File | Contents |
|---|---|
| `<shortcode>.mp4` | The downloaded video |
| `<shortcode>.txt` | The transcript — identical to stdout |
| `<shortcode>.log` | Detected language with confidence, then one timestamped line per segment |

**Streams**

- **stdout** — the transcript text, and nothing else. This is the only stream
  a caller should read into an LLM context.
- **stderr** — two progress lines (`Downloading …`, `Transcribing with …`) and
  any traceback.

The split is deliberate: Whisper's per-segment output is useful for debugging
and worthless in an LLM's context window, so it goes to the `.log` file rather
than to stdout.

### 5.2 Exit codes

No explicit exit codes are set; the script inherits argparse's and Python's:

| Code | Meaning |
|---|---|
| `0` | Transcript produced and written |
| `1` | Uncaught exception — traceback on stderr |
| `2` | Usage error from argparse — missing `target`, or a `--model` outside the allowed list |

Because there is no `try`/`except` anywhere in the script, every runtime
failure is code `1` with a traceback. A caller that needs to distinguish
causes must read stderr.

### 5.3 Failure modes

| Condition | Result |
|---|---|
| Post is private, deleted, or behind a login wall | An `instaloader.exceptions` error (e.g. `QueryReturnedNotFoundException`, `LoginRequiredException`, `PrivateProfileNotFollowedException`) → exit `1` |
| Instagram rate-limits or blocks the IP | `TooManyRequestsException` / `ConnectionException` → exit `1` |
| Download succeeded but the file is not named `<shortcode>.mp4` | Explicit `FileNotFoundError` naming the expected path, so the actual directory can be inspected |
| Model weights cannot be downloaded on first run | Network error from `huggingface_hub` → exit `1` |
| Video has no speech | Exit `0` with an empty transcript — silence is not an error |

Note the rate-limit case is the one most likely to be hit in practice, and it
is indistinguishable from a transient network failure without reading the
traceback.

### 5.4 Dependencies and their roles

`requirements.txt` declares two unpinned lines, `instaloader` and
`faster-whisper`, which resolve to ~30 packages.

| Package | Role |
|---|---|
| `instaloader` | Downloads the post's video, logged out |
| `faster-whisper` | Whisper inference wrapper |
| `ctranslate2` | The actual inference engine — runs the quantised model on CPU |
| `av` (PyAV) | Decodes the video's audio. Its wheel bundles FFmpeg shared libraries, so **no system ffmpeg is required** |
| `onnxruntime` | Backend for the voice-activity-detection model |
| `huggingface_hub`, `hf-xet`, `filelock` | Fetch and cache the model weights |
| `tokenizers` | Text tokenisation for decoding |
| `numpy` | Array maths in the audio pipeline |
| `httpx`, `httpcore`, `h11`, `requests`, `urllib3`, `certifi`, `idna`, `charset-normalizer` | HTTP stack |
| `tqdm`, `PyYAML`, `protobuf`, `flatbuffers`, `fsspec`, `colorama`, `packaging`, `anyio`, `typing_extensions` | Transitive support libraries |

**Model weights are not in this repository.** On first use of a given size,
`faster-whisper` downloads the corresponding `Systran/faster-whisper-<size>`
repository from Hugging Face — a CTranslate2 conversion of OpenAI's Whisper,
published under the MIT licence — and caches it under the user profile
(`~/.cache/huggingface/hub`). Subsequent runs are offline for that size.

### 5.5 Setup and usage

```
cd ig-reel-transcript
python -m venv .venv
.venv\Scripts\pip.exe install -r requirements.txt
```

```
.venv\Scripts\python.exe transcribe_reel.py https://www.instagram.com/reel/SHORTCODE/
.venv\Scripts\python.exe transcribe_reel.py SHORTCODE --model base
```

Model-size trade-off, on CPU-only hardware:

- `tiny` / `base` — near-instant, noticeably less accurate.
- `small` — the default, and the practical balance.
- `medium` / `large-v3` — substantially slower without a GPU; worth it only
  for heavy accents, poor audio, or dense background noise.

---

## 6. Configuration

There is no configuration file, and neither script reads any environment
variable. Every knob is either a flag or a constant in the source:

| Knob | Where | Default |
|---|---|---|
| Whisper model size | `--model` flag | `small` |
| Output directory | `DOWNLOAD_DIR` constant in `transcribe_reel.py` | `./downloads` |
| Device / quantisation | `WhisperModel(..., device="cpu", compute_type="int8")` | CPU, int8 — edit to use a GPU |
| Decoding beam width | `beam_size=5` in `transcribe()` | 5 |
| Fetcher choice, headless mode | Arguments in your own Scrapling script | `headless=True` |

`.gitignore` excludes `.venv/`, `downloads/`, `__pycache__/`, `*.pyc`, `*.log`
and `.env`. Nothing currently reads a `.env` file — that entry is
precautionary, so a future credential file cannot be committed by accident.

---

## 7. Known limitations

**scrapling-scraper**

- No CLI. Using it means writing a short Python script against the library.
- `example.py` is a smoke test against `example.com`; it is not a template for
  any real extraction job.
- Anti-bot bypass is never permanent. Detection changes; expect breakage.
- A challenge or interstitial page can arrive with a `200` status. Validate
  content, not just status.
- No authentication, no proxy support, no retry or backoff logic.
- `requirements.txt` is unpinned, so an install today and an install in six
  months are not the same environment.

**ig-reel-transcript**

- **Public posts only.** Logged-out `instaloader` cannot see private accounts,
  and cannot reach Instagram's own explore or recommendation surfaces. It
  works for a direct link you already have.
- **Instagram exposes no fetchable caption track.** Even reels displaying
  on-screen auto-captions do not publish them as a text asset, so
  transcription is the only route — there is no shortcut to add later.
- Transcription quality is Whisper's: accents, overlapping speakers, music
  over speech, and code-switching all degrade it. Output is not a
  verbatim-accurate record and should not be treated as one.
- No batching, no delay, no retry. Sequential runs against many URLs will get
  the IP throttled (see §8).
- Downloaded videos accumulate in `downloads/` indefinitely; nothing cleans
  them up.
- Windows is the only environment this has been exercised on. The scripts use
  `pathlib` and contain no platform-specific calls, so POSIX should work, but
  it is untested and all documented paths use Windows form.

---

## 8. Responsible use

These tools retrieve content from services that did not invite the request.
That places the decisions below on the operator — the code makes none of them.

**Site terms and robots.txt.** Check a site's terms of service and its
`robots.txt` before fetching it, and honour what they say. `Protego`, a
robots.txt parser, appears in Scrapling's dependency tree, but **nothing in
this repository consults it for you** — no automatic robots.txt check happens
at any point. If you need that, implement it in your own script.

**Bot evasion is a deliberate act.** `StealthyFetcher` exists to make an
automated request look like a human one. Using it to render JavaScript that a
plain client cannot execute is an ordinary technical workaround. Using it to
get around an access control that has specifically refused you is a different
thing, and the fact that a tool makes it easy does not make it appropriate.
Know which one you are doing.

**Rate limiting.** Neither tool implements any delay, backoff, or
concurrency limit. Serving a request costs the target real resources. Fetch
what you actually need, one target at a time, with pauses between requests —
Instagram in particular will throttle or block an IP that is hit repeatedly in
a short window, and that is the system behaving correctly, not a bug to route
around.

**Personal data.** Do not use these tools to collect personal data — profiles,
contact details, or any material that identifies individuals — and do not
assemble retrieved content into a dataset about people. Content being publicly
visible does not make collecting it lawful or acceptable, and data-protection
regimes such as the GDPR apply to scraped personal data exactly as they apply
to data collected any other way.

**Instagram transcription.** Use `ig-reel-transcript` only for content you have
a right to use: your own, content you have permission to process, or a
specific piece you are entitled to quote or analyse. The downloaded video and
its transcript remain the creator's work, whatever your local rules on
quotation and fair dealing allow. Transcribing at scale, republishing a
transcript as your own, or building a corpus out of other people's reels is
outside what this tool is for.

**Not legal advice.** This section describes the intended use of the software.
It is not legal advice, and it does not tell you what is lawful where you are.
Scraping law varies by jurisdiction and keeps moving. If a use matters, take
proper advice on it.

---

## 9. Claude Code skill integration

The toolkit is registered as a personal Claude Code skill so an agent reaches
for it on its own when a plain fetch comes back empty or blocked, rather than
reporting failure and stopping.

**The skill file is not part of this repository.** It lives in the user's
Claude Code configuration:

```
~/.claude/skills/web-scraping-toolkit/SKILL.md
```

To register the toolkit after cloning, create that directory and write a
`SKILL.md` with YAML frontmatter:

```yaml
---
name: web-scraping-toolkit
description: Use when a web page can't be reached with a plain fetch (bot walls,
  Cloudflare, client-side-rendered JS content) or when the task needs an
  Instagram reel, post, or video transcribed.
metadata:
  trigger: WebFetch fails or returns an empty/JS-shell page, a site blocks
    scraping, or the user asks for an Instagram reel/video transcript
---
```

The body should give the agent what it cannot infer: the **absolute paths to
your clone's two venv interpreters**, the fetcher escalation ladder, and the
extraction convention.

Because the skill body hard-codes absolute interpreter paths, **it breaks
silently if the clone is moved or renamed.** The paths in the skill file must
be checked against the clone's real location whenever either changes.

What the skill needs to convey, and why each point exists:

- Try `Fetcher` before `StealthyFetcher` — most targets need no browser, and
  the browser path is far slower.
- Read `.markdown()` or `.css(...)` into context, never `page.html_content` —
  raw HTML defeats the purpose of using this over a plain fetch.
- For reels, read **stdout only**; the `.log` file exists precisely so its
  contents stay out of the context window.
- Instagram has no caption track to fetch, so the agent should not waste turns
  looking for one.
- A private account's reel is not retrievable by this toolkit at all — the
  correct response is to say so, not to retry.

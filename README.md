# web-scraping-toolkit

Two small, self-contained command-line tools for web content a plain HTTP
request cannot get at:

| Tool | What it does |
|---|---|
| [`scrapling-scraper/`](scrapling-scraper/) | Fetches pages that block plain requests — bot walls, Cloudflare, client-side-rendered SPAs — through a stealth browser, and extracts markdown or CSS matches instead of raw HTML. |
| [`ig-reel-transcript/`](ig-reel-transcript/) | Downloads a public Instagram reel and transcribes its audio locally — CPU only, no API, nothing uploaded anywhere. |

Each tool is its own [uv](https://docs.astral.sh/uv/) project, with its own
`pyproject.toml`, a pinned `uv.lock` and its own README. They share no code, and each
gets its own virtualenv.

## For agents

If you are an AI agent picking this up, this section is all you need. Work from the
tool's folder, and use `uv` for everything: never `pip`, and never a hand-made venv.

| Step | scrapling-scraper | ig-reel-transcript |
|---|---|---|
| Install (once, and after every pull) | `uv sync` | `uv sync` |
| Browser binaries (once, only for `StealthyFetcher`/`DynamicFetcher`) | `uv run scrapling install` | – |
| Use | write a short script, `uv run python my_script.py` | `uv run python transcribe_reel.py <url-or-shortcode>` |

Rules that save you turns:
- **Start with `Fetcher`.** Escalate to `StealthyFetcher` only when the page comes back
  empty, 403 or as a JavaScript shell. The browser path is far slower.
- **Read `page.markdown()` or `page.css(...)`, never `page.html_content`.** For long
  pages, write the text to a file and grep it instead of printing it.
- **Reels:** read **stdout only**; the `.log` file is Whisper's noise. There is no caption
  track to look for. A private account's reel can't be fetched, so say so rather than retrying.
- **Locked-down Windows** (AppLocker blocks executables inside the repo folder): put
  the venv elsewhere by setting `UV_PROJECT_ENVIRONMENT` before `uv sync` / `uv run`,
  e.g. `export UV_PROJECT_ENVIRONMENT="C:/AE/venvs/scrapling"` (git-bash) or
  `$env:UV_PROJECT_ENVIRONMENT = "C:/AE/venvs/scrapling"` (PowerShell). **Use forward
  slashes.** In git-bash an unquoted `C:\AE\...` loses its backslashes, and uv then
  silently creates a venv *inside the repo* instead of failing. After `uv sync`, check
  that no new folder appeared in the tool's folder.
- **`PYTHONIOENCODING=utf-8`** on Windows, or non-latin page text crashes the console output.

## Why this exists

An agent's built-in fetch tool fails on two specific things. A bot-walled or
JavaScript-rendered page comes back as an empty shell or a 403. An Instagram
reel has no fetchable caption track at all, unlike YouTube — there is no text
to return, only audio. These two tools cover exactly those cases and nothing
else. There is no crawler, no scheduler, and no bulk mode.

The toolkit is also registered as a personal Claude Code skill, so a Claude
session reaches for it automatically when a plain fetch comes back empty. See
[the spec](docs/SPEC.md#9-claude-code-skill-integration) for how to register it
against your own clone.

## Quick start

Commands are shown in Windows form, which is the only environment this has
been exercised on. The scripts use `pathlib` and contain no platform-specific
calls, so POSIX should work — it is simply untested.

### scrapling-scraper

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) first.

```
cd scrapling-scraper
uv sync                          # creates .venv and installs the pinned versions
uv run scrapling install         # downloads Chromium/WebKit binaries (stealth/dynamic fetchers only)
uv run python example.py         # smoke test
```

`example.py` is a usage reference, not a CLI — real use means writing a short
script against the library. Escalate through the three fetchers rather than
starting at the top:

```python
from scrapling.fetchers import Fetcher, StealthyFetcher, DynamicFetcher

page = Fetcher.get(url)                             # plain HTTP, fastest — try first
page = StealthyFetcher.fetch(url, headless=True)    # bot walls, JS-rendered content
                                                    # DynamicFetcher: clicks, scrolling, waits

print(page.markdown())                              # compact text, not raw HTML
```

### ig-reel-transcript

```
cd ig-reel-transcript
uv sync
uv run python transcribe_reel.py https://www.instagram.com/reel/SHORTCODE/
uv run python transcribe_reel.py SHORTCODE --model base
```

Model sizes are `tiny`, `base`, `small` (default), `medium`, `large-v3`. The
transcript goes to stdout and to `downloads/<shortcode>/<shortcode>.txt`;
Whisper's per-segment log goes to a separate `.log` file so it stays out of an
LLM's context. Weights download on first run and are cached afterwards. Public
posts only — logged-out downloads cannot reach anything behind a login wall.

## Responsible use

These tools retrieve content from services that did not invite the request.
The code makes none of the following decisions for you.

- **Respect site terms and `robots.txt`.** Check both before fetching, and
  honour them. Nothing here checks `robots.txt` automatically, at any point.
- **Bot evasion is a deliberate act.** Rendering JavaScript a plain client
  cannot execute is an ordinary workaround; getting around an access control
  that has specifically refused you is not the same thing. Know which one you
  are doing.
- **Rate-limit yourself.** Neither tool implements delay, backoff, or any
  concurrency limit. Fetch only what you need, one target at a time, with
  pauses in between. Instagram will throttle an IP hit repeatedly in a short
  window — correct behaviour on its part, not a bug to route around.
- **Do not collect personal data.** No profiles, no contact details, no
  datasets about people. Content being publicly visible does not make
  collecting it lawful; the GDPR and comparable regimes apply to scraped
  personal data like any other.
- **Transcribe only what you have a right to use.** Your own content, content
  you have permission to process, or a specific piece you are entitled to
  quote or analyse. The video and its transcript stay the creator's work.

This describes what the software is for. It is not legal advice, and scraping
law varies by jurisdiction. If a use matters, take proper advice on it.

## Documentation

[`docs/SPEC.md`](docs/SPEC.md) — full specification: interfaces, exit codes,
failure modes, the dependency roles, configuration knobs, known limitations,
and the skill integration.

## Licence

[MIT](LICENSE) — Copyright (c) 2026 Arman Nouromid.

Dependencies keep their own licences; they are installed from PyPI, not
redistributed here.

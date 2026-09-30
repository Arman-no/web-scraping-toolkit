# scrapling-scraper

Self-contained install of [Scrapling](https://github.com/D4Vinci/Scrapling) — a Python
web-scraping library with stealth-browser and anti-bot-bypass fetchers, plus
markdown/CSS/XPath extraction so only the relevant text ever needs to reach an
LLM's context (not the raw page HTML).

## Setup

A [uv](https://docs.astral.sh/uv/) project: dependencies are in `pyproject.toml`,
and the exact tested versions are in `uv.lock`.

```
uv sync                      # creates .venv with the locked versions
uv run scrapling install     # downloads Playwright's Chromium/WebKit binaries
```

`uv run scrapling install` is only needed for `StealthyFetcher`/`DynamicFetcher`;
plain `Fetcher` works right after `uv sync`.

## Usage

```
uv run python example.py
```

See `example.py` for the three fetcher types:
- `Fetcher` — plain HTTP, no browser, fastest. Use by default.
- `StealthyFetcher` — real browser with fingerprint spoofing, gets past
  Cloudflare/bot walls and renders client-side JS.
- `DynamicFetcher` — full Playwright automation for pages that need clicks,
  scrolling, or waiting on dynamic content.

Pull `page.markdown()` or `page.css(...)` results — not the raw HTML — before
handing content to Claude. That's the token-efficiency point of using this
over a plain fetch.

## Re-installing / updating

```
uv lock --upgrade-package scrapling   # move the lock to the newest scrapling
uv sync
uv run scrapling install              # re-syncs browser binaries after an update
```

Commit the changed `uv.lock` so everyone else gets the same versions.

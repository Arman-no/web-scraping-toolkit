# scrapling-scraper

Self-contained install of [Scrapling](https://github.com/D4Vinci/Scrapling) — a Python
web-scraping library with stealth-browser and anti-bot-bypass fetchers, plus
markdown/CSS/XPath extraction so only the relevant text ever needs to reach an
LLM's context (not the raw page HTML).

## Setup

### Fresh clone

```
python -m venv .venv
.venv\Scripts\pip.exe install -r requirements.txt
.venv\Scripts\scrapling.exe install   # downloads Playwright's Chromium/WebKit binaries
```

### This machine

Already installed in `.venv` (Python 3.13, `scrapling[fetchers]`, Playwright
Chromium/WebKit browser binaries). Nothing else to do.

## Usage

```
.venv\Scripts\python.exe example.py
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
.venv\Scripts\pip.exe install --upgrade scrapling
.venv\Scripts\scrapling.exe install   # re-syncs browser binaries after an update
```

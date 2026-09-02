# web-scraping-toolkit

Two self-contained local tools for pulling content from the web that a plain
HTTP fetch can't reach on its own — bot-walled or JS-rendered pages, and
Instagram reels (which expose no fetchable caption track the way YouTube
does). Each tool has its own isolated Python venv and its own README with
full setup/usage detail.

Also registered as a personal Claude Code skill
(`~/.claude/skills/web-scraping-toolkit/`) so a Claude session knows to reach
for these automatically when a plain fetch comes back empty or blocked.

## Tools

| Folder | What it does |
|---|---|
| [`scrapling-scraper/`](scrapling-scraper/) | Fetches pages that block plain requests — Cloudflare/bot-detection walls, client-side-rendered SPAs — via a stealth browser, and extracts markdown/CSS instead of raw HTML. |
| [`ig-reel-transcript/`](ig-reel-transcript/) | Downloads a public Instagram reel and transcribes its audio locally (CPU, no API, nothing uploaded anywhere). |

## Workflow: scrapling-scraper

```mermaid
flowchart TD
    A[Target URL] --> B{Plain HTTP works?}
    B -- yes --> C["Fetcher.get()<br/>no browser, fastest"]
    B -- "no — bot wall<br/>or JS-only content" --> D["StealthyFetcher.fetch()<br/>real browser, fingerprint spoofing"]
    D -- needs clicks / scrolling --> E["DynamicFetcher<br/>full Playwright automation"]
    C --> F["page.markdown() / page.css()"]
    D --> F
    E --> F
    F --> G[Compact text, not raw HTML]
```

## Workflow: ig-reel-transcript

```mermaid
flowchart TD
    A[Reel URL or shortcode] --> B["instaloader downloads the video<br/>logged-out, public posts only"]
    B --> C["faster-whisper transcribes locally<br/>CPU, int8 quantized, no GPU/CUDA needed"]
    C --> D["shortcode.txt — the transcript"]
    C --> E["shortcode.log — per-segment debug log"]
    D --> F[Read the .txt / stdout only —<br/>the .log stays out of any LLM context]
```

## Setup

Each tool is self-contained — see its own README for exact commands:

```
cd scrapling-scraper && python -m venv .venv && .venv\Scripts\pip.exe install -r requirements.txt && .venv\Scripts\scrapling.exe install
cd ig-reel-transcript && python -m venv .venv && .venv\Scripts\pip.exe install -r requirements.txt
```

## Status

Private, personal-use tooling. Built and verified working 2026-09-02.

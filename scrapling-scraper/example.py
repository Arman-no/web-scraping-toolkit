"""
Smoke-test / usage reference for Scrapling.

Run with this folder's own venv:
    .venv\\Scripts\\python.exe example.py

Three fetcher types, pick the cheapest one that works for the target site:
  - Fetcher        : plain HTTP request, no browser. Fast, use by default.
  - StealthyFetcher : real browser (patchright) with anti-bot fingerprinting.
                      Use for Cloudflare/bot-walled or JS-rendered sites.
  - DynamicFetcher  : full Playwright automation (clicks, scrolling, waits).
                      Use when you need to interact with the page, not just read it.
"""

from scrapling.fetchers import Fetcher, StealthyFetcher

# --- 1. Plain HTTP fetch (no browser) ---
page = Fetcher.get("https://example.com")
print("[Fetcher] status:", page.status)
print("[Fetcher] title:", page.css("title::text").extract_first())

# --- 2. Stealth browser fetch (bypasses basic bot detection, renders JS) ---
# Uncomment to test against a real target. Runs headless by default.
# page = StealthyFetcher.fetch("https://example.com", headless=True)
# print("[StealthyFetcher] status:", page.status)

# --- 3. Markdown extraction (compact, LLM/token-friendly output) ---
# print(page.markdown())

# --- 4. CSS/XPath selection, the token-efficient way to pull just what you need ---
# titles = page.css("h1, h2::text").extract()
# print(titles)

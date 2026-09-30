# Agent setup

For an AI agent (or a colleague) picking this toolkit up on a new machine. Follow it
top to bottom; the troubleshooting table covers every problem actually hit so far.

## Rules

- **Work from the tool's folder and use `uv` for everything.** Never `pip`, never a
  hand-made venv. The tested versions are pinned in each tool's `uv.lock`.
- **Start with `Fetcher`.** Escalate to `StealthyFetcher` only when the page comes back
  empty, 403 or as a JavaScript shell. The browser path is far slower.
- **Read `page.markdown()` or `page.css(...)`, never `page.html_content`.** For long
  pages, write the text to a file and grep it instead of printing it.
- **Reels:** read **stdout only**; the `.log` file is Whisper's segment log. There is no
  caption track to look for. A private account's reel can't be fetched: say so, don't retry.
- **Quote the URL** you fetched whenever an answer depends on the page.

## Install

| Step | scrapling-scraper | ig-reel-transcript |
|---|---|---|
| Install (once, and after every pull) | `uv sync` | `uv sync` |
| Browser binaries (once, only for `StealthyFetcher`/`DynamicFetcher`) | `uv run scrapling install` | – |
| Use | write a short script, `uv run python my_script.py` | `uv run python transcribe_reel.py <url-or-shortcode>` |

### Locked-down Windows (AppLocker)

If executables inside the repo folder are blocked, keep the venv elsewhere by setting
`UV_PROJECT_ENVIRONMENT` before `uv sync` / `uv run`:

```bash
# git-bash
export UV_PROJECT_ENVIRONMENT="C:/AE/venvs/scrapling"
```

```powershell
# PowerShell
$env:UV_PROJECT_ENVIRONMENT = "C:/AE/venvs/scrapling"
```

**Use forward slashes.** In git-bash an unquoted `C:\AE\...` loses its backslashes, and
uv then silently creates a venv *inside the repo* instead of failing. After `uv sync`,
check that no new folder appeared in the tool's folder.

Set `PYTHONIOENCODING=utf-8` on Windows too, or non-latin page text crashes the console.

## Check it works

```bash
cd scrapling-scraper
uv run python example.py          # prints [Fetcher] status: 200 and the page title
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `No module named 'markdownify'` from `page.markdown()` | venv older than the lock file | `uv sync` in `scrapling-scraper/` |
| A new folder named like `C:AEvenvs...` appears in the tool folder | Backslash path in git-bash | Delete it; set `UV_PROJECT_ENVIRONMENT` with forward slashes |
| `This program is blocked by group policy` running `.venv\Scripts\python.exe` | AppLocker blocks the repo folder | Venv outside the repo, see above |
| `UnicodeEncodeError: 'charmap' codec` | Windows console is cp1252 | `PYTHONIOENCODING=utf-8` |
| `StealthyFetcher` fails to launch a browser | `scrapling install` never ran | `uv run scrapling install` |
| Status `200` but the text is a challenge page | Bot wall answered with a normal status | Check the content, not the status; escalate one rung |
| `LoginRequiredException` / `PrivateProfileNotFollowedException` | Private or login-walled post | Not retrievable; report it |
| `TooManyRequestsException` / `ConnectionException` | Instagram throttling the IP | Stop and wait; don't loop |

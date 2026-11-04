# ClosedTabs

**Close the tab. Keep the link. Find it when you need it.**

Paste a link and ClosedTabs saves the page, reads it, gives it labels and a short
description, and makes it searchable, for you and for Claude.

- Runs **only on your computer**. No accounts, no login, no email. One **Enter** button.
- Labels come from **your** label system (`type/`, `topic/`, `use/`). See [`docs/04-taxonomy.md`](docs/04-taxonomy.md).
- **Claude can use it.** Ask *"what did I save about pricing psychology?"* and Claude searches your library.

> New here? Follow **[SETUP-GUIDE.md](SETUP-GUIDE.md)**: super simple, step by step.

## What it does

| You do | ClosedTabs does |
|---|---|
| Paste one link, or many (one per line) | Saves it, removes tracking junk (`utm_…`), skips duplicates |
| Nothing | Opens the page, stores its title, image, description and text |
| Nothing (with a Claude, Gemini or other AI key) | Adds 1 `type/`, 1–3 `topic/`, 0–2 `use/` labels + a 2–3 sentence summary |
| Search or click a label | Full-text search over titles, summaries, notes and page text |
| Import a bookmarks file | Brings in all your old tabs/bookmarks at once |
| Ask Claude | Claude searches, reads and saves links through the built-in MCP connector |

## Project layout

| Path | What it is |
|---|---|
| `start.sh` / `start.ps1` | One-command start with Docker (Mac/Linux / Windows) |
| `start-local.sh` | One-command start without Docker (Python 3.10+) |
| `app/closedtabs/` | The app (Python, FastAPI, SQLite) |
| `app/closedtabs/providers.py` | AI providers: Claude (Anthropic SDK) or any OpenAI-compatible API |
| `app/closedtabs/taxonomy.py` | The label lists and the AI instructions. Edit here to change labels. |
| `deploy/` | Docker setup + settings file (`.env`) |
| `claude/` | How to connect Claude + things to ask |
| `docs/` | Research, architecture, wireframes, label system |

## For developers

```bash
cd app && pip install -r requirements.txt pytest && python -m pytest -q tests
DATA_DIR=./data uvicorn closedtabs.web:app --port 3000
```

Endpoints: `/` welcome · `/library` · `/links/{id}` · `/export.json` · `/api/links?q=&tag=` · `/health` · `/mcp` (MCP, streamable HTTP).

## Roadmap

- [x] v0: research, structure, label system
- [x] v1: ClosedTabs app, local only, no login, AI labels, Claude connector
- [ ] v2: design pass (from `docs/03-wireframes.md`)
- [ ] v3: browser extension / one-click save, weekly "rediscovery" digest

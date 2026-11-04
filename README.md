# Tabs → Links

**A second brain for the tabs you keep "for later."**
You paste a link and the system does the rest: it saves the page, gives it labels, writes a short description, and makes it searchable, both by you and by Claude.

> Status: **v0, structure and wireframe.** Visual design comes later.

---

## The idea in one picture

```
  CAPTURE                  ENRICH (automatic)            RETRIEVE
 ┌──────────────┐        ┌─────────────────────┐       ┌────────────────────────┐
 │ Browser ext. │        │ fetch page + archive │       │ Web app: search/filter │
 │ Mobile share │──URL──▶│ AI labels (your      │──────▶│ Smart lists ("Tools")  │
 │ Paste in app │        │   taxonomy)          │       │ Claude (MCP):          │
 │ Bulk: tabs → │        │ AI short summary     │       │  "find me that tool    │
 │   import     │        │ full-text index      │       │   for X…"              │
 └──────────────┘        └─────────────────────┘       └────────────────────────┘
```

## Decision: build on Karakeep, don't start from scratch

We compared the most-starred open-source projects (details in
[`docs/01-research-and-decision.md`](docs/01-research-and-decision.md)).
**[Karakeep](https://github.com/karakeep-app/karakeep)** (~30k ★, very active)
already covers about 90% of the brief:

| Your requirement | Karakeep |
|---|---|
| "I add the link only" | Browser extension, iOS/Android share sheet, web paste |
| Gets labels | AI auto-tagging, with a custom prompt so labels follow **your** taxonomy |
| Short description | AI auto-summary |
| Connect with Claude | Official MCP server (`@karakeep/mcp`): Claude can search, read, save and tag |
| Find it again | Full-text search (Meilisearch), smart lists, search query language |
| Old tabs | Imports from browser bookmarks, Pocket, and plain URL lists (script in this repo) |

So this repo is the **system layer** on top of it: your label taxonomy, the
tagging prompt, the Claude setup and playbook, the tab-import tooling, deploy
config, and the wireframes for a future custom front end.

## Repo map

| Path | What it is |
|---|---|
| [`docs/01-research-and-decision.md`](docs/01-research-and-decision.md) | Options compared, and why Karakeep |
| [`docs/02-architecture.md`](docs/02-architecture.md) | Components, data model, flows, hosting options |
| [`docs/03-wireframes.md`](docs/03-wireframes.md) | Low-fi wireframes (structure only, no styling) |
| [`docs/04-taxonomy.md`](docs/04-taxonomy.md) | Label system + the custom AI tagging prompt |
| [`deploy/`](deploy/) | `docker-compose.yml` + `.env.example` (Claude as the tagging model) |
| [`claude/`](claude/) | MCP config for Claude Desktop/Code + a "how to ask" playbook |
| [`scripts/tabs_to_import.py`](scripts/tabs_to_import.py) | Turns a dump of open tabs into an importable bookmarks file |

## Quick start (about 20 minutes)

1. **Run it.** With [Docker Desktop](https://www.docker.com/products/docker-desktop/) open, run `./start.sh` (Mac/Linux) or `.\start.ps1` (Windows). It creates `deploy/.env` with random secrets and starts everything.
   No server? Use a one-click host instead (see the architecture doc, "Hosting").
2. **Create your account** at `http://localhost:3000`, then go to *Settings → API keys* and create a key.
3. **Paste the tagging prompt** from `docs/04-taxonomy.md` into *Settings → AI*.
4. **Install capture.** Add the browser extension and the mobile app, and point them at your server.
5. **Empty your tabs.** Copy all tab URLs into `tabs.txt`, run
   `python3 scripts/tabs_to_import.py tabs.txt -o tabs.html`, and import `tabs.html` in *Settings → Import*.
6. **Connect Claude.** Merge `claude/mcp-config.example.json` into your Claude Desktop config (or run the `claude mcp add` one-liner in `claude/README.md`).
7. Ask Claude: *"What did I save about onboarding emails for SaaS?"*

## Roadmap

- [x] v0: research, structure, taxonomy, deploy, Claude wiring, tab import
- [ ] v1: run for 2 weeks, then tune the taxonomy based on the tags the AI actually produces
- [ ] v2: design pass (custom front end from `docs/03-wireframes.md`, or a Karakeep theme)
- [ ] v3: weekly "rediscovery" digest (Claude picks 5 forgotten saves related to current projects)

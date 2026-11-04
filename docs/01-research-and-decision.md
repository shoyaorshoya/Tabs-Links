# 01 · Research & decision

*Researched 2026-11-04. Star and fork counts come from the GitHub API on that date.*

## The brief
1. Add **only the link**, nothing else.
2. It gets **labels** and a **short description** automatically.
3. It connects with **Claude**, so the saved links work as a usable knowledge and tool base.
4. You can **find things again** when you need them. This is the real pain point.

## Candidates (top open-source projects by stars)

| Project | ★ | Forks | Stack | AI tags | AI summary | Claude/MCP | Notes |
|---|---|---|---|---|---|---|---|
| **karakeep-app/karakeep** (formerly Hoarder) | 30.3k | 1.6k | TS / Next.js | ✅ | ✅ | ✅ official `@karakeep/mcp` + agent skill | Links, notes, images, PDFs. Extension and mobile apps. Pushed today. |
| linkwarden/linkwarden | 20.3k | 892 | TS | ✅ | partial | community only | Strong at preservation and collaboration (PDF/screenshot archive) |
| sissbruecker/linkding | 11.4k | 687 | Python/Django | ❌ | ❌ | community `linkding-mcp` (15★) | Minimal and fast, but no AI |
| goniszewski/grimoire | 2.9k | 90 | TS/Svelte | ❌ | ❌ | ❌ | Nice UI, small |
| denho/faved | 1.3k | 73 | TS | ❌ | ❌ | ❌ | Nested tags, lightweight |
| Raindrop.io + `raindrop-io-mcp-server` | n/a (SaaS) | n/a | — | paid tier | ❌ | community MCP (74★) | Hosted and polished, but not open source, and your data lives with them |

## Three ways to approach it

**A. Adopt Karakeep and add a system layer (recommended)**
- ✅ Works this week, and capture apps already exist on every device.
- ✅ The official MCP server lets Claude search, read the full text, save and tag.
- ✅ You keep your data (self-hosted, exportable).
- ⚠️ You need somewhere to run it (Docker on a small VPS, home server, or a one-click host).
- ⚠️ Uses an OpenAI-compatible API. Claude works for tagging through Anthropic's OpenAI-compatibility endpoint, but there is no Claude embeddings model, so *semantic* search needs a separate embeddings provider or stays off. Keyword and full-text search work regardless.

**B. Build a custom lightweight app** (e.g. Next.js + SQLite + Claude API + custom MCP)
- ✅ Full control over the UX, and Claude-native from day one.
- ❌ 4–8 weeks to reach what Karakeep already does (crawling, extension, mobile, search, archiving).
- Only worth it if the design/UX itself becomes a product (e.g. for your community).

**C. Zero-infra: a Notion/Airtable database + Claude connector**
- ✅ No server. Claude can already talk to Notion.
- ❌ No automatic capture or crawling. You or Claude must enrich each link manually. Search is weaker.

## Update (same day): switched to our own app, ClosedTabs
After trying Karakeep, the login screen made no sense for a single-user app that runs only
on one computer, and Karakeep has no way to switch it off (only password or OAuth login).
The app also couldn't be renamed without maintaining a fork. So we built **ClosedTabs**: a small
app (Python + SQLite) that does only what's needed. No login, our own label system built in,
Claude labelling via the official Anthropic SDK, and a built-in MCP connector for Claude.
Karakeep remains a good option if the project ever needs multi-user or mobile apps.

## Original decision (superseded)
**Go with A.** It answers the brief today, and keeps **B** open: the
wireframes in `03-wireframes.md` can later become a custom front end on top of
Karakeep's REST API, so the backend never needs rebuilding.

## Sources
- Karakeep repo, MCP README (`apps/mcp/README.md`), and docs (`docs/docs/…`) read from the source tree
- Anthropic OpenAI SDK compatibility: https://platform.claude.com/docs/en/api/openai-sdk

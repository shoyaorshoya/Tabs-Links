# 02 · Architecture

## Components

```
                         ┌───────────────────────── Karakeep (Docker) ─────────────────────────┐
 Browser extension ─┐    │                                                                      │
 Mobile share sheet ├──▶ │  web (Next.js UI + REST API) ──▶ workers ──▶ chrome (headless crawl) │
 Web "paste link"   │    │        │                           │                                 │
 tabs_to_import.py ─┘    │        ▼                           ├──▶ LLM (Claude via OpenAI-compat)│
                         │   SQLite (/data)                   │      → tags + summary            │
                         │        │                           └──▶ meilisearch (full-text index) │
                         └────────┼─────────────────────────────────────────────────────────────┘
                                  │ REST API + API key
                                  ▼
                       @karakeep/mcp (runs next to Claude Desktop / Claude Code)
                                  │
                                  ▼
                               Claude  ← "find / summarise / compare / save"
```

## Data model (what each saved item holds)

| Field | Source | Example |
|---|---|---|
| `url`, `title`, `favicon`, `image` | crawler | `github.com/karakeep-app/karakeep` |
| `content` (readable text) | crawler | full article / README text |
| `summary` | AI | "Self-hosted bookmark app with AI tagging…" |
| `tags[]` | AI + you | `type/tool`, `topic/neuromarketing`, `use/client-work` |
| `lists[]` | you, or smart-list rules | "Toolbox", "Read this week", "Fundraising" |
| `note` | you (optional) | "Try for client X's onboarding" |
| `highlights[]` | you, while reading | quoted passages |
| `createdAt`, `archived`, `favourited` | system | status flags |

**Tags vs. lists.** Tags describe *what something is* and are added automatically.
Lists describe *what you're doing with it*: projects, queues and clients.
Smart lists are saved searches, e.g. `#type/tool -is:archived`. Query syntax: Karakeep docs → *Search query language*.

## Core flows

1. **Capture.** You send a URL and get a bookmark back instantly. Crawling, tagging and summarising run in the background (seconds to a minute).
2. **Triage (weekly, 10 min).** Open the *Inbox* smart list (`-is:inlist -is:archived`) and drag items into lists or archive them. Fix any tag the AI got wrong; that feeds back into how you tune the prompt.
3. **Retrieve.**
   - *You:* search bar, or filter by tag or list.
   - *Claude:* asks the MCP server `search-bookmarks`, then `get-bookmark-content` to read the full text, and answers with links.
4. **Use a tool.** For `type/tool` items, Claude can read the README or docs you saved and tell you how to apply the tool to the task at hand.

## Claude as the tagging model
Karakeep supports any OpenAI-compatible provider. Anthropic provides an
OpenAI-SDK-compatible endpoint at `https://api.anthropic.com/v1/`, which
Anthropic describes as mainly for testing and evaluation. Settings are in
`deploy/.env.example`. Notes:
- Use `INFERENCE_OUTPUT_SCHEMA=json`. If tags come back malformed, fall back to `plain`.
- No Claude embeddings model exists, so keep `EMBEDDING_ENABLE_AUTO_INDEXING` off, or point `EMBEDDING_OPENAI_BASE_URL`/`EMBEDDING_OPENAI_API_KEY` at a separate provider if you want semantic search. Meilisearch full-text search works either way.
- If the compatibility layer ever misbehaves, swap in another provider with two env lines. Nothing else changes.

## Hosting options

| Option | Effort | Cost (rough) | Notes |
|---|---|---|---|
| Your laptop (Docker Desktop) | Low | €0 | Fine for testing. Phone capture only works on the same network. |
| Small VPS (Hetzner, DigitalOcean…) + domain | Medium | ~€5–8/mo | Recommended for daily use. Put it behind HTTPS (Caddy/Cloudflare Tunnel). |
| One-click hosts listed in Karakeep docs (PikaPods, Hostinger…) | Lowest | small monthly fee | No terminal needed |

Check the current prices with each provider. The figures above are only an order of magnitude.

## Security notes
- Keep `.env` out of git (`.gitignore` already does this).
- The Karakeep API key gives Claude full read and write access to your library. Store it only in your local Claude config.
- Turn off public sign-ups after creating your account (`DISABLE_SIGNUPS=true`).

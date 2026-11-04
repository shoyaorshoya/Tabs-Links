# 02 · Architecture (ClosedTabs)

```
 Paste box / bookmarks import ─┐
                               ▼
                    ┌──────────────── ClosedTabs (one Docker container, 127.0.0.1:3000) ───────────────┐
                    │  FastAPI web app ──▶ SQLite (links + FTS5 full-text index)  /data/closedtabs.db  │
                    │        │                     ▲                                                   │
                    │        ▼                     │                                                   │
                    │  background workers: fetch page → title/description/image/text                   │
                    │                      → Claude (labels + summary, structured JSON output)         │
                    │  /mcp  MCP server: search_links · get_link · add_link · list_labels               │
                    └──────────────────────────────────────────────────────────────────────────────────┘
                               ▲
          Claude Desktop (via mcp-remote) / Claude Code (HTTP)
```

## Design choices
- **No accounts.** The port is bound to `127.0.0.1`, so only this computer can reach it. The welcome page is a single **Enter** button.
- **Labels are constrained.** Claude must answer in a JSON schema whose `type`, `topics` and `uses` are fixed lists (`app/closedtabs/taxonomy.py`), so labels can't sprawl.
- **Works without AI.** Without an API key, links still get title, description, image and page text, and search works.
- **Page text is untrusted.** It's sent to Claude inside `<page>` tags with an instruction to describe, not obey. Output is schema-constrained.
- **AI provider.** Claude by default (`claude-opus-5-5`, low effort, server-side refusal fallback; `CLAUDE_MODEL=claude-haiku-5-5` is cheaper), or any OpenAI-compatible API via `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` (Gemini, OpenAI, Mistral, Groq, OpenRouter, Ollama). For the latter, ClosedTabs tries strict JSON schema output, then JSON mode, then plain instructions, and always filters the answer down to the allowed labels.
- **Your data.** One SQLite file in a Docker volume (`closedtabs-data`). *Export everything* gives you a JSON backup.

## Data model (`links` table)
`url` (unique, tracking params removed) · `title` · `description` · `image` · `site` · `content` (page text, up to 100k chars) ·
`summary` · `tags` (JSON list like `["type/tool","topic/ai-tools"]`) · `note` · `status` (pending/done/error) · `error` · `created_at`

## Not yet (candidates for later)
- One-click save from the browser (bookmarklet or small extension)
- Phone capture (needs hosting beyond localhost)
- Semantic search (embeddings), weekly rediscovery digest

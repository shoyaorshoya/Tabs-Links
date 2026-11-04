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

## Website data (`seo.py`)
Collected from the same page download, no extra requests: on-page SEO checks (approach from
python-seo-analyzer), top keywords and two-word phrases with stopwords removed for EN/RO/HU/DE/FR/ES,
headings, Open Graph/Twitter, schema.org types, hreflang, social profiles, mailto/tel links, timing and
size, and a marketing/tech stack detected by fingerprints in the HTML and headers (the Wappalyzer
method, with a short self-written list of ~50 marketing-relevant technologies; Wappalyzer's full
database is GPL-licensed and mostly irrelevant here). Tech names, schema types and keywords are added
to the search index. Claude gets everything through `get_link` → `website_data`.

## Data model (`links` table)
`url` (unique, tracking params removed) · `title` · `description` · `image` · `site` · `content` (page text, up to 100k chars) ·
`summary` · `seo` (website data, JSON) · `tags` (JSON list like `["type/tool","topic/ai-tools"]`) · `note` · `status` (pending/done/error) · `error` · `created_at`

## Not yet (candidates for later)
- One-click save from the browser (bookmarklet or small extension)
- Phone capture (needs hosting beyond localhost)
- Semantic search (embeddings), weekly rediscovery digest

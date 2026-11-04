# Connecting Claude to your library

Karakeep ships an official MCP server, `@karakeep/mcp`. It lets Claude
**search, read the full text, save, tag, list and highlight** your bookmarks.

## Claude Desktop
1. In Karakeep, go to *Settings → API keys* and create a key.
2. In Claude Desktop, open *Settings → Developer → Edit config* and merge in
   [`mcp-config.example.json`](mcp-config.example.json) with your server address and key filled in.
3. Restart Claude Desktop. "karakeep" should appear in the tools menu.
   (Requires Node.js installed, since it runs via `npx`.)

## Claude Code
```bash
claude mcp add karakeep -e KARAKEEP_API_ADDR=https://<YOUR_SERVER_ADDR> -e KARAKEEP_API_KEY=<KEY> -- npx @karakeep/mcp
```
Karakeep also publishes an agent skill (`npx skills add karakeep-app/karakeep`) that teaches
assistants its search syntax. It's optional, but it helps.

## Playbook: things to ask

**Finding**
- "What did I save about *pricing psychology*? Give me the 5 most useful, with links."
- "Find that GitHub repo for scraping ad libraries I saved a few weeks ago."
- "List all `type/tool` items tagged `use/try-it` that I haven't archived."

**Using**
- "Read the saved docs for *<tool>* and tell me how to set it up for a client's landing-page test."
- "From my saved research papers on attention, pull 3 findings I can cite in a workshop."
- "Compare the email tools in my Toolbox: pricing, strengths, best fit for a 5-person startup."

**Saving and organising**
- "Save these links and add them to the *Fundraising* list: …"
- "Go through my Inbox, suggest a list for each item, and archive duplicates." (Review the suggestions before saying yes.)
- "Which tags are near-duplicates? Propose merges." (Feeds the 2-week taxonomy review.)

**Rediscovery**
- "I'm starting a GTM plan for a fintech SME. What have I saved that's relevant?"

> Tip: Claude only knows what the search returns. If something isn't found, try
> asking with different words (tool name, domain, topic), or ask it to search by tag.

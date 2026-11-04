# Connecting Claude to ClosedTabs

ClosedTabs has a built-in connector (an MCP server) at `http://localhost:3000/mcp`.
It gives Claude four tools: **search_links**, **get_link** (reads the saved page text),
**add_link**, and **list_labels**.

ClosedTabs must be running (Docker Desktop open) whenever Claude uses it.

## Claude desktop app (Mac / Windows)

1. Install **Node.js** (the LTS version) from https://nodejs.org. Claude uses it to reach the connector.
2. In the Claude app, open **Settings → Developer → Edit Config**. This opens `claude_desktop_config.json`.
   Paste in the contents of [`mcp-config.example.json`](mcp-config.example.json).
   If the file already has an `"mcpServers"` section, add just the `"closedtabs"` part inside it.
3. Quit Claude completely and reopen it. "closedtabs" now appears in the tools/connectors menu.

## Claude Code (terminal)

```bash
claude mcp add --transport http closedtabs http://localhost:3000/mcp
```

## Things to ask

**Finding**
- "What did I save about *pricing psychology*? Give me the best 5 with links."
- "Find that GitHub repo for scraping ad libraries I saved a few weeks ago."
- "Show my `type/tool` links labelled `use/try-it`."

**Using**
- "Read the saved page for *<tool>* and tell me how to set it up for a client's landing-page test."
- "From my saved research papers on attention, pull 3 findings I can cite in a workshop."
- "Compare the email tools I saved: pricing, strengths, best fit for a 5-person startup."

**Saving**
- "Save these links to ClosedTabs: …"

**Rediscovery**
- "I'm starting a GTM plan for a fintech SME. What have I saved that's relevant?"

> Tip: if Claude doesn't find something, ask with other words (the tool's name, the website, or a label).

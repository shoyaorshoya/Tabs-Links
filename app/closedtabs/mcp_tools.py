"""MCP server so Claude can search, read and save links. Served at /mcp."""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from . import db
from .urls import clean_url

mcp = MCPServer(
    name="ClosedTabs",
    instructions=(
        "ClosedTabs is the user's personal library of saved links (articles, tools, GitHub repos, "
        "papers...). Each link has one type/ label (e.g. type/tool, type/company), topic/ labels the AI "
        "derived from the page (e.g. topic/eye-tracking), the owner's own labels without a prefix "
        "(e.g. project-delia), and a short summary. Use search_links to find things (try synonyms and tag filters if the first "
        "search is thin), get_link to read a page's saved text, and add_link to save new links. "
        "Always give the user the URL of anything you recommend."
    ),
)


def _brief(link: dict) -> dict:
    return {
        "id": link["id"], "url": link["url"], "title": link["title"], "site": link["site"],
        "summary": link["summary"] or link["description"], "tags": link["tags"], "note": link["note"],
    }


@mcp.tool()
def search_links(query: str = "", tag: str = "", limit: int = 15) -> list[dict]:
    """Search saved links by words (title, summary, page text, note) and/or one exact label.

    Args:
        query: words to look for, e.g. "landing page a/b testing". Empty = newest first.
        tag: optional exact label such as "type/tool", "topic/email-marketing", "project-delia".
        limit: max results (1-50).
    """
    return [_brief(l) for l in db.search(query, tag, limit=max(1, min(limit, 50)))]


@mcp.tool()
def get_link(link_id: int, max_chars: int = 20000) -> dict:
    """Get one saved link with its full saved page text (truncated to max_chars)."""
    link = db.get(link_id)
    if not link:
        return {"error": f"No link with id {link_id}"}
    return dict(_brief(link), content=link["content"][:max_chars], status=link["status"])


@mcp.tool()
def add_link(url: str, note: str = "") -> dict:
    """Save a new link. Labels and a summary are added automatically within about a minute."""
    from .enrich import worker  # local import: avoids a cycle at startup

    if not url.startswith(("http://", "https://")):
        return {"error": "URL must start with http:// or https://"}
    link_id, created = db.add(clean_url(url), note=note)
    if created:
        worker.submit(link_id)
    return {"id": link_id, "created": created}


@mcp.tool()
def list_labels() -> list[dict]:
    """All labels in use, with how many links carry each."""
    return [{"label": t, "count": n} for t, n in db.tag_counts()]

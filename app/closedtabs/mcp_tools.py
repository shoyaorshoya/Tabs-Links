"""MCP server so Claude can search, read and save links. Served at /mcp."""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from . import db, notes
from .urls import clean_url

mcp = MCPServer(
    name="ClosedTabs",
    instructions=(
        "ClosedTabs is the user's personal library of saved links (articles, tools, GitHub repos, "
        "papers...). Each link has one type/ label (e.g. type/tool, type/company), topic/ labels the AI "
        "derived from the page (e.g. topic/eye-tracking), the owner's own labels without a prefix "
        "(e.g. project-delia), and a short summary. Use search_links to find things (try synonyms and tag filters if the first "
        "search is thin), get_link to read a page's saved text, and add_link to save new links. "
        "get_link also returns website_data: SEO checks, top keywords, headings, structured data, "
        "the marketing/tech stack (analytics, ad pixels, CMS, CRM, consent, chat), social profiles and "
        "public contact links (only for links labelled commdata; the owner uses these, grouped by "
        "project label, for client communication analyses). search_links also matches technology names, e.g. 'Meta Pixel' or 'HubSpot'. "
        "The library also holds the owner's own notes (kind 'note'); notes link to other items with "
        "[[Title]] and get_link lists those connections. "
        "Always give the user the URL of anything you recommend."
    ),
)


def _brief(link: dict) -> dict:
    return {
        "id": link["id"], "kind": link["kind"], "url": "" if link["kind"] == "note" else link["url"],
        "title": link["title"], "source": link["source"],
        "platform": link["source_kind"], "why_saved": link["why"],
        "summary": link["summary"] or link["description"], "tags": link["tags"], "note": link["note"],
    }


@mcp.tool()
def search_links(query: str = "", tag: str = "", why: str = "", source: str = "", limit: int = 15) -> list[dict]:
    """Search saved links by words (title, summary, page text, note, website technology and keywords)
    and/or one exact label.

    Args:
        query: words to look for, e.g. "landing page a/b testing". Empty = newest first.
        tag: optional exact label such as "type/tool", "topic/email-marketing", "project-delia".
        why: optional exact "why I saved it" keyword of the owner, e.g. "inspiration" (see list_labels).
        source: optional exact source name, e.g. "mero.ro", "sethblack/python-seo-analyzer", a YouTube channel.
        limit: max results (1-50).
    """
    return [_brief(l) for l in db.search(query, tag, why=why, source=source, limit=max(1, min(limit, 50)))]


@mcp.tool()
def get_link(link_id: int, max_chars: int = 20000) -> dict:
    """Get one saved link with its full saved page text (truncated to max_chars)."""
    link = db.get(link_id)
    if not link:
        return {"error": f"No link with id {link_id}"}
    seo = dict(link["seo"] or {})
    links_to = [{"id": r["id"], "title": r["title"]} for r in
                (db.resolve_ref(x) for x in notes.refs(link["content"] if link["kind"] == "note" else "")
                 + notes.refs(link["note"])) if r]
    linked_from = [{"id": r["id"], "title": r["title"]} for r in db.backlinks(link)]
    return dict(_brief(link), kind=link["kind"], content=link["content"][:max_chars], status=link["status"],
                website_data=seo, links_to=links_to, linked_from=linked_from)


@mcp.tool()
def add_link(url: str, why: str = "", labels: str = "", commdata: bool = False, note: str = "") -> dict:
    """Save a new link. Labels and a summary are added automatically within about a minute.

    Args:
        url: the web address.
        why: why it was saved, as comma-separated keywords, e.g. "inspiration, pricing" (optional).
        note: a longer free-text note (optional).
        labels: the owner's own labels, comma separated, e.g. "project-delia, client" (optional).
        commdata: True to also collect website data (SEO, keywords, marketing stack, socials) and
            label it CommData. Use when the owner wants a communication analysis of the site.
    """
    from .enrich import worker  # local import: avoids a cycle at startup

    if not url.startswith(("http://", "https://")):
        return {"error": "URL must start with http:// or https://"}
    from . import taxonomy

    link_id, created = db.add(clean_url(url), note=note, why=taxonomy.why_keywords(why))
    own = [l for l in taxonomy.own_labels(labels) if l != taxonomy.COMMDATA]
    if created:
        db.update(link_id, tags=own, want_commdata=int(commdata))
        worker.submit(link_id)
    else:
        old = db.get(link_id)
        db.update(link_id, tags=sorted(set(old["tags"]) | set(own)))
        if commdata and not old["want_commdata"]:
            db.update(link_id, want_commdata=1, status="pending")
            worker.submit(link_id)
    return {"id": link_id, "created": created}


@mcp.tool()
def add_note(text: str, title: str = "", why: str = "", labels: str = "") -> dict:
    """Save a note (no web address) in the owner's library, e.g. an idea, a summary you wrote together,
    meeting notes or a synthesis of several saved links. Use [[Exact title]] or [[#id]] inside the
    text to link to other saved items; those show up as connections.

    Args:
        text: the note body (plain text; blank lines separate paragraphs).
        title: optional title (default: the first line of the text).
        why: why it was saved, comma-separated keywords (optional).
        labels: project / own labels, comma separated (optional).
    """
    from . import taxonomy
    from .enrich import worker

    own = [l for l in taxonomy.own_labels(labels) if l != taxonomy.COMMDATA]
    note_id = db.add_note(text, title=title, why=taxonomy.why_keywords(why), tags=own)
    worker.submit(note_id)
    return {"id": note_id}


@mcp.tool()
def list_labels() -> dict:
    """Everything the library is organised by, with counts: labels (type/…, topic/…, own project
    labels, commdata), the owner's 'why I saved it' keywords, and sources."""
    return {
        "labels": [{"label": t, "count": n} for t, n in db.tag_counts()],
        "why_keywords": [{"why": w, "count": n} for w, n in db.why_counts()],
        "sources": [{"source": s, "platform": k, "count": n} for s, k, n in db.source_counts()[:200]],
    }

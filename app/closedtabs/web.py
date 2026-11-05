"""Web app: welcome screen with one Enter button, library, add, search, import, detail."""
from __future__ import annotations

import contextlib
import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import commdata_csv, compare, db, enrich, notes, obsidian, projects, providers, review, taxonomy
from .mcp_tools import mcp
from .urls import parse_bookmarks_html, parse_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
HERE = Path(__file__).parent

mcp_app = mcp.streamable_http_app(streamable_http_path="/mcp", stateless_http=True, json_response=True)


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    enrich.worker.start()
    obsidian.auto.start()
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="ClosedTabs", lifespan=lifespan, docs_url=None, redoc_url=None)


@app.middleware("http")
async def same_site_posts_only(request: Request, call_next):
    """Browsers send an Origin header with form posts. Refuse posts coming from other websites,
    so no web page can add, change or delete things in your library behind your back.
    (Claude's connector and scripts send no Origin header and are unaffected.)"""
    origin = request.headers.get("origin")
    if request.method == "POST" and origin and origin != "null":
        host = request.headers.get("host", "")
        if urlsplit(origin).netloc not in {host, "localhost:3000", "127.0.0.1:3000"}:
            return Response("Blocked: this request came from another website.", status_code=403)
    return await call_next(request)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")


def _ago(ts: float) -> str:
    s = max(0, time.time() - ts)
    for unit, n in (("d", 86400), ("h", 3600), ("min", 60)):
        if s >= n:
            return f"{int(s // n)}{unit} ago"
    return "just now"


templates.env.filters["ago"] = _ago


def _with(filters: dict, **changes) -> str:
    """URL for the library with some filters changed. A value of None removes that filter;
    for list filters, ('+', v) adds and ('-', v) removes one value."""
    f = {k: (list(v) if isinstance(v, list) else v) for k, v in filters.items()}
    for k, v in changes.items():
        if isinstance(v, tuple):
            op, val = v
            cur = f.get(k) or []
            f[k] = (cur + [val] if val not in cur else cur) if op == "+" else [x for x in cur if x != val]
        else:
            f[k] = v
    params = []
    for k, v in f.items():
        if k == "sort" and v == "new":
            continue
        for x in (v if isinstance(v, list) else [v]):
            if x not in (None, "", 0):
                params.append((k, x))
    return "/library" + ("?" + urlencode(params) if params else "")


templates.env.globals["with_filters"] = _with
templates.env.filters["render_note"] = notes.render
templates.env.filters["plain_refs"] = notes.plain
templates.env.globals["nav_extra"] = [("/projects", "Projects"), ("/review", "Review")]
templates.env.tests["search"] = lambda value, pattern: re.search(pattern, str(value)) is not None


def _back(q: str = "", tag: str | list[str] = "", msg: str = "") -> RedirectResponse:
    tags = [tag] if isinstance(tag, str) else tag
    params = [("q", q)] if q else []
    params += [("tag", t) for t in tags if t]
    params += [("msg", msg)] if msg else []
    return RedirectResponse("/library" + (f"?{urlencode(params)}" if params else ""), status_code=303)


def _save_many(items: list[tuple[str, str]], why: list[str] | None = None, labels: list[str] | None = None,
               commdata: bool = False) -> tuple[int, int]:
    added = dup = 0
    for url, title in items:
        link_id, created = db.add(url, title=title, why=why)
        if created:
            added += 1
            db.update(link_id, tags=labels or [], want_commdata=int(commdata))
            enrich.worker.submit(link_id)
        else:
            dup += 1
            old = db.get(link_id)
            if labels:  # already saved: just add the new labels to it
                db.update(link_id, tags=sorted(set(old["tags"]) | set(labels)))
            if why:
                db.update(link_id, why=old["why"] + [w for w in why if w not in old["why"]])
            if commdata and not old["want_commdata"]:  # now also wanted: collect it
                db.update(link_id, want_commdata=1, status="pending", error="")
                enrich.worker.submit(link_id)
    return added, dup


def _msg(added: int, dup: int) -> str:
    parts = []
    if added:
        parts.append(f"Saved {added} link{'s' if added != 1 else ''}.")
    if dup:
        parts.append(f"{dup} {'was' if dup == 1 else 'were'} already saved.")
    return " ".join(parts) or "No links found in what you pasted."


@app.get("/", response_class=HTMLResponse)
def welcome(request: Request):
    return templates.TemplateResponse(request, "welcome.html", {"count": db.count()})


@app.get("/library", response_class=HTMLResponse)
def library(request: Request, q: str = "", tag: list[str] = Query([]), why: list[str] = Query([]),
            source: str = "", days: int = 0, sort: str = "new", kind: str = "", archived: int = 0, msg: str = ""):
    tag = [t for t in tag if t]
    why = [w for w in why if w]
    kind = kind if kind in ("link", "note") else ""
    links = db.search(q, tag, why=why, source=source, since_days=days or None, sort=sort, kind=kind,
                      archived=bool(archived), limit=500)
    filters = {"q": q, "tag": tag, "why": why, "source": source, "days": days, "kind": kind,
               "archived": archived, "sort": sort}
    return templates.TemplateResponse(request, "library.html", {
        "links": links, "q": q, "tag": tag, "why": why, "source": source, "days": days, "sort": sort,
        "kind": kind, "n_notes": db.count_kind("note"), "n_links": db.count_kind("link"),
        "archived": archived, "n_archived": db.count_archived(),
        "filters": filters, "filtered": bool(q or tag or why or source or days or kind or archived),
        "msg": msg, "tags": db.tag_counts(), "whys": db.why_counts(), "sources": db.source_counts(),
        "week": db.count_since(7), "obsidian": obsidian.status | {"enabled": obsidian.enabled()},
        "projects": db.commdata_projects(), "commdata_view": taxonomy.COMMDATA in tag,
        "total": db.count(), "ai": enrich.ai_enabled(), "all_labels": [t for t, _ in db.tag_counts()],
        "processing": any(l["status"] == "pending" for l in links),
    })


@app.post("/add")
def add(text: str = Form(""), why: str = Form(""), note: str = Form(""), labels: str = Form(""),
        commdata: str = Form("")):
    items = parse_text(text)
    own = [l for l in taxonomy.own_labels(labels) if l != taxonomy.COMMDATA]
    keywords = taxonomy.why_keywords(why or note)
    if not items and text.strip():  # no web address in it: keep it as a note
        note_id = db.add_note(text, why=keywords, tags=own)
        enrich.worker.submit(note_id)
        return _back(msg="Saved as a note (there was no web address in it).")
    added, dup = _save_many(items, keywords, own, commdata=bool(commdata))
    return _back(msg=_msg(added, dup))


BOOKMARKLET = (
    "javascript:(()=>{const s=String(getSelection()).slice(0,3000);"
    "window.open('http://localhost:3000/save?url='+encodeURIComponent(location.href)"
    "+'&title='+encodeURIComponent(document.title)+'&sel='+encodeURIComponent(s),"
    "'closedtabs','width=520,height=640')})()"
)


@app.get("/save", response_class=HTMLResponse)
def save_popup(request: Request, url: str = "", title: str = "", sel: str = ""):
    """The small window the 'Save to ClosedTabs' bookmark opens."""
    from .urls import clean_url

    url = clean_url(url) if url.startswith(("http://", "https://")) else ""
    existing = None
    if url:
        with db._lock:
            r = db.conn().execute("SELECT id FROM links WHERE url=?", (url,)).fetchone()
        existing = db.get(r["id"]) if r else None
    return templates.TemplateResponse(request, "save_popup.html", {
        "url": url, "title": title, "sel": sel.strip(), "existing": existing,
        "whys": db.why_counts(), "tags": db.tag_counts(), "saved": None})


@app.post("/save", response_class=HTMLResponse)
def save_from_popup(request: Request, url: str = Form(""), title: str = Form(""), why: str = Form(""),
                    labels: str = Form(""), commdata: str = Form(""), note: str = Form("")):
    from .urls import clean_url

    if not url.startswith(("http://", "https://")):
        return HTMLResponse("This page can't be saved (it has no web address).", status_code=400)
    url = clean_url(url)
    own = [l for l in taxonomy.own_labels(labels) if l != taxonomy.COMMDATA]
    added, _ = _save_many([(url, title.strip())], taxonomy.why_keywords(why), own, commdata=bool(commdata))
    with db._lock:
        link_id = db.conn().execute("SELECT id FROM links WHERE url=?", (url,)).fetchone()["id"]
    if note.strip():
        old = db.get(link_id)["note"]
        quote = "> " + note.strip().replace("\n", "\n> ")
        db.update(link_id, note=(old + "\n\n" + quote).strip() if quote not in old else old)
    return templates.TemplateResponse(request, "save_popup.html", {
        "saved": {"id": link_id, "new": bool(added)}, "url": url, "title": title})


@app.get("/projects", response_class=HTMLResponse)
def projects_index(request: Request):
    return templates.TemplateResponse(request, "projects.html", {"projects": projects.all_projects()})


@app.get("/projects/{label}", response_class=HTMLResponse)
def project_page(request: Request, label: str, msg: str = ""):
    data = projects.page_data(label)
    if not data["items"]:
        return _back(msg=f"No items with the label {label}.")
    return templates.TemplateResponse(request, "project.html", data | {
        "msg": msg, "ai": enrich.ai_enabled(), "langs": projects.LANGS,
        "whys": db.why_counts(), "tags": db.tag_counts()})


@app.post("/projects/{label}/brief")
def project_brief(label: str, lang: str = Form("en")):
    if not enrich.ai_enabled():
        return RedirectResponse(f"/projects/{label}?" + urlencode({"msg": "AI is off: add an AI key or Ollama first."}),
                                status_code=303)
    projects.start_brief(label, lang)
    return RedirectResponse(f"/projects/{label}", status_code=303)


@app.get("/tools", response_class=HTMLResponse)
def tools(request: Request):
    return templates.TemplateResponse(request, "tools.html", {
        "bookmarklet": BOOKMARKLET, "obsidian": obsidian.enabled(), "ai": providers.describe()})


@app.get("/notes/new", response_class=HTMLResponse)
def new_note(request: Request, why: str = "", labels: str = "", ref: int = 0):
    start = ""
    if ref and (item := db.get(ref)):
        start = f"[[{item['title']}]]\n\n"
    return templates.TemplateResponse(request, "note_new.html", {
        "why": why, "labels": labels, "start": start,
        "whys": db.why_counts(), "tags": db.tag_counts()})


@app.post("/notes")
def create_note(title: str = Form(""), text: str = Form(""), why: str = Form(""), labels: str = Form("")):
    if not (title.strip() or text.strip()):
        return _back(msg="The note was empty, nothing saved.")
    own = [l for l in taxonomy.own_labels(labels) if l != taxonomy.COMMDATA]
    note_id = db.add_note(text, title=title.strip(), why=taxonomy.why_keywords(why), tags=own)
    enrich.worker.submit(note_id)
    return RedirectResponse(f"/links/{note_id}", status_code=303)


@app.get("/compare", response_class=HTMLResponse)
def compare_view(request: Request, tag: list[str] = Query([])):
    tags = [taxonomy.COMMDATA] + [t for t in tag if t and t != taxonomy.COMMDATA]
    links = db.search("", tags, limit=60, sort="source")
    return templates.TemplateResponse(request, "compare.html", {
        "links": links, "tags": tags, "project": ", ".join(tags[1:]) or "all CommData websites",
        "table": compare.build(links)})


@app.post("/import")
async def import_file(file: UploadFile = File(...), commdata: str = Form(""), labels: str = Form("")):
    raw = (await file.read()).decode("utf-8", errors="replace")
    items = parse_bookmarks_html(raw) if "<a" in raw.lower() else parse_text(raw)
    own = [l for l in taxonomy.own_labels(labels) if l != taxonomy.COMMDATA]
    added, dup = _save_many(items, labels=own, commdata=bool(commdata))
    return _back(msg=_msg(added, dup))


@app.post("/links/{link_id}/commdata")
def toggle_commdata(link_id: int, on: str = Form("1")):
    want = on == "1"
    link = db.get(link_id)
    if link:
        if want:
            db.update(link_id, want_commdata=1, status="pending", error="")
            enrich.worker.submit(link_id)
        else:
            db.update(link_id, want_commdata=0, seo={},
                      tags=[t for t in link["tags"] if t != taxonomy.COMMDATA])
    return RedirectResponse(f"/links/{link_id}", status_code=303)


@app.get("/export/commdata.csv")
def export_commdata(tag: list[str] = Query([]), sep: str = ""):
    tags = [taxonomy.COMMDATA] + [t for t in tag if t and t != taxonomy.COMMDATA]
    links = db.search("", tags, limit=100_000)
    body = commdata_csv.build(links, semicolon=(sep == "semicolon"))
    name = "commdata" + "".join(f"-{t}" for t in tags[1:]) + time.strftime("-%Y-%m-%d") + ".csv"
    return Response(body, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/links/{link_id}", response_class=HTMLResponse)
def detail(request: Request, link_id: int, edit: int = 0):
    link = db.get(link_id)
    if not link:
        return _back(msg="That link no longer exists.")
    return templates.TemplateResponse(request, "detail.html", {
        "link": link, "ai": enrich.ai_enabled(), "backlinks": db.backlinks(link), "edit": edit,
        "outgoing": [r for r in (db.resolve_ref(x) for x in notes.refs(link["content"] if link["kind"] == "note"
                                                                      else "") + notes.refs(link["note"])) if r]})


@app.post("/links/{link_id}/edit")
def edit(link_id: int, tags: str = Form(""), note: str = Form(""), why: str = Form(""),
         title: str = Form(None), text: str = Form(None)):
    link = db.get(link_id)
    new = set(taxonomy.own_labels(tags))
    # The CommData label follows the data, not the text box.
    new.discard(taxonomy.COMMDATA)
    if link and link["want_commdata"] and link["seo"]:
        new.add(taxonomy.COMMDATA)
    extra = {}
    if link and link["kind"] == "note":
        if title is not None:
            extra["title"] = title.strip() or "Untitled note"
        if text is not None:
            extra["content"] = text.strip()
    db.update(link_id, tags=sorted(new), note=note.strip(), why=taxonomy.why_keywords(why), **extra)
    return RedirectResponse(f"/links/{link_id}", status_code=303)


@app.post("/links/{link_id}/retry")
def retry(link_id: int):
    db.update(link_id, status="pending", error="")
    enrich.worker.submit(link_id)
    return RedirectResponse(f"/links/{link_id}", status_code=303)


@app.post("/obsidian/sync")
def obsidian_sync():
    if not obsidian.enabled():
        return _back(msg="Obsidian isn't set up yet: add OBSIDIAN_VAULT to deploy/.env (see the guide).")
    st = obsidian.sync()
    if st["error"]:
        return _back(msg=st["error"])
    return _back(msg=f"Synced with Obsidian: {st['written']} file(s) updated, {st['pulled']} change(s) "
                     f"taken from Obsidian, {st['imported']} new note(s) imported.")


@app.post("/relabel-all")
def relabel_all():
    if not enrich.ai_enabled():
        return _back(msg="AI is off. Add an AI key first (see the guide).")
    ids = db.mark_all_pending()
    for link_id in ids:
        enrich.worker.submit(link_id)
    return _back(msg=f"Re-labelling {len(ids)} links. This can take a while; the page updates by itself.")


@app.post("/links/{link_id}/archive")
def archive(request: Request, link_id: int, on: str = Form("1"), back: str = Form("")):
    db.update(link_id, archived=1 if on == "1" else 0)
    target = back if back.startswith("/") else f"/links/{link_id}"
    return RedirectResponse(target, status_code=303)


@app.get("/review", response_class=HTMLResponse)
def review_page(request: Request, msg: str = ""):
    return templates.TemplateResponse(request, "review.html", {
        "week": review.this_week(), "todo": review.unsorted(), "again": review.rediscover(), "msg": msg,
        "whys": db.why_counts(), "tags": db.tag_counts()})


@app.post("/review/sort/{link_id}")
def review_sort(link_id: int, why: str = Form(""), labels: str = Form(""), action: str = Form("save")):
    link = db.get(link_id)
    if link:
        if action == "archive":
            db.update(link_id, archived=1)
        else:
            new_why = link["why"] + [w for w in taxonomy.why_keywords(why) if w not in link["why"]]
            own = [l for l in taxonomy.own_labels(labels) if l != taxonomy.COMMDATA]
            db.update(link_id, why=new_why, tags=sorted(set(link["tags"]) | set(own)))
    return RedirectResponse("/review#todo", status_code=303)


@app.post("/links/{link_id}/delete")
def remove(link_id: int):
    db.delete(link_id)
    return _back(msg="Deleted.")


@app.get("/export.json")
def export():
    body = json.dumps(db.export_all(), ensure_ascii=False, indent=2)
    return Response(body, media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="closedtabs-export.json"'})


@app.get("/api/links")
def api_links(q: str = "", tag: str = "", limit: int = 50):
    return JSONResponse([
        {k: l[k] for k in ("id", "url", "title", "site", "source", "source_kind", "summary", "why", "tags",
                           "note", "status", "created_at")}
        for l in db.search(q, tag, limit=min(limit, 500))
    ])


@app.get("/health")
def health():
    return {"ok": True, "links": db.count_all(), "active": db.count(), "archived": db.count_archived(),
            "ai": enrich.ai_enabled(), **providers.describe(),
            "obsidian": {"enabled": obsidian.enabled(), "folder": str(obsidian.vault_dir() or ""),
                         "last_sync": obsidian.status["last_sync"], "error": obsidian.status["error"]}}


# MCP endpoint (/mcp) for Claude. Mounted last so the routes above win.
app.mount("/", mcp_app)

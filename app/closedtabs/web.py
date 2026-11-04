"""Web app: welcome screen with one Enter button, library, add, search, import, detail."""
from __future__ import annotations

import contextlib
import json
import logging
import time
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import commdata_csv, db, enrich, providers, taxonomy
from .mcp_tools import mcp
from .urls import parse_bookmarks_html, parse_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
HERE = Path(__file__).parent

mcp_app = mcp.streamable_http_app(streamable_http_path="/mcp", stateless_http=True, json_response=True)


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    enrich.worker.start()
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="ClosedTabs", lifespan=lifespan, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")


def _ago(ts: float) -> str:
    s = max(0, time.time() - ts)
    for unit, n in (("d", 86400), ("h", 3600), ("min", 60)):
        if s >= n:
            return f"{int(s // n)}{unit} ago"
    return "just now"


templates.env.filters["ago"] = _ago


def _back(q: str = "", tag: str | list[str] = "", msg: str = "") -> RedirectResponse:
    tags = [tag] if isinstance(tag, str) else tag
    params = [("q", q)] if q else []
    params += [("tag", t) for t in tags if t]
    params += [("msg", msg)] if msg else []
    return RedirectResponse("/library" + (f"?{urlencode(params)}" if params else ""), status_code=303)


def _save_many(items: list[tuple[str, str]], note: str = "", labels: list[str] | None = None,
               commdata: bool = False) -> tuple[int, int]:
    added = dup = 0
    for url, title in items:
        link_id, created = db.add(url, title=title, note=note)
        if created:
            added += 1
            db.update(link_id, tags=labels or [], want_commdata=int(commdata))
            enrich.worker.submit(link_id)
        else:
            dup += 1
            old = db.get(link_id)
            if labels:  # already saved: just add the new labels to it
                db.update(link_id, tags=sorted(set(old["tags"]) | set(labels)))
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
def library(request: Request, q: str = "", tag: list[str] = Query([]), msg: str = ""):
    tag = [t for t in tag if t]
    links = db.search(q, tag)
    return templates.TemplateResponse(request, "library.html", {
        "links": links, "q": q, "tag": tag, "msg": msg, "tags": db.tag_counts(),
        "projects": db.commdata_projects(), "commdata_view": taxonomy.COMMDATA in tag,
        "total": db.count(), "ai": enrich.ai_enabled(), "all_labels": [t for t, _ in db.tag_counts()],
        "processing": any(l["status"] == "pending" for l in links),
    })


@app.post("/add")
def add(text: str = Form(""), note: str = Form(""), labels: str = Form(""), commdata: str = Form("")):
    items = parse_text(text)
    own = [l for l in taxonomy.own_labels(labels) if l != taxonomy.COMMDATA]
    added, dup = _save_many(items, note.strip(), own, commdata=bool(commdata))
    return _back(msg=_msg(added, dup))


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
def detail(request: Request, link_id: int):
    link = db.get(link_id)
    if not link:
        return _back(msg="That link no longer exists.")
    return templates.TemplateResponse(request, "detail.html", {"link": link, "ai": enrich.ai_enabled()})


@app.post("/links/{link_id}/edit")
def edit(link_id: int, tags: str = Form(""), note: str = Form("")):
    link = db.get(link_id)
    new = set(taxonomy.own_labels(tags))
    # The CommData label follows the data, not the text box.
    new.discard(taxonomy.COMMDATA)
    if link and link["want_commdata"] and link["seo"]:
        new.add(taxonomy.COMMDATA)
    db.update(link_id, tags=sorted(new), note=note.strip())
    return RedirectResponse(f"/links/{link_id}", status_code=303)


@app.post("/links/{link_id}/retry")
def retry(link_id: int):
    db.update(link_id, status="pending", error="")
    enrich.worker.submit(link_id)
    return RedirectResponse(f"/links/{link_id}", status_code=303)


@app.post("/relabel-all")
def relabel_all():
    if not enrich.ai_enabled():
        return _back(msg="AI is off. Add an AI key first (see the guide).")
    ids = db.mark_all_pending()
    for link_id in ids:
        enrich.worker.submit(link_id)
    return _back(msg=f"Re-labelling {len(ids)} links. This can take a while; the page updates by itself.")


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
        {k: l[k] for k in ("id", "url", "title", "site", "summary", "tags", "note", "status", "created_at")}
        for l in db.search(q, tag, limit=min(limit, 500))
    ])


@app.get("/health")
def health():
    return {"ok": True, "links": db.count(), "ai": enrich.ai_enabled(), **providers.describe()}


# MCP endpoint (/mcp) for Claude. Mounted last so the routes above win.
app.mount("/", mcp_app)

"""Fetch a page, pull out its title/description/text, and ask the AI for labels + summary."""
from __future__ import annotations

import logging
import queue
import threading
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx

from . import db, providers, taxonomy

log = logging.getLogger("closedtabs")

MAX_BYTES = 3_000_000
STORE_CHARS = 100_000   # text kept for search / Claude to read later
AI_CHARS = 15_000       # text sent to the model for labelling
UA = "Mozilla/5.0 (compatible; ClosedTabs/1.0; personal bookmark manager)"

def ai_enabled() -> bool:
    return providers.provider() is not None


# ── page parsing ─────────────────────────────────────────────────────
class _PageParser(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "template"}
    BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "br", "tr", "section", "article", "pre"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title = ""
        self._in_title = False
        self._skip = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and a.get("content"):
                self.meta.setdefault(key, a["content"].strip())
        elif tag == "title":
            self._in_title = True
        elif tag in self.SKIP:
            self._skip += 1
        elif tag in self.BLOCK:
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.chunks.append(data)

    def text(self) -> str:
        raw = "".join(self.chunks)
        lines = (" ".join(line.split()) for line in raw.splitlines())
        return "\n".join(line for line in lines if line)


def parse_page(html_text: str, base_url: str) -> dict:
    p = _PageParser()
    try:
        p.feed(html_text)
    except Exception:  # malformed HTML: keep what we got
        pass
    m = p.meta
    image = m.get("og:image") or m.get("twitter:image") or ""
    return {
        "title": (m.get("og:title") or p.title or "").strip()[:300],
        "description": (m.get("og:description") or m.get("description") or m.get("twitter:description") or "").strip()[:1000],
        "image": urljoin(base_url, image) if image else "",
        "site": m.get("og:site_name") or urlsplit(base_url).netloc.removeprefix("www."),
        "content": p.text()[:STORE_CHARS],
    }


def fetch(url: str) -> dict:
    with httpx.Client(follow_redirects=True, timeout=20, headers={"User-Agent": UA}) as client:
        with client.stream("GET", url) as r:
            r.raise_for_status()
            ctype = r.headers.get("content-type", "")
            body = b""
            for chunk in r.iter_bytes():
                body += chunk
                if len(body) > MAX_BYTES:
                    break
            final_url = str(r.url)
            encoding = r.encoding or "utf-8"
    if "html" not in ctype and "xml" not in ctype:
        site = urlsplit(final_url).netloc.removeprefix("www.")
        name = urlsplit(final_url).path.rsplit("/", 1)[-1] or site
        return {"title": name, "description": f"{ctype or 'file'} file", "image": "", "site": site, "content": ""}
    return parse_page(body.decode(encoding, errors="replace"), final_url)


# ── pipeline ─────────────────────────────────────────────────────────
def enrich(link_id: int) -> None:
    link = db.get(link_id)
    if not link:
        return
    url = link["url"]
    try:
        page = fetch(url)
    except Exception as e:  # unreachable / blocked site: still keep the link
        log.info("fetch failed for %s: %s", url, e)
        site = urlsplit(url).netloc.removeprefix("www.")
        page = {"title": link["title"] or site, "description": "", "image": "", "site": site, "content": ""}
        fetch_error = f"Couldn't open the page ({type(e).__name__})."
    else:
        fetch_error = ""
    if link["title"] and not page["title"]:
        page["title"] = link["title"]

    fields = dict(page, summary=page["description"], status="done", error=fetch_error)
    if ai_enabled():
        try:
            result = providers.label(url, page, AI_CHARS, note=link["note"])
            fields["summary"] = result["summary"] or page["description"]
            # Replace earlier AI labels (type/ topic/ use/); keep labels the owner typed by hand.
            own = {t for t in link["tags"] if not t.startswith(taxonomy.AI_PREFIXES)}
            fields["tags"] = sorted(own | set(taxonomy.to_tags(result)))
        except providers.LabelError as e:
            log.warning("labelling failed for %s: %s", url, e)
            fields.update(status="error", error=str(e)[:300])
    db.update(link_id, **fields)


class Worker:
    """Background threads that enrich links one at a time per thread."""

    def __init__(self, threads: int = 3) -> None:
        self.q: queue.Queue[int] = queue.Queue()
        self.threads = threads
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        for _ in range(self.threads):
            threading.Thread(target=self._run, daemon=True).start()
        for link_id in db.pending_ids():  # resume after a restart
            self.q.put(link_id)
        if ai_enabled():  # label links saved before the API key was added
            todo = db.unlabeled_ids()
            if todo:
                log.info("labelling %d links that have no labels yet", len(todo))
            for link_id in todo:
                db.update(link_id, status="pending", error="")
                self.q.put(link_id)

    def submit(self, link_id: int) -> None:
        self.q.put(link_id)

    def _run(self) -> None:
        while True:
            link_id = self.q.get()
            try:
                enrich(link_id)
            except Exception:
                log.exception("enrich crashed for %s", link_id)
                db.update(link_id, status="error", error="Something went wrong while processing.")


worker = Worker()

"""Fetch a page, pull out its title/description/text, and ask the AI for labels + summary."""
from __future__ import annotations

import logging
import queue
import threading
import time
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit

import httpx

from . import db, providers, seo, sources, taxonomy

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


def fetch(url: str, analyze: bool = False) -> dict:
    """Download a page. analyze=True also collects website data (CommData) under 'seo'."""
    started = time.monotonic()
    with httpx.Client(follow_redirects=True, timeout=20, headers={"User-Agent": UA}) as client:
        with client.stream("GET", url) as r:
            r.raise_for_status()
            elapsed_ms = int((time.monotonic() - started) * 1000)
            headers = dict(r.headers)
            status, redirects = r.status_code, len(r.history)
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
    html_text = body.decode(encoding, errors="replace")
    page = parse_page(html_text, final_url)
    if not analyze:
        return page
    try:
        page["seo"] = seo.analyze(html_text, final_url, headers=headers, status=status,
                                  elapsed_ms=elapsed_ms, size_bytes=len(body), redirects=redirects)
    except Exception:  # website data is a bonus; never let it block saving the link
        log.exception("website analysis failed for %s", final_url)
    return page


OEMBED = {
    "youtube": "https://www.youtube.com/oembed?format=json&url=",
    "vimeo": "https://vimeo.com/api/oembed.json?url=",
}


def video_info(url: str) -> dict:
    """Channel name and title of a YouTube/Vimeo video via the platform's official oEmbed endpoint
    (no cookie-consent page in the way). Empty dict if not a video or not reachable."""
    kind = sources.is_video(url)
    if not kind:
        return {}
    try:
        r = httpx.get(OEMBED[kind] + quote(url, safe=""), timeout=10, headers={"User-Agent": UA},
                      follow_redirects=True)
        r.raise_for_status()
        d = r.json()
        return {"author": (d.get("author_name") or "").strip(), "title": (d.get("title") or "").strip(),
                "image": d.get("thumbnail_url") or "", "kind": "YouTube" if kind == "youtube" else "Vimeo"}
    except (httpx.HTTPError, ValueError):
        return {}


# ── pipeline ─────────────────────────────────────────────────────────
def enrich_note(link: dict) -> None:
    """Notes have no page to fetch: the AI labels the note's own text."""
    fields = {"status": "done", "error": "", "summary": ""}
    tags = set(link["tags"])
    if ai_enabled() and (link["content"] or link["title"]):
        page = {"title": link["title"], "description": "", "content": link["content"]}
        try:
            result = providers.label("(a personal note, not a web page)", page, AI_CHARS,
                                     note=", ".join(link["why"]), known=db.topic_labels())
            tags = {t for t in tags if not t.startswith(taxonomy.AI_PREFIXES)} | {"type/note"} | {
                f"topic/{t}" for t in result["topics"]}
            fields["summary"] = result["summary"] if len(link["content"]) > 400 else ""
        except providers.LabelError as e:
            fields.update(status="error", error=str(e)[:300])
    fields["tags"] = sorted(tags)
    db.update(link["id"], **fields)


def enrich(link_id: int) -> None:
    link = db.get(link_id)
    if not link:
        return
    if link["kind"] == "note":
        return enrich_note(link)
    url = link["url"]
    want = bool(link["want_commdata"])
    try:
        page = fetch(url, analyze=want)
    except Exception as e:  # unreachable / blocked site: still keep the link
        log.info("fetch failed for %s: %s", url, e)
        site = urlsplit(url).netloc.removeprefix("www.")
        page = {"title": link["title"] or site, "description": "", "image": "", "site": site, "content": ""}
        fetch_error = f"Couldn't open the page ({type(e).__name__})."
    else:
        fetch_error = ""
    if link["title"] and not page["title"]:
        page["title"] = link["title"]

    # Readable source name (domain, GitHub user/repo, YouTube channel…)
    page["source"], page["source_kind"] = sources.from_url(url)
    video = video_info(url)
    if video.get("author"):
        page["source"], page["source_kind"] = video["author"], video["kind"]
    if video.get("title"):
        page["title"] = video["title"]
        page["image"] = page.get("image") or video.get("image", "")
        page["site"] = video["kind"]
        if fetch_error:  # the page itself was blocked, but we know what the video is
            fetch_error = ""

    tags = set(link["tags"])
    # Website data (CommData): only when asked for. Keep earlier data if the page couldn't be opened.
    if want and page.get("seo"):
        tags.add(taxonomy.COMMDATA)
    elif want and link["seo"]:
        page["seo"] = link["seo"]
    elif not want:
        page["seo"] = {}
        tags.discard(taxonomy.COMMDATA)
    if want and not page.get("seo") and fetch_error:
        fetch_error += " Website data (CommData) couldn't be collected; try 'Re-read page' later."

    fields = dict(page, summary=page["description"], status="done", error=fetch_error)
    if ai_enabled():
        try:
            result = providers.label(url, page, AI_CHARS, note="; ".join(filter(None, [", ".join(link["why"]), link["note"]])),
                                     known=db.topic_labels())
            fields["summary"] = result["summary"] or page["description"]
            # Replace earlier AI labels (type/ topic/ use/); keep labels the owner typed by hand.
            tags = {t for t in tags if not t.startswith(taxonomy.AI_PREFIXES)} | set(taxonomy.to_tags(result))
        except providers.LabelError as e:
            log.warning("labelling failed for %s: %s", url, e)
            fields.update(status="error", error=str(e)[:300])
    fields["tags"] = sorted(tags)
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

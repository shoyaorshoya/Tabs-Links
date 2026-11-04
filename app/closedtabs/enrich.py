"""Fetch a page, pull out its title/description/text, and ask Claude for labels + summary."""
from __future__ import annotations

import json
import logging
import os
import queue
import threading
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import anthropic
import httpx

from . import db, taxonomy

log = logging.getLogger("closedtabs")

MAX_BYTES = 3_000_000
STORE_CHARS = 100_000   # text kept for search / Claude to read later
AI_CHARS = 15_000       # text sent to the model for labelling
UA = "Mozilla/5.0 (compatible; ClosedTabs/1.0; personal bookmark manager)"

# Models that accept the server-side refusal fallback (Haiku does not).
_FALLBACK_PREFIXES = ("claude-opus-5", "claude-fable-5", "claude-sonnet-5-5")


def api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:  # accept a key left over from the earlier setup's variable name
        legacy = os.environ.get("OPENAI_API_KEY", "").strip()
        key = legacy if legacy.startswith("sk-ant-") else ""
    return key


def model() -> str:
    return os.environ.get("CLAUDE_MODEL", "").strip() or "claude-opus-5-5"


def ai_enabled() -> bool:
    return bool(api_key())


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


# ── Claude ───────────────────────────────────────────────────────────
_client: anthropic.Anthropic | None = None


def _claude() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=api_key(), max_retries=3)
    return _client


def label(url: str, page: dict) -> dict:
    """Ask Claude for {type, topics, uses, summary}. Raises on API errors."""
    body = (
        f"<page>\nURL: {url}\nTitle: {page.get('title','')}\n"
        f"Description: {page.get('description','')}\n\n{(page.get('content') or '')[:AI_CHARS]}\n</page>"
    )
    kwargs = {}
    m = model()
    if m.startswith(_FALLBACK_PREFIXES):
        kwargs = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    resp = _claude().beta.messages.create(
        model=m,
        max_tokens=4000,
        system=taxonomy.SYSTEM_PROMPT,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": taxonomy.SCHEMA}},
        messages=[{"role": "user", "content": body}],
        **kwargs,
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("Claude declined to label this page")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("Claude's answer was cut off")
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


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
            result = label(url, page)
            fields["summary"] = result["summary"].strip()
            fields["tags"] = sorted(set(link["tags"]) | set(taxonomy.to_tags(result)))
        except anthropic.AuthenticationError:
            fields.update(status="error", error="Claude API key was rejected. Check ANTHROPIC_API_KEY.")
        except anthropic.APIConnectionError:
            fields.update(status="error", error="Couldn't reach Claude. Check the internet connection.")
        except (anthropic.APIStatusError, RuntimeError, ValueError, StopIteration, KeyError) as e:
            log.warning("labelling failed for %s: %s", url, e)
            fields.update(status="error", error=f"AI labelling failed: {e}"[:300])
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

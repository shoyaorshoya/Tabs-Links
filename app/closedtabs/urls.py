"""Pull URLs out of pasted text and bookmark files, and normalise them."""
from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

URL_RE = re.compile(r"https?://[^\s<>\]\)\"']+")
MD_RE = re.compile(r"\[(?P<title>[^\]]*)\]\((?P<url>https?://[^\s)]+)\)")
TRACKING = re.compile(r"^(utm_.*|fbclid|gclid|mc_cid|mc_eid|ref_src|igshid|si)$", re.I)


def clean_url(url: str) -> str:
    url = url.strip().rstrip(".,;")
    parts = urlsplit(url)
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                       if not TRACKING.match(k)])
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path, query, parts.fragment))


def parse_line(line: str) -> tuple[str, str] | None:
    """One pasted line -> (url, title-or-empty). Handles plain, 'url | title', markdown."""
    line = line.strip()
    if not line:
        return None
    m = MD_RE.search(line)
    if m:
        return clean_url(m["url"]), m["title"].strip()
    m = URL_RE.search(line)
    if not m:
        return None
    rest = (line[: m.start()] + line[m.end():]).strip(" |-–—\t")
    return clean_url(m.group(0)), rest


def parse_text(text: str) -> list[tuple[str, str]]:
    out, seen = [], set()
    for line in text.splitlines():
        p = parse_line(line)
        if p and p[0] not in seen:
            seen.add(p[0])
            out.append(p)
    return out


class _BookmarkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href:
            if self._href.startswith(("http://", "https://")):
                self.items.append((clean_url(self._href), "".join(self._text).strip()))
            self._href = None


def parse_bookmarks_html(html_text: str) -> list[tuple[str, str]]:
    """Chrome/Firefox/Safari 'Export bookmarks' file -> [(url, title)]."""
    p = _BookmarkParser()
    p.feed(html_text)
    seen, out = set(), []
    for url, title in p.items:
        if url not in seen:
            seen.add(url)
            out.append((url, title))
    return out

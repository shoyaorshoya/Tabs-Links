#!/usr/bin/env python3
"""Turn a dump of open browser tabs into a Netscape bookmarks HTML file
that Karakeep (and most bookmark tools) can import.

Accepted input, one tab per line, mixed formats are fine:
  https://example.com
  https://example.com | Page title          (OneTab export format)
  [Page title](https://example.com)         (Markdown, e.g. "Copy all tabs" extensions)
  Page title - https://example.com
Blank lines and lines without a URL are skipped. Duplicates are removed
(ignoring tracking parameters like utm_*, fbclid, gclid).

Usage:
  python3 scripts/tabs_to_import.py tabs.txt -o tabs.html [--tag inbox/tabs-2026-11]
  pbpaste | python3 scripts/tabs_to_import.py - -o tabs.html
"""
from __future__ import annotations

import argparse
import html
import re
import sys
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

URL_RE = re.compile(r"https?://[^\s<>\]\)\"']+")
MD_RE = re.compile(r"\[(?P<title>[^\]]*)\]\((?P<url>https?://[^\s)]+)\)")
TRACKING = re.compile(r"^(utm_.*|fbclid|gclid|mc_cid|mc_eid|ref_src|igshid|si)$", re.I)
SKIP_SCHEMES = ("chrome://", "about:", "edge://", "file://")


def clean_url(url: str) -> str:
    url = url.rstrip(".,;")
    parts = urlsplit(url)
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                       if not TRACKING.match(k)])
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path, query, parts.fragment))


def dedupe_key(url: str) -> str:
    p = urlsplit(url)
    return f"{p.netloc.removeprefix('www.')}{p.path.rstrip('/')}?{p.query}"


def parse_line(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith(SKIP_SCHEMES):
        return None
    m = MD_RE.search(line)
    if m:
        return clean_url(m["url"]), m["title"].strip()
    m = URL_RE.search(line)
    if not m:
        return None
    url = clean_url(m.group(0))
    rest = (line[: m.start()] + line[m.end():]).strip(" |-–—\t")
    return url, rest


def build_html(items: list[tuple[str, str]], tag: str | None) -> str:
    now = int(time.time())
    tags_attr = f' TAGS="{html.escape(tag)}"' if tag else ""
    rows = [
        f'    <DT><A HREF="{html.escape(u)}" ADD_DATE="{now}"{tags_attr}>'
        f"{html.escape(t or u)}</A>"
        for u, t in items
    ]
    return "\n".join([
        "<!DOCTYPE NETSCAPE-Bookmark-file-1>",
        '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
        "<TITLE>Bookmarks</TITLE>",
        "<H1>Bookmarks</H1>",
        "<DL><p>",
        "  <DT><H3>Open tabs import</H3>",
        "  <DL><p>",
        *rows,
        "  </DL><p>",
        "</DL><p>",
        "",
    ])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="text file with one tab per line, or - for stdin")
    ap.add_argument("-o", "--output", default="tabs.html")
    ap.add_argument("--tag", default=None, help="extra tag on every item, e.g. inbox/tabs-2026-11")
    args = ap.parse_args(argv)

    src = sys.stdin if args.input == "-" else open(args.input, encoding="utf-8")
    seen: set[str] = set()
    items: list[tuple[str, str]] = []
    skipped = 0
    with src:
        for line in src:
            parsed = parse_line(line)
            if not parsed:
                skipped += bool(line.strip())
                continue
            key = dedupe_key(parsed[0])
            if key in seen:
                skipped += 1
                continue
            seen.add(key)
            items.append(parsed)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(build_html(items, args.tag))
    print(f"✓ {len(items)} links written to {args.output} ({skipped} skipped: duplicates/non-URLs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

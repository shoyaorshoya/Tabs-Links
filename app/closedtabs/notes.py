"""Turn note text into safe HTML: paragraphs, clickable web addresses and [[links]] to other items."""
from __future__ import annotations

import html
import re

from . import db

REF = re.compile(r"\[\[([^\[\]\n]{1,200})\]\]")
URL = re.compile(r"https?://[^\s<>\"']+[^\s<>\"'.,;:!?)\]]")


def refs(text: str) -> list[str]:
    return [m.strip() for m in REF.findall(text or "")]


def _inline(line: str) -> str:
    """Escape one line and turn [[links]], web addresses and **bold** into HTML."""
    pieces, pos = [], 0
    for m in re.finditer(f"{REF.pattern}|{URL.pattern}", line):
        pieces.append(_bold(html.escape(line[pos:m.start()])))
        if m.group(1) is not None:
            raw = m.group(1).strip()
            ref = raw.split("|", 1)[1].strip() if "|" in raw else raw   # [[target|shown]]
            item = db.resolve_ref(raw)
            if item:
                shown = ref
                if re.fullmatch(r"#\d+", ref):  # [[#12]] reads better as the item's title
                    t = item["title"] or item["url"]
                    shown = t if len(t) <= 48 else t[:46] + "…"
                pieces.append(f'<a class="wikilink" href="/links/{item["id"]}" title="{html.escape(item["title"])}">'
                              f'{html.escape(shown)}</a>')
            else:
                pieces.append(f'<a class="wikilink missing" href="/library?q={html.escape(ref)}" '
                              f'title="Nothing with this exact title yet: search instead">{html.escape(ref)}</a>')
        else:
            u = m.group(0)
            pieces.append(f'<a href="{html.escape(u)}" target="_blank" rel="noopener">{html.escape(u)}</a>')
        pos = m.end()
    pieces.append(_bold(html.escape(line[pos:])))
    return "".join(pieces)


def _bold(escaped: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def render(text: str) -> str:
    """Note text -> safe HTML. Understands a little Markdown: # headings, - / 1. lists, **bold**;
    a short first line without end punctuation is treated as a heading too (AI briefs use that)."""
    out = []
    for para in re.split(r"\n\s*\n", (text or "").strip()):
        lines = [l for l in para.split("\n") if l.strip()]
        if not lines:
            continue
        m = re.match(r"^\s*#{1,6}\s+(.*)$", lines[0])
        first = lines[0].strip()
        if m:
            out.append(f"<h4>{_inline(m.group(1).strip())}</h4>")
            lines = lines[1:]
        elif len(lines) > 1 and len(first) <= 60 and not re.search(r"[.!?,;:]$", first) \
                and not BULLET.match(first) and "[[" not in first:
            out.append(f"<h4>{_inline(first)}</h4>")
            lines = lines[1:]
        if not lines:
            continue
        if all(BULLET.match(l) for l in lines):
            items = "".join(f"<li>{_inline(BULLET.sub('', l, count=1))}</li>" for l in lines)
            out.append(f"<ul>{items}</ul>")
        else:
            out.append("<p>" + "<br>".join(_inline(l) for l in lines) + "</p>")
    return "\n".join(out)


def plain(text: str) -> str:
    """For short previews: [[#12]] -> the item's title, [[target|shown]] -> shown, [[x]] -> x."""
    def repl(m):
        raw = m.group(1).strip()
        if "|" in raw:
            return raw.split("|", 1)[1].strip()
        if re.fullmatch(r"#\d+", raw):
            item = db.resolve_ref(raw)
            return item["title"] if item else raw
        return raw
    return REF.sub(repl, text or "")

"""Turn note text into safe HTML: paragraphs, clickable web addresses and [[links]] to other items."""
from __future__ import annotations

import html
import re

from . import db

REF = re.compile(r"\[\[([^\[\]\n]{1,200})\]\]")
URL = re.compile(r"https?://[^\s<>\"']+[^\s<>\"'.,;:!?)\]]")


def refs(text: str) -> list[str]:
    return [m.strip() for m in REF.findall(text or "")]


def render(text: str) -> str:
    out = []
    for para in re.split(r"\n\s*\n", (text or "").strip()):
        if not para.strip():
            continue
        pieces, pos = [], 0
        for m in re.finditer(f"{REF.pattern}|{URL.pattern}", para):
            pieces.append(html.escape(para[pos:m.start()]))
            if m.group(1) is not None:
                ref = m.group(1).strip()
                item = db.resolve_ref(ref)
                if item:
                    pieces.append(f'<a class="wikilink" href="/links/{item["id"]}">{html.escape(ref)}</a>')
                else:
                    pieces.append(f'<a class="wikilink missing" href="/library?q={html.escape(ref)}" '
                                  f'title="Nothing with this exact title yet: search instead">{html.escape(ref)}</a>')
            else:
                u = m.group(0)
                pieces.append(f'<a href="{html.escape(u)}" target="_blank" rel="noopener">{html.escape(u)}</a>')
            pos = m.end()
        pieces.append(html.escape(para[pos:]))
        out.append("<p>" + "".join(pieces).replace("\n", "<br>") + "</p>")
    return "\n".join(out)

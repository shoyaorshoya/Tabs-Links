"""Side-by-side comparison of CommData websites (competitor analysis)."""
from __future__ import annotations

from collections import Counter

from .commdata_csv import CATEGORIES, SOCIAL_COLUMNS


def _cell(text="", cls=""):
    return {"text": "" if text is None else str(text), "cls": cls}


def _yes(flag: bool, yes="✓", no="none"):
    return _cell(yes if flag else no, "ok" if flag else "warn")


def build(links: list[dict]) -> dict:
    sites = [l for l in links if l.get("seo")]
    names = Counter(l["source"] for l in sites)
    cols = [{"id": l["id"], "url": l["url"], "title": l["title"],
             # same source twice (e.g. two pages of one site): tell them apart by title
             "name": (l["source"] if names[l["source"]] == 1 and l["source"] else (l["title"] or l["url"])[:40])}
            for l in sites]
    S = [l["seo"] for l in sites]
    rows: list[dict] = []

    def section(name):
        rows.append({"section": name})

    def row(label, cells, hint=""):
        rows.append({"label": label, "cells": cells, "hint": hint})

    section("Overview")
    row("Type", [_cell(", ".join(t.split("/", 1)[1] for t in l["tags"] if t.startswith("type/"))) for l in sites])
    row("Topics", [_cell(", ".join(t.split("/", 1)[1] for t in l["tags"] if t.startswith("topic/"))) for l in sites])
    row("Language", [_cell((s.get("lang") or "none") + (f" (+{', '.join(s['hreflang'])})" if s.get("hreflang") else ""))
                     for s in S])

    section("SEO basics")
    passed = []
    for s in S:
        checks = s.get("checks") or []
        ok = sum(1 for c in checks if c.get("level") == "ok")
        passed.append((ok, len(checks)))
    best = max((p[0] for p in passed), default=0)
    row("SEO checks passed", [_cell(f"{ok}/{n}", "ok" if ok == best and n else ("warn" if n and ok < n * 0.6 else ""))
                              for ok, n in passed])
    row("Issues", [_cell(" · ".join(c["text"] for c in (s.get("checks") or []) if c.get("level") == "warn") or "none",
                         "small") for s in S])
    row("Title length", [_cell(len(s.get("title", "")), "ok" if 20 <= len(s.get("title", "")) <= 60 else "warn") for s in S],
        "aim for 20–60")
    row("Description length", [_cell(len(s.get("description", "")),
                                     "ok" if 70 <= len(s.get("description", "")) <= 160 else "warn") for s in S],
        "aim for 70–160")
    row("H1", [_cell(" · ".join(s.get("h1", [])) or "none", "" if len(s.get("h1", [])) == 1 else "warn") for s in S])
    row("Structured data", [_cell(", ".join(s.get("schema_types", [])) or "none",
                                  "ok" if s.get("schema_types") else "warn") for s in S])
    row("Social share image", [_yes(bool((s.get("og") or {}).get("image"))) for s in S])
    row("Mobile-ready", [_yes(bool(s.get("viewport"))) for s in S])
    row("HTTPS", [_yes(bool(s.get("https"))) for s in S])
    times = [s.get("response_ms") for s in S]
    fastest = min((t for t in times if t is not None), default=None)
    row("Response time", [_cell(f"{t} ms" if t is not None else "none",
                                "ok" if t is not None and t == fastest else ("warn" if t and t > 1500 else ""))
                          for t in times])
    row("Words on page", [_cell(s.get("word_count", "")) for s in S])

    section("Marketing & tech stack")
    for cat, label in CATEGORIES:
        vals = [[t["name"] for t in (s.get("tech") or []) if t.get("category") == cat] for s in S]
        if any(vals):
            row(label, [_cell(", ".join(v) or "none", "" if v else "none") for v in vals])

    section("Social presence")
    for net in SOCIAL_COLUMNS:
        vals = [(s.get("socials") or {}).get(net, "") for s in S]
        if any(vals):
            row(net, [_cell("✓" if v else "none", "ok" if v else "none") | {"href": v} for v in vals])
    row("Public contact", [_cell(" · ".join((s.get("emails") or []) + (s.get("phones") or [])) or "none") for s in S])

    section("Content focus")
    row("Top keywords", [_cell(", ".join(w for w, _ in (s.get("keywords") or {}).get("words", [])[:6])) for s in S])
    row("Top phrases", [_cell(", ".join(w for w, _ in (s.get("keywords") or {}).get("phrases", [])[:4])) for s in S])

    # Insights across the set
    kw_sites, tech_sites = Counter(), Counter()
    for s in S:
        kws = {w for w, _ in (s.get("keywords") or {}).get("words", [])[:12]}
        kws |= {w for w, _ in (s.get("keywords") or {}).get("phrases", [])[:8]}
        kw_sites.update(kws)
        tech_sites.update({t["name"] for t in (s.get("tech") or [])})
    n = len(S)
    insights = {
        "shared_keywords": [(k, c) for k, c in kw_sites.most_common() if c >= 2][:20],
        "shared_tools": [(k, c) for k, c in tech_sites.most_common() if c >= 2],
        "unique_tools": [
            (cols[i]["name"], sorted(t["name"] for t in (s.get("tech") or []) if tech_sites[t["name"]] == 1))
            for i, s in enumerate(S)
        ] if n > 1 else [],
    }
    insights["unique_tools"] = [(name, tools) for name, tools in insights["unique_tools"] if tools]
    return {"cols": cols, "rows": rows, "insights": insights, "n": n,
            "missing": [l for l in links if not l.get("seo")]}

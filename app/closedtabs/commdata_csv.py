"""CommData export: one row per website, ready for Excel / Google Sheets."""
from __future__ import annotations

import csv
import io
import time

from . import taxonomy

CATEGORIES = [
    ("analytics", "Analytics"), ("ads", "Ad pixels"), ("cms", "CMS / site builder"), ("shop", "Shop"),
    ("crm", "CRM"), ("email", "Email marketing"), ("chat", "Chat"), ("booking", "Booking"),
    ("consent", "Cookie consent"), ("framework", "Framework"), ("hosting", "Hosting / CDN"),
    ("media", "Media embeds"), ("assets", "Fonts / assets"),
]
SOCIAL_COLUMNS = ["Facebook", "Instagram", "LinkedIn", "TikTok", "YouTube", "X", "Pinterest"]


def _join(xs) -> str:
    return " | ".join(str(x) for x in xs if x)


def row(link: dict) -> dict:
    s = link.get("seo") or {}
    og = s.get("og") or {}
    tech = s.get("tech") or []
    kw = s.get("keywords") or {}
    checks = s.get("checks") or []
    warnings = [c["text"] for c in checks if c.get("level") == "warn"]
    own = [t for t in link["tags"] if "/" not in t and t != taxonomy.COMMDATA]
    r = {
        "Website": s.get("title") or link["title"],
        "URL": link["url"],
        "Source": link.get("source", ""),
        "Platform": link.get("source_kind", ""),
        "Project labels": _join(own),
        "Why saved": _join(link.get("why", [])),
        "Type": _join(t.split("/", 1)[1] for t in link["tags"] if t.startswith("type/")),
        "Topics": _join(t.split("/", 1)[1] for t in link["tags"] if t.startswith("topic/")),
        "Note": link.get("note", ""),
        "Summary": link.get("summary", ""),
        "Saved": time.strftime("%Y-%m-%d", time.localtime(link["created_at"])),
        "Language": s.get("lang", ""),
        "Language versions": _join(s.get("hreflang", [])),
        "Page title": s.get("title", ""),
        "Title length": len(s.get("title", "")),
        "Meta description": s.get("description", ""),
        "Description length": len(s.get("description", "")),
        "Meta keywords": _join(s.get("meta_keywords", [])),
        "H1": _join(s.get("h1", [])),
        "H2": _join(s.get("h2", [])),
        "Top keywords": _join(f"{w} ({n})" for w, n in kw.get("words", [])),
        "Top phrases": _join(f"{w} ({n})" for w, n in kw.get("phrases", [])),
        "Word count": s.get("word_count", ""),
        "Images": s.get("images", ""),
        "Images without alt": s.get("images_no_alt", ""),
        "Internal links": s.get("links_internal", ""),
        "External links": s.get("links_external", ""),
        "Structured data": _join(s.get("schema_types", [])),
        "OG title": og.get("title", ""),
        "OG description": og.get("description", ""),
        "OG image": og.get("image", ""),
        "Twitter card": s.get("twitter_card", ""),
        "Canonical": s.get("canonical", ""),
        "Indexable": "no" if "noindex" in s.get("robots", "").lower() else "yes",
        "HTTPS": "yes" if s.get("https") else "no",
        "Mobile viewport": "yes" if s.get("viewport") else "no",
        "Response (ms)": s.get("response_ms", ""),
        "Page size (KB)": s.get("size_kb", ""),
        "Redirects": s.get("redirects", ""),
        "Server": s.get("server", ""),
    }
    for cat, label in CATEGORIES:
        r[label] = _join(t["name"] for t in tech if t.get("category") == cat)
    socials = s.get("socials") or {}
    for name in SOCIAL_COLUMNS:
        r[name] = socials.get(name, "")
    r["Other socials"] = _join(f"{n}: {u}" for n, u in socials.items() if n not in SOCIAL_COLUMNS)
    r["Emails"] = _join(s.get("emails", []))
    r["Phones"] = _join(s.get("phones", []))
    r["SEO checks passed"] = sum(1 for c in checks if c.get("level") == "ok")
    r["SEO issues"] = len(warnings)
    r["SEO issue list"] = _join(warnings)
    return r


def build(links: list[dict], semicolon: bool = False) -> str:
    rows = [row(l) for l in links]
    buf = io.StringIO()
    fields = list(rows[0].keys()) if rows else list(row({"url": "", "title": "", "tags": [], "why": [], "created_at": 0}).keys())
    w = csv.DictWriter(buf, fieldnames=fields, delimiter=";" if semicolon else ",", quoting=csv.QUOTE_MINIMAL)
    w.writeheader()
    w.writerows(rows)
    return "﻿" + buf.getvalue()  # BOM: Excel then reads accents (ő, ș, ă…) correctly

"""Readable source names from URLs: 'mero.ro', 'sethblack/python-seo-analyzer', a YouTube channel…

name: what you see and filter by. kind: the platform ('website', 'GitHub', 'YouTube', …).
"""
from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit

# second-level domains where the "registrable" part has three labels (e.g. example.co.uk)
_MULTI_TLDS = {
    "co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "net.au", "org.au", "co.nz", "co.jp", "co.kr",
    "com.br", "com.mx", "com.ar", "com.tr", "com.cn", "com.hk", "com.sg", "co.in", "co.za", "co.il",
    "com.ro", "org.ro", "co.hu", "org.hu", "info.hu", "com.pl", "com.ua", "co.at", "or.at",
}

_RESERVED_GITHUB = {"orgs", "topics", "marketplace", "features", "sponsors", "settings", "explore",
                    "collections", "trending", "search", "about", "pricing", "login", "join", "apps"}
_RESERVED_SOCIAL = {"p", "reel", "reels", "explore", "stories", "hashtag", "share", "sharer", "intent",
                    "i", "home", "search", "watch", "feed", "login", "signup", "about", "tag", "tags"}


def registrable_domain(host: str) -> str:
    host = host.lower().split(":")[0].strip(".")
    host = host.removeprefix("www.")
    if re.fullmatch(r"[\d.]+", host) or host in ("localhost",):
        return host
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in _MULTI_TLDS:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _seg(path: str) -> list[str]:
    return [unquote(p) for p in path.split("/") if p]


def from_url(url: str) -> tuple[str, str]:
    """(name, kind) from the URL alone."""
    u = urlsplit(url)
    host = u.netloc.lower().split(":")[0].removeprefix("www.").removeprefix("m.")
    seg = _seg(u.path)
    dom = registrable_domain(host)

    if dom == "github.com" and host in ("github.com",) and seg and seg[0] not in _RESERVED_GITHUB:
        return ("/".join(seg[:2]), "GitHub")
    if host.endswith(".github.io"):
        return (host.split(".")[0] + (f"/{seg[0]}" if seg else ""), "GitHub Pages")
    if dom == "gitlab.com" and seg:
        return ("/".join(seg[:2]), "GitLab")
    if dom == "huggingface.co" and seg and seg[0] not in ("docs", "blog", "learn", "pricing"):
        s = seg[1:] if seg[0] in ("spaces", "datasets") else seg
        return ("/".join(s[:2]), "Hugging Face")
    if dom in ("youtube.com", "youtu.be"):
        if seg and seg[0].startswith("@"):
            return (seg[0], "YouTube")
        if len(seg) >= 2 and seg[0] in ("c", "user", "channel"):
            return (seg[1], "YouTube")
        return ("YouTube", "YouTube")  # a video: the channel name is looked up separately (oEmbed)
    if dom == "vimeo.com":
        return ("Vimeo", "Vimeo")
    if dom == "linkedin.com" and len(seg) >= 2 and seg[0] in ("in", "company", "school", "showcase"):
        return (seg[1], "LinkedIn")
    if dom == "linkedin.com" and len(seg) >= 2 and seg[0] == "posts":
        return (seg[1].split("_")[0], "LinkedIn")
    if dom in ("x.com", "twitter.com") and seg and seg[0] not in _RESERVED_SOCIAL:
        return ("@" + seg[0], "X")
    if dom == "instagram.com" and seg and seg[0] not in _RESERVED_SOCIAL:
        return ("@" + seg[0], "Instagram")
    if dom == "tiktok.com" and seg and seg[0].startswith("@"):
        return (seg[0], "TikTok")
    if dom == "facebook.com" and seg and seg[0] not in _RESERVED_SOCIAL | {"groups", "events", "pages", "profile.php"}:
        return (seg[0], "Facebook")
    if dom == "medium.com":
        if seg and seg[0].startswith("@"):
            return (seg[0], "Medium")
        if host != "medium.com":
            return (host.split(".")[0], "Medium")
        return (seg[0] if seg else "Medium", "Medium")
    if dom == "substack.com" and host != "substack.com":
        return (host.split(".")[0], "Substack")
    if dom == "reddit.com" and len(seg) >= 2 and seg[0] in ("r", "u", "user"):
        return (f"{'r' if seg[0] == 'r' else 'u'}/{seg[1]}", "Reddit")
    if dom == "npmjs.com" and len(seg) >= 2 and seg[0] == "package":
        return ("/".join(seg[1:3]) if seg[1].startswith("@") else seg[1], "npm")
    if dom == "pypi.org" and len(seg) >= 2 and seg[0] == "project":
        return (seg[1], "PyPI")
    if dom == "producthunt.com" and len(seg) >= 2 and seg[0] in ("products", "posts"):
        return (seg[1], "Product Hunt")
    if dom == "google.com" and host.startswith("docs."):
        return ("Google Docs", "Google")
    return (dom or host or url, "website")


def is_video(url: str) -> str | None:
    """'youtube' / 'vimeo' if this is a single video page whose channel we can look up."""
    u = urlsplit(url)
    host = u.netloc.lower().removeprefix("www.").removeprefix("m.")
    seg = _seg(u.path)
    if host == "youtu.be" and seg:
        return "youtube"
    if host.endswith("youtube.com") and (u.path == "/watch" or (seg and seg[0] in ("shorts", "live"))):
        return "youtube"
    if host == "vimeo.com" and seg and seg[0].isdigit():
        return "vimeo"
    return None

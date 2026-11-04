"""Website data for online communication work: SEO basics, keywords, marketing stack, socials.

Approach follows python-seo-analyzer (on-page checks + keyword/phrase frequency) and
Wappalyzer (technology detection by fingerprints), with a short, self-written list of
marketing-relevant technologies instead of Wappalyzer's full GPL-licensed database.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

# ── marketing / web technology fingerprints ─────────────────────────
# (name, category, regex searched in the raw HTML, regex searched in "header: value" lines or None)
TECH = [
    # analytics
    ("Google Analytics 4", "analytics", r"gtag\(['\"]config['\"],\s*['\"]G-|googletagmanager\.com/gtag/js\?id=G-", None),
    ("Google Analytics (Universal)", "analytics", r"google-analytics\.com/(analytics|ga)\.js|['\"]UA-\d{4,}-\d+['\"]", None),
    ("Google Tag Manager", "analytics", r"googletagmanager\.com/gtm\.js|GTM-[A-Z0-9]{4,}", None),
    ("Matomo", "analytics", r"matomo\.js|piwik\.js|_paq\.push", None),
    ("Plausible", "analytics", r"plausible\.io/js", None),
    ("Hotjar", "analytics", r"static\.hotjar\.com|hjSetting", None),
    ("Microsoft Clarity", "analytics", r"clarity\.ms/tag", None),
    ("Mixpanel", "analytics", r"cdn\.mxpnl\.com|mixpanel\.init", None),
    ("Segment", "analytics", r"cdn\.segment\.com/analytics", None),
    # ads / pixels
    ("Meta Pixel", "ads", r"connect\.facebook\.net/[^\"']*/fbevents\.js|fbq\(['\"]init", None),
    ("Google Ads", "ads", r"googleadservices\.com|gtag\(['\"]config['\"],\s*['\"]AW-|googletagmanager\.com/gtag/js\?id=AW-", None),
    ("LinkedIn Insight", "ads", r"snap\.licdn\.com/li\.lms-analytics|_linkedin_partner_id", None),
    ("TikTok Pixel", "ads", r"analytics\.tiktok\.com|ttq\.load", None),
    ("Pinterest Tag", "ads", r"s\.pinimg\.com/ct/core\.js|pintrk\(", None),
    ("X (Twitter) Pixel", "ads", r"static\.ads-twitter\.com|twq\(", None),
    ("Microsoft Ads (UET)", "ads", r"bat\.bing\.com/bat\.js", None),
    # CMS / site builders / shops
    ("WordPress", "cms", r"/wp-content/|/wp-includes/|<meta[^>]+generator[^>]+WordPress", None),
    ("WooCommerce", "shop", r"woocommerce", None),
    ("Shopify", "shop", r"cdn\.shopify\.com|Shopify\.theme", r"^x-shopify|^x-shopid"),
    ("Wix", "cms", r"static\.wixstatic\.com|wix-bolt|<meta[^>]+generator[^>]+Wix", r"^x-wix"),
    ("Squarespace", "cms", r"static1\.squarespace\.com|Squarespace\.", None),
    ("Webflow", "cms", r"webflow\.(js|com)|data-wf-page", None),
    ("Framer", "cms", r"framerusercontent\.com|<meta[^>]+generator[^>]+Framer", None),
    ("Ghost", "cms", r"<meta[^>]+generator[^>]+Ghost", None),
    ("Drupal", "cms", r"Drupal\.settings|/sites/default/files/|<meta[^>]+generator[^>]+Drupal", r"^x-drupal"),
    ("Joomla", "cms", r"<meta[^>]+generator[^>]+Joomla", None),
    ("Elementor", "cms", r"elementor-", None),
    ("Next.js", "framework", r"/_next/static/|__NEXT_DATA__", r"^x-powered-by: next\.js"),
    ("Nuxt", "framework", r"/_nuxt/|__NUXT__", None),
    # CRM / email / automation
    ("HubSpot", "crm", r"js\.hs-scripts\.com|js\.hsforms\.net|hs-analytics", None),
    ("Mailchimp", "email", r"chimpstatic\.com|list-manage\.com", None),
    ("Klaviyo", "email", r"static\.klaviyo\.com|klaviyo\.js", None),
    ("ActiveCampaign", "email", r"trackcmp\.net|activehosted\.com", None),
    ("Brevo (Sendinblue)", "email", r"sibautomation\.com|sendinblue|brevo\.com/js", None),
    ("MailerLite", "email", r"mailerlite\.com", None),
    ("Salesforce", "crm", r"salesforce\.com|force\.com|pardot\.com", None),
    # chat / booking
    ("Intercom", "chat", r"widget\.intercom\.io|intercomSettings", None),
    ("Drift", "chat", r"js\.driftt\.com", None),
    ("Crisp", "chat", r"client\.crisp\.chat", None),
    ("Tawk.to", "chat", r"embed\.tawk\.to", None),
    ("Zendesk", "chat", r"static\.zdassets\.com|zopim", None),
    ("Calendly", "booking", r"assets\.calendly\.com|calendly\.com/", None),
    # consent
    ("Cookiebot", "consent", r"consent\.cookiebot\.com", None),
    ("OneTrust", "consent", r"cdn\.cookielaw\.org|onetrust", None),
    ("Usercentrics", "consent", r"usercentrics\.(eu|com)", None),
    ("CookieYes", "consent", r"cdn-cookieyes\.com", None),
    ("Complianz", "consent", r"complianz", None),
    # infrastructure
    ("Cloudflare", "hosting", r"cdnjs\.cloudflare\.com/ajax/libs/cloudflare|/cdn-cgi/", r"^server: cloudflare|^cf-ray"),
    ("Google Fonts", "assets", r"fonts\.googleapis\.com", None),
    ("YouTube embeds", "media", r"youtube\.com/embed|youtube-nocookie\.com", None),
    ("Vimeo embeds", "media", r"player\.vimeo\.com", None),
]
_TECH_RE = [(n, c, re.compile(h, re.I), re.compile(hd, re.I | re.M) if hd else None) for n, c, h, hd in TECH]

SOCIAL = {
    "facebook.com": "Facebook", "instagram.com": "Instagram", "linkedin.com": "LinkedIn",
    "tiktok.com": "TikTok", "youtube.com": "YouTube", "x.com": "X", "twitter.com": "X",
    "pinterest.com": "Pinterest", "threads.net": "Threads", "github.com": "GitHub",
    "wa.me": "WhatsApp", "t.me": "Telegram",
}

# Small stopword lists (en, ro, hu, de, fr, es): enough to get meaningful keywords.
STOP = set("""
a about above after again all also am an and any are as at be because been before being below between both but by can could
did do does doing down during each few for from further get got had has have having he her here hers him his how i if in into
is it its just me more most my no nor not now of off on once only or other our out over own same she should so some such than
that the their them then there these they this those through to too under until up us very was we were what when where which
while who whom why will with would you your yours new one also use using used via per may like make made way well
www http https com html page click read more home menu contact cookie cookies privacy policy terms rights reserved
și si sau cu de la în in pe pentru din care ce cum este sunt fi fost mai un una unei unui al ale ai lui lor nu da dar ca că
vă va vom sa să se ne noi voi ei ele acest această acesta aceste acum doar foarte prin după despre fără până toate tot
és a az egy hogy nem is meg de ez azt van volt mint már csak még ha vagy el ki be fel le mi te ő mi ti ők itt ott
minden kell lehet lesz akkor után alatt felett között szerint nagyon
der die das und oder mit von zu im den dem des ein eine einer ist sind war für auf aus bei nicht auch es sie wir ihr
le la les des du un une et ou est sont pour par avec dans sur pas plus nous vous
el los las del y o es son por con para una unos como más
""".split())


class _SeoParser(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template"}
    BOILER = {"nav", "footer", "header"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.lang = ""
        self.canonical = ""
        self.favicon = ""
        self.hreflang: list[str] = []
        self.headings: dict[str, list[str]] = {"h1": [], "h2": []}
        self.images = 0
        self.images_no_alt = 0
        self.links: list[str] = []
        self.jsonld: list[str] = []
        self.itemtypes: list[str] = []
        self.text: list[str] = []
        self._skip = 0
        self._boiler = 0
        self._head: str | None = None
        self._head_buf: list[str] = []
        self._in_jsonld = False
        self._jsonld_buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html":
            self.lang = a.get("lang", "")
        elif tag == "meta":
            key = (a.get("property") or a.get("name") or a.get("http-equiv") or "").lower()
            if key and "content" in a:
                self.meta.setdefault(key, a["content"].strip())
        elif tag == "link":
            rel = a.get("rel", "").lower()
            if "canonical" in rel:
                self.canonical = a.get("href", "")
            elif "icon" in rel and not self.favicon:
                self.favicon = a.get("href", "")
            elif "alternate" in rel and a.get("hreflang"):
                self.hreflang.append(a["hreflang"])
        elif tag == "img":
            self.images += 1
            if not a.get("alt", "").strip():
                self.images_no_alt += 1
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "script" and "ld+json" in a.get("type", "").lower():
            self._in_jsonld, self._jsonld_buf = True, []
            self._skip += 1
        elif tag in self.SKIP:
            self._skip += 1
        if tag in self.BOILER:
            self._boiler += 1
        if tag in ("h1", "h2"):
            self._head, self._head_buf = tag, []
        if a.get("itemtype"):
            self.itemtypes.append(a["itemtype"].rstrip("/").rsplit("/", 1)[-1])

    def handle_endtag(self, tag):
        if tag == "script" and self._in_jsonld:
            self.jsonld.append("".join(self._jsonld_buf))
            self._in_jsonld = False
            self._skip = max(0, self._skip - 1)
        elif tag in self.SKIP and self._skip:
            self._skip -= 1
        if tag in self.BOILER and self._boiler:
            self._boiler -= 1
        if tag == self._head:
            h = " ".join("".join(self._head_buf).split())
            if h:
                self.headings[tag].append(h[:200])
            self._head = None

    def handle_data(self, data):
        if self._in_jsonld:
            self._jsonld_buf.append(data)
            return
        if self._skip:
            return
        if self._head:
            self._head_buf.append(data)
        if not self._boiler:
            self.text.append(data)


def _schema_types(blocks: list[str]) -> list[str]:
    found: list[str] = []

    def walk(x):
        if isinstance(x, dict):
            t = x.get("@type")
            for v in (t if isinstance(t, list) else [t]):
                if isinstance(v, str) and v not in found:
                    found.append(v)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    for b in blocks:
        try:
            walk(json.loads(b))
        except ValueError:
            continue
    return found


def keywords(text: str, top: int = 12) -> dict:
    words = [w for w in re.findall(r"[^\W\d_]{3,}", text.lower(), flags=re.UNICODE)]
    content = [w for w in words if w not in STOP]
    singles = Counter(content).most_common(top)
    pairs = Counter(
        f"{a} {b}" for a, b in zip(words, words[1:]) if a not in STOP and b not in STOP and a != b
    )
    phrases = [(p, n) for p, n in pairs.most_common(top) if n >= 2]
    return {"words": singles, "phrases": phrases}


def analyze(html: str, url: str, headers: dict | None = None, status: int = 200,
            elapsed_ms: int | None = None, size_bytes: int | None = None, redirects: int = 0) -> dict:
    p = _SeoParser()
    try:
        p.feed(html)
    except Exception:
        pass
    m = p.meta
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    header_lines = "\n".join(f"{k}: {v}" for k, v in headers.items())
    host = urlsplit(url).netloc.removeprefix("www.")

    tech = []
    for name, cat, html_re, head_re in _TECH_RE:
        if html_re.search(html) or (head_re and head_re.search(header_lines)):
            tech.append({"name": name, "category": cat})
    gen = m.get("generator", "")
    if gen and not any(t["name"].split()[0].lower() in gen.lower() for t in tech):
        tech.append({"name": gen[:60], "category": "cms"})

    internal = external = 0
    socials: dict[str, str] = {}
    emails, phones = [], []
    for href in p.links:
        h = href.strip()
        if h.lower().startswith("mailto:"):
            e = h[7:].split("?")[0]
            if e and e not in emails:
                emails.append(e)
            continue
        if h.lower().startswith("tel:"):
            t = h[4:].strip()
            if t and t not in phones:
                phones.append(t)
            continue
        full = urljoin(url, h)
        lh = urlsplit(full).netloc.lower().removeprefix("www.")
        if not lh:
            continue
        if lh == host or lh.endswith("." + host):
            internal += 1
            continue
        external += 1
        for dom, name in SOCIAL.items():
            if (lh == dom or lh.endswith("." + dom)) and name not in socials:
                path = urlsplit(full).path.strip("/")
                if path and not path.startswith(("sharer", "share", "intent", "embed", "plugins", "dialog")):
                    socials[name] = full

    body_text = " ".join(" ".join(p.text).split())
    title = (re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S) or [None, ""])[1]
    title = " ".join(re.sub(r"<[^>]+>", "", title).split())
    desc = m.get("description", "")
    schema = _schema_types(p.jsonld) + [t for t in p.itemtypes if t]
    schema = list(dict.fromkeys(schema))

    data = {
        "url": url,
        "status": status,
        "https": url.startswith("https://"),
        "redirects": redirects,
        "response_ms": elapsed_ms,
        "size_kb": round(size_bytes / 1024) if size_bytes else None,
        "server": headers.get("server", ""),
        "lang": p.lang,
        "title": title,
        "description": desc,
        "meta_keywords": [k.strip() for k in m.get("keywords", "").split(",") if k.strip()][:30],
        "canonical": urljoin(url, p.canonical) if p.canonical else "",
        "robots": m.get("robots", ""),
        "viewport": bool(m.get("viewport")),
        "favicon": urljoin(url, p.favicon) if p.favicon else "",
        "hreflang": p.hreflang[:20],
        "og": {k[3:]: (urljoin(url, v) if k in ("og:image", "og:url") else v)
               for k, v in m.items() if k.startswith("og:")},
        "twitter_card": m.get("twitter:card", ""),
        "h1": p.headings["h1"][:5],
        "h2": p.headings["h2"][:12],
        "word_count": len(body_text.split()),
        "images": p.images,
        "images_no_alt": p.images_no_alt,
        "links_internal": internal,
        "links_external": external,
        "schema_types": schema[:15],
        "tech": tech,
        "socials": socials,
        "emails": emails[:5],
        "phones": phones[:5],
        "keywords": keywords(body_text),
    }
    data["checks"] = checks(data)
    return data


def checks(d: dict) -> list[dict]:
    """Quick on-page SEO / sharing checks. level: ok | warn."""
    out = []

    def add(ok: bool, good: str, bad: str):
        out.append({"level": "ok" if ok else "warn", "text": good if ok else bad})

    tl = len(d["title"])
    add(20 <= tl <= 60, f"Title length is good ({tl} characters)",
        "No page title" if not tl else f"Title is {'too short' if tl < 20 else 'long'} ({tl} characters; aim for 20–60)")
    dl = len(d["description"])
    add(70 <= dl <= 160, f"Meta description length is good ({dl} characters)",
        "No meta description (search engines will guess one)" if not dl
        else f"Meta description is {'short' if dl < 70 else 'long'} ({dl} characters; aim for 70–160)")
    h1 = len(d["h1"])
    add(h1 == 1, "Exactly one H1 heading",
        "No H1 heading" if h1 == 0 else f"{h1} H1 headings (usually one is best)")
    add(d["https"], "Uses HTTPS", "Not using HTTPS")
    add(d["viewport"], "Mobile viewport is set", "No mobile viewport tag (may look bad on phones)")
    add(bool(d["canonical"]), "Has a canonical URL", "No canonical URL")
    add("noindex" not in d["robots"].lower(), "Can be indexed by search engines",
        "Page asks search engines NOT to index it (noindex)")
    add(bool(d["og"].get("image")), "Has a social share image (og:image)",
        "No social share image (links shared on social media look plain)")
    add(bool(d["og"].get("title") or d["og"].get("description")), "Has Open Graph text for social sharing",
        "No Open Graph title/description")
    add(bool(d["schema_types"]), f"Structured data: {', '.join(d['schema_types'][:4])}",
        "No structured data (schema.org)")
    if d["images"]:
        add(d["images_no_alt"] == 0, "All images have alt text",
            f"{d['images_no_alt']} of {d['images']} images have no alt text")
    if d["response_ms"] is not None:
        add(d["response_ms"] < 1500, f"Responds quickly ({d['response_ms']} ms)",
            f"Slow response ({d['response_ms']} ms)")
    return out


def search_text(d: dict) -> str:
    """Words added to the search index so you (or Claude) can find links by their website data."""
    if not d:
        return ""
    parts = [t["name"] for t in d.get("tech", [])]
    parts += d.get("schema_types", []) + d.get("meta_keywords", [])
    parts += list(d.get("socials", {}).keys())
    parts += [w for w, _ in d.get("keywords", {}).get("words", [])]
    parts += [ph for ph, _ in d.get("keywords", {}).get("phrases", [])]
    parts.append(d.get("lang", ""))
    return " ".join(parts)

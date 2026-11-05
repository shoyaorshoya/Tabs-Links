"""Run: pip install -r requirements.txt pytest && python -m pytest -q tests"""
import json
import time
from types import SimpleNamespace

import pytest

import httpx

from closedtabs import db, enrich, providers, taxonomy, urls

PAGE = """<html><head><title>Fallback title</title>
<meta property="og:title" content="AdLab: A/B test landing pages">
<meta name="description" content="Freemium tool for testing landing pages.">
<meta property="og:image" content="/img/cover.png">
<script>var x = "ignore me";</script></head>
<body><nav>Menu</nav><h1>AdLab</h1><p>Run neuromarketing experiments on landing pages.</p></body></html>"""


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db.reset_for_tests(tmp_path)
    for v in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "CLAUDE_MODEL", "AI_PROVIDER",
              "LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(v, raising=False)
    yield


def test_parse_text_formats_and_tracking():
    text = """https://a.com/x?utm_source=t&id=1
    https://b.com | B title
    [C title](https://c.com/page)
    nothing here
    https://a.com/x?id=1"""
    assert urls.parse_text(text) == [
        ("https://a.com/x?id=1", ""), ("https://b.com", "B title"), ("https://c.com/page", "C title"),
    ]


def test_parse_bookmarks_html():
    html = '<DL><DT><H3>Folder</H3><DT><A HREF="https://x.org/a" ADD_DATE="1">X &amp; Co</A>' \
           '<DT><A HREF="javascript:void(0)">bad</A></DL>'
    assert urls.parse_bookmarks_html(html) == [("https://x.org/a", "X & Co")]


def test_parse_page():
    p = enrich.parse_page(PAGE, "https://adlab.io/home")
    assert p["title"] == "AdLab: A/B test landing pages"
    assert p["description"].startswith("Freemium")
    assert p["image"] == "https://adlab.io/img/cover.png"
    assert "neuromarketing experiments" in p["content"]
    assert "ignore me" not in p["content"] and "Menu" not in p["content"]


def test_db_add_search_tags():
    i, created = db.add("https://adlab.io", note="for client X")
    assert created and db.add("https://adlab.io") == (i, False)
    db.update(i, title="AdLab", summary="Landing page testing", tags=["type/tool", "topic/analytics"])
    assert [l["id"] for l in db.search("landing")] == [i]
    assert [l["id"] for l in db.search("client")] == [i]          # note is searchable
    assert [l["id"] for l in db.search("", tag="type/tool")] == [i]
    assert db.search("", tag="type/article") == []
    assert dict(db.tag_counts()) == {"topic/analytics": 1, "type/tool": 1}
    db.delete(i)
    assert db.count() == 0 and db.search("landing") == []


def test_search_survives_odd_input():
    db.add("https://x.com")
    assert db.search('"unbalanced AND (') == []


def test_normalize_free_topics():
    out = taxonomy.normalize({"type": "Company", "summary": " s ",
                              "topics": ["Permanent Makeup", "#Oradea", "permanent-makeup", "topic/Beauty Salon",
                                         "x", "eye_tracking", "extra-one"]})
    assert out == {"type": "company", "topics": ["permanent-makeup", "oradea", "beauty-salon", "eye-tracking"],
                   "summary": "s"}
    assert taxonomy.normalize({"type": "nonsense", "topics": "oops"})["type"] == "other"
    assert taxonomy.to_tags(out)[:2] == ["type/company", "topic/permanent-makeup"]


def test_own_labels():
    assert taxonomy.own_labels("Project Delia, client ,, client\nÉpítészet, type/Tool") == \
        ["project-delia", "client", "építészet", "type/tool"]


def test_enrich_with_claude(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(enrich, "fetch", lambda url, **kw: enrich.parse_page(PAGE, url))
    sent = {}

    def fake_create(**kw):
        sent.update(kw)
        out = {"type": "tool", "topics": ["landing-pages", "ab-testing"], "summary": "A test tool."}
        return SimpleNamespace(stop_reason="end_turn", content=[
            SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=json.dumps(out))])

    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=fake_create)))
    monkeypatch.setattr(providers, "_client", fake)
    i, _ = db.add("https://adlab.io")
    enrich.enrich(i)
    link = db.get(i)
    assert link["status"] == "done" and link["summary"] == "A test tool."
    assert link["tags"] == ["topic/ab-testing", "topic/landing-pages", "type/tool"]
    assert sent["model"] == "claude-opus-5-5" and sent["fallbacks"] == "default"
    assert sent["output_config"]["format"]["schema"] == taxonomy.SCHEMA
    assert "<page>" in sent["messages"][0]["content"]


def test_enrich_without_key_and_unreachable_site(monkeypatch):
    def boom(url, **kw):
        raise OSError("offline")
    monkeypatch.setattr(enrich, "fetch", boom)
    i, _ = db.add("https://down.example", title="My title")
    enrich.enrich(i)
    link = db.get(i)
    assert link["status"] == "done" and link["title"] == "My title"
    assert "Couldn't open" in link["error"]


def test_haiku_skips_fallbacks(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("CLAUDE_MODEL", "claude-haiku-5-5")
    sent = {}

    def fake_create(**kw):
        sent.update(kw)
        return SimpleNamespace(stop_reason="refusal", content=[])

    monkeypatch.setattr(providers, "_client",
                        SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=fake_create))))
    with pytest.raises(providers.LabelError):
        providers.label("https://x", {"title": "x"})
    assert "fallbacks" not in sent


def test_web_flow(monkeypatch):
    from fastapi.testclient import TestClient
    from closedtabs import web

    monkeypatch.setattr(enrich, "fetch", lambda url, **kw: enrich.parse_page(PAGE, url))
    with TestClient(web.app) as c:
        r = c.get("/")
        assert r.status_code == 200 and ">Enter<" in r.text and "password" not in r.text.lower()
        r = c.post("/add", data={"text": "https://adlab.io\nhttps://adlab.io", "note": ""}, follow_redirects=False)
        assert r.status_code == 303 and "Saved+1+link" in r.headers["location"]
        for _ in range(50):
            if db.search("")[0]["status"] != "pending":
                break
            time.sleep(0.05)
        r = c.get("/library?q=neuromarketing")
        assert "AdLab: A/B test landing pages" in r.text
        r = c.post("/import", files={"file": ("b.html", b'<A HREF="https://new.org">New</A>')}, follow_redirects=False)
        assert "Saved+1+link" in r.headers["location"]
        assert c.get("/health").json()["links"] == 2
        assert len(json.loads(c.get("/export.json").text)) == 2


def test_links_saved_before_key_get_labelled_on_start(monkeypatch):
    i, _ = db.add("https://old.example")
    db.update(i, status="done", title="Old")                 # saved with AI off
    j, _ = db.add("https://done.example")
    db.update(j, status="done", tags=["type/tool"])           # already labelled
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    w = enrich.Worker(threads=0)                              # no threads: just inspect the queue
    w.start()
    assert list(w.q.queue) == [i]
    assert db.get(i)["status"] == "pending" and db.get(j)["status"] == "done"


def _gemini_env(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    monkeypatch.setenv("LLM_API_KEY", "g-key")
    monkeypatch.setenv("LLM_MODEL", "some-gemini-model")


def _resp(status, payload=None, text=""):
    return httpx.Response(status, json=payload) if payload is not None else httpx.Response(status, text=text)


def test_other_provider_json_schema_and_cleanup(monkeypatch):
    _gemini_env(monkeypatch)
    sent = []
    answer = {"type": "Tool", "topics": ["Neuromarketing", "Made Up"], "summary": "Gem."}

    def fake_post(payload):
        sent.append(payload)
        return _resp(200, {"choices": [{"message": {"content": "```json\n" + json.dumps(answer) + "\n```"}}]})

    monkeypatch.setattr(providers, "_post_chat", fake_post)
    assert providers.provider() == "other"
    out = providers.label("https://x", {"title": "x"})
    assert out == {"type": "tool", "topics": ["neuromarketing", "made-up"], "summary": "Gem."}
    assert sent[0]["response_format"]["type"] == "json_schema" and sent[0]["model"] == "some-gemini-model"


def test_other_provider_falls_back_when_json_mode_unsupported(monkeypatch):
    _gemini_env(monkeypatch)
    calls = []

    def fake_post(payload):
        calls.append(payload.get("response_format", {}).get("type"))
        if len(calls) < 3:
            return _resp(400, text="response_format not supported")
        return _resp(200, {"choices": [{"message": {"content": 'Sure! {"type":"video","topics":[],"uses":[],"summary":"S"}'}}]})

    monkeypatch.setattr(providers, "_post_chat", fake_post)
    out = providers.label("https://x", {"title": "x"})
    assert calls == ["json_schema", "json_object", None]
    assert out["type"] == "video" and out["topics"] == []


def test_other_provider_bad_key_message(monkeypatch):
    _gemini_env(monkeypatch)
    monkeypatch.setattr(providers, "_post_chat", lambda p: _resp(401, text="nope"))
    with pytest.raises(providers.LabelError, match="LLM_API_KEY"):
        providers.label("https://x", {"title": "x"})


def test_provider_choice(monkeypatch):
    assert providers.provider() is None
    _gemini_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    assert providers.provider() == "claude"            # both set: Claude by default
    monkeypatch.setenv("AI_PROVIDER", "other")
    assert providers.provider() == "other"
    monkeypatch.delenv("LLM_API_KEY")                   # Ollama-style: no key needed
    assert providers.provider() == "other"


def test_other_provider_out_of_credits_message(monkeypatch):
    _gemini_env(monkeypatch)
    monkeypatch.setattr(providers, "_post_chat", lambda p: _resp(402, text='{"error":"Purchase pre-paid credits"}'))
    with pytest.raises(providers.LabelError, match="out of credits"):
        providers.label("https://x", {"title": "x"})


def test_relabel_replaces_old_ai_labels_keeps_own(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(enrich, "fetch", lambda url, **kw: enrich.parse_page(PAGE, url))
    seen = {}

    def fake_label(url, page, ai_chars, note="", known=None):
        seen["note"], seen["known"] = note, known
        return {"type": "company", "topics": ["permanent-makeup"], "summary": "A salon."}

    monkeypatch.setattr(providers, "label", fake_label)
    i, _ = db.add("https://salon.example", note="Project Delia")
    db.update(i, tags=["type/tool", "topic/neuromarketing", "use/try-it", "project-delia"], status="done")
    enrich.enrich(i)
    assert db.get(i)["tags"] == ["project-delia", "topic/permanent-makeup", "type/company"]
    assert seen["note"] == "Project Delia" and seen["known"] == ["neuromarketing"]


def test_known_labels_reach_prompt(monkeypatch):
    _gemini_env(monkeypatch)
    sent = []
    monkeypatch.setattr(providers, "_post_chat", lambda p: sent.append(p) or _resp(
        200, {"choices": [{"message": {"content": '{"type":"company","topics":["beauty"],"summary":"s"}'}}]}))
    providers.label("https://x", {"title": "x"}, known=["beauty", "oradea"])
    assert "Existing labels: beauty, oradea" in sent[0]["messages"][1]["content"]


def test_note_reaches_prompt(monkeypatch):
    _gemini_env(monkeypatch)
    sent = []
    monkeypatch.setattr(providers, "_post_chat", lambda p: sent.append(p) or _resp(
        200, {"choices": [{"message": {"content": '{"type":"company","topics":["salon"],"summary":"s"}'}}]}))
    providers.label("https://x", {"title": "x"}, note="Project Delia")
    assert "Project Delia" in sent[0]["messages"][1]["content"]


def test_web_own_labels_and_relabel_all(monkeypatch):
    from fastapi.testclient import TestClient
    from closedtabs import web

    monkeypatch.setattr(enrich, "fetch", lambda url, **kw: enrich.parse_page(PAGE, url))
    c = TestClient(web.app)  # no lifespan: startup already ran once in test_web_flow
    if True:
        c.post("/add", data={"text": "https://a.example", "labels": "Project Delia, client"})
        i = db.search("")[0]["id"]
        assert {"project-delia", "client"} <= set(db.get(i)["tags"])
        c.post("/add", data={"text": "https://a.example", "labels": "later"})   # duplicate: labels merge
        assert "later" in db.get(i)["tags"]
        r = c.get("/library")
        assert "my labels" in r.text and "Re-label all" not in r.text            # AI off: no button
        r = c.post("/relabel-all", follow_redirects=False)
        assert "AI+is+off" in r.headers["location"]


SITE = """<!doctype html><html lang="ro"><head>
<title>Judith Ardelean - Permanent Makeup Oradea</title>
<meta name="description" content="Dermopigmentare și machiaj permanent în Oradea din 1997. Sprâncene, buze, eyeliner. Programează-te online.">
<meta name="keywords" content="machiaj permanent, sprancene, oradea">
<meta name="viewport" content="width=device-width">
<meta property="og:title" content="Judith Ardelean PMU"><meta property="og:image" content="/og.jpg">
<meta name="generator" content="WordPress 6.6">
<link rel="canonical" href="/ro/"><link rel="alternate" hreflang="hu" href="/hu/">
<script async src="https://www.googletagmanager.com/gtag/js?id=G-ABC123"></script>
<script>fbq('init', '123');</script>
<script src="https://consent.cookiebot.com/uc.js"></script>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"BeautySalon","address":{"@type":"PostalAddress"}}</script>
</head><body><nav>Acasă Servicii Contact</nav>
<h1>Machiaj permanent Oradea</h1><h2>Sprâncene</h2><h2>Buze</h2>
<p>Machiaj permanent pentru sprâncene și buze. Machiaj permanent realizat cu grijă. Sprâncene naturale.</p>
<img src="a.jpg" alt="sprancene"><img src="b.jpg">
<a href="/servicii">Servicii</a><a href="https://www.instagram.com/judith.pmu/">Insta</a>
<a href="https://www.facebook.com/sharer/sharer.php?u=x">share</a><a href="mailto:hello@example.ro">mail</a>
<a href="tel:+40700000000">call</a><footer>© 2026 cookie policy</footer></body></html>"""


def test_seo_analyze():
    from closedtabs import seo
    d = seo.analyze(SITE, "https://judith.example/ro/", headers={"Server": "cloudflare"},
                    elapsed_ms=420, size_bytes=4000, redirects=1)
    names = {t["name"] for t in d["tech"]}
    assert {"Google Analytics 4", "Meta Pixel", "Cookiebot", "WordPress", "Cloudflare"} <= names
    assert d["lang"] == "ro" and d["hreflang"] == ["hu"]
    assert d["canonical"] == "https://judith.example/ro/"
    assert d["schema_types"] == ["BeautySalon", "PostalAddress"]
    assert d["h1"] == ["Machiaj permanent Oradea"] and d["h2"] == ["Sprâncene", "Buze"]
    assert d["images"] == 2 and d["images_no_alt"] == 1
    assert d["socials"] == {"Instagram": "https://www.instagram.com/judith.pmu/"}   # share links ignored
    assert d["emails"] == ["hello@example.ro"] and d["phones"] == ["+40700000000"]
    assert d["meta_keywords"] == ["machiaj permanent", "sprancene", "oradea"]
    words = dict(d["keywords"]["words"])
    assert words["machiaj"] == 3 and "pentru" not in words and "acasă" not in words    # stopwords, nav removed
    assert ("machiaj permanent", 3) in d["keywords"]["phrases"]
    levels = {c["text"].split(" (")[0]: c["level"] for c in d["checks"]}
    assert levels["Exactly one H1 heading"] == "ok"
    assert any(c["level"] == "warn" and "alt text" in c["text"] for c in d["checks"])
    assert "Meta Pixel" in seo.search_text(d)


def test_search_by_technology_and_migration(tmp_path):
    import sqlite3
    from closedtabs import seo
    old = sqlite3.connect(tmp_path / "closedtabs.db")       # database from an older version
    old.executescript("""
      CREATE TABLE links (id INTEGER PRIMARY KEY, url TEXT NOT NULL UNIQUE, title TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '', image TEXT NOT NULL DEFAULT '', site TEXT NOT NULL DEFAULT '',
        content TEXT NOT NULL DEFAULT '', summary TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '[]',
        note TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending', error TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL);
      CREATE VIRTUAL TABLE links_fts USING fts5(title, summary, description, tags, note, url, content);
      INSERT INTO links(url,title,created_at) VALUES ('https://old.example','Old salon',1);
      INSERT INTO links_fts(rowid,title) VALUES (1,'Old salon');""")
    old.commit(); old.close()
    db.reset_for_tests(tmp_path)
    assert [l["title"] for l in db.search("salon")] == ["Old salon"] and db.get(1)["seo"] == {}
    db.update(1, seo=seo.analyze(SITE, "https://old.example/"))
    assert [l["id"] for l in db.search("Meta Pixel")] == [1]
    assert [l["id"] for l in db.search("BeautySalon")] == [1]


def test_detail_page_shows_website_data():
    from fastapi.testclient import TestClient
    from closedtabs import seo, web
    i, _ = db.add("https://judith.example/ro/")
    db.update(i, status="done", title="Judith", seo=seo.analyze(SITE, "https://judith.example/ro/"))
    r = TestClient(web.app).get(f"/links/{i}")
    assert "Website data" in r.text and "Meta Pixel" in r.text and "BeautySalon" in r.text
    assert "machiaj permanent" in r.text



def _fetch_with_seo(url, analyze=False):
    from closedtabs import seo
    page = enrich.parse_page(SITE, url)
    if analyze:
        page["seo"] = seo.analyze(SITE, url)
    return page


def test_commdata_only_when_ticked(monkeypatch):
    from fastapi.testclient import TestClient
    from closedtabs import web

    monkeypatch.setattr(enrich, "fetch", _fetch_with_seo)
    c = TestClient(web.app)
    c.post("/add", data={"text": "https://plain.example", "labels": "project-delia"})
    c.post("/add", data={"text": "https://salon1.example\nhttps://salon2.example",
                         "labels": "project-delia", "commdata": "1"})
    c.post("/add", data={"text": "https://other.example", "labels": "project-x", "commdata": "1"})
    for l in db.search("", limit=50):
        enrich.enrich(l["id"])                        # run the background step synchronously
    by_url = {l["url"]: l for l in db.search("", limit=50)}
    assert by_url["https://plain.example"]["seo"] == {}
    assert "commdata" not in by_url["https://plain.example"]["tags"]
    assert "commdata" in by_url["https://salon1.example"]["tags"]
    assert by_url["https://salon1.example"]["seo"]["tech"]
    assert db.commdata_projects() == [("project-delia", 2), ("project-x", 1)]
    assert [l["url"] for l in db.search("", ["commdata", "project-delia"])] == \
        ["https://salon2.example", "https://salon1.example"]

    r = c.get("/library?tag=commdata&tag=project-delia")
    assert "CommData" in r.text and "project-delia" in r.text and "CSV (;)" in r.text
    assert 'name="commdata" value="1" checked' in r.text            # saving from this view ticks the box

    # toggle off and on again
    sid = by_url["https://salon1.example"]["id"]
    c.post(f"/links/{sid}/commdata", data={"on": "0"})
    assert db.get(sid)["seo"] == {} and "commdata" not in db.get(sid)["tags"]
    c.post(f"/links/{sid}/commdata", data={"on": "1"})
    enrich.enrich(sid)
    assert "commdata" in db.get(sid)["tags"]

    # editing labels by hand can't fake or drop the CommData label
    c.post(f"/links/{sid}/edit", data={"tags": "project-delia", "note": ""})
    assert "commdata" in db.get(sid)["tags"]


def test_commdata_csv(monkeypatch):
    import csv as _csv
    import io
    from fastapi.testclient import TestClient
    from closedtabs import web

    monkeypatch.setattr(enrich, "fetch", _fetch_with_seo)
    c = TestClient(web.app)
    c.post("/add", data={"text": "https://salon1.example", "labels": "project-delia", "commdata": "1"})
    c.post("/add", data={"text": "https://other.example", "labels": "project-x", "commdata": "1"})
    for l in db.search(""):
        enrich.enrich(l["id"])

    r = c.get("/export/commdata.csv?tag=project-delia&sep=semicolon")
    assert r.status_code == 200 and "project-delia" in r.headers["content-disposition"]
    text = r.content.decode("utf-8")
    assert text.startswith("\ufeff")
    rows = list(_csv.DictReader(io.StringIO(text[1:]), delimiter=";"))
    assert len(rows) == 1
    row = rows[0]
    assert row["URL"] == "https://salon1.example" and row["Project labels"] == "project-delia"
    assert "Meta Pixel" in row["Ad pixels"] and "Google Analytics 4" in row["Analytics"]
    assert row["Instagram"].startswith("https://www.instagram.com/") and row["Language"] == "ro"
    assert "machiaj permanent (3)" in row["Top phrases"] and int(row["SEO issues"]) >= 1

    rows = list(_csv.DictReader(io.StringIO(c.get("/export/commdata.csv").content.decode("utf-8")[1:])))
    assert {r["URL"] for r in rows} == {"https://salon1.example", "https://other.example"}


def test_why_keywords_and_sources_flow(monkeypatch):
    from fastapi.testclient import TestClient
    from closedtabs import web

    monkeypatch.setattr(enrich, "fetch", lambda url, **kw: enrich.parse_page(PAGE, url))
    monkeypatch.setattr(enrich, "video_info", lambda url: {})
    c = TestClient(web.app)
    c.post("/add", data={"text": "https://www.mero.ro/judith", "why": "Inspiration, pricing page ,inspiration"})
    c.post("/add", data={"text": "https://github.com/sethblack/python-seo-analyzer", "why": "tool to try"})
    c.post("/add", data={"text": "https://blog.hubspot.com/x", "why": "inspiration"})
    links = {l["url"]: l for l in db.search("")}
    assert links["https://www.mero.ro/judith"]["why"] == ["inspiration", "pricing page"]
    assert links["https://www.mero.ro/judith"]["source"] == "mero.ro"
    assert links["https://github.com/sethblack/python-seo-analyzer"]["source"] == "sethblack/python-seo-analyzer"
    assert links["https://github.com/sethblack/python-seo-analyzer"]["source_kind"] == "GitHub"
    assert db.why_counts()[0] == ("inspiration", 2)
    assert [l["url"] for l in db.search("", why="inspiration", source="hubspot.com")] == ["https://blog.hubspot.com/x"]
    assert len(db.search("pricing")) == 1                                  # why keywords are searchable
    assert db.search("", sort="source")[0]["source"] == "hubspot.com"      # alphabetical

    r = c.get("/library?why=inspiration")
    assert "why: inspiration" in r.text and "2 links" in r.text
    assert "sethblack/python-seo-analyzer" in r.text                       # sidebar lists sources
    r = c.get("/library?sort=source")
    assert 'class="group-head"' in r.text

    lid = links["https://www.mero.ro/judith"]["id"]
    c.post(f"/links/{lid}/edit", data={"why": "competitor, inspiration", "tags": "", "note": "long text"})
    assert db.get(lid)["why"] == ["competitor", "inspiration"] and db.get(lid)["note"] == "long text"


def test_with_filters_helper():
    from closedtabs.web import _with
    f = {"q": "", "tag": ["commdata"], "why": [], "source": "", "days": 0, "sort": "new"}
    assert _with(f, why=("+", "inspiration")) == "/library?tag=commdata&why=inspiration"
    assert _with(f, tag=("-", "commdata")) == "/library"
    assert _with(f, source="mero.ro", sort="old") == "/library?tag=commdata&source=mero.ro&sort=old"


def test_youtube_channel_via_oembed(monkeypatch):
    monkeypatch.setattr(enrich, "fetch", lambda url, **kw: (_ for _ in ()).throw(OSError("consent page")))
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        return httpx.Response(200, json={"author_name": "Neuro Channel", "title": "Eye tracking 101",
                                         "thumbnail_url": "https://i.ytimg.com/x.jpg"},
                              request=httpx.Request("GET", url))

    monkeypatch.setattr(enrich.httpx, "get", fake_get)
    i, _ = db.add("https://www.youtube.com/watch?v=abc123")
    assert db.get(i)["source"] == "YouTube"
    enrich.enrich(i)
    link = db.get(i)
    assert link["source"] == "Neuro Channel" and link["source_kind"] == "YouTube"
    assert link["title"] == "Eye tracking 101" and link["error"] == ""      # blocked page, still known
    assert calls[0].startswith("https://www.youtube.com/oembed?format=json&url=https%3A%2F%2F")


def test_migration_moves_note_to_why_and_fills_sources(tmp_path):
    import sqlite3
    old = sqlite3.connect(tmp_path / "closedtabs.db")
    old.executescript("""
      CREATE TABLE links (id INTEGER PRIMARY KEY, url TEXT NOT NULL UNIQUE, title TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '', image TEXT NOT NULL DEFAULT '', site TEXT NOT NULL DEFAULT '',
        content TEXT NOT NULL DEFAULT '', summary TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '[]',
        note TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending', error TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL, seo TEXT NOT NULL DEFAULT '{}', want_commdata INTEGER NOT NULL DEFAULT 0);
      CREATE VIRTUAL TABLE links_fts USING fts5(title, summary, description, tags, note, url, content, seo);
      INSERT INTO links(url,title,note,created_at) VALUES ('https://www.mero.ro/j','Salon','Project Delia, Pricing',1);
      INSERT INTO links(url,title,note,created_at) VALUES ('https://github.com/a/b','Repo','',2);""")
    old.commit(); old.close()
    db.reset_for_tests(tmp_path)
    a, b = db.get(1), db.get(2)
    assert a["why"] == ["project delia", "pricing"] and a["note"] == "" and a["source"] == "mero.ro"
    assert b["why"] == [] and (b["source"], b["source_kind"]) == ("a/b", "GitHub")
    assert [l["id"] for l in db.search("pricing")] == [1]


def test_notes_wikilinks_and_backlinks(monkeypatch):
    from fastapi.testclient import TestClient
    from closedtabs import notes, web

    monkeypatch.setattr(enrich, "fetch", lambda url, **kw: enrich.parse_page(PAGE, url))
    monkeypatch.setattr(enrich, "video_info", lambda url: {})
    c = TestClient(web.app)
    c.post("/add", data={"text": "https://www.mero.ro/judith"})
    salon = db.search("")[0]
    enrich.enrich(salon["id"])
    salon = db.get(salon["id"])

    # typing text without a web address into the main box makes a note
    r = c.post("/add", data={"text": "Idea: trust signals\nSalons win on reviews.", "why": "insight",
                             "labels": "project-delia"}, follow_redirects=False)
    assert "Saved+as+a+note" in r.headers["location"]
    idea = db.search("", kind="note")[0]
    assert idea["title"] == "Idea: trust signals" and idea["content"] == "Salons win on reviews."
    assert idea["why"] == ["insight"] and "project-delia" in idea["tags"] and idea["source"] == "My notes"

    # a longer note that links to the salon (by source name) and to the idea (by #id)
    r = c.post("/notes", data={"title": "Delia: competitor summary",
                               "text": f"Compared [[mero.ro]] with others.\n\nSee [[#{idea['id']}]] and [[Nothing Here]]. https://example.org/x",
                               "why": "synthesis", "labels": "project-delia"}, follow_redirects=False)
    summary_id = int(r.headers["location"].rsplit("/", 1)[1])
    html = notes.render(db.get(summary_id)["content"])
    assert f'href="/links/{salon["id"]}"' in html and f'href="/links/{idea["id"]}"' in html
    assert 'class="wikilink missing"' in html and 'href="https://example.org/x"' in html
    assert "<script" not in notes.render("<script>alert(1)</script>")          # escaped
    assert [b["id"] for b in db.backlinks(salon)] == [summary_id]
    assert [b["id"] for b in db.backlinks(idea)] == [summary_id]

    page = c.get(f"/links/{salon['id']}").text
    assert "Linked from" in page and "Delia: competitor summary" in page
    page = c.get(f"/links/{summary_id}").text
    assert "Links to" in page and "Edit note" in page

    # editing a note
    c.post(f"/links/{summary_id}/edit", data={"title": "Delia summary v2", "text": "New body",
                                               "why": "synthesis", "tags": "project-delia", "note": ""})
    assert db.get(summary_id)["title"] == "Delia summary v2" and db.get(summary_id)["content"] == "New body"

    # filters: notes vs links
    assert {l["kind"] for l in db.search("", kind="note")} == {"note"}
    assert c.get("/library?kind=note").text.count('class="card"') == 2
    assert all(s != "My notes" for s, _, _ in db.source_counts())          # notes aren't a "source"


def test_note_ai_labels(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(providers, "label", lambda url, page, chars, note="", known=None:
                        {"type": "article", "topics": ["trust-signals"], "summary": "S"})
    i = db.add_note("Short idea about trust", why=["insight"])
    enrich.enrich(i)
    n = db.get(i)
    assert n["status"] == "done" and n["tags"] == ["topic/trust-signals", "type/note"] and n["summary"] == ""
    assert i not in db.unlabeled_ids()


def test_compare_view(monkeypatch):
    from fastapi.testclient import TestClient
    from closedtabs import compare, seo, web

    a = seo.analyze(SITE, "https://a.example/")
    b = seo.analyze(SITE.replace("fbq('init', '123');", "").replace("Machiaj", "Tatuaj"), "https://b.example/")
    for url, data in (("https://a.example/", a), ("https://b.example/", b)):
        i, _ = db.add(url, why=[])
        db.update(i, seo=data, want_commdata=1, tags=["commdata", "project-delia"], status="done")
    i, _ = db.add("https://c.example/")
    db.update(i, want_commdata=1, tags=["commdata", "project-delia"], status="done")   # no data yet

    t = compare.build(db.search("", ["commdata", "project-delia"]))
    assert t["n"] == 2 and len(t["cols"]) == 2 and [l["url"] for l in t["missing"]] == ["https://c.example/"]
    assert ("Google Analytics 4", 2) in t["insights"]["shared_tools"]
    assert ("a.example", ["Meta Pixel"]) in t["insights"]["unique_tools"]
    assert any(k == "permanent" for k, _ in t["insights"]["shared_keywords"])
    labels = [r.get("label") for r in t["rows"]]
    assert "SEO checks passed" in labels and "Instagram" in labels and "Ad pixels" in labels

    page = TestClient(web.app).get("/compare?tag=project-delia").text
    assert "Compare: project-delia" in page and "Common tools" in page and "Only one site uses" in page
    lib = TestClient(web.app).get("/library?tag=commdata&tag=project-delia").text
    assert "/compare?tag=project-delia" in lib


def test_obsidian_two_way_sync(monkeypatch, tmp_path):
    from closedtabs import obsidian, seo

    vault = tmp_path / "vault"
    monkeypatch.setenv("OBSIDIAN_VAULT", str(vault))
    monkeypatch.setattr("closedtabs.enrich.worker.submit", lambda i: None)
    root = vault / "ClosedTabs"

    a, _ = db.add("https://www.mero.ro/judith", why=["competitor"])
    db.update(a, title="Judith: PMU / Oradea", summary="Salon page.", source="mero.ro",
              tags=["type/company", "topic/permanent-makeup", "project-delia", "commdata"],
              seo=seo.analyze(SITE, "https://www.mero.ro/judith"), want_commdata=1, status="done")
    b, _ = db.add("https://other.example/x")
    db.update(b, title="Judith: PMU / Oradea", status="done")                 # same title -> unique file name
    n = db.add_note(f"Compare [[mero.ro]] and [[#{a}]].", title="Delia ideas", why=["insight"], tags=["project-delia"])

    st = obsidian.sync()
    assert st["error"] == "" and st["written"] > 0
    fa = root / "Links" / "Judith- PMU - Oradea.md"
    fb = root / "Links" / f"Judith- PMU - Oradea ({b}).md"
    fn = root / "Notes" / "Delia ideas.md"
    assert fa.exists() and fb.exists() and fn.exists()
    props, above, below = obsidian._split(fa.read_text())
    assert props["closedtabs_id"] == a and props["why"] == ["competitor"] and props["projects"] == ["project-delia"]
    assert "why/competitor" in props["tags"] and "topic/permanent-makeup" in props["tags"]
    assert "Website data (CommData)" in above and "Meta Pixel" in above
    assert "[[project-delia]]" in above and "[[Sources - mero.ro|mero.ro]]" in above
    note_text = obsidian._split(fn.read_text())[2]
    assert "[[Sources - mero.ro|mero.ro]]" in note_text and "[[Judith- PMU - Oradea|#" in note_text
    assert (root / "Projects" / "project-delia.md").exists() and (root / "Why" / "Why - insight.md").exists()
    assert (root / "ClosedTabs.md").exists()
    # nothing changed -> nothing rewritten
    assert obsidian.sync()["written"] == 0

    # edit in Obsidian: text below the marker + properties
    t = fa.read_text().replace("why:\n- competitor", "why:\n- competitor\n- pricing")
    t = t.replace("projects:\n- project-delia", "projects:\n- project-delia\n- client-x")
    fa.write_text(t.rstrip("\n") + "\nGreat trust signals.\n")
    fn.write_text(fn.read_text().replace("Compare", "Compared"))
    st = obsidian.sync()
    assert st["pulled"] == 2
    assert db.get(a)["note"] == "Great trust signals." and db.get(a)["why"] == ["competitor", "pricing"]
    assert {"project-delia", "client-x", "commdata"} <= set(db.get(a)["tags"])
    assert db.get(n)["content"].startswith("Compared [[mero.ro]]")          # back to ClosedTabs-style links
    assert db.backlinks(db.get(a))[0]["id"] == n

    # edit in ClosedTabs -> file follows; nothing pulled back
    db.update(a, note="Updated in the app.")
    st = obsidian.sync()
    assert st["pulled"] == 0 and obsidian._split(fa.read_text())[2] == "Updated in the app."

    # a new note written in Obsidian is imported
    (root / "Notes" / "Workshop plan.md").write_text("---\nwhy: [workshop]\nprojects: [project-delia]\n---\nIntro to [[Delia ideas]].\n")
    st = obsidian.sync()
    assert st["imported"] == 1
    w = db.search("", kind="note", why="workshop")[0]
    assert w["title"] == "Workshop plan" and w["content"] == "Intro to [[Delia ideas]]." and "project-delia" in w["tags"]
    assert obsidian._split((root / "Notes" / "Workshop plan.md").read_text())[0]["closedtabs_id"] == w["id"]

    # rename + delete in ClosedTabs
    db.update(n, title="Delia positioning")
    db.delete(b)
    obsidian.sync()
    assert not fn.exists() and (root / "Notes" / "Delia positioning.md").exists() and not fb.exists()
    assert not (root / "Projects" / "client-y.md").exists()


def test_obsidian_off_by_default(monkeypatch):
    from closedtabs import obsidian
    monkeypatch.delenv("OBSIDIAN_VAULT", raising=False)
    assert not obsidian.enabled() and obsidian.sync()["enabled"] is False


def test_bookmarklet_popup_and_cross_site_guard(monkeypatch):
    from fastapi.testclient import TestClient
    from closedtabs import web

    monkeypatch.setattr(enrich.worker, "submit", lambda i: None)
    c = TestClient(web.app)
    r = c.get("/tools")
    assert "Save to ClosedTabs" in r.text and "javascript:" in r.text
    r = c.get("/save", params={"url": "https://www.mero.ro/j?utm_source=x", "title": "Judith", "sel": "Best PMU in town"})
    assert 'value="https://www.mero.ro/j"' in r.text and "Best PMU in town" in r.text and "Already" not in r.text

    r = c.post("/save", data={"url": "https://www.mero.ro/j", "title": "Judith", "why": "competitor",
                              "labels": "project-delia", "commdata": "1", "note": "Best PMU in town"},
               headers={"Origin": "http://localhost:3000"})
    assert "✓ Saved" in r.text and "window.close" in r.text
    link = db.search("")[0]
    assert link["why"] == ["competitor"] and "project-delia" in link["tags"] and link["want_commdata"] == 1
    assert link["note"] == "> Best PMU in town"

    # saving the same page again merges, doesn't duplicate
    assert "Already in your library" in c.get("/save", params={"url": "https://www.mero.ro/j"}).text
    c.post("/save", data={"url": "https://www.mero.ro/j", "why": "pricing", "note": "Best PMU in town"})
    link = db.get(link["id"])
    assert db.count() == 1 and link["why"] == ["competitor", "pricing"] and link["note"] == "> Best PMU in town"

    # another website can't post into the library
    r = c.post("/add", data={"text": "https://evil.example"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403 and db.count() == 1
    r = c.post(f"/links/{link['id']}/delete", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403 and db.count() == 1

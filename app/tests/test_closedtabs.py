"""Run: pip install -r requirements.txt pytest && python -m pytest -q tests"""
import json
import time
from types import SimpleNamespace

import pytest

from closedtabs import db, enrich, taxonomy, urls

PAGE = """<html><head><title>Fallback title</title>
<meta property="og:title" content="AdLab: A/B test landing pages">
<meta name="description" content="Freemium tool for testing landing pages.">
<meta property="og:image" content="/img/cover.png">
<script>var x = "ignore me";</script></head>
<body><nav>Menu</nav><h1>AdLab</h1><p>Run neuromarketing experiments on landing pages.</p></body></html>"""


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db.reset_for_tests(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
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


def test_to_tags_limits():
    tags = taxonomy.to_tags({"type": "tool", "topics": ["dev", "ai-tools", "analytics", "other"],
                             "uses": ["try-it", "try-it", "content-idea", "learn-later"], "summary": ""})
    assert tags == ["type/tool", "topic/dev", "topic/ai-tools", "topic/analytics", "use/try-it", "use/content-idea"]


def test_enrich_with_claude(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(enrich, "fetch", lambda url: enrich.parse_page(PAGE, url))
    sent = {}

    def fake_create(**kw):
        sent.update(kw)
        out = {"type": "tool", "topics": ["neuromarketing"], "uses": ["try-it"], "summary": "A test tool."}
        return SimpleNamespace(stop_reason="end_turn", content=[
            SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=json.dumps(out))])

    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=fake_create)))
    monkeypatch.setattr(enrich, "_client", fake)
    i, _ = db.add("https://adlab.io")
    enrich.enrich(i)
    link = db.get(i)
    assert link["status"] == "done" and link["summary"] == "A test tool."
    assert link["tags"] == ["topic/neuromarketing", "type/tool", "use/try-it"]
    assert sent["model"] == "claude-opus-5-5" and sent["fallbacks"] == "default"
    assert sent["output_config"]["format"]["schema"] == taxonomy.SCHEMA
    assert "<page>" in sent["messages"][0]["content"]


def test_enrich_without_key_and_unreachable_site(monkeypatch):
    def boom(url):
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

    monkeypatch.setattr(enrich, "_client",
                        SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=fake_create))))
    with pytest.raises(RuntimeError):
        enrich.label("https://x", {"title": "x"})
    assert "fallbacks" not in sent


def test_web_flow(monkeypatch):
    from fastapi.testclient import TestClient
    from closedtabs import web

    monkeypatch.setattr(enrich, "fetch", lambda url: enrich.parse_page(PAGE, url))
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

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
    monkeypatch.setattr(providers, "_client", fake)
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

    monkeypatch.setattr(providers, "_client",
                        SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=fake_create))))
    with pytest.raises(providers.LabelError):
        providers.label("https://x", {"title": "x"})
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


def _gemini_env(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    monkeypatch.setenv("LLM_API_KEY", "g-key")
    monkeypatch.setenv("LLM_MODEL", "some-gemini-model")


def _resp(status, payload=None, text=""):
    return httpx.Response(status, json=payload) if payload is not None else httpx.Response(status, text=text)


def test_other_provider_json_schema_and_cleanup(monkeypatch):
    _gemini_env(monkeypatch)
    sent = []
    answer = {"type": "Tool", "topics": ["Neuromarketing", "made-up"], "uses": ["try-it"], "summary": "Gem."}

    def fake_post(payload):
        sent.append(payload)
        return _resp(200, {"choices": [{"message": {"content": "```json\n" + json.dumps(answer) + "\n```"}}]})

    monkeypatch.setattr(providers, "_post_chat", fake_post)
    assert providers.provider() == "other"
    out = providers.label("https://x", {"title": "x"})
    assert out == {"type": "tool", "topics": ["neuromarketing"], "uses": ["try-it"], "summary": "Gem."}
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
    assert out["type"] == "video" and out["topics"] == ["other"]


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
    monkeypatch.setattr(enrich, "fetch", lambda url: enrich.parse_page(PAGE, url))
    seen = {}

    def fake_label(url, page, ai_chars, note=""):
        seen["note"] = note
        return {"type": "company", "topics": ["other"], "uses": [], "summary": "A salon."}

    monkeypatch.setattr(providers, "label", fake_label)
    i, _ = db.add("https://salon.example", note="Project Delia")
    db.update(i, tags=["type/tool", "topic/neuromarketing", "project-delia"], status="done")
    enrich.enrich(i)
    assert db.get(i)["tags"] == ["project-delia", "topic/other", "type/company"]
    assert seen["note"] == "Project Delia"


def test_normalize_drops_other_when_real_topic_present():
    out = taxonomy.normalize({"type": "company", "topics": ["other", "branding", "branding"], "uses": []})
    assert out["topics"] == ["branding"]


def test_note_reaches_prompt(monkeypatch):
    _gemini_env(monkeypatch)
    sent = []
    monkeypatch.setattr(providers, "_post_chat", lambda p: sent.append(p) or _resp(
        200, {"choices": [{"message": {"content": '{"type":"company","topics":["other"],"uses":[],"summary":"s"}'}}]}))
    providers.label("https://x", {"title": "x"}, note="Project Delia")
    assert "Project Delia" in sent[0]["messages"][1]["content"]

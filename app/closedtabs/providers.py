"""Which AI writes the labels: Claude (Anthropic SDK) or any OpenAI-compatible provider.

Settings (deploy/.env):
  ANTHROPIC_API_KEY, CLAUDE_MODEL            -> Claude
  LLM_BASE_URL, LLM_API_KEY, LLM_MODEL       -> any OpenAI-compatible API
                                                (Gemini, OpenAI, Mistral, Groq, OpenRouter, Ollama…)
  AI_PROVIDER = claude | other               -> pick one when both are filled in (default: claude)
"""
from __future__ import annotations

import json
import os
import re

import anthropic
import httpx

from . import taxonomy

# Claude models that accept the server-side refusal fallback (Haiku does not).
_FALLBACK_PREFIXES = ("claude-opus-5", "claude-fable-5", "claude-sonnet-5-5")


class LabelError(RuntimeError):
    """A labelling failure with a message fit to show the user."""


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


# ── configuration ────────────────────────────────────────────────────
def claude_key() -> str:
    key = _env("ANTHROPIC_API_KEY")
    if not key:  # accept a key left over from the earlier setup's variable name
        legacy = _env("OPENAI_API_KEY")
        key = legacy if legacy.startswith("sk-ant-") else ""
    return key


def claude_model() -> str:
    return _env("CLAUDE_MODEL") or "claude-opus-5-5"


def other_configured() -> bool:
    # A key is optional: local servers such as Ollama need only the address.
    return bool(_env("LLM_BASE_URL") and _env("LLM_MODEL"))


def provider() -> str | None:
    """'claude', 'other' or None (AI off)."""
    choice = _env("AI_PROVIDER").lower()
    if choice in ("other", "openai", "gemini", "llm") and other_configured():
        return "other"
    if claude_key():
        return "claude"
    if other_configured():
        return "other"
    return None


def describe() -> dict:
    p = provider()
    if p == "claude":
        return {"provider": "claude", "model": claude_model()}
    if p == "other":
        return {"provider": "other", "model": _env("LLM_MODEL"), "base_url": _env("LLM_BASE_URL")}
    return {"provider": None, "model": None}


# ── Claude ───────────────────────────────────────────────────────────
_client: anthropic.Anthropic | None = None


def _claude() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=claude_key(), max_retries=3)
    return _client


def _label_claude(body: str) -> dict:
    kwargs = {}
    m = claude_model()
    if m.startswith(_FALLBACK_PREFIXES):
        kwargs = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    try:
        resp = _claude().beta.messages.create(
            model=m,
            max_tokens=4000,
            system=taxonomy.SYSTEM_PROMPT,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": taxonomy.SCHEMA}},
            messages=[{"role": "user", "content": body}],
            **kwargs,
        )
    except anthropic.AuthenticationError:
        raise LabelError("Claude API key was rejected. Check ANTHROPIC_API_KEY.")
    except anthropic.NotFoundError:
        raise LabelError(f"Claude model '{m}' wasn't found. Check CLAUDE_MODEL.")
    except anthropic.APIConnectionError:
        raise LabelError("Couldn't reach Claude. Check the internet connection.")
    except anthropic.APIStatusError as e:
        raise LabelError(f"Claude API error {e.status_code}: {e.message}"[:300])
    if resp.stop_reason == "refusal":
        raise LabelError("Claude declined to label this page.")
    if resp.stop_reason == "max_tokens":
        raise LabelError("Claude's answer was cut off.")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return _parse_json(text)


# ── any OpenAI-compatible API ────────────────────────────────────────
def _post_chat(payload: dict) -> httpx.Response:
    base = _env("LLM_BASE_URL").rstrip("/")
    headers = {"Content-Type": "application/json"}
    if _env("LLM_API_KEY"):
        headers["Authorization"] = f"Bearer {_env('LLM_API_KEY')}"
    return httpx.post(f"{base}/chat/completions", json=payload, headers=headers, timeout=120)


def _label_other(body: str) -> dict:
    messages = [{"role": "system", "content": taxonomy.SYSTEM_PROMPT + "\n\n" + taxonomy.JSON_INSTRUCTIONS},
                {"role": "user", "content": body}]
    base_payload = {"model": _env("LLM_MODEL"), "messages": messages}
    attempts = [
        {"response_format": {"type": "json_schema",
                             "json_schema": {"name": "labels", "schema": taxonomy.SCHEMA, "strict": True}}},
        {"response_format": {"type": "json_object"}},
        {},  # providers without JSON mode: rely on the instructions
    ]
    last = ""
    for extra in attempts:
        try:
            r = _post_chat({**base_payload, **extra})
        except httpx.HTTPError as e:
            raise LabelError(f"Couldn't reach {_env('LLM_BASE_URL')} ({type(e).__name__}).")
        if r.status_code in (401, 403):
            raise LabelError("The AI provider rejected the key. Check LLM_API_KEY.")
        if r.status_code == 404:
            raise LabelError(f"Model '{_env('LLM_MODEL')}' or address not found. Check LLM_MODEL and LLM_BASE_URL.")
        if r.status_code == 429:
            raise LabelError("The AI provider says: too many requests / quota reached. Try again later.")
        if r.status_code == 400:  # usually: this JSON mode isn't supported, try the next one
            last = r.text[:200]
            continue
        if r.status_code >= 300:
            raise LabelError(f"AI provider error {r.status_code}: {r.text[:200]}")
        try:
            text = r.json()["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError):
            raise LabelError("The AI provider sent an answer ClosedTabs couldn't read.")
        return _parse_json(text)
    raise LabelError(f"The AI provider refused the request: {last}")


# ── shared ───────────────────────────────────────────────────────────
def _parse_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    if not text.startswith("{") and "{" in text:
        text = text[text.index("{"): text.rindex("}") + 1]
    try:
        data = json.loads(text)
    except ValueError:
        raise LabelError("The AI's answer wasn't valid JSON.")
    if not isinstance(data, dict):
        raise LabelError("The AI's answer had the wrong shape.")
    return taxonomy.normalize(data)


def label(url: str, page: dict, ai_chars: int = 15_000) -> dict:
    """Return {type, topics, uses, summary} using whichever provider is configured."""
    body = (
        f"<page>\nURL: {url}\nTitle: {page.get('title', '')}\n"
        f"Description: {page.get('description', '')}\n\n{(page.get('content') or '')[:ai_chars]}\n</page>"
    )
    p = provider()
    if p == "claude":
        return _label_claude(body)
    if p == "other":
        return _label_other(body)
    raise LabelError("AI is off: no API key configured.")

"""Weekly review: what came in, what still needs sorting, and older items worth seeing again."""
from __future__ import annotations

import random
import time
from collections import Counter

from . import db, taxonomy

DAY = 86400


def own_labels(item: dict) -> list[str]:
    return [t for t in item["tags"] if "/" not in t and t != taxonomy.COMMDATA]


def unsorted(limit: int = 40) -> list[dict]:
    """Active items without a why-keyword and without a project/own label (briefs excluded)."""
    out = []
    for it in db.search("", limit=5000):
        if not it["why"] and not own_labels(it):
            out.append(it)
            if len(out) >= limit:
                break
    return out


def this_week(days: int = 7) -> dict:
    items = db.search("", since_days=days, limit=5000)
    topics = Counter(t.split("/", 1)[1] for i in items for t in i["tags"] if t.startswith("topic/"))
    return {
        "count": len(items),
        "links": sum(1 for i in items if i["kind"] == "link"),
        "notes": sum(1 for i in items if i["kind"] == "note"),
        "why": Counter(w for i in items for w in i["why"]).most_common(8),
        "topics": topics.most_common(10),
        "sources": Counter(i["source"] for i in items if i["kind"] == "link" and i["source"]).most_common(6),
        "projects": Counter(p for i in items for p in own_labels(i)).most_common(6),
    }


def rediscover(n: int = 5, now: float | None = None) -> list[dict]:
    """Older items (30+ days) that share topics or projects with what you worked on in the last 30 days.
    The pick changes once a week, and isn't random every reload."""
    now = now or time.time()
    recent = db.search("", since_days=30, limit=5000)
    focus = Counter()
    for it in recent:
        focus.update(t for t in it["tags"] if t.startswith("topic/"))
        focus.update(own_labels(it))
    older = [it for it in db.search("", limit=20000, sort="old") if it["created_at"] < now - 30 * DAY]
    if not older:
        return []
    week = time.strftime("%G-%V", time.localtime(now))
    rnd = random.Random(week)
    scored = []
    for it in older:
        keys = [t for t in it["tags"] if t.startswith("topic/")] + own_labels(it)
        score = sum(focus.get(k, 0) for k in keys)
        scored.append((score, rnd.random(), it))
    scored.sort(key=lambda x: (-x[0], x[1]))
    picks = [it for score, _, it in scored if score > 0][:n]
    if len(picks) < n:  # fill up with a few random older ones
        rest = [it for _, _, it in scored if it not in picks]
        rnd.shuffle(rest)
        picks += rest[: n - len(picks)]
    for it in picks:
        keys = [t for t in it["tags"] if t.startswith("topic/")] + own_labels(it)
        it["because"] = [k.split("/", 1)[-1] for k in keys if focus.get(k)][:3]
    return picks

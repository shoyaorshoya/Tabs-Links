"""SQLite storage with full-text search. One file: $DATA_DIR/closedtabs.db"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
from collections import Counter
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
_lock = threading.RLock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS links (
  id          INTEGER PRIMARY KEY,
  url         TEXT NOT NULL UNIQUE,
  title       TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  image       TEXT NOT NULL DEFAULT '',
  site        TEXT NOT NULL DEFAULT '',
  content     TEXT NOT NULL DEFAULT '',
  summary     TEXT NOT NULL DEFAULT '',
  tags        TEXT NOT NULL DEFAULT '[]',
  note        TEXT NOT NULL DEFAULT '',
  status      TEXT NOT NULL DEFAULT 'pending',  -- pending | done | error
  error       TEXT NOT NULL DEFAULT '',
  created_at  REAL NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS links_fts USING fts5(
  title, summary, description, tags, note, url, content, tokenize='unicode61'
);
"""

FIELDS = ("title", "description", "image", "site", "content", "summary", "tags", "note", "status", "error")


def conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(DATA_DIR / "closedtabs.db", check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.executescript(SCHEMA)
        return _conn


def reset_for_tests(path: Path) -> None:
    global _conn, DATA_DIR
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn, DATA_DIR = None, path


def _row(r: sqlite3.Row | None) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    d["tags"] = json.loads(d["tags"])
    return d


def _reindex(c: sqlite3.Connection, link_id: int) -> None:
    r = c.execute("SELECT * FROM links WHERE id=?", (link_id,)).fetchone()
    c.execute("DELETE FROM links_fts WHERE rowid=?", (link_id,))
    if r:
        tags = " ".join(json.loads(r["tags"])).replace("/", " ")
        c.execute(
            "INSERT INTO links_fts(rowid,title,summary,description,tags,note,url,content)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (link_id, r["title"], r["summary"], r["description"], tags, r["note"], r["url"], r["content"]),
        )


def add(url: str, title: str = "", note: str = "") -> tuple[int, bool]:
    """Insert a link. Returns (id, created). Existing URL -> (existing id, False)."""
    with _lock:
        c = conn()
        r = c.execute("SELECT id FROM links WHERE url=?", (url,)).fetchone()
        if r:
            return r["id"], False
        cur = c.execute(
            "INSERT INTO links(url,title,note,created_at) VALUES (?,?,?,?)",
            (url, title, note, time.time()),
        )
        _reindex(c, cur.lastrowid)
        c.commit()
        return cur.lastrowid, True


def update(link_id: int, **fields) -> None:
    fields = {k: v for k, v in fields.items() if k in FIELDS}
    if "tags" in fields and not isinstance(fields["tags"], str):
        fields["tags"] = json.dumps(list(fields["tags"]))
    if not fields:
        return
    with _lock:
        c = conn()
        c.execute(
            f"UPDATE links SET {', '.join(f'{k}=?' for k in fields)} WHERE id=?",
            (*fields.values(), link_id),
        )
        _reindex(c, link_id)
        c.commit()


def get(link_id: int) -> dict | None:
    with _lock:
        return _row(conn().execute("SELECT * FROM links WHERE id=?", (link_id,)).fetchone())


def delete(link_id: int) -> None:
    with _lock:
        c = conn()
        c.execute("DELETE FROM links WHERE id=?", (link_id,))
        c.execute("DELETE FROM links_fts WHERE rowid=?", (link_id,))
        c.commit()


def pending_ids() -> list[int]:
    with _lock:
        return [r["id"] for r in conn().execute("SELECT id FROM links WHERE status='pending' ORDER BY id")]


def unlabeled_ids() -> list[int]:
    """Finished links with no AI 'type/' label yet (e.g. saved before the API key was added)."""
    with _lock:
        return [r["id"] for r in conn().execute(
            "SELECT id FROM links WHERE status != 'pending' AND tags NOT LIKE '%\"type/%' ORDER BY id")]


def _fts_query(q: str) -> str:
    words = re.findall(r"\w+", q, flags=re.UNICODE)
    return " ".join(f'"{w}"*' for w in words)


def search(q: str = "", tag: str = "", limit: int = 200, offset: int = 0) -> list[dict]:
    """Newest first; with q, best match first. tag filters by exact label (e.g. 'type/tool')."""
    sql, args = "SELECT l.* FROM links l", []
    where = []
    fq = _fts_query(q) if q else ""
    if fq:
        sql += " JOIN links_fts f ON f.rowid = l.id"
        where.append("links_fts MATCH ?")
        args.append(fq)
    if tag:
        where.append("l.tags LIKE ?")
        args.append(f'%"{tag}"%')
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY " + ("bm25(links_fts)" if fq else "l.created_at DESC")
    sql += " LIMIT ? OFFSET ?"
    args += [limit, offset]
    with _lock:
        return [_row(r) for r in conn().execute(sql, args)]


def tag_counts() -> list[tuple[str, int]]:
    with _lock:
        c = Counter()
        for r in conn().execute("SELECT tags FROM links"):
            c.update(json.loads(r["tags"]))
        order = {"type": 0, "topic": 1, "use": 2}
        return sorted(c.items(), key=lambda kv: (order.get(kv[0].split("/")[0], 3), -kv[1], kv[0]))


def count() -> int:
    with _lock:
        return conn().execute("SELECT COUNT(*) FROM links").fetchone()[0]


def export_all() -> list[dict]:
    with _lock:
        return [_row(r) for r in conn().execute("SELECT * FROM links ORDER BY created_at")]

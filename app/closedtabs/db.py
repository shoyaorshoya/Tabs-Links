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
  created_at  REAL NOT NULL,
  seo         TEXT NOT NULL DEFAULT '{}',     -- website data (see seo.py), JSON
  want_commdata INTEGER NOT NULL DEFAULT 0,   -- 1 = collect website data for this link
  why         TEXT NOT NULL DEFAULT '[]',     -- "why am I saving this" keywords, JSON list
  source      TEXT NOT NULL DEFAULT '',       -- readable source: mero.ro, user/repo, channel…
  source_kind TEXT NOT NULL DEFAULT '',       -- website | GitHub | YouTube | LinkedIn | …
  kind        TEXT NOT NULL DEFAULT 'link',   -- link | note (a note has no web address; url = note:<id>)
  archived    INTEGER NOT NULL DEFAULT 0      -- 1 = archived: hidden from lists, still searchable by Claude
);
"""

FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS links_fts USING fts5(
  title, summary, description, tags, note, url, content, seo, why, source, tokenize='unicode61'
);
"""

FIELDS = ("title", "description", "image", "site", "content", "summary", "tags", "note", "status", "error", "seo", "want_commdata",
          "why", "source", "source_kind", "kind", "archived")
FTS_COLUMNS = {"seo", "why", "source"}


def _migrate(c: sqlite3.Connection) -> None:
    """Bring databases from older versions up to date (safe to run every start)."""
    cols = {r[1] for r in c.execute("PRAGMA table_info(links)")}
    if "seo" not in cols:
        c.execute("ALTER TABLE links ADD COLUMN seo TEXT NOT NULL DEFAULT '{}'")
    if "want_commdata" not in cols:
        c.execute("ALTER TABLE links ADD COLUMN want_commdata INTEGER NOT NULL DEFAULT 0")
        # links that already have website data (from the version before the checkbox) keep it
        for r in c.execute("SELECT id, tags FROM links WHERE seo NOT IN ('', '{}')").fetchall():
            tags = sorted(set(json.loads(r[1])) | {"commdata"})
            c.execute("UPDATE links SET want_commdata=1, tags=? WHERE id=?", (json.dumps(tags), r[0]))
    if "why" not in cols:
        from .taxonomy import why_keywords
        from .sources import from_url

        c.execute("ALTER TABLE links ADD COLUMN why TEXT NOT NULL DEFAULT '[]'")
        c.execute("ALTER TABLE links ADD COLUMN source TEXT NOT NULL DEFAULT ''")
        c.execute("ALTER TABLE links ADD COLUMN source_kind TEXT NOT NULL DEFAULT ''")
        # the old "Why am I saving this?" text becomes keywords; sources come from the URLs
        for r in c.execute("SELECT id, url, note FROM links").fetchall():
            name, kind = from_url(r[1])
            c.execute("UPDATE links SET why=?, note='', source=?, source_kind=? WHERE id=?",
                      (json.dumps(why_keywords(r[2]), ensure_ascii=False), name, kind, r[0]))
    if "kind" not in cols:
        c.execute("ALTER TABLE links ADD COLUMN kind TEXT NOT NULL DEFAULT 'link'")
    if "archived" not in cols:
        c.execute("ALTER TABLE links ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")
    fts_cols = {r[1] for r in c.execute("PRAGMA table_info(links_fts)")}
    stale = bool(fts_cols) and not FTS_COLUMNS <= fts_cols
    if stale:
        c.execute("DROP TABLE links_fts")
    c.executescript(FTS_SCHEMA)
    if not fts_cols or stale:
        for (link_id,) in c.execute("SELECT id FROM links").fetchall():
            _reindex(c, link_id)
    c.commit()


def conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(DATA_DIR / "closedtabs.db", check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.executescript(SCHEMA)
            _migrate(_conn)
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
    d["seo"] = json.loads(d.get("seo") or "{}")
    d["why"] = json.loads(d.get("why") or "[]")
    return d


def _reindex(c: sqlite3.Connection, link_id: int) -> None:
    r = c.execute("SELECT * FROM links WHERE id=?", (link_id,)).fetchone()
    c.execute("DELETE FROM links_fts WHERE rowid=?", (link_id,))
    if r:
        from .seo import search_text  # local import keeps db.py free of parsing code at import time

        tags = " ".join(json.loads(r["tags"])).replace("/", " ").replace("-", " ")
        seo_words = search_text(json.loads(r["seo"] or "{}"))
        why = " ".join(json.loads(r["why"] or "[]"))
        c.execute(
            "INSERT INTO links_fts(rowid,title,summary,description,tags,note,url,content,seo,why,source)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (link_id, r["title"], r["summary"], r["description"], tags, r["note"], r["url"], r["content"],
             seo_words, why, f"{r['source']} {r['source_kind']}"),
        )


def add(url: str, title: str = "", note: str = "", why: list[str] | None = None) -> tuple[int, bool]:
    """Insert a link. Returns (id, created). Existing URL -> (existing id, False)."""
    from .sources import from_url

    with _lock:
        c = conn()
        r = c.execute("SELECT id FROM links WHERE url=?", (url,)).fetchone()
        if r:
            return r["id"], False
        name, kind = from_url(url)
        cur = c.execute(
            "INSERT INTO links(url,title,note,why,source,source_kind,created_at) VALUES (?,?,?,?,?,?,?)",
            (url, title, note, json.dumps(why or [], ensure_ascii=False), name, kind, time.time()),
        )
        _reindex(c, cur.lastrowid)
        c.commit()
        return cur.lastrowid, True


NOTE_SOURCE = ("My notes", "note")


def add_note(text: str, title: str = "", why: list[str] | None = None, tags: list[str] | None = None) -> int:
    """A note without a web address. Title = given title, or the first line of the text."""
    import uuid

    text = (text or "").strip()
    first, _, rest = text.partition("\n")
    if not title:
        title, body = first.strip()[:200], (rest.strip() if len(first) <= 200 else text)
    else:
        body = text
    with _lock:
        c = conn()
        cur = c.execute(
            "INSERT INTO links(url,title,content,why,tags,source,source_kind,kind,created_at) "
            "VALUES (?,?,?,?,?,?,?,'note',?)",
            (f"note:{uuid.uuid4().hex[:12]}", title or "Untitled note", body,
             json.dumps(why or [], ensure_ascii=False), json.dumps(sorted(set(tags or []))),
             *NOTE_SOURCE, time.time()),
        )
        _reindex(c, cur.lastrowid)
        c.commit()
        return cur.lastrowid


def resolve_ref(ref: str) -> dict | None:
    """Find the item a [[reference]] points to: '#12', an exact title, or a source name."""
    ref = ref.split("|", 1)[0].strip()  # Obsidian style [[File name|shown text]]
    m = re.fullmatch(r".* \((\d+)\)", ref)       # file names made unique as "Title (12)"
    with _lock:
        c = conn()
        if m and (r := c.execute("SELECT * FROM links WHERE id=?", (int(m.group(1)),)).fetchone()):
            return _row(r)
        if re.fullmatch(r"#\d+", ref):
            return _row(c.execute("SELECT * FROM links WHERE id=?", (int(ref[1:]),)).fetchone())
        r = c.execute("SELECT * FROM links WHERE LOWER(title)=LOWER(?) ORDER BY kind='note' DESC, id LIMIT 1",
                      (ref,)).fetchone()
        if r is None:
            r = c.execute("SELECT * FROM links WHERE LOWER(source)=LOWER(?) AND kind='link' ORDER BY id LIMIT 1",
                          (ref,)).fetchone()
        return _row(r)


def backlinks(link: dict) -> list[dict]:
    """Items whose text or note mentions this one as [[Title]] or [[#id]]."""
    keys = {f"[[#{link['id']}]]", f"[[{link['title'].lower()}]]"}
    if link.get("kind") == "link" and link.get("source"):
        keys.add(f"[[{link['source'].lower()}]]")
    where = " OR ".join(["LOWER(content) LIKE ? OR LOWER(note) LIKE ?"] * len(keys))
    args = [a for k in keys for a in (f"%{k}%", f"%{k}%")]
    with _lock:
        rows = conn().execute(f"SELECT * FROM links WHERE id != ? AND ({where}) ORDER BY created_at DESC",
                              (link["id"], *args)).fetchall()
        return [_row(r) for r in rows]


def update(link_id: int, **fields) -> None:
    fields = {k: v for k, v in fields.items() if k in FIELDS}
    if "tags" in fields and not isinstance(fields["tags"], str):
        fields["tags"] = json.dumps(list(fields["tags"]))
    for k in ("seo", "why"):
        if k in fields and not isinstance(fields[k], str):
            fields[k] = json.dumps(fields[k], ensure_ascii=False)
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


SORTS = {"new": "l.created_at DESC", "old": "l.created_at ASC", "source": "l.source COLLATE NOCASE, l.created_at DESC"}


def search(q: str = "", tag: str | list[str] = "", limit: int = 200, offset: int = 0,
           why: str | list[str] = "", source: str = "", since_days: int | None = None,
           sort: str = "new", kind: str = "", archived: bool | None = False) -> list[dict]:
    """Filter by words (q), labels (tag), why-keywords, source and age. All filters combine (AND).
    Sorted newest first by default; with q and sort='new', best match first."""
    sql, args = "SELECT l.* FROM links l", []
    where = []
    fq = _fts_query(q) if q else ""
    if fq:
        sql += " JOIN links_fts f ON f.rowid = l.id"
        where.append("links_fts MATCH ?")
        args.append(fq)
    for t in ([tag] if isinstance(tag, str) else tag):
        if t:
            where.append("l.tags LIKE ?")
            args.append(f'%"{t}"%')
    for w in ([why] if isinstance(why, str) else why):
        if w:
            where.append("l.why LIKE ?")
            args.append("%" + json.dumps(w, ensure_ascii=False) + "%")
    if source:
        where.append("l.source = ?")
        args.append(source)
    if kind:
        where.append("l.kind = ?")
        args.append(kind)
    if archived is not None:  # False: active items only (default) · True: archive only · None: everything
        where.append("l.archived = ?")
        args.append(1 if archived else 0)
    if since_days:
        where.append("l.created_at >= ?")
        args.append(time.time() - since_days * 86400)
    if where:
        sql += " WHERE " + " AND ".join(where)
    order = SORTS.get(sort, SORTS["new"])
    sql += " ORDER BY " + ("bm25(links_fts)" if fq and sort == "new" else order)
    sql += " LIMIT ? OFFSET ?"
    args += [limit, offset]
    with _lock:
        return [_row(r) for r in conn().execute(sql, args)]


def tag_counts() -> list[tuple[str, int]]:
    with _lock:
        c = Counter()
        for r in conn().execute("SELECT tags FROM links WHERE archived = 0"):
            c.update(json.loads(r["tags"]))
        def group(t):
            return {"type": 0, "topic": 1}.get(t.split("/")[0], 3) if "/" in t else 2
        return sorted(c.items(), key=lambda kv: (group(kv[0]), -kv[1], kv[0]))


def why_counts() -> list[tuple[str, int]]:
    with _lock:
        c = Counter()
        for r in conn().execute("SELECT why FROM links WHERE archived = 0"):
            c.update(json.loads(r["why"] or "[]"))
        return sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))


def source_counts() -> list[tuple[str, str, int]]:
    """(source, kind, count), most links first."""
    with _lock:
        rows = conn().execute(
            "SELECT source, MAX(source_kind) AS kind, COUNT(*) AS n FROM links WHERE source != '' AND kind = 'link' AND archived = 0 "
            "GROUP BY source ORDER BY n DESC, source COLLATE NOCASE").fetchall()
        return [(r["source"], r["kind"], r["n"]) for r in rows]


def count_kind(kind: str) -> int:
    with _lock:
        return conn().execute("SELECT COUNT(*) FROM links WHERE kind=? AND archived = 0", (kind,)).fetchone()[0]


def count_archived() -> int:
    with _lock:
        return conn().execute("SELECT COUNT(*) FROM links WHERE archived = 1").fetchone()[0]


def count_since(days: int) -> int:
    with _lock:
        return conn().execute("SELECT COUNT(*) FROM links WHERE archived = 0 AND created_at >= ?",
                              (time.time() - days * 86400,)).fetchone()[0]


def topic_labels(limit: int = 150) -> list[str]:
    """Most-used AI topic labels (without the 'topic/' prefix), for reuse by the AI."""
    return [t.split("/", 1)[1] for t, _ in sorted(
        ((t, n) for t, n in tag_counts() if t.startswith("topic/")), key=lambda kv: -kv[1])[:limit]]


def commdata_projects() -> list[tuple[str, int]]:
    """Own labels (projects) used on CommData links, with counts."""
    c = Counter()
    for l in search("", tag="commdata", limit=100_000):
        c.update(t for t in l["tags"] if "/" not in t and t != "commdata")
    return sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))


def mark_all_pending() -> list[int]:
    with _lock:
        c = conn()
        ids = [r["id"] for r in c.execute("SELECT id FROM links ORDER BY id")]
        c.execute("UPDATE links SET status='pending', error=''")
        c.commit()
        return ids


def count() -> int:
    with _lock:
        return conn().execute("SELECT COUNT(*) FROM links WHERE archived = 0").fetchone()[0]


def count_all() -> int:
    with _lock:
        return conn().execute("SELECT COUNT(*) FROM links").fetchone()[0]


def export_all() -> list[dict]:
    with _lock:
        return [_row(r) for r in conn().execute("SELECT * FROM links ORDER BY created_at")]

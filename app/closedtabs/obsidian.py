"""Two-way sync between ClosedTabs and an Obsidian vault (plain Markdown files).

Layout inside <vault>/<folder> (default folder: "ClosedTabs"):
  ClosedTabs.md            home page (generated)
  Links/<title>.md         one file per saved link
  Notes/<title>.md         one file per note
  Projects/, Why/, Sources/   index pages (generated)

Each item file = YAML properties + a generated part + YOUR TEXT below the marker line.
Synced both ways: the text below the marker (link note / note body) and the 'why' and 'projects'
properties. Last-synced fingerprints are kept in the 'cts_sync' property, so we can tell which side
changed (three-way merge, like the obsidian-hoarder plugin). If both changed, Obsidian wins.
New .md files you create in Notes/ become ClosedTabs notes.
Approach adapted from https://github.com/jhofker/obsidian-hoarder (frontmatter + preserved notes section).
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import time
from pathlib import Path

import yaml

from . import db, notes, taxonomy

log = logging.getLogger("closedtabs")

MARKER = "%% ↓ Your text below is synced with ClosedTabs. Everything above is regenerated. ↓ %%"
BAD = re.compile(r'[\\/:*?"<>|#^\[\]]+')

status = {"enabled": False, "last_sync": None, "error": "", "written": 0, "pulled": 0, "imported": 0,
          "folder": ""}
_lock = threading.Lock()


def vault_dir() -> Path | None:
    v = os.environ.get("OBSIDIAN_VAULT", "").strip()
    if not v:
        return None
    return Path(os.path.expanduser(v)) / (os.environ.get("OBSIDIAN_FOLDER", "").strip() or "ClosedTabs")


def enabled() -> bool:
    return vault_dir() is not None


def safe_name(text: str, limit: int = 90) -> str:
    s = BAD.sub("-", (text or "").strip())
    s = re.sub(r"\s+", " ", s).strip(" .-")
    return s[:limit].rstrip(" .-") or "Untitled"


def _h(value) -> str:
    if isinstance(value, list):
        value = "\n".join(value)
    return hashlib.sha1((value or "").strip().encode("utf-8")).hexdigest()[:10]


def _split(text: str) -> tuple[dict, str, str | None]:
    """file text -> (properties, body above marker, your text below marker or None)."""
    props, body = {}, text
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if m:
        try:
            props = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            props = {}
        body = m.group(2)
    if MARKER in body:
        above, below = body.split(MARKER, 1)
        return props, above, below.strip("\n")
    return props, body, None


def _as_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        v = [v]
    return [str(x).strip() for x in v if str(x).strip()]


def _props_text(props: dict) -> str:
    return yaml.safe_dump(props, allow_unicode=True, sort_keys=False, default_flow_style=False, width=1000).strip()


class Names:
    """File names for items and index pages, unique and stable within one sync."""

    def __init__(self, items: list[dict]):
        self.item: dict[int, str] = {}
        seen: dict[str, int] = {}
        for it in sorted(items, key=lambda x: x["id"]):
            base = safe_name(it["title"] or it["source"] or it["url"])
            key = base.lower()
            name = base if key not in seen else f"{base} ({it['id']})"
            seen[name.lower()] = it["id"]
            self.item[it["id"]] = name

    @staticmethod
    def folder(it: dict) -> str:
        return "Notes" if it["kind"] == "note" else "Links"

    def link(self, it: dict, label: str | None = None) -> str:
        name = self.item[it["id"]]
        shown = label if label is not None else it["title"]
        return f"[[{name}]]" if not shown or shown == name else f"[[{name}|{shown}]]"

    @staticmethod
    def index(kind: str, value: str) -> str:
        return f"{kind} - {safe_name(value, 70)}" if kind != "Projects" else safe_name(value, 70)

    def index_link(self, kind: str, value: str) -> str:
        name = self.index(kind, value)
        return f"[[{name}]]" if name == value else f"[[{name}|{value}]]"


def _to_obsidian_links(text: str, names: Names) -> str:
    """ClosedTabs [[ref]] -> Obsidian [[File name|ref]] where the file name differs."""
    def repl(m):
        ref = m.group(1).strip()
        target = ref.split("|", 1)[0]
        item = db.resolve_ref(target)
        if not item or item["id"] not in names.item:
            return m.group(0)
        if item["kind"] == "link" and target.lower() == (item["source"] or "").lower() \
                and target.lower() != (item["title"] or "").lower():
            return names.index_link("Sources", item["source"])
        shown = ref.split("|", 1)[1] if "|" in ref else ref
        return names.link(item, shown)
    return notes.REF.sub(repl, text or "")


def _compact_commdata(s: dict) -> list[str]:
    if not s:
        return []
    checks = s.get("checks") or []
    ok = sum(1 for c in checks if c.get("level") == "ok")
    lines = ["## Website data (CommData)", f"- **SEO checks:** {ok}/{len(checks)} passed"]
    issues = [c["text"] for c in checks if c.get("level") == "warn"]
    if issues:
        lines.append("- **Issues:** " + "; ".join(issues))
    if s.get("tech"):
        lines.append("- **Stack:** " + ", ".join(t["name"] for t in s["tech"]))
    if s.get("socials"):
        lines.append("- **Socials:** " + " · ".join(f"[{n}]({u})" for n, u in s["socials"].items()))
    kw = s.get("keywords") or {}
    if kw.get("words"):
        lines.append("- **Top keywords:** " + ", ".join(w for w, _ in kw["words"][:10]))
    if kw.get("phrases"):
        lines.append("- **Top phrases:** " + ", ".join(w for w, _ in kw["phrases"][:6]))
    if s.get("schema_types"):
        lines.append("- **Structured data:** " + ", ".join(s["schema_types"]))
    lines.append(f"- **Title / description:** {s.get('title', '')} — {s.get('description', '')}")
    return lines + [""]


def _item_file(it: dict, names: Names, text: str, sync: dict) -> str:
    projects = [t for t in it["tags"] if "/" not in t and t != taxonomy.COMMDATA]
    topics = [t.split("/", 1)[1] for t in it["tags"] if t.startswith("topic/")]
    typ = next((t.split("/", 1)[1] for t in it["tags"] if t.startswith("type/")), "")
    tags = ["closedtabs"] + [t for t in it["tags"] if t.startswith(("type/", "topic/"))] \
        + [f"why/{taxonomy.slug(w)}" for w in it["why"] if taxonomy.slug(w)] \
        + [taxonomy.slug(p) for p in projects] + (["commdata"] if taxonomy.COMMDATA in it["tags"] else [])
    props = {"closedtabs_id": it["id"], "kind": it["kind"], "title": it["title"]}
    if it["kind"] == "link":
        props |= {"url": it["url"], "source": names.index_link("Sources", it["source"]) if it["source"] else "",
                  "platform": it["source_kind"]}
    props |= {"type": typ, "topics": topics, "why": it["why"], "projects": projects,
              "saved": time.strftime("%Y-%m-%d", time.localtime(it["created_at"]))}
    if it["kind"] == "link":
        props["commdata"] = taxonomy.COMMDATA in it["tags"]
    if it.get("archived"):
        props["archived"] = True
        tags.append("archived")
    props |= {"tags": list(dict.fromkeys(tags)), "cts_sync": sync}

    lines = [f"# {it['title'] or it['url']}", ""]
    meta = []
    if it["kind"] == "link":
        meta.append(f"🔗 [Open the page]({it['url']})")
        if it["source"]:
            meta.append("Source: " + names.index_link("Sources", it["source"]))
    if projects:
        meta.append("Projects: " + ", ".join(names.index_link("Projects", p) for p in projects))
    if it["why"]:
        meta.append("Why: " + ", ".join(names.index_link("Why", w) for w in it["why"]))
    if meta:
        lines += [" · ".join(meta), ""]
    if it["summary"] or (it["kind"] == "link" and it["description"]):
        lines += ["> " + (it["summary"] or it["description"]).replace("\n", " "), ""]
    if it["kind"] == "link":
        lines += _compact_commdata(it.get("seo") or {})
        lines += ["## My notes", ""]
    lines += [MARKER, "", text.strip(), ""]
    return f"---\n{_props_text(props)}\n---\n" + "\n".join(lines)


def _write(path: Path, content: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)
    return True


def _index_page(title: str, intro: str, items: list[dict], names: Names, extra: list[str] | None = None) -> str:
    props = {"closedtabs_index": True, "tags": ["closedtabs"]}
    lines = [f"# {title}", "", intro, ""] + (extra or [])
    for it in sorted(items, key=lambda x: -x["created_at"]):
        icon = "📝" if it["kind"] == "note" else "🔗"
        date = time.strftime("%Y-%m-%d", time.localtime(it["created_at"]))
        src = f" — {it['source']}" if it["kind"] == "link" and it["source"] else ""
        lines.append(f"- {icon} {names.link(it)}{src} · {date}")
    lines += ["", "*Generated by ClosedTabs: edits to this page are overwritten.*", ""]
    return f"---\n{_props_text(props)}\n---\n" + "\n".join(lines)


def sync() -> dict:
    """Run one full two-way sync. Safe to call often: only changed files are written."""
    root = vault_dir()
    if root is None:
        status.update(enabled=False)
        return status
    with _lock:
        try:
            result = _sync(root)
            status.update(enabled=True, last_sync=time.time(), error="", folder=str(root), **result)
        except PermissionError:
            status.update(enabled=True, error=(
                f"macOS didn't allow writing to {root}. If the vault is in iCloud Drive, Documents or "
                "Desktop, start ClosedTabs with ClosedTabs.command (not the background autostart), "
                "or move the vault to your home folder."), folder=str(root))
        except OSError as e:
            status.update(enabled=True, error=f"Couldn't sync with Obsidian: {e}", folder=str(root))
        return status


def _sync(root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    pulled = imported = written = 0

    # 1. read what's in the vault: our item files (by id) and new notes you created
    files_by_id: dict[int, Path] = {}
    new_notes: list[Path] = []
    for sub in ("Links", "Notes"):
        for p in (root / sub).glob("*.md") if (root / sub).exists() else []:
            props, _, _ = _split(p.read_text(encoding="utf-8"))
            cid = props.get("closedtabs_id") if isinstance(props, dict) else None
            if isinstance(cid, int):
                files_by_id[cid] = p
            elif sub == "Notes":
                new_notes.append(p)

    # 2. notes you wrote in Obsidian -> ClosedTabs
    for p in new_notes:
        props, above, below = _split(p.read_text(encoding="utf-8"))
        body = (below if below is not None else above).strip()
        body = re.sub(r"^# .*\n?", "", body).strip() if body.startswith("# ") else body
        why = taxonomy.why_keywords(", ".join(_as_list(props.get("why")))) if isinstance(props, dict) else []
        projects = taxonomy.own_labels(", ".join(_as_list(props.get("projects")))) if isinstance(props, dict) else []
        new_id = db.add_note(body, title=p.stem, why=why, tags=projects)
        from .enrich import worker
        worker.submit(new_id)
        p.unlink()  # rewritten below in ClosedTabs format, under the same name
        imported += 1

    items = db.export_all()
    names = Names(items)

    # 3. three-way merge of the synced fields for every item
    for it in items:
        path = files_by_id.get(it["id"])
        own = [t for t in it["tags"] if "/" not in t and t != taxonomy.COMMDATA]
        text_db = it["content"] if it["kind"] == "note" else it["note"]
        if path and path.exists():
            props, _, below = _split(path.read_text(encoding="utf-8"))
            last = props.get("cts_sync") or {} if isinstance(props, dict) else {}
            changes = {}
            if below is not None and _h(below) != last.get("text") and below.strip() != (text_db or "").strip():
                changes["content" if it["kind"] == "note" else "note"] = below.strip()
            ob_why = taxonomy.why_keywords(", ".join(_as_list(props.get("why"))))
            if _h(ob_why) != last.get("why") and ob_why != it["why"]:
                changes["why"] = ob_why
            ob_proj = taxonomy.own_labels(", ".join(_as_list(props.get("projects"))))
            if _h(ob_proj) != last.get("projects") and sorted(ob_proj) != sorted(own):
                keep = [t for t in it["tags"] if "/" in t or t == taxonomy.COMMDATA]
                changes["tags"] = sorted(set(keep) | {p for p in ob_proj if p != taxonomy.COMMDATA})
            if changes:
                # notes keep ClosedTabs-style links: turn [[File name|shown]] back into [[shown]]
                for k in ("content", "note"):
                    if k in changes:
                        changes[k] = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"[[\1]]", changes[k])
                db.update(it["id"], **changes)
                it = db.get(it["id"])
                pulled += 1
        text = it["content"] if it["kind"] == "note" else it["note"]
        own = [t for t in it["tags"] if "/" not in t and t != taxonomy.COMMDATA]
        text_ob = _to_obsidian_links(text, names)
        sync = {"text": _h(text_ob), "why": _h(it["why"]), "projects": _h(own)}
        target = root / Names.folder(it) / f"{names.item[it['id']]}.md"
        if path and path.exists() and path != target:
            path.unlink()  # title changed: move to the new name
        written += _write(target, _item_file(it, names, text_ob, sync))

    # 4. items deleted in ClosedTabs -> remove their files
    ids = {it["id"] for it in items}
    for cid, p in files_by_id.items():
        if cid not in ids and p.exists():
            p.unlink()

    # 5. index pages
    wanted: set[Path] = set()

    def index(kind: str, value: str, intro: str, members: list[dict], extra=None):
        p = root / kind / f"{Names.index(kind, value)}.md"
        wanted.add(p)
        return _write(p, _index_page(value, intro, members, names, extra))

    projects: dict[str, list] = {}
    whys: dict[str, list] = {}
    sources: dict[str, list] = {}
    for it in items:
        if it.get("archived"):
            continue
        for t in it["tags"]:
            if "/" not in t and t != taxonomy.COMMDATA:
                projects.setdefault(t, []).append(it)
        for w in it["why"]:
            whys.setdefault(w, []).append(it)
        if it["kind"] == "link" and it["source"]:
            sources.setdefault(it["source"], []).append(it)
    for p, members in projects.items():
        cd = [m for m in members if taxonomy.COMMDATA in m["tags"]]
        extra = [f"**{len(cd)} websites with CommData** · compare them in ClosedTabs: "
                 f"http://localhost:3000/compare?tag={p}", ""] if cd else None
        written += index("Projects", p, f"Everything saved for **{p}**.", members, extra)
    for w, members in whys.items():
        written += index("Why", w, f"Saved because: **{w}**.", members)
    for s, members in sources.items():
        kind = members[0]["source_kind"]
        written += index("Sources", s, f"Saved from **{s}**" + (f" ({kind})." if kind != "website" else "."), members)
    for kind in ("Projects", "Why", "Sources"):
        for p in (root / kind).glob("*.md") if (root / kind).exists() else []:
            if p not in wanted:
                props, _, _ = _split(p.read_text(encoding="utf-8"))
                if isinstance(props, dict) and props.get("closedtabs_index"):
                    p.unlink()

    home = ["---", _props_text({"closedtabs_index": True, "tags": ["closedtabs"]}), "---",
            "# ClosedTabs", "", f"{sum(1 for i in items if i['kind'] == 'link')} links · "
            f"{sum(1 for i in items if i['kind'] == 'note')} notes · last sync {time.strftime('%Y-%m-%d %H:%M')}", "",
            "New note? Create it in the **Notes** folder (properties `why` and `projects` are optional).", "",
            "## Projects", *[f"- {names.index_link('Projects', p)} ({len(m)})" for p, m in sorted(projects.items())], "",
            "## Why I saved things", *[f"- {names.index_link('Why', w)} ({len(m)})" for w, m in
                                         sorted(whys.items(), key=lambda kv: -len(kv[1]))], "",
            "## Top sources", *[f"- {names.index_link('Sources', s)} ({len(m)})" for s, m in
                               sorted(sources.items(), key=lambda kv: -len(kv[1]))[:30]], ""]
    written += _write(root / "ClosedTabs.md", "\n".join(home))
    return {"written": written, "pulled": pulled, "imported": imported}


class AutoSync:
    """Background sync every `every` seconds while ClosedTabs runs (only if a vault is configured)."""

    def __init__(self, every: int = 30):
        self.every = every
        self._started = False

    def start(self):
        if self._started or not enabled():
            return
        self._started = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            try:
                sync()
            except Exception:
                log.exception("Obsidian sync crashed")
            time.sleep(self.every)


auto = AutoSync()

# 05 · Towards a second brain

ClosedTabs started as "a place for tabs". The aim now: a **second brain**, where saved material
turns into connected knowledge that helps with real work (client analyses, content, workshops).

## Inspiration (researched 2026-11-05)

| Project / method | ★ | What we take from it |
|---|---|---|
| [Foam](https://github.com/foambubble/foam) (VS Code PKM) | 17.5k | `[[wikilinks]]` between notes + **backlinks** ("linked from") |
| [Dendron](https://github.com/dendronhq/dendron) | 7.5k | hierarchies that grow with you; structure emerges from use |
| [claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian) | 16k | Claude reads, links and summarises sources into the vault |
| Tiago Forte, *Building a Second Brain*: **PARA** + **CODE** | n/a | how to organise (PARA) and the workflow (Capture → Organize → Distill → Express) |

## How ClosedTabs maps to it

**CODE workflow**

| Step | Meaning | In ClosedTabs |
|---|---|---|
| **Capture** | keep what resonates | paste a link or a quick note; *Why* keywords record the reason |
| **Organize** | by actionability, not by topic | projects (own labels), CommData, sources, topics, type |
| **Distill** | find the essence | AI summary, top keywords, notes that link to sources with `[[…]]` |
| **Express** | turn it into output | competitor comparison, CSV, Claude drafting from your library |

**PARA (by actionability)**

| PARA | Meaning | ClosedTabs today | Later |
|---|---|---|---|
| **Projects** | short-term, with a goal and an end | own labels like `project-delia` | project page: links, notes, CommData and comparison in one place |
| **Areas** | ongoing responsibilities | own labels like `area-neuromarketing` | an "area" kind of label with its own sidebar block |
| **Resources** | topics of interest | AI topics + type + sources | topic pages, merging near-duplicate topics |
| **Archive** | done / inactive | not yet | "Archive" button; archived items hidden unless asked for |

## Obsidian as the thinking space

ClosedTabs **captures and enriches** (links, AI labels, CommData, comparison, Claude access).
**Obsidian** is where you **read, connect and write**. The two stay in sync (`app/closedtabs/obsidian.py`):
one Markdown file per item with properties (`why`, `projects`, `topics`, `type`, `source`, tags such as
`why/…`, `topic/…`), plus generated pages per project, why-keyword and source. Graph view and backlinks
then show the structure. Your text below the marker line, and the `why`/`projects` properties,
sync back. New notes in `ClosedTabs/Notes/` are imported. Approach adapted from
[obsidian-hoarder](https://github.com/jhofker/obsidian-hoarder).

## Item kinds

- **Link:** a web page (optionally with CommData)
- **Note:** your own text. Links to anything with `[[Exact title]]`, `[[source name]]` or `[[#id]]`.
  Every item shows **Links to** and **Linked from**.

## Roadmap (suggested order)

1. **Archive** + "status" (inbox → kept → archived), so the library doesn't silt up.
2. ~~Project pages~~ ✅ done: /projects, with AI brief saved as a linked note.
3. **Weekly review**: "saved this week, not yet sorted"; resurface 5 older items related to active projects.
4. **Distill with Claude**: "summarise everything I saved for project-delia into a note" → saved as a note with `[[links]]` to its sources (the `add_note` tool already allows this).
5. **Topic hygiene**: merge near-duplicate topics; rename labels across all items.
6. **Graph view**: a map of notes, links and how they connect.
7. **Highlights / quotes** from saved pages as their own small notes.

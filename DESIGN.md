# DESIGN.md: ClosedTabs

Method: the `/awwwards` skill (github.com/juliobsz/skills), scaled to the brief. ClosedTabs is a
working tool, not a showcase: it earns the same craft in type, layout, interaction and
accessibility, but no loader, no WebGL and no smooth-scroll library.

## Brief

- **Subject:** ClosedTabs, a personal second-brain library for links, notes and website data.
- **Owner and audience:** Shoya (neurocommunication & growth strategist). Mostly herself, sometimes
  on a shared screen with a client (project pages, competitor comparison, briefs).
- **The job:** capture in one click, find again in seconds, see patterns (why / project / source).
- **Constraints:** runs locally and offline (self-hosted fonts, no CDN), server-rendered HTML,
  no build step, light and dark mode, usable at 390 px.

## Concepts (three territories, scored 1 to 5; portability: lower is better)

| | A. Tabs, filed (name) | B. Attention map (profession) | C. Field notebook (process) |
|---|---|---|---|
| Idea | Closed browser tabs become filed index cards; every card keeps a tab you can read and pull | The library as an eye-tracking heatmap of what caught her attention | Every find passes through stages like entries in a research notebook |
| Anchor | The product's own name: a *tab* is both a browser tab and the tab on a file card | Her neuromarketing work (eye tracking) | How she works: capture, sort, distill |
| Layout rule | Cards with a protruding label tab; sidebar groups are divider tabs | Density and warmth by attention | Dated entries, margin notes |
| Motion verb | **pull and file** | glow, fade | write, cross out |
| Originality / fit / feasibility / portability | 4 / 5 / 5 / **2** | 3 / 4 / 2 / 3 | 3 / 4 / 4 / 4 |

**Chosen: A.** It comes straight from the name, it works in plain CSS, and it can't be moved to another product without the double meaning of "tab". B risks brain/heatmap clichés and would compete with real data; C could be any notes app.

## Concept card

```
Idea:        Closed browser tabs become filed index cards. Each card keeps a tab you can read and pull.
Metaphor:    a card-index drawer: white cards, typewritten tabs, colored dividers, a highlighter.
Signature:   the label tab on every card (its source, typewritten) and the "pull" hover: the card
             lifts out of the drawer, its tab first. On the welcome page your real recent sources
             drop into the drawer as tabs.
Emotion:     calm order. Everything has its place and can be pulled out again.
Motion verb: pull and file. Things lift slightly toward you on hover and settle back; new things
             drop into place from above.
Screenshot:  the library: a column of white cards on a steel-blue drawer, each with a mono tab.
```

## Art direction system

**Palette** (named by role; from a steel filing cabinet with white cards and a highlighter):

| Role | Light | Dark | Source |
|---|---|---|---|
| ground (drawer) | `#DCE2E5` | `#121619` | painted steel cabinet |
| card | `#FFFFFF` | `#1C2226` | index card |
| ink | `#14181B` | `#EEF2F4` | typewriter ribbon |
| muted | `#4F5B64` | `#A4B0B8` | pencil (AA on card and ground) |
| line | `#C4CDD2` | `#2F383E` | card edge |
| accent (filing ink) | `#2340C8` | `#8FA2FF` | blue divider tab, used for actions and links |
| highlight (why) | `#FFE45C` | `#5C4D00` | highlighter on the card: the owner's own reasons |

No cream, no serif, no gradient wash. One accent, one highlight, both meaningful.

**Type:** Schibsted Grotesk (variable 400 to 800, Google, OFL) for everything; IBM Plex Mono
(400/500) **only** for what a typewriter would put on a tab: source names, counts, dates, URLs.
Hungarian and Romanian accents covered (latin-ext). Display tracking negative (-0.02 to -0.035em);
body 16 px, leading 1.55; UI text 12 to 14 px.

**Shape:** one radius rule: 6 px (cards, inputs, buttons); tabs get 6 px on the top corners only.

**Grid & rhythm:** sidebar 260 px + content (max 1240 px); 8 px spacing base; cards stack on a
12 px rhythm; detail pages read at 760 px measure.

**Interaction (one treatment per role):**
- Cards and project cards (primary): *pull*: lift 3 px, the tab rises 2 px more, shadow deepens.
- Buttons: *press and lift*: 1 px lift on hover, settle on press; secondary buttons flood with the
  accent tint from the bottom.
- Nav links: the current page is an open tab joined to the page; others draw an underline on hover.
- Sidebar items: a divider marker slides in from the left.
- Inline links in notes: underline at rest, rising into a highlighter band on hover.
- All hovers sit in `@media (hover: hover)`, every one is also reachable by `:focus-visible`,
  and under reduced motion the movement is dropped and a color/underline state remains.

**Continuity:** cross-document View Transitions: pages slide up 8 px and fade (filing a card).
Off under reduced motion. No loader.

**Idle state (decision):** the tool is still at rest on purpose; it is used for long sessions and
movement would distract. Life comes from the hovers and the welcome signature.

## Genericness test (what changed from the previous design)

- Warm cream ground + serif titles + teal (AI default 1): replaced by the filing-cabinet palette
  and one grotesk with a functional mono.
- Identical rounded cards with the same soft shadow (AI default 4): cards now carry a label tab and
  answer with a pull; notes are visibly a different card (ruled top edge).
- Tracked uppercase eyebrow labels above sidebar groups (AI default 5): now sentence-case divider tabs.
- Em dashes in visible UI text: removed.

## Decisions recorded during QA

- **No autofocus on the library**: the skip link comes first for keyboard users. Instead, pasting
  anywhere on the page (Cmd/Ctrl + V) drops the link into the save box, and `/` jumps to search.
  The desktop-only tip says so; it's hidden on touch devices (copy fits the device).
- **No Open Graph, canonical or sitemap**: ClosedTabs is a private app on localhost, never shared
  or indexed. `robots.txt` disallows everything on purpose.
- **Em dashes**: none in UI copy. Those the audit still finds come from saved page titles (real
  data, kept as written).
- **Designed 404** ("This card isn't in the drawer") for every unknown address, including those
  that reach the Claude connector mount.

## QA (skill scripts: shoot.mjs + audit.mjs, three passes)

| Check | Result |
|---|---|
| audit.mjs FAILs | 0 |
| axe violations (serious/critical) | 0 on home, library, link, note, project, review, tools, 404 |
| Skip link first in tab order | yes, every page |
| Focus visible on every stop | yes (0 invisible) |
| Horizontal overflow (1440 / 390) | none |
| Text hidden under reduced motion | 0 |
| Primary hover targets with no change | none |
| CLS | 0 · LCP under 110 ms locally · heaviest page 88 KB, 0 KB JS framework |
| WCAG contrast (all palette pairs, light + dark) | all at or above 4.5:1 |

**Score** (self-scored from the screenshots with the skill's rubric; the skill recommends a
separate critic agent, which wasn't launched in this session):

| Design | Usability | Creativity | Content | Weighted |
|---|---|---|---|---|
| 7.5 | 8 | 7 | 7 | **7.5** |

What would raise it most: real data instead of sample data in the screenshots, and a second
signature moment in the library (e.g. a newly saved card visibly "filed" into the list).

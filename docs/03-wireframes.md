# 03 · Wireframes (structure only)

These are low-fidelity wireframes: they show layout and information hierarchy
only, no colour, type or styling. They describe the experience we want, whether
they guide the ClosedTabs design pass.

## Screen 1 · Home / Capture

```
┌──────────────────────────────────────────────────────────────────────┐
│  TABS→LINKS                                   [ Ask Claude ⌘K ]  (me)│
├──────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────┐ [ Save ] │
│  │ Paste a link…                                          │          │
│  └────────────────────────────────────────────────────────┘          │
│  (optional) why am I saving this? ______________________             │
├───────────────┬──────────────────────────────────────────────────────┤
│ LISTS         │  INBOX (12 new)                       sort: newest ▾ │
│ ▸ Inbox    12 │  ┌──────────────────────────────────────────────────┐│
│ ▸ Toolbox  48 │  │ [img] Title of the page                    ⋯     ││
│ ▸ Read wk   7 │  │       domain.com · 2h ago                        ││
│ ▸ Clients     │  │       AI summary, two lines max, saying what it  ││
│   ▸ Client A  │  │       is and why it might matter…                ││
│ ▸ Fundraising │  │       #type/tool  #topic/ai  #use/client-work    ││
│               │  │       [→ List] [Archive] [Open]                  ││
│ TAGS          │  └──────────────────────────────────────────────────┘│
│  type/…       │  ┌──────────────────────────────────────────────────┐│
│  topic/…      │  │ … next card …                                    ││
│  use/…        │  └──────────────────────────────────────────────────┘│
└───────────────┴──────────────────────────────────────────────────────┘
```

## Screen 2 · Search / Filter

```
┌──────────────────────────────────────────────────────────────────────┐
│  🔍 [ onboarding emails                                   ]  [Search] │
│  Filters: type [tool ▾]  topic [any ▾]  use [any ▾]  date [any ▾]    │
│  Chips:   (#type/tool ×) (-archived ×)                               │
├──────────────────────────────────────────────────────────────────────┤
│  24 results                                     view: ☰ list ▦ grid  │
│  • Title — domain · #tags · one-line summary                         │
│  • Title — domain · #tags · one-line summary                         │
│  …                                                                   │
└──────────────────────────────────────────────────────────────────────┘
```

## Screen 3 · Item detail

```
┌──────────────────────────────────────────────────────────────────────┐
│ ← Back                                       [Open original ↗] [⋯]   │
│ TITLE OF THE PAGE                                                    │
│ domain.com · saved 3 Nov · in: Toolbox, Client A                     │
│ ┌ Summary (AI) ──────────────────────────────────────────────────┐   │
│ │ 3–4 sentences.                                                  │   │
│ └─────────────────────────────────────────────────────────────────┘   │
│ Tags: #type/tool #topic/growth  [+ add]                               │
│ My note: __________________________________________                   │
│ ┌ Reader view (archived text) ────────────────────────────────────┐   │
│ │ … full readable text, highlightable …                          │   │
│ └─────────────────────────────────────────────────────────────────┘   │
│ [ Ask Claude about this ]  → "How could I use this for <project>?"    │
└──────────────────────────────────────────────────────────────────────┘
```

## Screen 4 · Ask Claude (side panel or Claude app itself)

```
┌───────────────────────────── Ask Claude ─────────────────────────────┐
│ You: Which tools did I save for A/B testing landing pages?            │
│                                                                       │
│ Claude: You saved 3:                                                  │
│  1. <Tool A> (link) · free tier, good for quick tests…                │
│  2. <Tool B> (link) · …                                               │
│  3. Article: "…" (link) · method, not a tool                          │
│  Best fit for your Q4 client: …                                       │
│                                                                       │
│ [ Save answer as note ]  [ Add all to list ▾ ]                        │
└───────────────────────────────────────────────────────────────────────┘
```

## Mobile capture (share sheet)

```
┌──────────────────────┐
│ Share to Tabs→Links  │
│ ✓ Saved              │
│ Add to list: [▾]     │
│ Note: _____________  │
│        [Done]        │
└──────────────────────┘
```

## Questions to settle in the design phase
- Card density: rich cards (image + summary) or a compact list?
- Should "why am I saving this?" be a prompt shown on every save, or optional?
- Is Ask Claude a panel inside the app, or do we rely on the Claude app plus MCP? The second option needs no build.

# 04 · Label system (taxonomy)

The idea: a **small set of label families** ("faceted tags") instead of
hundreds of random tags. Every item gets *one* `type`, *1–3* `topic`s, and
*0–2* `use`s. This makes filtering predictable for you and for Claude.

## Families

**`type/`: what it is** (exactly one)
`type/tool` · `type/github-repo` · `type/article` · `type/research-paper` ·
`type/video` · `type/podcast` · `type/course` · `type/template` ·
`type/dataset` · `type/newsletter` · `type/inspiration` · `type/reference-docs`

**`topic/`: what it is about** (1–3)
`topic/neuromarketing` · `topic/behavioral-science` · `topic/consumer-psychology` ·
`topic/ai-creative-analysis` · `topic/ai-tools` · `topic/growth-strategy` ·
`topic/go-to-market` · `topic/fundraising` · `topic/performance-marketing` ·
`topic/copywriting` · `topic/branding` · `topic/ux-research` · `topic/analytics` ·
`topic/sustainability` · `topic/community-building` · `topic/automation` ·
`topic/dev` · `topic/other`

**`use/`: where it could help you** (0–2)
`use/client-work` · `use/own-business` · `use/content-idea` ·
`use/teaching-workshops` · `use/learn-later` · `use/try-it`

*These are a starting point. After two weeks, review which tags the AI actually
produced and merge, rename or add as needed.*

## Custom tagging prompt

Paste this into **Karakeep → Settings → AI → custom prompts** (tagging). It is added to the built-in prompt.

```text
Tag using ONLY these label families, written exactly as shown (lowercase, with the slash):
- Exactly ONE "type/" tag from: tool, github-repo, article, research-paper, video, podcast,
  course, template, dataset, newsletter, inspiration, reference-docs.
  (A GitHub repository is type/github-repo; a web app/SaaS/product is type/tool.)
- ONE to THREE "topic/" tags from: neuromarketing, behavioral-science, consumer-psychology,
  ai-creative-analysis, ai-tools, growth-strategy, go-to-market, fundraising,
  performance-marketing, copywriting, branding, ux-research, analytics, sustainability,
  community-building, automation, dev, other.
- ZERO to TWO "use/" tags from: client-work, own-business, content-idea,
  teaching-workshops, learn-later, try-it.
Context: the owner is a neurocommunication & growth strategist (psychologist) advising
startups and SMEs. Prefer the most specific fitting topic. Do not invent new tags.
```

Summary prompt (Settings → AI → summarisation):

```text
Write 2–3 plain sentences: what this is, who it is for, and one concrete way a
growth/neuromarketing consultant could use it. For tools, mention pricing model
(free / freemium / paid / open source) if stated on the page.
```

## Suggested smart lists

| List | Query |
|---|---|
| 🧰 Toolbox | `#type/tool or #type/github-repo` |
| 🕰️ Forgotten gems | `age:>2m -is:inlist -is:archived` |
| 📥 Inbox | `-is:inlist -is:archived` |
| 💡 Content ideas | `#use/content-idea` |
| 🧪 To try | `#use/try-it -is:archived` |

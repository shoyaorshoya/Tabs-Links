# 04 · Label system (taxonomy)

The idea: a **small set of label families** ("faceted tags") instead of
hundreds of random tags. Every item gets *one* `type`, *1–3* `topic`s, and
*0–2* `use`s. This makes filtering predictable for you and for Claude.

## Families

**`type/`: what it is** (exactly one)
`type/tool` · `type/company` · `type/github-repo` · `type/article` · `type/research-paper` ·
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

## Where this lives in the app
The lists and the AI instructions are in **`app/closedtabs/taxonomy.py`**. Edit the lists,
then run the start script again. Claude can only choose labels from these lists, because
its answer is checked against a schema. You can still type any label by hand on a link's
details page.

## Handy searches

Click a label in the left sidebar to filter by it, e.g. **tool**, **try-it** or **content-idea**.
Then type in the search bar to search within that label.

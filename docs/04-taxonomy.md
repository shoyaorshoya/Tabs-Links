# 04 · Label system

Every link can carry three kinds of labels:

| Kind | Looks like | Who sets it | Notes |
|---|---|---|---|
| **Type** | `type/company` | AI (you can change it) | Exactly one, from a short fixed list: tool, company, github-repo, article, research-paper, video, podcast, course, template, dataset, newsletter, inspiration, reference-docs, other |
| **Topics** | `permanent-makeup`, `eye-tracking`, `oradea` | AI, **from the page content** | 2–4 short lowercase labels. The AI reuses your existing topics when they fit, so they don't sprawl. |
| **My labels** | `project-delia`, `client`, `workshop` | **You** | Add as many as you like, comma separated, when saving or on the details page. The AI never removes them. Shown with an outline. |

## Why this split
- *Type* stays fixed so "show me all tools" always works.
- *Topics* follow what you actually save. No pre-made list to maintain.
- *My labels* hold what only you know: projects, clients, intentions ("try-it", "for-newsletter").

## Changing things
- The type list and the AI instructions are in `app/closedtabs/taxonomy.py`.
- After changing the AI setup, use **Re-label all links** (left sidebar). Your own labels and notes are kept.
- To merge two near-duplicate topics, edit the links in question on their details page. (A one-click merge could come later.)

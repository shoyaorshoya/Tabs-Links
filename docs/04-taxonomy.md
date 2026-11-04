# 04 · Label system

Every link is findable through six "dimensions", each with its own block in the sidebar:

| Dimension | Example | Set by | Answers |
|---|---|---|---|
| **Why** | `inspiration`, `pricing`, `competitor` | you, comma separated, when saving | *why did I keep this?* (intent) |
| **Projects & my labels** | `project-delia`, `client-x` | you | *for whom / which project?* |
| **Sources** | `mero.ro`, `sethblack/python-seo-analyzer`, a YouTube channel | automatic, from the URL | *where is it from?* |
| **Topics** | `permanent-makeup`, `eye-tracking` | AI, from the page content | *what is it about?* |
| **Type** | `company`, `tool`, `article` | AI | *what is it?* |
| **Time** | last 7 days | automatic | *when?* |

Filters combine: e.g. **why: inspiration** + **topic: onboarding** + **source: lenny (Substack)**.
Clicking a chip on a card adds it as a filter; the bar above the list shows active filters (× removes one).

**Source naming:** normal websites → registrable domain without `www`/subdomains (`blog.hubspot.com` → `hubspot.com`);
GitHub/GitLab/Hugging Face → `user/repo`; YouTube/Vimeo videos → channel name (official oEmbed lookup);
YouTube channels → `@handle`; LinkedIn → profile/company; X/Instagram/TikTok → `@handle`; Medium → author;
Substack → publication; Reddit → `r/subreddit`; npm/PyPI → package. Rules live in `app/closedtabs/sources.py`.

## Labels in detail

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

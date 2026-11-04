# Super simple setup guide

About 10 minutes. ☕ marks the steps where you just wait.

---

## Part 1: Start ClosedTabs

**Step 1.** Open **Docker Desktop** and wait for **"Engine running"** (bottom left).

**Step 2.** Download the project (log in to GitHub first):
https://github.com/shoyaorshoya/tabs-links/archive/refs/heads/claude/zen-wozniak-ap0j7f.zip
Unzip it and put the folder in **Documents**.
*Already have the older download? Replace it with this new one.*

**Step 3.** Open **Terminal**, type `cd ` (with a space), **drag the folder** into the window, and press **Enter**.

**Step 4.** Paste this and press **Enter**:
```
bash start.sh
```
☕ The first time takes a few minutes. Then your browser opens **http://localhost:3000**.
*If you ran the earlier Karakeep version, this also removes it automatically.*

**Step 5.** Click **Enter**. That's it: no account, no password. 🎉

> **No Docker? Use this instead of Step 4** (needs Python 3.10+; check with `python3 --version`):
> ```
> bash start-local.sh
> ```
> Keep that Terminal window open while you use ClosedTabs. Press **Ctrl + C** to stop it.

## Easier starting (Mac, no Terminal)

**Option A: start automatically (recommended).**
1. Move the whole ClosedTabs folder to your **home folder** (Finder → **Go → Home**, then drag it there).
   macOS doesn't allow background apps in iCloud Drive, Desktop, Documents or Downloads.
2. Double-click **Autostart-ON.command** in the folder. The first time, macOS may say it's from
   an unidentified developer: **right-click → Open → Open**.
3. Done. ClosedTabs now runs in the background and starts by itself whenever you log in.
   Just open **http://localhost:3000** (bookmark it!).
   To switch it off: double-click **Autostart-OFF.command**. Your links stay.

**Option B: double-click to start.** Double-click **ClosedTabs.command**. It starts ClosedTabs
and opens the browser. If it's already running, it only opens the browser.

---

## Part 2: Add links

**One by one:** paste a link in the top box and press **Enter** (or click **Save**).
The *"Why am I saving this?"* box is optional, but future-you will thank you.
The *"My labels"* box is optional too: type your own labels separated by commas, e.g.
`project-delia, client`. The AI adds its own topic labels from the page content and never
removes yours. You can change labels later via **details**.

**Website data for client work (CommData):** tick **Collect website data (CommData)** before
saving. ClosedTabs then also collects SEO data, keywords, the marketing/tech stack and social
profiles, and adds the **CommData** label. In the sidebar, **CommData** lists these websites
grouped by your project labels (e.g. `project-delia`). Open a project and click **CSV** (or
**CSV for Excel (;)** if Excel puts everything in one column) to export them as a table.
For an already-saved link: open **details** → **Collect CommData**.

**Several at once:** paste many links, one per line, then click **Save**.

**All your open tabs:**
1. In Chrome, press **Cmd + Shift + D** and save all tabs into a folder, e.g. "Tabs to sort".
2. Go to `chrome://bookmarks`, click **⋮**, then **Export bookmarks**.
3. In ClosedTabs, click **Import bookmarks file…** (left side) and choose that file.
4. Close those tabs. Really. 😌

Each link shows *"⏳ Reading the page…"* for a few seconds, then fills in by itself.

---

## Part 3: Switch on AI labels + descriptions

You need **one** AI key. Pick whichever you like:

| Option | Where to get a key | Notes |
|---|---|---|
| **Claude** (default) | https://platform.claude.com → API keys | Best labels. Roughly 1–2 cents per link. |
| **Gemini** | https://aistudio.google.com/apikey | Google offers a free tier (check their current limits). |
| **Any other** (OpenAI, Mistral, Groq, OpenRouter…) | That provider's website | Anything "OpenAI-compatible" works |
| **Ollama** | No key. Free and runs on your computer | Install from https://ollama.com and download a model |

**Step 6.** In Finder, open the project folder, then the **deploy** folder.
Press **Cmd + Shift + .** to show hidden files, and open **.env** with TextEdit.
*(No .env yet? Start ClosedTabs once and it gets created.)*

**Step 7.** Fill in your choice:

- **Claude:** paste the key right after `ANTHROPIC_API_KEY=` (no spaces).
- **Gemini:** fill in these three lines:
  ```
  LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
  LLM_API_KEY=your-gemini-key
  LLM_MODEL=the-model-name
  ```
  For the model name, open https://ai.google.dev/gemini-api/docs/models and copy the exact
  name of a current **Flash** model (fast and cheap, perfect for this).
- **Others:** the file lists the address to use for each provider.

*If you fill in both Claude and Gemini, Claude is used. To switch, set `AI_PROVIDER=other`.*

**Step 8.** Save the file. Restart ClosedTabs (Ctrl + C, then start it again the same way).

New links now get labels and a summary. Links you saved **before** adding a key are labelled
automatically the first time ClosedTabs starts with the key. You'll see "⏳ Reading the page…"
on them for a little while.

**Check it's on:** open http://localhost:3000/health. It shows which AI and model are in use.
If a link shows an orange message (e.g. "key rejected"), fix the .env line it names and restart.

---

## Part 4: Connect Claude

See [`claude/README.md`](claude/README.md). It's 3 small steps for the Claude desktop app.

---

## Everyday use

| I want to… | Do this |
|---|---|
| Open ClosedTabs | Go to **http://localhost:3000** (bookmark it!) |
| Find something | Use the search bar, or click a label on the left |
| Fix a label or add a note | Click **details** on the link |
| Back up everything | Click **Export everything** (left side) |
| Stop / start it | Docker: Docker Desktop → **Containers** → ⏹ / ▶ next to **deploy**. Without Docker: **Ctrl + C** to stop, `bash start-local.sh` to start |

ClosedTabs only runs while Docker Desktop (or the `start-local.sh` window) is open. Your links stay safe when it's closed.

**Stuck?** Screenshot the terminal and send it to me.

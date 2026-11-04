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

---

## Part 2: Add links

**One by one:** paste a link in the top box and press **Enter** (or click **Save**).
The *"Why am I saving this?"* box is optional, but future-you will thank you.

**Several at once:** paste many links, one per line, then click **Save**.

**All your open tabs:**
1. In Chrome, press **Cmd + Shift + D** and save all tabs into a folder, e.g. "Tabs to sort".
2. Go to `chrome://bookmarks`, click **⋮**, then **Export bookmarks**.
3. In ClosedTabs, click **Import bookmarks file…** (left side) and choose that file.
4. Close those tabs. Really. 😌

Each link shows *"⏳ Reading the page…"* for a few seconds, then fills in by itself.

---

## Part 3: Switch on AI labels + descriptions

**Step 6.** Get a Claude API key at https://platform.claude.com, under **API keys**.

**Step 7.** In Finder, open the project folder, then the **deploy** folder.
Press **Cmd + Shift + .** to show hidden files, and open **.env** with TextEdit.

**Step 8.** Paste your key right after `ANTHROPIC_API_KEY=` (no spaces). Save the file.

**Step 9.** Stop ClosedTabs (Ctrl + C, if you use `start-local.sh`) and start it again the same way.

New links now get labels and a summary. For links saved before the key, open one,
click **details**, then **Re-read page & re-label**.

*Cost: roughly 1–2 cents per link with the default model. For about 40× cheaper, change
`CLAUDE_MODEL=claude-opus-5-5` to `CLAUDE_MODEL=claude-haiku-5-5` in the same file.*

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

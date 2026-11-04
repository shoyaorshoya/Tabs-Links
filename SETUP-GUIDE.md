# Super simple setup guide

Takes about 15 minutes. Steps marked ☕ are where you just wait.

---

## Part 1: Start the app

**Step 1. Open Docker Desktop.**
Wait until the bottom-left corner shows **"Engine running"** (green). ☕

**Step 2. Download the project.**
Open this link while logged in to GitHub:
https://github.com/shoyaorshoya/tabs-links/archive/refs/heads/claude/zen-wozniak-ap0j7f.zip
Unzip it, then move the folder somewhere easy, such as **Documents**.

**Step 3. Open a terminal in that folder.**
- **Mac:** open the **Terminal** app. Type `cd ` (with a space after it), **drag the folder** into the Terminal window, and press **Enter**.
- **Windows:** open the folder, right-click an empty spot, and choose **Open in Terminal**.

**Step 4. Copy, paste, and press Enter:**
- **Mac:**
  ```
  bash start.sh
  ```
- **Windows:**
  ```
  powershell -ExecutionPolicy Bypass -File .\start.ps1
  ```
The first run downloads about 1–2 GB. ☕ (5–10 min)
When it's done, your browser opens **http://localhost:3000**.

**Step 5. Create your account.**
Click **Sign up** and enter your name, email and a password.
The first account becomes the admin, which is you. 🎉

---

## Part 2: Move your open tabs in

**Step 6. Bookmark all your tabs at once (Chrome).**
Press **Cmd + Shift + D** (Mac) or **Ctrl + Shift + D** (Windows).
Name the folder "Tabs to sort" and click **Save**.
*You can close those tabs now. Yes, really.* 😌

**Step 7. Export them.**
Go to `chrome://bookmarks`, click the **⋮** menu (top right), choose **Export bookmarks**, and save the file.

**Step 8. Import them.**
In the app at localhost:3000, click your **profile icon** and open **Settings → Import**.
Choose **Import bookmarks from HTML file** and pick the file from Step 7. ☕

---

## Part 3: Save new links in one click

**Step 9. Install the browser extension.**
- Chrome: https://chromewebstore.google.com/detail/karakeep/kgcjekpmcjjogibpjebkhaanilehneje
- Firefox: https://addons.mozilla.org/en-US/firefox/addon/karakeep/

Click the extension icon. For the server address, enter `http://localhost:3000`, then log in.
From now on, one click on the icon saves the page you're on.

---

## Part 4 (when you're ready): Turn on AI labels and descriptions

**Step 10.** Get a Claude API key at https://platform.claude.com, under **API keys**.

**Step 11.** In the project folder, open `deploy/.env` with any text editor (TextEdit or Notepad).
Find the line `# OPENAI_API_KEY=sk-ant-paste_your_key_here`.
Delete the `# ` at the start and replace the placeholder with your key. Save the file.
*(On Mac the file may be hidden. Press **Cmd + Shift + .** in Finder to show it.)*

**Step 12.** Run Step 4 again.

**Step 13.** In the app, go to **Settings → AI** and paste in the two prompts from `docs/04-taxonomy.md`.
New links will now get your labels and a short description automatically.
**Step 14.** To label the links you already imported, open **Admin → Background Jobs** and click
**Regenerate AI Tags for All Bookmarks**, then **Regenerate AI Summaries for All Bookmarks**. ☕

---

## Everyday use

| I want to… | Do this |
|---|---|
| Save a link | Click the extension icon |
| Find something | Use the search bar at localhost:3000 |
| Stop the app | Docker Desktop → **Containers** → ⏹ next to `deploy` |
| Start it again | Docker Desktop → **Containers** → ▶ next to `deploy` (or repeat Step 4) |

The app only runs while Docker Desktop is open. Your saved links stay safe when it's closed.

**Stuck?** Take a screenshot of the terminal and send it to me.

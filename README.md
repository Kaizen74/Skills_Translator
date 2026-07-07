# SkillBridge

**Turn Claude skills into skills your local AI can use.**

SkillBridge is a small web app that runs entirely on your Beelink GTR9 Pro. You give it a Claude skill (a `SKILL.md` folder or ZIP), and it produces three things for your local setup:

1. **A Hermes standing rule** — a ready-to-paste Telegram message that teaches Hermes the skill's method.
2. **An Obsidian template** — a fill-in note filed straight into your vault.
3. **A Qwen prompt pack** — a prompt file your local Qwen model can use via Ollama.

You review and approve every draft in your browser before anything is saved. Nothing ever leaves your machine — no cloud, no accounts, works with WiFi off (the only internet use is downloading packages during installation).

It **ports the method, never the file**: skills that need Claude's code tools (like building PowerPoint files) are honestly labelled as staying on the Claude tier.

---

## Installing on your Beelink (one time, about 5 minutes)

You'll copy-paste four commands into the Terminal. That's the only terminal use, ever — after this, everything happens in your browser.

### Before you start

- Your Beelink is on and you're logged in (directly or via remote desktop).
- Ollama is already installed and running (it is, on your machine).

### Step 1 — Open the Terminal

Press `Ctrl` + `Alt` + `T` together. A dark window appears where you can type commands.

### Step 2 — Download SkillBridge

Copy this whole line, paste it into the Terminal (right-click → Paste), and press Enter:

```bash
git clone https://github.com/Kaizen74/Skills_Translator.git ~/Skills_Translator
```

**You'll know it worked when:** it prints a few lines ending without any red "error" text, and typing `ls ~/Skills_Translator` shows files like `install.sh` and `README.md`.

> If it says `git: command not found`, first run `sudo apt install -y git` (it will ask for your login password — typing shows nothing, that's normal), then repeat this step.

### Step 3 — Run the installer

Copy-paste these two lines and press Enter:

```bash
cd ~/Skills_Translator
./install.sh
```

The installer talks you through 6 steps: it checks Python, installs SkillBridge's own packages, creates a `SkillBridge` folder in your home directory, runs a self-test, and sets SkillBridge up to start automatically every time the machine boots.

**You'll know it worked when:** it ends with

```
=== Done! ===
On this machine, open:      http://localhost:8788
```

> If it stops with a ❌ message, it will tell you exactly what to run to fix it (usually one `sudo apt install ...` line). Run that, then run `./install.sh` again — it's safe to re-run any number of times.
>
> **Most common one:** if it says *"Ubuntu is missing the add-on that builds Python environments"*, copy-paste the `sudo apt install -y python3-venv python3.12-venv` line it prints, then run `./install.sh` again. That's Ubuntu needing one small extra package the first time.

### Step 4 — Open SkillBridge

Open Firefox (or any browser) on the Beelink and go to:

```
http://localhost:8788
```

**You'll know it worked when:** you see the SkillBridge home screen with a **Health** section at the top.

From your laptop, use the Beelink's Tailscale name instead — the installer prints this address at the end, e.g. `http://beelink:8788`.

### Step 5 — One-time check in Settings

1. In SkillBridge, click **Settings** (top of the page).
2. Click **"Test connection to Ollama"**.
   - ✅ *"Connected. The model ... is installed and ready."* — you're done.
   - ⚠️ *"...the model is not installed. Models found: ..."* — copy the correct model name from that list into the **Ollama model name** box and click **Save settings**. (This is the one thing SkillBridge won't guess for you.)
3. Check the **Obsidian vault folder** shows your vault (normally `~/SecondBrain/Vault`). Fix and save if not.

That's it. You never need the Terminal again.

---

## Using SkillBridge day to day

1. **Add a skill.** On the Home screen, click **Upload skill ZIP** and pick the skill's `.zip` file. (Or drop a skill folder into `~/SkillBridge/inbox` — it's picked up within seconds.)
2. **Watch it work.** The queue shows plain-language progress: *"Reading skill… Classifying… Drafting standing rule (1 of 3)…"* A typical skill takes a few minutes on the local model.
3. **Open the review screen.** You'll see:
   - a **portability verdict** — FULL (everything ports), PARTIAL (the method ports; Claude-only parts are listed), or CLAUDE-ONLY (kept on the Claude tier, nothing generated);
   - the three drafts in editable text boxes.
4. **For each draft:** edit if you like, then **Approve**, **Regenerate** (optionally with a one-line steering note like "shorter, focus on scoring"), or **Skip**.
   - Approving the **template** files it into your vault. Existing files are never overwritten — a `_v2` copy is created instead.
   - Approving the **prompt pack** saves it to `~/SkillBridge/library/prompt-packs`.
   - Approving the **standing rule** shows it with a **Copy** button — paste it into your Hermes Telegram chat once, then click *"I've sent it"*.
5. **Registry.** Every ported skill is logged in `Synthesis/Skill-Porting-Registry.md` in your vault (also viewable in the app under **Registry**).
6. **Updating a skill.** Drop the newer version in again: SkillBridge shows you exactly what changed in the method and drafts a v2. Old approved files are never deleted.

Fields marked **IMPLICATION FOR PORTFOLIO** (or **Operator Decision**) are always left blank for you — the AI is not allowed to fill them, and an automated test enforces this.

---

## If something goes wrong

| Symptom | What to do |
|---|---|
| The page at `localhost:8788` won't load | Reboot the Beelink — SkillBridge starts itself on boot. Still down? In Terminal: `systemctl --user restart skillbridge` |
| Health says *"Could not reach Ollama"* | Ollama isn't running. In Terminal: `sudo systemctl restart ollama`, then refresh the page. |
| Health says *"Vault folder not found"* | Open **Settings** and correct the vault path, then Save. |
| An upload is rejected | The message on screen explains why (usually not a valid ZIP, or no SKILL.md inside). Re-download the skill and try again. |
| You want to stop SkillBridge | In Terminal: `systemctl --user stop skillbridge` (and `start` to bring it back). |

Logs live in `~/SkillBridge/logs/skillbridge.log` if you ever need to share details when asking for help.

---

## For the technically curious

- **Stack:** Python 3.11, FastAPI, SQLite, plain HTML/JS — no build toolchain. All state in `~/SkillBridge/`.
- **Privacy:** the app makes no network calls except to Ollama on `127.0.0.1` — enforced by an automated test (`tests/test_no_egress.py`).
- **Tests:** `./run_checks.sh` runs the full suite (57 tests) in mock-LLM mode, no model needed.
- **Docs:** `GUIDE.md` is the click-by-click owner's manual; `PROJECT_STATE.md`, `DECISIONS.md` and the PRD govern the build (resilient-build method).

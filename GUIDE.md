# SkillBridge — Owner's Guide
*Updated: 2026-07-07*

## What this app does
SkillBridge takes a Claude skill (a folder with a SKILL.md file, usually downloaded as a ZIP) and translates its *method* into three things your local AI stack can actually use: a Hermes standing rule (a Telegram message), an Obsidian template (filed into your vault), and a Qwen prompt pack (saved to a library folder). You approve every draft before anything is saved. It runs entirely on your Beelink — nothing is sent to the cloud, ever.

## How to start it
You normally don't: SkillBridge starts by itself when the Beelink boots.

1. Open your browser to **http://localhost:8788** (on the Beelink), or **http://<your-beelink-tailscale-name>:8788** from your laptop.
2. You'll know it's running when you see the home screen with the **Health** section showing three lines about Ollama, your vault, and disk space.
3. If the page won't load, see "If something goes wrong" below.

(First-time installation is in README.md — four copy-paste commands, once.)

## How to open it from your laptop
SkillBridge runs on the Beelink, but you can use it from your laptop over Tailscale (your private, secure tunnel — nothing is exposed publicly).
1. Make sure Tailscale is installed on your laptop and signed into the **same account** as the Beelink (get it at tailscale.com/download if you don't have it).
2. On the Beelink, open Terminal and type `tailscale ip -4` — it prints a number like `100.88.12.34`.
3. On the laptop, open your browser to `http://100.88.12.34:8788` (your number, keep the `:8788`).
The Beelink's name usually works too, e.g. `http://beelink:8788` (`tailscale status` on the Beelink shows the name). Both machines must be on and connected. Everything works the same as on the Beelink; files still land in the Beelink's vault.

## How to use it

### Port a new skill
1. On **Home**, click **Choose file**, pick the skill's `.zip` **or** a single `SKILL.md` (`.md`) file, and click **Upload skill**. (Alternative: drop the skill folder, ZIP, or `.md` file into `~/SkillBridge/inbox` using the file manager.)
2. The skill appears in the queue with live progress words. Wait for **"Ready for your review"**, then click **Open**.
3. Read the **portability verdict** at the top:
   - **FULL** — the whole method ports.
   - **PARTIAL** — the method ports; the parts that must stay on Claude are listed.
   - **CLAUDE-ONLY** — nothing is generated; the registry simply records "run on Claude tier".
4. For each of the three drafts, edit the text if you want, then click:
   - **✅ Approve** — the template is filed into your vault / the prompt pack is saved to the library / the standing rule becomes a copy-ready message.
   - **🔄 Regenerate** — optionally type a one-line note first (e.g. "shorter", "focus on the scoring steps").
   - **Skip this artefact** — if you don't need that one.
5. For the standing rule, after approving: click **📋 Copy**, paste it into your Hermes Telegram chat, send it once, then click **"I've sent it — mark as done"**.

### Fields that are yours alone
Any field named **IMPLICATION FOR PORTFOLIO** or **Operator Decision** always arrives blank with the note "Leave blank — owner completes." The AI is forbidden from filling these — an automated test fails the whole build if it ever does.

### Update a skill you already ported
Drop the new version in exactly like a new skill. SkillBridge notices the name, shows **"What changed since the last version"** in plain language, and drafts a v2. Your old approved files are never touched.

### The registry
Click **Registry** in the top bar to see every ported skill, its verdict, and status. The same table lives in your vault at `Synthesis/Skill-Porting-Registry.md` — it's a normal Obsidian note; edit the Status column there if you like.

### Settings
Click **Settings** to change the vault folder, the Ollama model name, or the port. The **"Test connection to Ollama"** button answers in plain language. After changing the model name, click Save — no restart needed (only the port needs a restart).

## What changed recently
- 2026-07-07: You can now add a skill as a single `.md` file, not just a ZIP (upload it or drop it in the inbox).
- 2026-07-07: First complete version — ingestion, portability verdicts, all three generators, review-and-approve screen, registry, skill updating, auto-start on boot, installer.

## If something goes wrong
- **Page won't load** → reboot the Beelink (SkillBridge auto-starts). If still down, open Terminal and run: `systemctl --user restart skillbridge`
- **"Could not reach Ollama" in Health** → open Terminal and run: `sudo systemctl restart ollama`, then refresh.
- **"Vault folder not found"** → fix the path in Settings and Save.
- **Upload rejected** → the on-screen message says exactly why (bad ZIP, missing SKILL.md, or a malformed header). Re-download the skill and retry.
- **A skill was "Halted (confidential flag)"** → it mentioned one of your flagged confidential terms; SkillBridge refused to process it, as designed.
- **To stop the app**: Terminal → `systemctl --user stop skillbridge`. To start again: same command with `start`.

## Glossary
- **Skill** — a folder with a SKILL.md file that teaches Claude a repeatable method.
- **Standing rule** — a one-message instruction that teaches Hermes a permanent behaviour.
- **Prompt pack** — a text file of ready-made prompts for the local Qwen model.
- **Ollama** — the program on your Beelink that runs local AI models.
- **Vault** — your Obsidian notes folder (`~/SecondBrain/Vault`).
- **Method core** — SkillBridge's structured summary of a skill (purpose, steps, output format); saved in `~/SkillBridge/work` for audit.
- **Mock mode** — a testing mode where no real AI model is used; you'll only ever see it mentioned on the Settings screen if it's on.

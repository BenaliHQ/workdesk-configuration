---
name: onboarding
description: Five-phase calm orientation for a freshly bootstrapped vault. Silent doctor self-check, welcome, operator-profile interview, brief zone tour, then graduate by either planning a real project with /pobo or starting today's daily note. One question per turn. Idempotent and resumable. Sub-commands --status, --restart, --update-profile.
---

# /onboarding

Calm, concierge-style first-run experience. Five phases. One question per turn. Each phase writes results as it goes — if interrupted, partial work is preserved and resuming picks up at the first non-`complete` phase.

Source spec: `atlas/projects/workdesk/specs/onboarding-redesign.md` (in the operator's secondary vault — that's the design contract this skill implements).

## Sub-commands

- `/onboarding` — resume from incomplete phase, or run full flow first time
- `/onboarding --status` — show what's been configured
- `/onboarding --restart` — wipe `config/onboarding-state.md` with confirmation; vault content untouched
- `/onboarding --update-profile` — interactive profile edit (post-graduation safe)

## Detection

Run proactively when:
- `config/onboarding-state.md` exists with any phase still `pending` or `incomplete`
- AND operator has not dismissed onboarding this session

Confirmation guard: running `/onboarding` after graduation says: *"Onboarding complete. Use `--restart` to redo it (vault content is safe), or `--update-profile` to adjust your profile."*

## Scope — workdesk skills only

The only skills that exist for this session are those under `<vault>/config/skills/*/SKILL.md`. That is the closed universe.

When listing, proposing, suggesting, resolving, or invoking a skill name during onboarding, enumerate **only** the `config/skills/` directory of the active vault. Do not surface, mention, or auto-invoke:

- skills installed at `~/.claude/skills/` (user-level)
- skills from sibling projects' `.claude/skills/` directories
- skills loaded by other vaults that share the same Claude Code environment
- tools surfaced by MCP servers as if they were skills
- plugin-provided skills outside the workdesk plugin set

If the operator references a skill by name (e.g., "/foo"), resolve it against `config/skills/` only. If no match, reply: "That's not a WorkDesk skill. The WorkDesk skills are: [list from `config/skills/`]." Do not silently fall through to a same-named skill from another scope.

## Style — pacing and tone

This is a guided conversation, not a form. Hard rules:

- **One question per turn.** Ask one thing, wait for the answer, then ask the next. Never stack two questions in one message.
- **Snappy.** Short sentences. Plain words. No bureaucratic preambles ("I need your input here", "Question 1 —", baseline-state dumps).
- **Frame each phase in one line before the first question.** Not three paragraphs. One line. Then the question.
- **Back-and-forth pace.** Treat it like a chat with someone next to you, not a wizard form.
- **Do not pre-fill answers from external context.** If you can see the operator's name or context from `~/.claude/CLAUDE.md`, env vars, vault path, or git config — ignore it for the purpose of asking. Ask fresh. Operators tell you if they want to short-circuit ("yeah, that's me"). Inferring up front feels presumptuous.
- **No baseline-state dumps before questions.** Don't list what's already in `atlas/` or what doctor returned before asking the next question. The operator doesn't need a status report; they need the next step.
- **Examples are illustrative, not options.** When a question lists examples (roles, tools, etc.), the operator can answer with anything — not just the listed ones. Treat examples as prompts for thought, not a closed multiple-choice.

## Phases

### Phase 0 — Doctor (silent)

**Purpose:** prove the install works without asking the operator to do anything.

Onboarding owns its own prerequisite. Do not bounce the operator out to run a separate command.

Read `config/state/doctor.md`. If `result: pass` is present and `last-run` is within the current session, continue silently. Otherwise:

1. Invoke `/workdesk-doctor` inline (as a skill call from within onboarding). Wait for it to complete.
2. Re-read `config/state/doctor.md`.
3. **Pass** → continue silently to Phase 1.
4. **Yellow** (fixable issues) → attempt minimal self-fix: chmod missing exec bits on `config/scripts/*.sh`, recreate broken state files from defaults, repair direct-symlink mismatches. Re-run doctor. If now green, continue silently.
5. **Red** (unfixable) → surface a single concise message naming what failed and stop. Do not list options or open a menu.

**Self-fix scope (V1.1):** chmod, recreate state files, repair symlinks. Out of scope: reinstalling plugins, reauth, anything that requires the operator to leave the chat.

**No operator prompt at this phase.** No "running doctor now…" status messages. Silent unless something's red.

Mark phase 0 complete in `config/onboarding-state.md`.

### Phase 1 — Welcome

**Purpose:** orient. Set expectations. Land the concierge tone.

**Pre-step (silent):** if `<vault>/README.md` does not exist, write the vault-root README from the template at `<vault>/config/templates/vault-readme.md`. Do not overwrite an existing README — operators who customized theirs keep their version.

**Opening message** (single short paragraph, exact text):

> *"Let's get your WorkDesk set up. Five quick steps — environment check (done), a few questions about you, a quick tour of your vault, and then we'll either plan a project together or start today's daily note. I'll go one thing at a time. You can bail anytime — we pick up where we left off. Sound good?"*

Wait for affirmative. If declined: *"Run `/onboarding` whenever you're ready."* Stop.

Mark phase 1 complete.

### Phase 2 — Operator profile interview

**Purpose:** build the operator profile that downstream skills read. One question per turn. Never stack.

After each answer, write to `config/operator-profile.md` immediately, then ask the next question.

**Q1 — name:**

> *"First — what should I call you?"*

Free text. Save to `name:`. Do not pull a name from `~/.claude/CLAUDE.md`, vault path, git config, or anywhere else.

**Q2 — role (open-ended):**

> *"How would you describe what you do? Examples — consultant, founder, employee, researcher, creative, parent, or anything else. There are no preset options; describe it the way you'd describe it to someone you just met."*

Free text. Examples are illustrative. Operator can answer however they like — coerce nothing. Save verbatim to `role:`.

**Q3 — work mode:**

> *"What does most of your work look like? Heavy meetings, heavy deep-work, mixed, or something else?"*

Free text. Save to `work-mode:`.

**Q4 — areas of focus (durable):**

> *"What are the areas you focus on most — generally, not just right now? Could be domains (finance, ops, design), topics, or kinds of work. Two or three is plenty."*

Parse into a list. Save under `## Areas of focus` in the profile body. Deliberately durable, not point-in-time priorities.

**Q5 — tools you use today (inventory only, no connection):**

Send a single message that names categories with several examples each, then asks the operator's list:

> *"What tools do you use day-to-day? Just naming them helps me know what's in your stack — I won't connect anything until you actually need it. Some categories and examples:*
>
> - *Comms — Slack, Microsoft Teams, Discord*
> - *Email + calendar — Gmail / Google Workspace, Outlook*
> - *Meetings + transcription — Granola, Google Meet, Zoom, Teams, Otter, Fireflies*
> - *Project management — ClickUp, Notion, Asana, Linear, Trello*
> - *CRM — HubSpot, Salesforce, Apollo, Pipedrive*
> - *Storage — Google Drive, Dropbox, OneDrive, iCloud*
> - *Design — Figma, Canva*
> - *Code + deploy — GitHub, GitLab, Vercel, Netlify*
> - *Finance — QuickBooks, Xero*
>
> *Tell me whichever you use — and anything else not on the list."*

For each named tool:

1. Slugify the name (lowercase, kebab-case).
2. If `config/tools/<slug>.md` already exists (seeded), set `confirmed-by-operator: true` on its frontmatter. Do **not** overwrite content.
3. If absent, create `config/tools/<slug>.md` with frontmatter (`tool:`, `slug:`, `category:` inferred from context, `class: operator-named`, `connected: false`, `added-on:` today, `connector: unknown`) and stub body sections (`## What it is`, `## Best practices`, `## Connection notes`, `## Linked use cases`).

Update the profile body's `## Tools in use` section with wikilinks to each tool note.

**Q6 — transcription sources (multiple allowed):**

> *"Of those, which do you actually use to capture meetings? You can name more than one — Granola for some meetings, Zoom for others, etc."*

For each named tool, append `transcription` to its `preferred-for:` list on the corresponding `config/tools/<slug>.md`. Multiple is normal.

If "none" or "skip," continue. Transcript-processing skill's first-run will handle wiring later.

Mark phase 2 complete.

### Phase 3 — Zone tour (6 short turns)

**Purpose:** name each zone and how to add to it. Briefly. Tutorial videos handle depth.

One zone per turn, in this order. Each turn is **three sentences max:** what it's for, how the operator adds to it, no preamble. No "Phase 3:" prefix on the messages — just the zone content.

After Phase 2 completes, send the first zone message. Operator doesn't need to respond between zones; you can send them as a back-to-back sequence with a brief pause for them to read. If they ask a question mid-tour, answer briefly and continue.

**3a — `personal/`:**

> *"`personal/` is your space — daily notes, journal, reading, anything you write. Claude or any other agent never writes in `personal/`, and you should never want me to. You'll add to it most by running your daily note. ▶ Watch (2 min): https://supercut.ai/share/benali/L7AMBy2jCo2GPqw2S66eRU"*

The lock language is deliberate. Do not soften it to "unless you ask." The PreToolUse hook enforces the boundary at runtime; this teaches it conceptually.

**3b — `atlas/`:**

> *"`atlas/` is what you manage — people, decisions, meetings. When something has its own identity worth tracking, it goes here. ▶ Watch (2 min): https://supercut.ai/share/benali/o8GxKPEpYFDBmSxuP79vR"*

**3c — `GTD/`:**

> *"`GTD/` is for actions and projects — standard getting-things-done shape, like David Allen recommends. ▶ Watch (2 min): https://supercut.ai/share/benali/tTmAzLhiuqHSuE2v1FdINX"*

**3d — `intel/`:**

> *"`intel/` is what I observe — daily briefings, research, vault improvements. Lower trust than `atlas/` because I write it independently. ▶ Watch (2 min): https://supercut.ai/share/benali/Sb94l7TDegwgPHsoniOZZT"*

**3e — `system/`:**

> *"`system/` is your sources — transcripts, bookmarks, session logs. Everything that comes in lands in `_intake/` first, gets processed, and once processed moves to the right folder. Objects in `atlas/` get updated or created from there. ▶ Watch (2 min): https://supercut.ai/share/benali/vlxgd2Vpz9pQCjuUeS0x79"*

**3f — `config/`:**

> *"`config/` is the harness — the skills, hooks, templates, and state that make WorkDesk run. It stays out of your way by default and you rarely touch it directly, but it's worth seeing once so you know what's under the hood. ▶ Watch (2 min): https://supercut.ai/share/benali/dBzNlZl8Yvwk3JT877kJ4F"*

**Closing line** (after 3f):

> *"All six tutorial videos live in your vault README — open it whenever you want to rewatch."*

Mark phase 3 complete.

### Phase 4 — Graduation (the fork)

**Purpose:** the operator does one real thing. Right now, not tomorrow.

**Opening message:**

> *"You're set up. Two ways to wrap: I can walk you through planning a project with `/pobo`, or we can just open today's daily note so you can start writing. Either's fine. Which?"*

Wait for choice.

**Path A — `/pobo` a project:**

If operator picks pobo:
1. Mark phase 4 in-progress with `path: pobo` in `config/onboarding-state.md`.
2. Invoke `/pobo` (skill call from within onboarding). Pobo runs its planning ritual and produces a real project structure at `gtd/projects/<slug>/`.
3. When pobo completes, return to onboarding to finalize graduation.

**Path B — daily note:**

If operator picks daily note:
1. Mark phase 4 in-progress with `path: daily-note`.
2. **Do not write to `personal/`**. The daily note is created by Obsidian itself (via the vendored Periodic Notes plugin and the template at `config/templates/daily-note.md`). Open Obsidian to today's daily note via URI scheme: `obsidian://open?vault=<vault-name>&file=personal/daily/{today}` (substitute the ISO date). If the URI launch fails or Obsidian's daily-note plugin isn't configured, fall back to telling the operator: *"Open today's daily note in Obsidian — click the calendar icon in the sidebar, or press the daily-note hotkey. Periodic Notes will create it from the template."* Do not create the file from the skill.

**Either path: graduation marker.**

After the chosen path completes, update:
- `config/onboarding-state.md` phase 4 `complete: true`, `graduated: true`, `graduated-at: <iso-timestamp>`, `graduation-path: pobo|daily-note`
- `config/state/signals.json` `vault-improvements.suppressed-until: <today + 14d>`

**Final summary** (two lines, no decoration):

```
Profile saved at config/operator-profile.md.
Tools tracked: <count>. Wire any with /define-tool <name> when you need them.
```

Do not point the operator at `/daily-ops`, `/weekly-review`, or any other follow-up skill at the close. They'll discover skills when they're ready — that's the whole point of the skill-first-run pattern.

Mark phase 4 complete.

## Output

After graduation:
- `config/operator-profile.md` populated
- `config/tools/<slug>.md` per named tool (seeded notes confirmed, operator-named notes created)
- `<vault>/README.md` materialized (if not pre-existing)
- One real artifact: either a project under `gtd/projects/` (Path A) or today's daily note under `personal/daily/` (Path B)
- `config/onboarding-state.md` shows `graduated: true`
- Vault-improvement suppression set 14 days out

## What NOT to do

- Don't skip Phase 0. Doctor must self-run and self-fix. Never instruct the operator to run a separate command before continuing.
- Don't write, edit, or `Bash`-mutate any path under `personal/` — ever. Phase 4 Path B opens Obsidian to the daily note; Obsidian creates the file via Periodic Notes. There are no sanctioned writes to `personal/` from this skill.
- Don't fabricate contexts or pre-fill answers from `~/.claude/CLAUDE.md`, env vars, vault path, or git config. Ask fresh.
- Don't stack questions. One question per turn, period.
- Don't dump baseline state ("atlas/ has X, Y, Z. Doctor green.") between turns.
- Don't invoke `/daily-ops` or `/weekly-review` during the flow. Don't reference them at graduation either — no "tomorrow run X" pointers, no skill catalog. The operator discovers downstream skills when they're ready.
- Don't surface or invoke skills outside `config/skills/`. No `ops-manager`, no sibling-project leakage, no MCP-surfaced tools as skills.
- Don't prompt for MCP / API integration setup. Phase 2 Q5 is inventory only; connection deferred to `/define-tool`.
- Don't ask for *lists* of things the operator might balk at. Ask for one (one project name, one tool category at a time when probing). Lists trigger overwhelm.
- Don't introduce a concept before the operator touches the artifact it names. Zones get named in Phase 3 because that's when it's time; no glossary up front.
- Don't enumerate the WorkDesk skill catalog at graduation. Don't name a "first habit" either. Graduation confirms what just happened; the operator drives what comes next.
- Don't gate Phase 4 on prior skips. Even if Phase 2 was skipped halfway, the operator can still choose pobo or daily-note.
- Don't coerce free-text answers (role, work-mode, areas) into preset categories. Examples are illustrative, not multiple-choice.

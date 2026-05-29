---
name: feedback
description: Send feedback, bug reports, and feature requests to the WorkDesk OS team via GitHub. Walks the operator through five short questions like a product manager would, then files the issue. Operator must have the GitHub CLI (gh) installed and authenticated — first run walks through that setup if needed.
---

# /feedback

Files a GitHub issue on `BenaliHQ/workdesk-configuration` from inside the vault. The operator never sees the GitHub UI unless they want to. Claude is the product manager; the operator is the user being interviewed.

## Boundaries

- **Never** attaches content from `personal/`, `atlas/`, `gtd/`, `intel/`, or `system/`. Only diagnostics from `config/` are auto-included (version, doctor state, OS, Claude Code version, timestamp).
- The operator can paste specifics in their answers if they want. Whatever they type is what goes in the issue body.
- Issues are filed under the operator's GitHub account (their `gh auth` identity). They own the issue — they can comment, close, follow up.
- Daily cap: 20 issues per 24 hours. Above that, the skill says so and waits.

## Phase 0 — Setup check (silent if already done)

Run:

```
config/scripts/file-issue.sh check
```

Parse the JSON output. Three cases:

- `gh_installed: true, gh_authenticated: true` → continue silently to Phase 1.
- `gh_installed: false` → tell the operator: *"To send feedback I need the GitHub CLI. Run this in your terminal: `brew install gh`. Tell me when it's done."* Wait. Re-run the check after they confirm.
- `gh_installed: true, gh_authenticated: false` → tell the operator: *"GitHub is installed but not connected to your account yet. Run `gh auth login` in your terminal — pick HTTPS and follow the browser flow. Tell me when you see 'Logged in as ...'"* Wait. Re-run the check after they confirm.

If either install or auth fails twice, surface the underlying error and stop. Don't loop indefinitely.

## Phase 1 — Throttle check

Run:

```
config/scripts/file-issue.sh throttle-check
```

If `ok: false`, tell the operator: *"You've filed 20 issues in the last 24 hours — that's the daily cap. Try again tomorrow."* Stop.

Otherwise continue to Phase 2.

## Phase 2 — Interview (one question per turn)

Five questions, each on its own turn. Wait for an answer before asking the next. No multiple-choice options — free text. Keep questions short.

**Q1 — What:**
> *"What's the feedback in one sentence?"*

This becomes the issue title. If the answer is longer than ~12 words, gently shorten it for the title (keep the operator's exact words for the body).

**Q2 — Why:**
> *"Why do you want this?"*

**Q3 — End state:**
> *"What does the end state look like — what would be different in your vault if this shipped?"*

**Q4 — Outcome:**
> *"What outcome are you hoping for?"*

**Q5 — Use:**
> *"How would you use this once it's there?"*

If the operator gives a vague answer ("I don't know" / "just feels off"), accept it — don't push. The operator's words are the data. Sparse is fine.

## Phase 3 — Classify

Pick a label based on what the operator said:
- **bug** — something broken: errors, crashes, hooks denying when they shouldn't, wrong output, missing files
- **enhancement** — a new feature, a change in behavior, a better way of doing something
- **question** — they want to understand something, not fix or add it

If ambiguous, default to `enhancement`.

## Phase 4 — File the issue

Build the issue body in this exact shape and write it to a temp file (e.g. `<vault>/.workdesk-migrate-tmp/feedback-body-<timestamp>.md`):

```markdown
## Feedback

### What
{Q1 answer — verbatim}

### Why
{Q2 answer — verbatim}

### Desired end state
{Q3 answer — verbatim}

### Hoped-for outcome
{Q4 answer — verbatim}

### How they'd use it
{Q5 answer — verbatim}

---

## Diagnostics

- **WorkDesk OS version:** {contents of config/VERSION}
- **Doctor result:** {result field from config/state/doctor.md, or "not run" if absent}
- **Doctor last-run:** {last-run from doctor.md, or "—"}
- **OS:** {`uname -sr` output}
- **Claude Code:** {`claude --version` if available, else "unknown"}
- **Filed:** {ISO timestamp now}

*Filed via `/feedback` skill. The operator can attach screenshots, code excerpts, or follow-up details by commenting on this issue.*
```

Tell the operator (single sentence — no draft, no approve step):

> *"I'm sending this to GitHub now: '{title}'."*

Then run:

```
config/scripts/file-issue.sh submit "<title>" "<body-file-path>" <bug|enhancement|question>
```

Capture the URL from stdout. If the command fails, surface the error and stop — do not retry automatically.

On success, run:

```
config/scripts/file-issue.sh throttle-record
```

Then close with:

> *"Filed: {url}. You'll get GitHub email when it's looked at. You can comment on it any time to add detail."*

## Voice and pacing

- Plain language. "Feedback," "GitHub," "issue" are fine. "Triage," "label," "epic" are not.
- One question per turn. Wait. Listen.
- Don't validate or critique their answer. Their words go in the issue verbatim.
- Don't show the operator the draft body. They've already given you all the input — just send it.
- If they want to abort mid-flow, accept it cleanly. Don't ask "are you sure?"

## What NOT to do

- Don't attach content from `personal/`, `atlas/`, `gtd/`, `intel/`, or `system/` to the issue body — even if the operator's answer references it. Their answer is verbatim; don't pull surrounding context.
- Don't auto-fill answers from prior sessions or session-log. Ask fresh each time.
- Don't add labels beyond `from-vault` + the type label. The maintainer triages further.
- Don't retry submissions that fail. One try, surface the error, stop.
- Don't loop infinitely on Phase 0. Two failed attempts → stop and tell the operator the underlying error.

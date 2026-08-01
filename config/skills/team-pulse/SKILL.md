---
name: team-pulse
description: What the team did and said in ClickUp — tasks closed, tasks moved, chat messages, task comments — synthesized into a short catch-up read against the operator's own projects. Also runs the new-work detector so new ClickUp folders/lists get flagged as vault project candidates. Use when the operator says "team pulse", "what did the team do", "what did I miss", "catch me up on ClickUp", "what's the team chatting about", or "what got checked off".
---

# /team-pulse

The catch-up read. Pulls ClickUp activity for a window and tells the operator what actually happened — what closed, what's stuck, what the team is talking about, and what needs them specifically.

Requires the ClickUp tool layer — see `config/rules/tools/clickup.md` for setup. Read-only against ClickUp by default; writes are gated (see § Writing to ClickUp).

## Invocation

- `/team-pulse` — last 3 days, all business spaces
- `/team-pulse --days 7` — wider window
- `/team-pulse --since 2026-01-15` — explicit start date
- `/team-pulse --space "<space name>"` — one space only (repeatable)
- `/team-pulse --dms` — include direct messages (excluded by default)
- `/team-pulse --raw` — print the markdown digest with no synthesis
- `/team-pulse --no-new-work` — skip the new-work detector

Vocabulary that should route here: "what did I miss", "catch me up", "what's the team working on", "what did <teammate> do this week", "what got checked off", "what are they chatting about", "anything waiting on me in ClickUp".

## Phases

### 1. Pull the digest

```bash
python3 config/scripts/clickup-digest.py --days 3
```

Pass through `--since`, `--space`, `--include-dms` as given. JSON is the default and what you want for synthesis; `--markdown` is for `--raw`.

The payload has five parts: `window`, `tasks` (each with a `closed` boolean), `comments`, `chat`, and `errors`. Check `errors` first — a chat permission failure still returns tasks, and reporting "the team was quiet" when the chat fetch actually failed is the worst outcome here.

**Scope matters.** One ClickUp workspace often holds several businesses, separated only by space. When the operator asks about one line of business or one client, scope with `--space`; unscoped is fine for "what did I miss" generally. Re-list spaces rather than trusting a remembered name.

### 2. Run the new-work detector (unless `--no-new-work`)

```bash
python3 config/scripts/clickup-new-work.py
```

Cheap, read-only against ClickUp, idempotent. It writes `[REVIEW]` inbox items for new ClickUp folders/lists that no vault project appears to cover. Where a daily LaunchAgent is installed, running it here just means the operator doesn't wait for the next scheduled pass.

If it flags anything, mention it in one line at the end of the report. Don't expand it into the body of the pulse; the inbox item carries the detail.

### 3. Read enough vault context to make it useful

A raw activity dump is not a pulse. Before synthesizing, read:

- `atlas/clients/*/projects/*/_status.md` and `atlas/businesses/*/projects/*/_status.md` for the projects the activity touches
- `config/operator-profile.md` for current priorities

The point is to connect ClickUp movement to the operator's own work: does this close an open item on a project? Does it contradict a `_status.md`? Is it the thing they've been waiting on?

### 4. Synthesize

Report in this order, and cut any section that's empty rather than printing "nothing here":

1. **Needs you** — anything where the operator is @-mentioned, assigned, asked a direct question, or is the named blocker. This goes first, every time.
2. **Checked off** — what closed, who closed it, and whether it clears an open item on a vault project.
3. **Moving** — tasks that changed state, grouped by client or project rather than by list.
4. **What they're talking about** — the chat and comment substance, in a couple of sentences per thread. Summarize; don't transcribe. Teams that paste full meeting recaps into task comments produce comments thousands of words long — pull the two or three things that matter to the operator and link the rest.
5. **Worth a look** — drift you noticed: a `_status.md` contradicted by ClickUp, a task sitting in "ready for review" for days, an unanswered question aimed at the team.

Keep it short per the writing-style rule — a few sentences per section, not a transcript. Long is a failure mode here, not thoroughness. Link tasks by their ClickUp `url` so the operator can click through.

### 5. Route actions correctly

This is where a digest skill most easily breaks the GTD rules. Per [[gtd-inbox-processing]]:

- **The operator's own actions** (they're assigned, they're asked a direct question, they're the blocker) → `gtd/inbox/` with `[ACTION]`, per [[inbox-item-format]].
- **Delegated work that doesn't block them** → mention it in the report and stop. No inbox item, no `actions/waiting/` entry. The operator does not track their team's task lists.
- **Delegated work that hard-blocks their own next action** → `gtd/actions/waiting/`, not the inbox.

When in doubt, it's not a blocker. An over-eager inbox doesn't self-clean.

### 6. Offer, don't assume, durable capture

Default output is conversational only — a pulse is operational awareness, not a source that needs a synthesis note. If the operator wants it durable, ask where before writing: today's daily note in `personal/` (their zone — they write there, Claude doesn't) or `intel/briefings/daily/`. Don't create a new folder for pulse output.

## Writing to ClickUp

**Default posture: Claude may write to ClickUp, and confirms every single time.**

The token has full write access to the whole workspace, and anything Claude does there is immediately visible to every teammate. So:

- State exactly what you're about to do — the verb, the target task or list by name, and the literal text of any comment — and wait for the operator's go-ahead.
- One confirmation per action. Approval to close one task is not approval to close its siblings.
- Never batch a write with a read in the same tool call.
- Reads need no confirmation. Fetching, listing, and digesting are always fine.

Write commands (only after confirmation):

```bash
CU=~/.local/bin/clickup
$CU task create --list <list-id> --name "..." --description "..."
$CU task update --task <task-id> --status "..."
$CU comment create --task <task-id> --comment-text "..."
```

Check `--help` on each before running — flags differ per subcommand.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `401 unauthorized` | Personal token regenerated | Regenerate the ClickUp API token and update `~/.clickup-cli.yaml`. Don't debug further. |
| Empty chat section, populated tasks | Chat fetch failed | Check the `errors` object; say the chat fetch failed rather than "the team was quiet." |
| Digest returns nothing at all | Window too narrow, or wrong space filter | Widen `--days`; re-list spaces before trusting a `--space` value. |
| Detector floods the inbox | State file missing, so everything reads as new | It self-seeds on first run. If `config/state/clickup-inventory.json` was deleted, re-run with `--seed` before a live pass. |

## Related

- `config/rules/tools/clickup.md` — full ClickUp tool reference (setup, CLI commands, API endpoints, limitations)
- `config/scripts/clickup-digest.py` — the read-only activity fetcher
- `config/scripts/clickup-new-work.py` — the new-work detector
- [[gtd-inbox-processing]] — ownership routing; the rule this skill most needs to respect
- ClickUp is production for task state; vault `_status.md` lags it — verify against ClickUp before reporting project state

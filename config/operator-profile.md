---
name: ""
email: ""
role: ""
work-mode: ""
daily-planning-style: "morning"
week-start: "monday"
daily-plan:
  calendar-scope: own
  calendar-lookahead-days: 7
  daily-note-lookback-days: 7
  action-email-label: ""
  exclude-calendars: []
first-30-days-mode: active
created: ""
last_updated: ""
version: 1.3
infisical-project-id: ""
infisical-key-suffix: ""
---

# Operator Profile

This file is populated by `/onboarding`. It captures the operator's role, work mode, areas of focus, and tools in use. Signals (daily-plan, weekly-review, vault-improvements) read this file to scope and tone their output.

Edit directly, or run `/onboarding --update-profile` to walk through changes interactively.

## Role

Free-text description of what the operator does — populated by Q2 in `/onboarding`. Examples are illustrative, not categorical. The `role:` and `work-mode:` frontmatter fields drive tonality choices in `/daily-ops`.

## Work mode

Free-text description of how the operator's days look (heavy meetings, deep-work, mixed, etc.) — populated by Q3 in `/onboarding`.

## Areas of focus

Durable areas the operator focuses on — domains (finance, ops, design), topics, or kinds of work. Populated by Q4 in `/onboarding`. Listed in the body, not in frontmatter.

## Tools in use

Wikilinks to `config/tools/<slug>.md` for each tool the operator named in onboarding. New tools are added via `/define-tool`, which writes a tool note and updates this section. Tool notes track connection state separately (`connected: true|false`).

## daily-plan preferences

Operator-owned settings the `daily-plan` signal (`/daily-ops`) reads to scope its sources. All have sane defaults — leave a field unset and the signal uses the default. The signal logic ships in the WorkDesk OS release; these values are yours and survive `/update`.

| Field | What | Default | Notes |
|---|---|---|---|
| `calendar-scope` | `own` = only your primary calendar (the `email` above); `all` = every calendar shared with you. | `own` | `own` excludes shared/subscribed calendars. Implemented as `--calendar <email>`. |
| `calendar-lookahead-days` | How many days ahead to scan for items needing action *today* (prep, replies, scheduling). | `7` | Today is always the focus; the lookahead only surfaces things that need a today-action to be ready. |
| `daily-note-lookback-days` | How many days of `personal/daily/` notes to read for carry-over context. | `7` | Today's note is weighted most heavily; days with no note are skipped. |
| `action-email-label` | Gmail label whose threads are pulled in as action candidates. | `""` (skip) | Empty → no email pull. Set to your label's exact name (e.g. `Actions`). Confirm the name via `gws gmail users labels list` — display name ≠ what you call it. |
| `exclude-calendars` | Explicit calendar names/IDs to always exclude, even under `calendar-scope: all`. | `[]` | Optional. |

## first-30-days-mode

`active` during the guided first 14 days. Flips to `graduated` once: onboarding complete + ≥1 weekly-review generated + at least one of (project, recurring item, processed transcript) exists. Set by `/weekly-review` graduation check.

## Infisical integration (optional)

The `email`, `infisical-project-id`, and `infisical-key-suffix` frontmatter fields are optional — required only if you use the Infisical secrets-management layer. They are read by `config/scripts/lib/operator-config.sh` and every script in the Infisical/tool-auth stack.

| Field | What | Example |
|---|---|---|
| `email` | Primary operator email. Used as the macOS Keychain account, and as the gws account label. | `you@example.com` |
| `infisical-project-id` | UUID of your "personal" Infisical project (the one holding your non-client static keys). | `00000000-0000-0000-0000-000000000000` |
| `infisical-key-suffix` | Uppercase identifier appended to per-account secret names (e.g. `PERSONAL_GWS_CREDENTIALS_<SUFFIX>_ENC_B64`). Usually the uppercase local part of your email. | `JANE` |

Run `bash config/scripts/bootstrap-infisical.sh` to populate these interactively and complete the rest of the Infisical setup.

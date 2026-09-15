---
type: source-declaration
name: intake
zone: system
location: system/intake/
naming: "{YYYY-MM-DD}-{slug}"
move-after-processing: false
version: 1.0
---

# Source: intake

Generic raw drops awaiting triage. Replaces both `system/inbox/` and `system/processing/` from the four-zone model.

## Format

```yaml
---
type: source
source-kind: intake
date: 2026-04-26
processed: false
processed-into: []
---
```

Body: anything. Pasted text, mobile-captured note, screenshot annotation, link with notes.

## Processing rule

Triage to atlas/intel/gtd:
- Action-shaped → `gtd/actions/` (subject to flood guard if Claude proposes)
- Object-shaped (person mention, decision, meeting) → propose appropriate atlas type
- Synthesis-shaped → `intel/observations/` or `intel/research/`
- Personal note → propose moving to `personal/{practice}/` (operator confirms; agent can't write to personal/)

After processing, flip `processed: true` and populate `processed-into:` backlinks.

## Detection

Session-entry scan surfaces intake items. Daily-plan includes intake count in the inbox section. Vault-improvements flags intake items unprocessed for >7 days.

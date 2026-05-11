---
name: define-source
description: Meta-skill — scaffold a new system source type. Sources are raw inputs (transcript, session-log, intake, bookmark, screenshot, etc.) with a processing rule that turns them into atlas/intel/gtd notes. Define identity, format, processing, retention.
---

# /define-source

Sources are how the vault learns. This skill defines a new raw-input type and its processing rule.

## Detection clause

Surface proactively when:
- A new kind of capture starts landing in `system/intake/` regularly (e.g., screenshots from a research project)
- The operator wires up a new tool that produces structured output (Defuddle bookmarks, Granola transcripts)
- vault-improvements identifies a "raw input shape with no processing pipeline"

Ask: *"You've dropped {kind} captures a few times. Want to define a `{type}` source so they auto-route?"*

## Mode detection

Before any interview or scaffold work, check whether the slug the operator named already has a seed:

1. The operator invokes the skill with a slug — either explicit (`/define-source transcript`) or inferred from the proactive surfacing question above.
2. Check for `config/sources/{slug}.md`:
   - **Exists →** enter **Review/edit mode** (walk the existing seed, identify what to change, apply edits).
   - **Does not exist →** enter **Net-new mode** (run the JTBD interview and scaffold from scratch).
3. State the mode out loud in one line so the operator knows which path they're on. Example: *"`transcript` already has a seed at `config/sources/transcript.md` — entering review/edit mode."* or *"No seed for `bookmark` — entering net-new mode."*
4. If the operator wants to force the other mode (e.g., redefine an existing source from scratch, or treat a missing slug as review-only), they can say so; honor the override and state it.

> **Pattern note for P2-P6 (other `/define-*` skills):** This mode-detection block is the canonical pattern. Lift it verbatim into `define-tool`, `define-object`, `define-signal`, `define-practice`, `define-rule` — substituting the seed-location path (`config/tools/{slug}.md`, `config/objects/{slug}.md`, etc.) and the proactive-surfacing example. The two-mode structure (review/edit vs net-new) and the "state the mode out loud" step are required.

## Review/edit mode

Use when `config/sources/{slug}.md` already exists. The job is to walk the existing seed with the operator and apply targeted edits — not to rewrite from scratch.

1. **Read the seed.** Read `config/sources/{slug}.md` end-to-end. Note its current frontmatter (`location`, `naming`, `move-after-processing`, `version`) and each body section (Format, Processing rule, Retention, Detection).
2. **Present the seed in summary form.** One short paragraph + a section list. Example: *"Current `transcript` seed: lives at `system/transcripts/`, naming `{YYYY-MM-DD}-{topic-slug}`, move-after-processing false, version 1.0. Sections: Format, Processing rule, Retention, Detection. Anything you want to change?"*
3. **Ask what to change.** Open question first. Let the operator name the section or field. Do not walk every section by default — that turns review into a re-interview.
4. **For each change the operator names, confirm scope before editing:**
   - Which section / which field
   - What the new value should be
   - Whether downstream artifacts need updating too (e.g., a `location` change implies `session-entry-scan.sh` may need an update; a `naming` change implies historical file rename is out of scope unless the operator asks)
5. **Apply edits one at a time.** Use targeted `Edit` calls, not full rewrites. Preserve unchanged sections verbatim.
6. **Bump `version`** in the frontmatter when the seed's behavior changes (processing rule, retention, location, naming). Skip the bump for pure typo or wording fixes.
7. **Validate after each edit:** re-read the section, confirm the change reads correctly, and check that the Verify checklist at the bottom of net-new mode still passes (deterministic processing rule, explicit retention, frontmatter shape includes `processed: false` and `processed-into: []`).
8. **Stop when the operator says they're done.** Do not push for more edits.

### What review/edit mode does NOT do

- Does not migrate or rename existing source files in `system/{folder}/` to match a new naming convention. That's a separate operator decision; flag it but don't execute it.
- Does not modify `config/scripts/session-entry-scan.sh` or other downstream consumers automatically. Flag the dependency in the conversation; the operator decides whether to update those as part of the same session or separately.
- Does not re-run the full JTBD interview. If the operator wants that, they can explicitly say "redefine from scratch" and the skill switches to net-new mode (overwriting after confirmation).

## Net-new mode

Use when no seed exists at `config/sources/{slug}.md`. Runs the original interview + scaffold flow.

### JTBD-first interview

1. **What kind of raw input?** Free response.
2. **Where does it come from?** Tool, manual paste, hook, API.
3. **What does an instance look like?** Show an example file/payload.
4. **What does Claude do with it?** Turn into what — atlas note, action, observation?
5. **What's the trigger to process?** Operator confirmation, automatic on drop, session-entry surfacing.
6. **Retention?** Keep forever, archive after N days, delete after N days.

Then formalize:

7. **Folder location** — usually a subfolder under `system/`
8. **Naming convention** — date-prefixed slug, or other
9. **Required frontmatter** — `type`, `source-kind`, `date`, `processed`, `processed-into` always; what else?
10. **Move-after-processing?** `false` (default) or `_archive/{YYYY-MM}/`

### Scaffold

Create:

```
system/{folder}/                        # source folder
config/sources/{type}.md             # declaration
```

#### `config/sources/{type}.md` shape

```markdown
---
type: source-declaration
name: {type}
zone: system
location: system/{folder}/
naming: "{pattern}"
move-after-processing: false | "_archive/{YYYY-MM}/"
version: 1.0
---

# Source: {type}

## Format

{Frontmatter + body shape}

## Processing rule

{Step-by-step: read source → produce atlas/intel/gtd notes → flip processed flags → backlinks}

## Retention

{Keep forever, archive policy, delete policy}

## Detection

{When session-entry-scan or other skills surface this source for processing}
```

### Update session-entry-scan.sh

If the new source type lives in a new folder under `system/`, update `config/scripts/session-entry-scan.sh` to scan that folder for unprocessed items. (Or accept that V1 only scans `transcripts/`, `intake/`, `session-log/` and the operator manually invokes processing for V1.x source types.)

### Verify

- [ ] Processing rule is deterministic enough that Claude can execute it without ambiguity
- [ ] Retention policy is explicit
- [ ] Frontmatter shape includes `processed: false` and `processed-into: []`

## What NOT to do

- Don't define a source that overlaps with `transcript`, `session-log`, or `intake`.
- Don't write a processing rule that auto-fires without operator confirmation.
- Don't skip the retention section. Source files persist by default; deviations need explicit opt-in.

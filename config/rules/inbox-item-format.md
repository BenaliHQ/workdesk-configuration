# Inbox Item Format

Every note created in `gtd/inbox/` must include an **Operator review** H2 section directly under the H1 title. The section is where the operator writes their review notes; Claude reads those notes when the operator says "process the inbox."

The section uses plain markdown — H2 header, a single empty bullet point, horizontal rule divider. No callout syntax. This renders identically in Obsidian view and edit modes, so typing into the slot has zero friction.

## When this applies

- Creating any new note in `gtd/inbox/`
- Re-generating or updating an existing inbox item's body content (the slot stays; the body below the divider gets updated)
- Defining new source/signal/skill workflows that produce inbox items

## What to do

Open every inbox item with this exact shape:

```markdown
---
type: inbox-item
prefix: ACTION  # or REVIEW, CONTENT, QUESTION, AWARENESS
...
---
# [ACTION] Note title here

## Operator review

- 

---

## Context

Claude-generated body content...
```

**Rules for the slot:**

- The H2 header is always `## Operator review` — exact string, so the operator can grep for it and so future-Claude can detect it.
- The body of the empty slot is always a single empty bullet: `- ` (dash, space, nothing else). The operator types their note after the space.
- A horizontal rule (`---`) separates the operator-review section from the rest of the body. Always include it.
- The slot sits **directly under the H1 title** and **above the first body section**. Frontmatter → H1 → `## Operator review` → empty bullet → `---` → body sections.

**When the operator writes in the slot:**

- They type after the dash on the existing bullet line.
- The `## Operator review` header stays as the marker.
- The horizontal rule below stays as the divider.
- Multiple bullets are fine — just hit enter to add more. No `>` prefixes; type naturally.

**When Claude processes the inbox item:**

- Read the slot (the content between `## Operator review` and the `---` rule). Apply the operator's notes when resolving the inbox item.
- After processing, the inbox item gets archived, deleted, promoted to a project/action, or otherwise resolved per the operator's instruction. The slot doesn't get "cleared and reset" — the whole note moves out of `gtd/inbox/`.

## Why H2 + empty bullet + horizontal rule (not a callout or italic placeholder)

Earlier versions of this rule used (a) an `> [!info] Operator review` callout and (b) an italicized "write your notes here" placeholder paragraph. Both were dropped:

- **Callout dropped** — Obsidian's edit mode forces a `>` prefix on every line inside a callout, which makes typing notes feel like editing source code.
- **Italic placeholder dropped** — required the operator to select and delete the placeholder text before typing. A pre-existing empty bullet is friendlier: just click and type after the dash.

Plain H2 + empty bullet + horizontal rule renders the same in view and edit modes — zero friction.

Trade-off: the H2 is less visually distinct than a colored callout. The horizontal rule mitigates by giving a clear visual break between operator-review and Claude-generated content.

## What NOT to do

- Don't put the slot anywhere other than directly under the H1. The operator scans inbox items top-down; the slot has to be the first body section.
- Don't omit the horizontal rule. The divider is what makes the slot visually distinct without needing a callout.
- Don't switch back to a callout because "it looks better in view mode." View mode is one of two modes — edit mode is where the operator actually types.
- Don't omit the slot "because the operator hasn't written anything yet." The empty placeholder is the affordance — without it, the operator has nothing to type into.
- Don't write Claude commentary inside the slot. The slot is operator-only. Claude's notes belong below the horizontal rule.
- Don't move the operator's review notes into the body when resolving the item. Their notes stay in the slot as audit trail of what they asked for; the body reflects Claude's action.

## Source

- Operator instruction 2026-05-25 (initial): "I need a clear space that I write and review items. Then after I review and write, I will tell you and you can update from there. Like a text box or call out or something. Needs to be above the note content."
- Operator correction 2026-05-25 (same session, callout dropped): the original `> [!info]` callout format "looks weird when editing — looks good in view mode but when I click to edit it becomes a weird format for entering info." Switched to plain H2 + paragraph + horizontal rule for edit/view parity.
- Operator correction 2026-05-25 (same session, italic placeholder dropped): "rather than put the 'write your notes here' line, just put a single bullet point." Switched the placeholder from italicized prose to a single empty bullet (`- `) so the operator can click and type without first deleting placeholder text.

Related: [[matching]] § Inbox notifications (when to fire an inbox item at all); [[writing-style]] § Obsidian markdown patterns (general callout/kbd guidance — note that callouts are intentionally NOT used for inbox-review slots per this rule).

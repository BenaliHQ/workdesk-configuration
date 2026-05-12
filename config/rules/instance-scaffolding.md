# Instance Scaffolding

When scaffolding a new instance of any atlas object type (client, business, person, company, project, decision, meeting, etc.), follow two patterns: (1) check the legacy vault for existing context before asking the operator from scratch, and (2) handle matching-rule targets conditionally based on whether their schemas and folders exist yet.

These patterns surfaced during the byrd-building client scaffold (2026-05-09) and applied immediately to the business object workflow. They generalize across all object types.

## When this applies

- Creating a new instance of any object type defined in `config/objects/`
- Operator-initiated ("add a new client X", "scaffold Y as a business") OR detection-triggered (per the object type's detection clause)
- Whenever a `## Creating an instance` workflow in a `config/objects/{type}.md` runs

## What to do

### 1. Check legacy vault before asking from scratch

If `~/khalils-vault/{matching-path}/{slug}/` exists (operator's archive vault), read it BEFORE asking the operator to dictate from memory:

- Pull forward what's still relevant: identity, current state, primary contacts, recent activity, strategy artifacts (if applicable to the object type)
- **Treat legacy data as DRAFT, not gospel.** Surface findings to the operator and ask them to confirm or correct each piece — roles change, attributions shift, strategy evolves
- **Carry forward as plain text when target entities don't exist in the operating vault.** When legacy references entities (people, meetings, decisions, projects, companies) that don't yet exist in the operating vault, use **plain text — not wikilinks**. Wikilinks are reserved for entities that exist in the operating vault. Plain-text legacy references upgrade to wikilinks as the vault is populated. Per [[double-entry-knowledge]] — broken wikilinks are worse than plain text. The Sources section is the canonical legacy attribution; per-claim inline annotation should be light ("per legacy" tag) rather than heavy footnotes pointing at non-existent notes.
- **Verify before declaring done.** Run `bash config/scripts/check-wikilinks.sh <file-or-dir>` after carrying forward or after any instance creation/edit. The script reports any `[[wikilinks]]` whose target note or folder doesn't exist in the vault. Zero broken before sign-off; non-zero means a wikilink slipped past the discipline above and needs to be downgraded to plain text or have its target created.
- Capture explicit corrections (role changes, removed items, renames) so future updates don't reintroduce stale data
- Source-document the legacy origin per [[source-documentation]] — note which legacy file informed which fields

If no legacy folder exists, gather from operator-direct dictation.

**Why:** legacy vault has accumulated real context. Operator-validate-then-carry-forward is faster than rebuild-from-memory and reduces fabrication risk per [[no-fabrication]]. Validated 2026-05-09 with byrd-building (caught a stale CAD Review role attribution).

### 2. Conditional matching

The matching rule for an object type names other notes that update when an instance is created (e.g., creating a client updates `atlas/people/`, `atlas/companies/`, `atlas/businesses/`). For each matching target:

**Check whether** the target's object schema is defined (`config/objects/{target-type}.md` exists) AND the target folder has any instances yet.

**If the target's schema isn't defined OR the folder is empty:**
- Do NOT create a speculative stub — that fabricates schema we haven't agreed to
- Document the missing matching link as an explicit open item in the new instance's `_status.md` (e.g., "Create `atlas/{target}/{slug}` entry once {target}-object scaffolding runs.")
- Reference the missing entity as **plain text** in `_brief.md` — wikilinks would be broken per [[double-entry-knowledge]]

**When the target's schema and folder structure are ready (later session):**
- Apply the matching rule per the object type's `## Matching` section
- Convert plain-text references to wikilinks
- Remove the corresponding open item from `_status.md`

**Why:** prevents fabricating schemas we haven't designed. Open items track what's deferred so we can do clean fix-ups when the target schemas arrive. Validated 2026-05-09 with byrd-building (atlas/people, atlas/companies, atlas/businesses schemas all undefined; client folder shipped with explicit open items rather than speculative stubs).

## What NOT to do

- Do not skip the legacy check when a legacy folder exists. Operators have accumulated context there worth carrying forward.
- Do not blindly copy legacy data without operator validation. Legacy may be stale, partially wrong, or no longer authoritative.
- Do not create speculative stubs for matching-rule targets whose schemas aren't defined yet. Stubs fabricate schema and become technical debt.
- Do not create broken wikilinks (links to entities that don't exist). Use plain text per [[double-entry-knowledge]] until the target exists.
- Do not silently defer the matching gaps. Each gap gets an explicit open item in `_status.md` so it's auditable in future sessions.

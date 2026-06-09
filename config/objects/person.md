---
type: object-type-definition
name: person
zone: atlas
location: atlas/people/
shape: atomic
folder-structure: n/a
naming: kebab-slug ({first-name}-{last-name}; {first-name} when last unknown)
version: 1.2
---

# Object Type: person

A person is any individual the operator interacts with, tracked at varying depth based on relationship-type. The note is the senior-teammate cold-pickup doc for that person — opening it before a meeting, when drafting a message, when re-engaging after lost touch, or when deciding who to bring into a project should give immediate orientation in 60 seconds.

## Format

### Frontmatter (required)

```yaml
---
type: person
slug: {first-name}-{last-name}                    # kebab-case
relationship-type: client-contact | internal-team | personal-contact | external-contact
status: active                                     # active | inactive
primary-affiliation: {wikilink}                   # optional — the company/business that defines them right now
created: YYYY-MM-DD
last_updated: YYYY-MM-DD
---
```

### Shape — atomic

Single file at `atlas/people/{slug}.md`. No subfolder. Heavy contacts (long histories, hundreds of meetings) can lazy-graduate to container shape later if needed; V1 is atomic for everyone.

### Body conventions

- 10-section structure (in order): Identity · Relationship · Affiliations · Contact · Communication channels & cadence · Active engagements · Interactions · Personal · Notes & watch-outs · Sources. The note is the senior-teammate cold-pickup doc — populated enough that any new Claude session or human teammate can orient on who this person is and why they matter.
- Wikilinks to companies, businesses, clients, projects, meetings, and decisions per [[double-entry-knowledge]]. When a target note doesn't exist yet (e.g., `atlas/companies/` schema not defined), use plain text and log the gap as a [[matching]] open item.
- **Per-claim provenance via inline footnotes**, per [[source-documentation]]. Specific claims accumulated across meetings cite their source: `Champion for the selections workflow.[^1]` followed by `[^1]: [[atlas/meetings/2026-04-23-acme-corp-decisions]]`. The Sources section at the bottom captures the broader audit trail (what informed the note overall); inline footnotes attach to specific claims.
- Naming: `{first-name}-{last-name}` kebab-case. When last name is unknown, use `{first-name}` only; rename via Obsidian when the last name surfaces. Obsidian's **"Automatically update internal links"** setting (Settings → Files & Links) must be ON so the rename propagates wikilinks vault-wide. Without it, renames break references.
- Disambiguator for first-name collisions: add last-name or qualifier (e.g., `sarah-chen`, `sarah-rodriguez`).

## Source rule

Primary sources: meeting notes (transcripts → meetings), decision notes, operator-direct dictation. Secondary updates flow from:

- Meeting notes via [[matching]] — any meeting touching this person updates the Interactions section
- Decision notes — decisions involving this person link from Interactions
- Bookmark / `keep-markdown` references — when the same name appears repeatedly, surface as a person-note candidate
- Personal notes (`personal/`) — read-only references; surface candidate when name appears and isn't yet in `atlas/people/`
- Client and business folder scaffolding — their primary contacts and team members get person notes per [[matching]]

Per [[source-documentation]], every claim traces to a specific source — captured via inline footnotes for specific claims and via the Sources section for the broader audit trail.

## Detection

Claude proposes creating a new person note when ANY of these triggers fire AND operator confirms:

- A transcript surfaces a new named person with role context
- A `personal/` reference names a person not yet in `atlas/people/`
- A person is mentioned in ≥3 atlas notes (meetings, decisions, status updates) without an existing person note (raised from the legacy threshold of ≥2 — fewer false positives, still catches durable contacts)
- A new client folder is scaffolded — primary contacts get person notes per matching
- A new business folder is scaffolded — team members get person notes per matching
- The operator volunteers info ("let me tell you about X") in any session
- `keep-markdown` bookmarks reference the same name repeatedly

Always operator-confirmed. Auto-creation is never silent.

## Matching

When a new person note lands or is updated, the following notes update in the same processing pass per [[matching]]:

- **`atlas/companies/{slug}`** for each affiliation — created as stub if missing (conditional matching per [[instance-scaffolding]] until the `company` schema is defined; until then, plain text in Affiliations + open item logged)
- **`atlas/clients/{slug}`** if `relationship-type: client-contact` — primary-contacts list updated to wikilink this person
- **`atlas/businesses/{slug}`** if `relationship-type: internal-team` — team list updated to wikilink this person
- **Active project folders** that reference this person — engagement list updated
- **Meeting and decision notes** that mention this person — bidirectional wikilinks confirmed (the Interactions section here mirrors the references in those notes; the meeting's `attendees:` frontmatter wikilinks back)

When the note is first created, **backfill Interactions** by scanning existing meeting / decision / transcript notes for references to this person. This is a one-time hydration; thereafter [[matching]] keeps Interactions current.

When a person transitions status (active → inactive):
- `Notes & watch-outs` section reflects the transition with date + reason narrative
- Active engagements reviewed (most should clear out before inactive transition)

## Lifecycle

| Status | Meaning | Transitions |
|---|---|---|
| `active` | Currently engaged | → `inactive` (lost touch, deliberate retirement, or relationship faded) |
| `inactive` | No current engagement; covers lost-touch, archived, retired *(narrative carries the nuance)* | → `active` (re-engaged) |

Two-state matches the `business` type. Body narrative carries the nuance — search queries can filter `active` vs `inactive`; the body narrative answers "should I reach out?" The note is NEVER deleted when status flips. Historical reference preserved.

## Creating an instance

Triggered by: any detection-clause trigger + operator confirmation, OR operator says "add a person for X" / "scaffold X as a person."

### 0. Check legacy vault for existing context

Per [[instance-scaffolding]] — if `~/<primary-vault>/atlas/people/{slug}.md` exists, read it as DRAFT, surface findings, capture corrections before scaffolding.

### 1. Confirm the trigger

Identify which detection trigger applies. Capture briefly in the Sources section.

### 2. Gather required info

Ask operator for enough to populate the full note at minimum. The senior-teammate cold-pickup test applies. Accept partial answers; mark missing fields explicitly per [[no-fabrication]] — but do not silently skip required sections. If the operator declines a required field, capture as TBD with a one-line note about what's needed and defer to a follow-up turn.

**Frontmatter / structural fields:**

- **Slug** — `{first-name}-{last-name}` kebab-case. Use `{first-name}` only if last name unknown; flag rename as an open item when last name surfaces.
- **Relationship-type** — `client-contact` | `internal-team` | `personal-contact` | `external-contact`
- **Status** — almost always `active` for a new note
- **Primary affiliation** *(optional)* — the company/business that defines this person right now (wikilink)

**Note-section fields (required at scaffolding, except where noted):**

- **Identity facts** — full name (or first only if last unknown), current role + primary affiliation, 1-sentence framing
- **Relationship** — how operator and person are connected. Origin (who introduced, when met, primary context). Current frame for the relationship.
- **Affiliations** — company/business/team links with role(s) per affiliation. Multi-role on one line per affiliation (e.g., Dana: Owner; Director of Design at Acme Corp).
- **Contact** *(optional at scaffolding; structured per V1.2)* — three canonical fields: **Email**, **Mobile**, **Mailing address**. Plus optional "Other channels" addendum (LinkedIn, Telegram, Slack handle, etc.). Always preserve the three field labels even when values are TBD — this is what makes the section scannable and operator-fillable later. Inline annotations welcome (e.g., `Email: contractor@example.com *(preferred; never accesses acme-corp.com)*`). Per [[no-fabrication]], do not invent.
- **Communication channels & cadence** *(optional at scaffolding)* — preferred channels (Slack/email/text), meeting rhythm, response norms; populate what's known.
- **Active engagements** *(optional at scaffolding)* — projects/clients/businesses currently in flight involving this person; often empty for new contacts.
- **Personal** *(optional at scaffolding)* — family, hobbies, things to remember at the relational level; honor no-fabrication. Most populated for `personal-contact` relationship-type; varies for others.
- **Notes & watch-outs** *(optional at scaffolding)* — operator's running observations; accumulates over time.

**Auto-populated:**
- **Interactions** — backfilled at note creation by scanning existing meeting / decision / transcript notes for references; thereafter via [[matching]] when new meetings/decisions are processed.
- **Sources** — initial entry generated at scaffolding (operator-direct dictation; legacy reference if cross-referenced).

### 3. Create note

Atomic file at `atlas/people/{slug}.md`. **Start from the template at `config/templates/person-instance.md`** — it has the full V1.2 frontmatter shell and all 10 section headers pre-scaffolded with TBD placeholders. Copy the template, then populate from step 2's gathered information. Using the template prevents the "missing section header" drift that affected early person notes.

### 4. Populate frontmatter and content

Set `created` and `last_updated` to today. Set required frontmatter fields from step 2. Populate body sections per the structure below. Per [[no-fabrication]], write content ONLY from what the operator supplied or what legacy validates. Mark unknown sections with `TBD — populate when known` rather than omitting headers.

**`atlas/people/{slug}.md` body sections (in this order):**

1. **Identity** — 1-2 sentences; who they are, primary current frame
2. **Relationship** — how connected, origin context, current frame for the relationship
3. **Affiliations** — bullet list. Each entry: `[[atlas/companies/{slug}]]` (or `[[atlas/clients/{slug}]]` / `[[atlas/businesses/{slug}]]`) — role(s), separated by semicolons for multi-role at one affiliation. Plain text when target note doesn't exist; log open item per [[instance-scaffolding]] conditional matching.
4. **Contact** — three canonical labeled bullets (always present, even when values are TBD): **Email**, **Mobile**, **Mailing address**. Plus an optional "Other channels" addendum for LinkedIn / Telegram / Slack handle / etc. Inline annotations welcome (e.g., preferred-channel notes, last-verified dates). Template:

   ```markdown
   ## Contact
   
   - **Email:** TBD — populate when known
   - **Mobile:** TBD — populate when known
   - **Mailing address:** TBD — populate when known
   
   *Other channels:* (free-form; LinkedIn, Telegram, Slack, etc. — omit this line entirely if not applicable)
   ```
5. **Communication channels & cadence** — bullet list. Preferred channels, meeting rhythm, response norms.
6. **Active engagements** — bullet list of `[[atlas/clients/{slug}]]`, `[[atlas/businesses/{slug}]]`, or active project wikilinks. Empty until engagements exist.
7. **Interactions** — chronological list (newest first). Each entry: `**YYYY-MM-DD** — [[meeting-or-decision-slug]] — one-line context`. Backfilled at note creation; updated automatically via [[matching]].
8. **Personal** — family, hobbies, watch-outs at the relational level. Honor [[no-fabrication]] — empty is honest.
9. **Notes & watch-outs** — operator's running observations (working style, sensitivities, watch-outs). When claims emerge across meetings, attach inline footnotes per [[source-documentation]].
10. **Sources** — multi-entry list. Each entry: **{date or "Legacy"}** — kind of source (operator-direct dictation, meeting note, transcript, decision, legacy archive, etc.) — what it contributed.

### 5. Apply matching rule

Per [[matching]] and [[instance-scaffolding]] § Conditional matching, in the same pass:

- For each affiliation: confirm `atlas/companies/{slug}` exists; if not, plain text in Affiliations + log open item until `company` schema is defined
- If `client-contact`: update `atlas/clients/{slug}/_brief.md` Primary-contacts list to wikilink this person (replacing plain text where it appeared)
- If `internal-team`: update `atlas/businesses/{slug}/_brief.md` Team list to wikilink this person (replacing plain text)
- For each named active engagement: update the project/client/business `_status.md` if substantive new info surfaces
- Backfill Interactions: scan existing `atlas/meetings/`, `atlas/decisions/`, `system/transcripts/` for references to this person; populate the Interactions section with each match

### 6. Verify

- All wikilinks resolve per [[double-entry-knowledge]] — entities not yet created appear as plain text. **Run `bash config/scripts/check-wikilinks.sh atlas/people/{slug}.md` and confirm zero broken before declaring done.**
- Every claim traces to a source per [[source-documentation]] — inline footnotes for specific claims; Sources section for the broader trail
- No fabrication per [[no-fabrication]] — gaps marked explicitly with TBD, not filled with inference
- Required sections populated; optional sections preserve TBD headers
- Frontmatter `relationship-type` matches the body framing
- Affiliations list reflects current state (move past affiliations to body narrative under Relationship if relevant)

### 7. Confirm with operator

Show the file + opening lines of each populated section. Operator confirms or corrects before scaffolding the next entity.

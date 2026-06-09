---
type: object-type-definition
name: company
zone: atlas
location: atlas/companies/
shape: atomic
folder-structure: n/a
naming: kebab-slug
version: 1.0
---

# Object Type: company

A company is any external organization the operator references in their work — not operator-owned (those are `business`), not necessarily in active engagement (that's `client`). Companies are the identity layer that everything else hangs off: person `primary-affiliation`, client `company` field, meeting/decision references. Without a company note, those references dangle.

The note is the senior-teammate cold-pickup doc for that org — opening it before a meeting, when drafting a message, when re-engaging after lost touch, or when deciding whether to pursue an engagement should give immediate orientation in 60 seconds.

A company can also be a client. When that happens, both notes coexist: `atlas/companies/{slug}.md` (atomic — identity + relationship) and `atlas/clients/{slug}/` (container — engagement structure). The company note never moves or duplicates; the client folder layers engagement-specific structure on top.

## Format

### Frontmatter (required)

```yaml
---
type: company
slug: {first-name-last-name}                     # kebab-case
relationship-type: prospect | vendor | competitor | partner | peer | reference | former-client
status: active                                    # active | inactive
location: {city, state}                          # optional
founded: {YYYY}                                  # optional
website: {url}                                   # optional
created: YYYY-MM-DD
last_updated: YYYY-MM-DD
---
```

### Shape — atomic

Single file at `atlas/companies/{slug}.md`. No subfolder. When a company becomes a client, `atlas/clients/{slug}/` is created alongside per the `client` object type; the company note stays as the identity layer.

### Body conventions

- 10-section structure (in order): Identity · Industry & scale · Services / products / capabilities · Leadership & team · Notable clients / customers · Relationship to operator · Active engagements · Strategic context · Notes & watch-outs · Sources. The note is the senior-teammate cold-pickup doc — populated enough that any new Claude session or human teammate can orient on what this company is and why it matters.
- Wikilinks to people, businesses, clients, projects, meetings, and decisions per [[double-entry-knowledge]]. When a target note doesn't exist yet, use plain text and log the gap.
- **Per-claim provenance via inline footnotes**, per [[source-documentation]]. Specific claims accumulated across sources cite their source. The Sources section at the bottom captures the broader audit trail.
- Naming: kebab-case slug derived from the company name. Strip generic suffixes (LLC, Inc., Corp.) unless they're part of how the company is referred to in conversation. Disambiguator for collisions: add city, parent-org, or qualifier.

## Source rule

Primary sources: operator-direct dictation, meeting notes, website (via `defuddle`), client/person-note matching. Secondary updates flow from:

- Person notes via [[matching]] — when a person is affiliated with this company, their note's `primary-affiliation` links here
- Client folders — when a company becomes a client, `atlas/clients/{slug}/_brief.md` references this company note
- Meeting notes — mentions of this company link bidirectionally
- Decision notes — decisions involving this company link from the company's Active engagements section
- Bookmarks / `keep-markdown` references — repeated mentions surface a company-note candidate

Per [[source-documentation]], every claim traces to a specific source — inline footnotes for specific claims, Sources section for the broader trail.

## Detection

Claude proposes creating a new company note when ANY of these triggers fire AND operator confirms:

- A person note's `primary-affiliation` references an unknown company
- A new client folder is scaffolded — the company gets stubbed if missing per [[matching]]
- A meeting or decision note references the same company across ≥2 separate notes without an existing company note
- Operator volunteers info about an org ("let me tell you about X")
- `keep-markdown` bookmarks reference the same company name ≥3 times
- A bookmark / source-processing run identifies a company worth tracking (per [[source-processing-pattern]])

Always operator-confirmed. Auto-creation is never silent.

## Matching

When a new company note lands or is updated, the following notes update in the same processing pass per [[matching]]:

- **`atlas/people/{slug}`** for each affiliated person — `primary-affiliation` linked; Leadership & team section here lists those people via wikilinks
- **`atlas/clients/{slug}`** — if this company has a client folder (active or archived), bidirectional link confirmed
- **`atlas/businesses/{owner-business}`** — if relationship-type is `competitor`, the relevant business unit's strategic context may be touched (operator-discretion, not auto)
- **Meeting and decision notes** that reference this company — bidirectional wikilinks confirmed

When a company transitions `relationship-type` (e.g., prospect → former-client), the body narrative reflects the transition with date + reason. The note is NEVER deleted or moved.

When status transitions `active → inactive`:
- `Notes & watch-outs` section reflects the transition
- Active engagements section reviewed (most should clear out)

## Lifecycle

| Status | Meaning | Transitions |
|---|---|---|
| `active` | Currently relevant to operator's work | → `inactive` (no longer relevant; lost touch; archived) |
| `inactive` | No current relevance; historical reference | → `active` (re-engaged) |

`relationship-type` carries the qualitative nuance — a company can be `status: active` + `relationship-type: prospect` for years before transitioning to `relationship-type: former-client` without ever becoming `inactive`. The two fields are orthogonal.

Body narrative carries the rest. The note is NEVER deleted when status flips. Historical reference preserved.

## Creating an instance

Triggered by: any detection-clause trigger + operator confirmation, OR operator says "add a company for X" / "scaffold X as a company."

### 0. Check legacy vault for existing context

Per [[instance-scaffolding]] — if the operator's primary vault has `atlas/companies/{slug}.md`, read it as DRAFT, surface findings, capture corrections before scaffolding. Skip if no legacy note.

### 1. Confirm the trigger

Identify which detection trigger applies. Capture briefly in the Sources section.

### 2. Gather required info

Ask operator for enough to populate the full note at minimum. The senior-teammate cold-pickup test applies. Accept partial answers; mark missing fields explicitly per [[no-fabrication]] — but do not silently skip required sections.

**Frontmatter / structural fields:**

- **Slug** — kebab-case derived from company name; strip generic suffixes unless conversationally used
- **Relationship-type** — `prospect | vendor | competitor | partner | peer | reference | former-client`
- **Status** — almost always `active` for a new note
- **Location** *(optional)* — city, state
- **Founded** *(optional)* — year
- **Website** *(optional)* — URL

**Note-section fields:**

- **Identity** *(required)* — 1-2 sentences: what they are, where based, when founded (if known), who founded (if relevant). Sufficient to orient a new reader cold.
- **Industry & scale** *(optional at scaffolding)* — sector, rough size signals (revenue tier, headcount, locations). Preserve header with `TBD — populate when known` if unknown.
- **Services / products / capabilities** *(optional at scaffolding)* — what they sell or do. For service firms, list their service lines. For product companies, their core products.
- **Leadership & team** *(optional at scaffolding)* — wikilinks to `atlas/people/{slug}` when affiliated people have notes; plain text otherwise. Tiered by seniority where helpful.
- **Notable clients / customers** *(optional at scaffolding)* — relevant for B2B firms. Plain text or wikilinks to other `atlas/companies/{slug}` when those companies are tracked.
- **Relationship to operator** *(required)* — how we know them, who introduced if anyone, what stage of relationship, current context. This is what makes the note operationally useful.
- **Active engagements** *(optional at scaffolding)* — wikilinks to `atlas/clients/{slug}`, active projects, meetings, decisions involving this company. Empty if reference-only.
- **Strategic context** *(optional at scaffolding)* — what's going on with them now (transition, growth, market shift, leadership change). Frequently takes time to crystallize; preserve header with TBD if unknown.
- **Notes & watch-outs** *(optional at scaffolding)* — operator's running observations. Accumulates over time.

**Auto-populated:**
- **Sources** *(required)* — multi-entry list. Each entry: `**{date or "Legacy"}** — kind of source (operator-direct dictation, defuddle, meeting note, legacy archive, etc.) — what it contributed`. Provenance compounds as the note grows.

### 3. Create note

Atomic file at `atlas/companies/{slug}.md`. **Start from the template at `atlas/companies/_template.md`** — it has the full frontmatter shell and all 10 section headers pre-scaffolded with TBD placeholders. Copy the template, then populate from step 2.

### 4. Populate frontmatter and content

Set `created` and `last_updated` to today. Set required frontmatter fields from step 2. Populate body sections per the structure above. Per [[no-fabrication]], write content ONLY from what was supplied or what defuddle/legacy validates. Mark unknown sections with `TBD — populate when known` rather than omitting headers.

### 5. Apply matching rule

Per [[matching]] and [[instance-scaffolding]] § Conditional matching, in the same pass:

- For each affiliated person already in `atlas/people/`: update their `primary-affiliation` and Affiliations section to wikilink this company
- If this company has an active client folder: confirm bidirectional link from `atlas/clients/{slug}/_brief.md`
- For each named meeting/decision: confirm bidirectional wikilinks

### 6. Verify

- All wikilinks resolve per [[double-entry-knowledge]] — entities not yet created appear as plain text. **Run `bash config/scripts/check-wikilinks.sh atlas/companies/{slug}.md` and confirm zero broken before declaring done.**
- Every claim traces to a source per [[source-documentation]]
- No fabrication per [[no-fabrication]] — gaps marked explicitly with TBD
- Required sections populated; optional sections preserve TBD headers
- Frontmatter `relationship-type` matches the body framing

### 7. Confirm with operator

Show the file + opening lines of each populated section. Operator confirms or corrects.

## What NOT to do

- Don't create a company note for operator-owned entities — those are `business`.
- Don't create a company note for a client without ALSO ensuring `atlas/clients/{slug}/` exists per the `client` schema.
- Don't conflate `status` with `relationship-type`. Status is binary (active/inactive); relationship-type carries qualitative nuance.
- Don't auto-create. Detection clauses propose; operator confirms.
- Don't fabricate affiliations or founding dates. Use defuddle on the website and cite the source.

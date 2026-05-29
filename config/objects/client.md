---
type: object-type-definition
name: client
zone: atlas
location: atlas/clients/
shape: container
folder-structure: custom (8-item — see Format below)
naming: kebab-slug
version: 1.0
---

# Object Type: client

A client is a company we have an active paid engagement with — agreement in place, deliverables we provide, recurring contact. Distinct from `company` (the generic entity, which may or may not be a client) and from `business` (entities the operator owns).

The client folder is the operator's working surface for everything tied to a specific engagement: status, deliverables, terms, in-flight projects, notes, reference material. Designed so Claude can pick up full client context like a team member would — for deliverable work, strategy, admin, meeting prep, and correspondence drafting.

## Format

### Frontmatter (required)

```yaml
---
type: client
slug: {kebab-slug}
status: active                  # active | paused | archived
business-owner: benali          # which Benali entity owns this engagement: benali | growthkits | demandcast
company: {company-slug}         # links to atlas/companies/{slug} — stub created if missing
start-date: YYYY-MM-DD          # when engagement began
created: YYYY-MM-DD             # when this client folder was created
last_updated: YYYY-MM-DD        # last meaningful update to any file in this folder
---
```

### Folder structure (container, 8-item)

```
atlas/clients/{slug}/
├── _brief.md          # who they are, why we're engaged, primary contacts (wikilinks to atlas/people/)
├── _status.md         # current phase, open items, recent activity (meeting links here)
├── deliverables.md    # what we're producing, current state
├── terms.md           # agreement, payment terms, scope, contract notes
├── notes/             # ad-hoc client-level captures (misc thoughts, drafts, brainstorms not tied to a project)
├── reference/         # source material from or about them (research, docs they shared, industry context)
├── projects/          # active client projects, each its own per-project-accounting structure
└── _archive/          # retired material (old terms, ended deliverables, paused projects)
```

`notes/`, `reference/`, and `_archive/` start empty; populated as the engagement runs. `projects/` may be empty if the engagement is retainer-only without discrete projects.

### Body conventions

- `_brief.md` — 10-section structure (in order): Who they are · Origin · Engagement model · Why we're engaged · Primary contacts (their team) · Assigned team · Active work · Working style · Strategic context · Sources. The brief is the senior-team-member onboarding doc — populated enough that any new Claude session or human teammate can pick up cold.
- `_status.md` — narrative status + recent meetings list (each `[[atlas/meetings/{slug}]]`) + open items
- People are captured via wikilinks to `atlas/people/`, NOT a separate `team.md` file. Both their team (their employees) and the assigned team (our side) reference `atlas/people/` entries when they exist.
- Meetings stay in `atlas/meetings/`; client folder only holds links

## Source rule

Primary source: operator-direct knowledge of the engagement. Secondary updates flow from:

- Meeting notes via the [[matching]] rule (any meeting touching this client updates `_status.md` recent activity)
- Decision notes (decisions affecting this client get logged to `atlas/decisions/` and linked from `_status.md`)
- Project status files inside `projects/` roll up to client `_status.md` open items

Per [[source-documentation]], every claim in the client folder should trace to a specific source — meeting note, decision, or operator-direct entry.

## Detection

Claude proposes creating a new client folder when ANY of these triggers fire AND operator confirms:

- An agreement (SOW, MSA, retainer contract) is signed with a company
- A payment is received from a company without an existing client folder
- Operator gives verbal confirmation that a new engagement has started ("we're working with X now")

The detection is operator-confirmed because PMF-exploration variability means engagements take many shapes; Claude shouldn't auto-create without check.

## Matching

When a new client lands, the following notes update in the same processing pass per [[matching]]:

- **`atlas/people/{slug}`** for each primary contact — created if missing, updated with role + client link if existing
- **`atlas/companies/{company-slug}`** — the company entity gets linked; created as a stub if missing (the client IS a company; the company note may have already existed as a prospect/lead)
- **`atlas/businesses/{business-owner}`** — the Benali entity owning this engagement gets its `_status.md` updated to reflect the new client

When a client transitions status (active → paused, paused → archived):

- `_status.md` reflects the transition with date + reason
- `atlas/businesses/{business-owner}` updates engagement count if relevant
- Active projects in `projects/` get reviewed for status implications (paused client → paused projects?)

## Lifecycle

| Status | Meaning | Transitions |
|---|---|---|
| `active` | Current paid engagement; deliverables in flight | → `paused` (temp pause) or → `archived` (engagement ended) |
| `paused` | Temporarily paused, expected to resume | → `active` (resumed) or → `archived` (didn't resume) |
| `archived` | Engagement ended | terminal state; folder stays for historical reference |

Prospect/lead/qualifying states do NOT live here — those belong in `atlas/companies/` with a `relationship: prospect` or similar field. A company becomes a client only when one of the detection triggers fires.

When a client moves to `archived`:

- Status updated with end-date + reason in `_status.md`
- All active projects under `projects/` get reviewed (most move to `_archive/`)
- The folder is NOT deleted or moved — historical reference preserved

## Creating an instance

Triggered by: operator says "add a new client", "scaffold X as a client", "we just signed Y", or the detection clause fires (agreement signed / payment received / verbal confirmation).

### 0. Check legacy vault for existing context

Per [[instance-scaffolding]] — if `~/khalils-vault/atlas/clients/{slug}/` exists, read it as DRAFT, surface findings to operator, capture corrections before scaffolding. Skip if no legacy folder.

### 1. Confirm the trigger

Identify which detection trigger applies and capture in `_brief.md` narrative (e.g., "engagement began with verbal confirmation 2024-09-12; agreement signed 2024-10-01"). If none of the three triggers can be confirmed, pause and ask the operator before proceeding — do not scaffold a client speculatively.

### 2. Gather required info

Ask operator for enough to populate the full brief at minimum. The principle: a senior teammate should be able to pick up the engagement cold from the brief alone. Accept partial answers; mark missing fields explicitly per [[no-fabrication]] — but do not silently skip required brief sections. If the operator declines a field in the moment, capture it as an explicit TBD with a one-line note about what's needed and defer to a follow-up turn.

**Frontmatter / structural fields:**

- **Slug** — kebab-case derived from the company name (e.g., "Byrd Building Co" → `byrd-building`). Confirm if non-obvious.
- **Business-owner** — which Benali entity owns this engagement: `benali` | `growthkits` | `demandcast`
- **Company slug** — should match an existing `atlas/companies/{slug}` entry if one exists; otherwise note "stub will be created"
- **Start-date** — when the engagement began (rough date acceptable; `TBD` accepted)
- **Initial status** — almost always `active` for a new client; `paused` only if paused-from-the-start

**Brief-section fields (required at scaffolding, except where noted):**

- **Identity facts** (Who they are) — industry, rough size, business model
- **Origin** — who referred / how we got connected, what they hired us for. Capture even when the answer is "no referrer, inbound" — that's a valid answer.
- **Engagement model** — type (retainer / project / hybrid), cadence (meeting rhythm), scope (what's covered). Fuzzy scope is acceptable as long as it's captured honestly with a note that it needs tightening.
- **Why we're engaged (JTBD)** — the underlying problem the operator is being hired to solve, in operator's words
- **Primary contacts (their team)** — names + roles for each direct contact at the client. Per [[no-fabrication]], do not invent last names if only first names are given. Distinguish referrers/connectors from contacts (referrers belong in Origin, not here).
- **Assigned team** — who on the operator's side is on this engagement, and what each one does on it (primary, supporting, account management, not-yet-started, etc.)
- **Working style** — on-site vs remote, meeting structure (mixed group vs one-function-at-a-time), known communication norms or watch-outs. Sub-items operator can't answer get individual TBDs, not a section-wide skip.
- **Active work** — current focus, what's in flight right now
- **Strategic context** — *optional at scaffolding.* What's going on in their business that frames the engagement (growth phase, leadership transition, market pressure). Frequently takes a few meetings to crystallize; section should exist with `TBD — populate when known` rather than be omitted.

### 3. Create folder structure

```
atlas/clients/{slug}/
├── _brief.md          # populated in step 4
├── _status.md         # populated in step 4
├── deliverables.md    # populated in step 4
├── terms.md           # populated in step 4
├── notes/             # empty directory
├── reference/         # empty directory
├── projects/          # empty unless an active project is named at scaffolding time
└── _archive/          # empty directory
```

### 4. Populate frontmatter and content

For `_brief.md` and `_status.md`:
- Set `created` and `last_updated` to today
- Set `status`, `business-owner`, `company`, `start-date`, `slug` from step 2
- Per [[no-fabrication]], write content ONLY from what the operator supplied. Mark unknown fields explicitly (e.g., "Primary contact role: not captured at scaffolding").

**`_brief.md` body sections (in this order):**

1. **Who they are** — industry, size, business model (1-3 sentences)
2. **Origin** — how we got connected, who referred (or "inbound — no referrer" if applicable), what they hired us for specifically
3. **Engagement model** — bullet list with **Type**, **Owner business** (wikilink to `atlas/businesses/{slug}`), **Cadence**, **Scope**. Capture fuzzy scope honestly with a note that it needs tightening rather than omitting.
4. **Why we're engaged** — the JTBD they hire us for, in operator's voice
5. **Primary contacts (their team)** — bullet list, names + roles. Use `[[atlas/people/{slug}]]` wikilinks if person notes exist; plain text otherwise — do NOT create broken wikilinks per [[double-entry-knowledge]]. Distinguish referrers (Origin) from contacts (here).
6. **Assigned team** — bullet list, who on the operator's side is on the engagement and what each does (primary / supporting / account management / not-yet-started). Use wikilinks to `atlas/people/` if available; plain text otherwise.
7. **Active work** — what's in flight; current focus. May reference legacy projects with explicit "not recreated as folders unless reactivated" note where relevant.
8. **Working style** — bullet list. On-site/remote, meeting structure, communication norms. Sub-items the operator can't answer at scaffolding stay as individual TBDs.
9. **Strategic context** — *optional at scaffolding.* What's going on in their business that frames the engagement. If TBD, leave the section header in place with a `TBD — populate when known` note so the structure is preserved.
10. **Sources** — multi-entry list. Each entry: **{date or "Legacy"}** — kind of source (operator-direct dictation, meeting note, transcript, decision, legacy archive, etc.) — what it contributed (parenthetical summary). Provenance compounds as the brief grows; new sources are appended, not blended into existing entries.

**`_status.md` body sections:**
- Current state (active phase, what's in flight)
- Recent activity (last 14 days; meeting links via `[[atlas/meetings/{slug}]]`)
- Open items (decisions pending, action items, things being tracked)

**`deliverables.md` and `terms.md`:** populate if operator supplied detail; otherwise create with `TBD — not yet captured` and note where the info will come from when known.

### 5. Apply matching rule

In the SAME pass per [[matching]] and [[instance-scaffolding]] § Conditional matching. For each target below, check whether the target's schema is defined and the folder has instances. If not, document open item in `_status.md` + use plain text in `_brief.md`. If yes, apply:

- For each primary contact named in step 2: create or update `atlas/people/{contact-slug}` with role + wikilink to this client folder
- Create or update `atlas/companies/{company-slug}` — stub with bare frontmatter (`type: company`, `slug`, `created`) if missing; full update if existing
- Update `atlas/businesses/{business-owner}/_status.md` — add this client under the active-engagements list

### 6. Verify

- All wikilinks resolve per [[double-entry-knowledge]] — entities not yet created should appear as plain text, or get stubs in step 5. **Run `bash config/scripts/check-wikilinks.sh atlas/clients/{slug}` and confirm zero broken before declaring done.**
- Every claim traces to a source per [[source-documentation]] — operator-direct knowledge from this scaffolding session, captured in the trigger context section
- No fabrication per [[no-fabrication]] — gaps are marked explicitly, not filled with inference

### 7. Confirm with operator

Show the file tree + opening lines of each populated file. Operator confirms or corrects before scaffolding the next entity.

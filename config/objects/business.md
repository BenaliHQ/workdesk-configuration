---
type: object-type-definition
name: business
zone: atlas
location: atlas/businesses/
shape: container
folder-structure: custom (16-item — see Format below)
naming: kebab-slug
version: 1.0
---

# Object Type: business

A business is an entity the operator owns and operates (or is actively building toward). Distinct from `client` (companies we're paid to work for) and from `company` (generic external entities). Businesses are the operator's own product/service vehicles — for example: acme-consulting, acme-studio, acme-media. The schema also supports businesses that are ideas-not-yet-started, via the `inactive` status.

The business folder is a focus-discipline tool: it isolates the business's identity (mission, brand, ICP, offerings, goals, org) from client work or personal projects, so Claude can pick up business context without contamination. When the operator works on an Acme Consulting project, the AI sees Acme Consulting context cleanly.

## Format

### Frontmatter (required)

```yaml
---
type: business
slug: {kebab-slug}
status: active                  # active | inactive (covers both ideas-not-yet-started AND wound-down)
incorporated: YYYY-MM-DD        # legal entity formation date (TBD if not yet incorporated or unknown)
created: YYYY-MM-DD             # when this folder was created
last_updated: YYYY-MM-DD        # last meaningful update to any file in this folder
---
```

### Folder structure (container, 16-item)

```
atlas/businesses/{slug}/
├── _brief.md          # overview, mission, current focus, primary people
├── _status.md         # current state, recent activity, open items, active engagements
├── offerings.md       # services / products / what we sell
├── pricing.md         # pricing structure, packages, rates
├── icp.md             # ideal customer profile
├── competition.md     # competitive landscape, alternatives, comparable offerings
├── positioning.md     # value prop, positioning statement, differentiators
├── goals.md           # current goals (quarterly, annual, multi-year)
├── brand-voice.md     # voice guidelines, tone, language conventions
├── brand-design.md    # visual identity, logo references, design system
├── org-chart.md       # who's involved, roles, reporting
├── tools.md           # tools the business uses (software, services, vendors)
├── notes/             # ad-hoc business-level captures
├── reference/         # source material, research
├── projects/          # active business projects (each its own per-project-accounting structure)
└── _archive/          # retired material
```

Lazy-create as needed: `processes.md` (operating procedures, SOPs). Add when content emerges; not pre-scaffolded.

### Body conventions

- `_brief.md` — 12-section structure (in order): Mission · Vision · Direction · Values · Brand overview · Origin & history · Operating model · Team · Active work · Legacy work · Strategic context · Sources. The brief is the senior-team-member onboarding doc — populated enough that any new Claude session or human teammate can pick up cold. Identity sections (Mission/Vision/Direction/Values) cluster at the top; the brief carries TLDRs and points to deeper strategy files (`offerings.md`, `goals.md`, `brand-voice.md`, etc.) for full detail.
- `_status.md` — narrative status + recent activity + open items + **active engagements** (clients owned by this business, with wikilinks to `atlas/clients/{slug}`)
- Strategy files (`offerings.md`, `icp.md`, `goals.md`, `brand-*.md`) — narrative; no enforced structure. The brief surfaces a TLDR + pointer; full detail lives in the file.
- Active project work links from `projects/` to the business `_status.md`
- Decisions affecting the business get logged to `atlas/decisions/` and linked from `_status.md`

## Source rule

Primary source: operator-direct knowledge — businesses are owned and operated by the operator. Secondary updates flow from:

- Active projects under `projects/` (status rolls up to business `_status.md`)
- Client engagements where `business-owner: {slug}` (each client folder updates this business's active-engagements list per [[matching]])
- Decisions in `atlas/decisions/` that name this business
- Meeting notes that touch business strategy

Per [[source-documentation]], every claim in the business folder should trace to a specific source — meeting note, decision, operator-direct entry, or explicit operator statement of mission/strategy.

## Detection

Manual operator-initiated. Claude does NOT propose creating a business folder from external triggers. The operator decides when an entity becomes a tracked business.

The trigger can be any of:
- "I'm starting/launching a new business called X"
- "Let's track Y as a business — I want to start working toward it"
- "Add Z as a business; it's an idea I'm exploring"

For idea-phase businesses (no incorporation, no customers yet), `status: inactive` is the right state.

## Matching

When a new business is added, the following notes update in the same processing pass per [[matching]]:

- **`atlas/people/{slug}`** for each primary person — created or updated with role + business wikilink
- **`atlas/clients/{slug}/_brief.md`** for each existing client where `business-owner: {this business}` — confirm the link is bidirectional
- **`atlas/decisions/`** entries that name this business — backlinked from `_status.md`
- **`atlas/projects/{slug}`** under the business's `projects/` subfolder — only if active projects already exist

When a business transitions status (active → inactive, or inactive → active):
- `_status.md` reflects the transition with date + reason
- All active projects under `projects/` get reviewed for status implications
- All clients with `business-owner: {this slug}` get reviewed (an inactive business may need its clients reassigned or paused)

## Lifecycle

| Status | Meaning | Transitions |
|---|---|---|
| `active` | Currently operating business — generating revenue, doing work, or building toward launch with momentum | → `inactive` (paused, sunset, or idea-deferred) |
| `inactive` | Not currently operating. Covers both: (a) ideas not yet started, (b) wound-down businesses, (c) suspended/folded businesses | → `active` (started, restarted, or revived) |

The frontmatter `status` doesn't distinguish idea-phase from wound-down — that nuance lives in `_status.md` body narrative. Acceptable trade-off because:
- It's a personal vault; scan time is fine
- Single-state inactive avoids decision-paralysis on "is this paused or archived?" mid-debate (e.g., Acme Studio 2026-05)

The folder is NOT deleted when status flips to inactive — historical reference preserved.

## Creating an instance

Triggered by: operator says "add a new business", "scaffold X as a business", or "track Y as an idea". Manual; no automatic detection.

### 0. Check legacy vault for existing context

Per [[instance-scaffolding]] — if the operator's primary vault has `atlas/businesses/{slug}/`, read it as DRAFT, surface findings to operator, capture corrections before scaffolding. Skip if no legacy folder.

### 1. Confirm the trigger

Identify why this business is being added now: starting fresh, migrating from legacy, capturing an idea, etc. Capture briefly in `_brief.md` narrative.

### 2. Gather required info

Ask operator for enough to populate the full brief at minimum. The principle: a senior teammate should be able to pick up the business cold from the brief alone. Accept partial answers; mark missing fields explicitly per [[no-fabrication]] — but do not silently skip required brief sections. If the operator declines a required field in the moment, capture it as an explicit TBD with a one-line note about what's needed and defer to a follow-up turn.

**Frontmatter / structural fields:**

- **Slug** — kebab-case (e.g., `acme-consulting`, `acme-studio`, `acme-media`)
- **Status** — `active` or `inactive` (idea-phase OR wound-down)
- **Incorporated date** — legal entity formation date if known (TBD if pre-incorporation or unknown)

**Brief-section fields (required at scaffolding, except where noted):**

- **Mission** — 1-2 sentences in operator's words, what the business does
- **Vision** — *optional at scaffolding.* Future-state north star; often takes time to articulate. If TBD, leave the section header in place with a `TBD — populate when articulated` note.
- **Direction** — *optional at scaffolding.* 1-3 year arc; concrete forward path. Same TBD discipline.
- **Values** — *optional at scaffolding.* What the business believes about how the work should be done. Same TBD discipline.
- **Brand overview** — *optional at scaffolding.* TLDR pointer to `brand-voice.md` and `brand-design.md`. If brand files are themselves TBD, brief notes this.
- **Origin & history** — how the business started, key pivots that shaped its current shape
- **Operating model** — TLDR of the service or product model (e.g., "four pillars" for acme-consulting). Brief carries the TLDR; `offerings.md` carries the detail.
- **Team** — operator + partners/contractors/contributors, with roles. Distinguish status flags where relevant (e.g., "moved from X 2026-04-20"; "assigned but hasn't started").
- **Active work** — current focus narrative + active engagements (clients) + active business projects. One coherent section, not three.
- **Legacy work** — *optional if no legacy.* Past projects/initiatives that aren't being recreated as folders unless reactivated. List with brief one-line descriptions.
- **Strategic context** — *optional at scaffolding.* Macro forces (market, competitive position, portfolio fit) that frame this business right now.
- **Existing legacy artifacts** — separate from the "Legacy work" brief section: this is a check during step 0 ([[instance-scaffolding]]) for whether brand voice, ICP, or offerings have authoritative legacy versions worth carrying forward verbatim.

### 3. Create folder structure

```
atlas/businesses/{slug}/
├── _brief.md          # populated in step 4
├── _status.md         # populated in step 4
├── offerings.md       # populated in step 4 (or TBD placeholder)
├── pricing.md         # populated in step 4 (or TBD placeholder)
├── icp.md             # populated in step 4 (or TBD placeholder)
├── competition.md     # populated in step 4 (or TBD placeholder)
├── positioning.md     # populated in step 4 (or TBD placeholder)
├── goals.md           # populated in step 4 (or TBD placeholder)
├── brand-voice.md     # populated in step 4 (or TBD placeholder)
├── brand-design.md    # populated in step 4 (or TBD placeholder)
├── org-chart.md       # populated in step 4 (or TBD placeholder)
├── tools.md           # populated in step 4 (or TBD placeholder)
├── notes/             # empty directory
├── reference/         # empty directory
├── projects/          # empty unless active projects exist
└── _archive/          # empty directory
```

### 4. Populate frontmatter and content

For `_brief.md` and `_status.md` (per [[per-project-accounting]] — these MUST have meaningful content, not hollow placeholders):
- Set `created` and `last_updated` to today
- Set `status`, `incorporated`, `slug` from step 2
- Per [[no-fabrication]], write content ONLY from what the operator supplied. Mark unknown fields explicitly.

**`_brief.md` body sections (in this order):**

1. **Mission** — 1-2 sentences in operator's words, what the business does
2. **Vision** — future-state north star *(optional at scaffolding; preserve the section header with a `TBD — populate when articulated` note if not yet articulated)*
3. **Direction** — 1-3 year arc, concrete forward path *(optional at scaffolding; brief carries TLDR + pointer to `goals.md` for detail)*
4. **Values** — what the business believes about how the work should be done *(optional at scaffolding)*
5. **Brand overview** — TLDR + pointer to `brand-voice.md` (voice / language) and `brand-design.md` (visual identity) *(optional at scaffolding)*
6. **Origin & history** — how it started, key pivots that shaped current shape
7. **Operating model** — TLDR of service or product model. Brief carries the structure; `offerings.md` carries the detail. Use a sub-heading or rename pattern (e.g., "Operating model — four pillars") if the model has a named shape.
8. **Team** — bullet list, operator + collaborators with roles. Distinguish status flags where relevant ("moved from X", "assigned but hasn't started", contractor vs employee, etc.). Use `[[atlas/people/{slug}]]` wikilinks if person notes exist; plain text otherwise.
9. **Active work** — current focus narrative + active engagements (clients) + active business projects. One coherent section; references `[[atlas/clients/{slug}]]` wikilinks for engagements.
10. **Legacy work** — past projects/initiatives not recreated as folders unless reactivated. List with one-line descriptions. Section omitted if no legacy.
11. **Strategic context** — macro forces (market, competitive position, portfolio fit) framing the business right now *(optional at scaffolding; preserve the section header with `TBD — populate when relevant` if empty)*
12. **Sources** — multi-entry list. Each entry: **{date or "Legacy"}** — kind of source (operator-direct dictation, decision, legacy archive, etc.) — what it contributed (parenthetical summary). Provenance compounds; new sources are appended, not blended into existing entries.

**`_status.md` body sections:**
- Current state (operating phase, what's in flight)
- Recent activity (last 14 days; meeting/decision links if relevant)
- Open items (decisions pending, action items, things being tracked)
- Active engagements (clients owned by this business — wikilinks to `atlas/clients/{slug}`)

**Strategy files** (`offerings.md`, `icp.md`, `goals.md`, `brand-voice.md`, `brand-design.md`, `org-chart.md`):
- Populate from legacy if validated, OR from operator-direct dictation, OR with TBD placeholder if not yet captured
- A TBD placeholder is acceptable for these (unlike _brief.md/_status.md) because they're strategy documents that evolve; operator iterates on them as content emerges
- Mark TBD content with explicit "TBD — to be authored by operator" so future Claude sessions don't mistake placeholder for content

### 5. Apply matching rule

In the SAME pass per [[matching]] and [[instance-scaffolding]] § Conditional matching. For each target below, check whether the target's schema is defined and the folder has instances. If not, document open item in `_status.md` + use plain text in `_brief.md`. If yes, apply:

- For each primary person named in step 2: create or update `atlas/people/{slug}` with role + wikilink to this business
- For each existing client where `business-owner: {this slug}`: confirm the bidirectional link in their `_brief.md`
- For each existing decision in `atlas/decisions/` naming this business: backlink from `_status.md`
- For active projects: ensure each lives under `projects/` with the per-project-accounting structure

### 6. Verify

- All wikilinks resolve per [[double-entry-knowledge]] — entities not yet created should appear as plain text, or get stubs in step 5. **Run `bash config/scripts/check-wikilinks.sh atlas/businesses/{slug}` and confirm zero broken before declaring done.**
- Every claim traces to a source per [[source-documentation]] — operator-direct or legacy-validated
- No fabrication per [[no-fabrication]] — gaps are marked explicitly with TBD, not filled with inference
- `_brief.md` and `_status.md` have meaningful content (not hollow) per [[per-project-accounting]]

### 7. Confirm with operator

Show the file tree + opening lines of each populated file. Operator confirms or corrects before scaffolding the next entity.

# Type Scaffolding (Schema Design)

When defining a new type — atlas object, source, signal, tool, practice, rule, or any other schema applied to many instances — be intentional about (a) what every instance must have at scaffolding, and (b) the structure within each item. A type definition is not a folder layout; it's a contract. Every future instance inherits whatever discipline (or lack of it) is baked into the type.

This rule applies at type *design* time. The sister rule [[instance-scaffolding]] applies at instance *creation* time — once a type exists, instance-scaffolding governs how new instances of that type get built. The pattern surfaced 2026-05-09 when the operator restructured `client` and `business` object briefs and the same design discipline (required vs optional, ask-enough-to-fill, preserve-headers-when-TBD) emerged twice — naming it once here so future `/define-*` work doesn't have to rediscover it.

## When this applies

- Defining a new type via any `/define-*` meta-skill: `/define-object`, `/define-source`, `/define-signal`, `/define-tool`, `/define-practice`, `/define-rule`
- Revising an existing type's schema after instance experience surfaces gaps (e.g., the 2026-05-09 client + business brief restructures)
- Promoting a learning to a type's `## Body conventions`, `## Creating an instance`, or analogous workflow section

## What to do

### 1. Design scaffolding content deliberately

For every instance of this type, define what MUST exist at creation, what's optional, and what's deferrable. Be explicit, not implicit:

- **Frontmatter contract.** List required frontmatter fields with allowed values (enums where applicable: `status: active | paused | archived`) and defaults. Frontmatter is the type's structured-data layer; design it as carefully as the body sections.
- **Lifecycle and state transitions.** When the type has states, define the transitions explicitly. A `## Lifecycle` table with rows-per-state earns its place in the type definition.
- **Detection clause.** When the type can be triggered automatically (operator-confirmed or otherwise), specify the triggers explicitly. When it's manual-only, say so. Don't leave detection ambiguous.
- **Required vs optional files and sections.** List required files and required sections within each file. Flag optional sections with `*optional at scaffolding.*` (or equivalent) and a sentence on why — preserve their headers in instances with a `TBD — populate when known` note rather than omitting them.
- **Lazy-create vs pre-scaffold.** Some files merit pre-scaffolding at instance creation; others should be lazy-created when content emerges (e.g., the `business` type's `processes.md`). Mark each file's mode in the schema.
- **Required-info questions.** For each required field, define the question the meta-skill workflow must ask of the operator at scaffolding time. Required-but-not-asked is the worst failure mode: instances ship hollow because the workflow didn't surface the field.
- **Senior-teammate cold-pickup test.** If a new Claude session or human teammate opens an instance fresh, can they orient in 60 seconds? If not, the scaffolding content is missing something.

Don't conflate "files exist" with "content is captured." A folder of empty files is not a scaffolded instance.

### 2. Design item structure deliberately

For every file (or component) within an instance, define its shape:

- List sections in order, with a one-line purpose per section. A section without a purpose accumulates lint.
- Specify the format per section: bullet list, narrative paragraph, table, frontmatter field
- Note where TLDR-vs-detail splits live. A brief carries TLDRs and points to deeper files (e.g., `_brief.md` carries operating-model TLDR; `offerings.md` carries detail). Be explicit about which file owns what depth.
- Mark required-vs-optional per section. Optional sections still get their header preserved in instances; only the body is deferred.

Don't leave files as "narrative free-form" by default. Free-form is the worst-case baseline; durable types do better.

### 3. Validate by instance, then propagate to schema

The schema is downstream of real instance experience. Workflow:

1. Define a draft schema with intentional scaffolding + item structure
2. Apply it to a real instance — operator-sourced, not synthetic
3. Iterate the instance to its fullest. Fill TBDs where possible, surface friction, identify what's missing or awkward
4. Promote what worked to the schema. Note what was iterated and why, so future revisions understand the rationale

This is the **iterate-instance-then-propagate-schema** pattern. It catches design gaps that abstract review misses. Validated 2026-05-09: both `client` + `business` briefs surfaced the "ask enough at scaffolding to fill the brief at minimum" discipline only after one instance was populated to completion. Schema-first design without instance grounding would have missed it.

### 4. Capture rationale alongside structure

For each design choice — which sections are required, which are optional, what's TLDR vs detail — the schema should make the rationale legible. A schema is a contract with the future; rationale is what keeps the contract honest. Future Claude sessions revising the schema need to understand the original intent, not just inherit the shape.

When the rationale matters durably, capture it adjacent to the structural marker (e.g., `*optional at scaffolding.*` followed by a sentence on why — see `business`'s Vision section: "future-state north star; often takes time to articulate"). When it's a one-time design pivot, link to the session that produced the change.

This rule's discipline is consistent with [[no-fabrication]] (TBD over invention), [[source-documentation]] (every claim traces to a source — type definitions should require a Sources section in instances so per-note source-documentation has a place to land), [[per-project-accounting]] (concrete example of scaffolding-content discipline applied to projects, the 8/9-item minimum), and [[instance-scaffolding]] (the sister rule that applies the schema once it's defined).

## What NOT to do

- Do not define a type by just listing folder contents. "Has these 8 files" is a layout, not a type definition. Each file needs purpose, structure, and required-vs-optional flagging.
- Do not omit "Gather required info" coverage in the meta-skill workflow. If a section is required in instances, the workflow MUST ask for the data to populate it. Silent gaps become permanent TBDs.
- Do not omit section headers when content is TBD. Preserving the header signals "this section exists; populate when known." Omitting it loses the structural commitment and the next instance starts hollow.
- Do not propagate a schema change up before validating it on a real instance. Abstract design without instance grounding produces schema that doesn't survive contact with operator data.
- Do not bake in sections without rationale. If you can't articulate why a section exists, it's a candidate for removal — not preservation.
- Do not duplicate detail across the brief and a deeper file. The brief carries TLDR + pointer; the deeper file carries detail. Duplication drifts; pointers don't.
- Do not leave frontmatter as freeform. Required fields, enums, and defaults belong in the schema, not as a one-time decision per instance.
- Do not leave detection ambiguous. Specify triggers explicitly or declare manual-only.

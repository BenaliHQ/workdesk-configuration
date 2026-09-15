# Workdesk ontology

This is the current folder and navigation contract. Use it with the operator policy and existing source/accounting rules.

## Work ownership

- Business improvement: `atlas/businesses/{business}/initiatives/{initiative}/projects/{project}/`.
- Client delivery: `atlas/clients/{client}/projects/{project}/`.
- Personal and standalone projects: `gtd/projects/{project}/`.
- Unassigned business projects remain under their current business `projects/` until the operator assigns an initiative.
- An initiative is sustained improvement. A project has a bounded outcome. Neither a product nor a repository requires another ontology layer.

Discover projects using `python3 config/scripts/project-discovery.py --root <vault>`, or an equivalent enumeration of all four homes. Ignore compatibility symlinks and deduplicate real paths. A listing is not evidence that a project is active: read its status and dated sources.

## Work documents

Use `brief.md` and `status.md`. Old underscored names may exist as compatibility aliases; never create a second independent document at an alias. Add `index.md` for navigation, `plan.md` for overall sequencing, and `specs/` for detailed executable plans. Add short `AGENTS.md` and `CLAUDE.md` entry points; shared policy remains centralized. Preserve archives and repository references. A missing plan or brief is an explicit gap, not permission to fabricate it.

## GTD and sources

Use `gtd/actions/` for next actions and `gtd/waiting/` for tracked dependencies. Read canonical directories without following legacy links. Index documents and symlinks are not actions. Keep client-internal tasks in their sourced records unless the operator is tracking a dependency.

Retain `intel/syntheses/` for source-linked interpretation. Classify legacy Intel reference items individually. Personal reference belongs in GTD; project inputs belong with their project. Existing uncertain items stay put until resolved.

`system/processing/` holds coordination and recovery records; `system/logs/` holds diagnostics. Preserve legacy aliases while external readers/writers are migrated. Raw source and session bodies remain evidence. A folder rename does not certify a processing workflow or runtime.

## Indexes and format

Indexes are navigation with annotated links and no duplicated status. Use standard relative Markdown links in index.md for portability. This deliberate exception to the general wikilink preference applies to indexes; sourced knowledge notes continue to use verified wikilinks. Indexes have no frontmatter. Do not claim whole-vault OKF conformance, rewrite source exports, or generate indexes in the read-only private zone, dependencies, baselines, or backups.

Related: [[per-project-accounting]], [[source-documentation]], [[../objects/initiative]], [[../objects/project]].

## Before an existing vault is migrated

Prefer canonical names when present. If absent, read the existing underscored brief/status files and the legacy Actions next/waiting directories. Their absence at the new path is not evidence of no work. Do not rename an existing vault as a side effect of a product update; use the reviewed manual migration. New projects use the canonical template.

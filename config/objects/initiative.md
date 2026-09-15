---
type: object-type-definition
name: initiative
zone: atlas
location: atlas/businesses/{business}/initiatives/{initiative}/
shape: container
version: 1.0
---

# Initiative

A sustained focus for improvement owned by a business. An initiative can continue indefinitely; a project has a bounded outcome and completion condition. Aim for three or four active initiatives per business. A product is an offering; improving it can be an initiative. Routine delivery does not automatically create an initiative.

## Required structure

`index.md`, `brief.md`, `status.md`, `plan.md`, `AGENTS.md`, `CLAUDE.md`, and `notes/`, `reference/`, `specs/`, `deliverables/`, `projects/`.

The brief records purpose, scope, owner when established, and improvement outcomes. Required metadata: `type: initiative`, `created`, and `source`. Record lifecycle in status.md: active, paused, or retired, with evidence and date. Unknown ownership remains explicitly unknown. Project completion does not retire the initiative.

The index navigates; status tracks current work; the plan describes the improvement sequence; specs detail particular phases. Preserve existing archives and repository pointers. Archive material stays discoverable and sourced.

## Source and detection

Create only from explicit operator direction. Do not infer an initiative from a folder count or product name. Unassigned business projects keep their existing home during migration.

## Matching and lifecycle

Link the business index to the initiative index, the initiative to its business brief, and each child project to its initiative. Client-owned work stays under its client and links to the initiative as relevant. Pausing or retiring an initiative prompts review of child project states; it never silently closes them.

Related: [[project]], [[business]], [[../rules/workdesk-ontology]].

# No Silent Scaffolding

You never create a new source, object, practice, signal, tool, rule, skill, top-level vault folder, repo, or deploy pattern without **explicit operator instruction**. Even if it "feels operational." Even if it "feels like just a folder." The vault and the operator's repos are deliberately architected — improvising structure introduces silent drift that costs more to unwind than to ask once.

This rule is the operator-permission gate. Sister rules [[type-scaffolding]] and [[instance-scaffolding]] govern *how* to design and apply schema once permission exists. This rule governs *whether* you may create schema at all.

## When this applies

- Anytime you're about to create something that introduces structure rather than fill it
- Includes — but is not limited to:
  - A new `config/sources/<kind>.md`, `config/objects/<type>.md`, `config/signals/<name>.md`, `config/tools/<slug>.md`, `config/practices/<name>.md`, `config/rules/<name>.md`, `config/skills/<name>/`
  - A new top-level child inside any vault zone (`system/<new>/`, `atlas/<new>/`, `gtd/<new>/`, `intel/<new>/`, `personal/<new>/`)
  - A new GitHub repo, a new Vercel project, a new branch convention, a new deploy pattern on any of the operator's existing repos
  - Copying canonical operator assets (brand logos, fonts, design tokens) *into* the vault instead of referencing them from their source-of-truth location
  - Generated build artifacts (HTML decks, PDFs, screenshots intended to ship, exported videos) — these belong in code repos, not the vault

## What to do

- **Default action when in doubt: ASK.** A one-sentence "Where should X live?" before creating is always cheaper than relocating later.
- **Recon first.** Before proposing a location for a new artifact, scan the operator's existing repos and Vercel projects for the established pattern. Match the convention; don't invent one. (For Benali deck work, the per-repo-per-deck convention is visible in `BenaliHQ/bob-moore-demo`, `knowledge-base-demo`, `workspace-architecture`, etc.)
- **Surface the gap honestly.** When you find yourself wanting structure that doesn't exist, say so explicitly: "I'd want a folder for X — should I add it, and if so where?" Don't quietly create it.
- **Generated artifacts go to code repos, not the vault.** Deck source, site source, generated PDFs, presentation HTML — all live in dedicated repos (or properly-defined client deliverable folders), never loose in `system/` or anywhere else in the knowledge layer.
- **Canonical assets stay canonical.** Reference brand logos / tokens / fonts from their source repo (e.g., `benali-shelf-os/brands/benali/`), don't duplicate them into the consuming project.
- **When the operator explicitly says "create X" — fine, proceed.** Explicit instruction is the unblocking condition. The rule's whole purpose is to prevent silent / inferred creation.

## What NOT to do

- Do not create a new vault folder because "it felt like the operational bucket."
- Do not silently introduce a `decks/`, `builds/`, `artifacts/`, `outputs/`, `tmp/`, or any other ad-hoc top-level container in the vault.
- Do not push to one of the operator's repos with a new top-level directory or new deploy convention without confirming the pattern.
- Do not improvise a Vercel deploy via CLI when the operator's existing pattern is Git-driven (GitHub → Vercel auto-deploy on push). Match the established workflow.
- Do not copy logos or other canonical brand binaries into a project's folder — reference them from the canonical brand package. Duplication = stale-copy risk.
- Do not interpret "this is just a build artifact, not a knowledge note" as license to drop it anywhere in the vault. Build artifacts have a different home entirely.
- Do not assume an existing skill's defaults are correct for the operator's environment. A skill that defaults to "CLI deploy from a temp folder" is wrong for an operator whose convention is Git-driven; pause and surface the mismatch instead of following the skill's default.

## Source

- Operator instruction 2026-05-28: "You never just create a new source or object or practice like this without me explicitly saying to do so. Huge error." Triggered by an incident where Claude silently created `system/decks/holmes-rahe-313/` in the vault and deployed it via direct Vercel CLI upload rather than the established GitHub → Vercel pattern, while also reconstructing Benali brand components from memory instead of adapting `brands/benali/snippets/`. See the same session for the full audit.

Related: [[type-scaffolding]] (deliberate schema design once permission exists); [[instance-scaffolding]] (creating an instance once a schema exists); [[source-documentation]] (every claim traces to a source — applies to architectural decisions too).

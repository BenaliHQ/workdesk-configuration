---
name: deck
description: Produce a shareable, brand-correct HTML deck through a disciplined recon → confirm → build → git-deploy loop. Never improvises brand, repo, or deploy pattern. Use when the operator asks to "make a deck", "build a presentation", "create slides", "build a pitch deck", "build an explainer deck", or similar.
---

# /deck

Generate a shareable web deck the right way. The skill exists because building a deck has three places to silently go wrong — wrong brand source, wrong repo home, wrong deploy mechanism — and a generic "spin up some HTML" skill steps on all three. This skill makes those three a reconnaissance + confirmation gate, not a default.

> **Operates under [[no-silent-scaffolding]]** — never creates a repo, vault folder, or deploy pattern without explicit operator confirmation.
>
> **Operates under [[type-scaffolding]]** — every deck is an instance of a defined pattern; the skill applies that pattern rather than reconstructing it.

## When to invoke

- Operator says "make a deck", "build a presentation", "create slides", "build a pitch / explainer / proposal deck", "shareable presentation"
- A shareable HTML artifact is the deliverable (not a doc, not a one-pager, not a video)
- Not the right skill for: speaker-only slides that won't be shared, PDF-only output, video presentations (those route to /frontend-slides or /hyperframes)

If the operator has a brand-specific deck skill for a recurring brand (a brand-hardcoded specialization), **invoke that instead** — it hardcodes the brand source and saves you the recon step.

## Intake (Phase 1)

Capture in a single AskUserQuestion batch:

1. **Purpose** — explainer, pitch, proposal, training, internal, demo
2. **Audience** — one specific reader you're talking to
3. **Length** — short (5–10), medium (10–20), long (20+)
4. **Brand** — which brand identity should it use? Operator names the brand or says "none / generic"
5. **Repo target hint** — does the operator have a repo in mind, or should the skill recommend?

If brand is "none / generic", the skill uses a documented default neutral style (defined in this skill's `default-style.md` once it exists; for v0 the skill stops and asks the operator for a brand reference). **Never improvises a brand.**

## Recon (Phase 2 — MANDATORY, cannot skip)

Recon is what was missing from the dogfood incident that produced this skill. Three reads, in order:

### 2a. Brand source-of-truth

Locate the brand's design system. The skill must find at minimum:
- A tokens file (CSS or JSON) with colors, typography, spacing
- A constraints / "never use" list (the `## Constraints` section in DESIGN.md style specs)
- Snippets / canonical components to adapt
- Logo assets

Default search paths to try in order:
1. `~/Projects/<brand>-shelf-os/brands/<brand>/` (a `<brand>-shelf-os` brand-package layout)
2. `~/Projects/<brand>-website/src/styles/` (live-site tokens)
3. `~/code/<brand>/brand/` or `~/code/<brand>-brand/`
4. The brand's published design-system URL

If none of those exist → **STOP and ask** the operator where the canonical brand source lives. Do not improvise tokens or fonts.

### 2b. Existing deck convention

Scan the operator's existing deck repos for the established pattern. For each:
- Single repo per deck, or monorepo of decks?
- Static HTML or build framework (Astro / Next.js)?
- Logo vendored in-repo, or referenced?
- Vercel project per deck, or shared?

Quick discovery commands:
- `gh repo list <account> --limit 50 --json name,description` — look for `-demo`, `-deck`, `-proposal`, `-slides` suffixes
- `vercel projects ls` — see which Vercel projects already exist for this account/team
- Read one representative deck's `index.html` to extract its CSS class system and slide controller pattern

**Adapt that pattern. Don't invent a new one.**

### 2c. Deploy mechanism

Identify how existing decks deploy. The default operator pattern is **GitHub → Vercel auto-deploy on push**. If the operator's existing decks were deployed via CLI uploads, ask whether they want to keep that or switch to git-driven for this one.

## Confirm with operator (Phase 3)

Before writing any HTML, present the recon as a single AskUserQuestion confirmation:

> **Brand source:** `<path>` — `<n>` tokens, `<n>` snippets, `<n>` logos
> **Pattern reference:** `<repo>` — `<class-system-summary>`
> **Repo target:** `<account>/<slug>` (new) or `<existing-repo>/<subfolder>`
> **Deploy:** GitHub → Vercel project `<name>` (new) or existing `<name>`
>
> Proceed?

Operator confirms, corrects, or amends. Skill does not proceed until confirmation.

## Build (Phase 4)

- **Generate the deck file in the target repo's local clone**, not the vault.
- **Reuse the pattern reference's CSS verbatim** when one was found in 2b. Substitute slide content; keep the class system, controller, and viewport-fitting rules intact.
- **Adapt from brand snippets**, do not reconstruct components from memory.
- **Use exact token values.** If a token doesn't exist for what's needed, ask before introducing one.
- **Vendor only required logo variants** into the deck repo (per the brand's `BRAND.md` for which variant fits which slide).
- Include a `README.md` with: brand source path, pattern reference, live URL, brief description.

### Viewport-fitting invariants (mandatory)

These are not negotiable — they come from the operator's established slide system:
- Every `.slide` has `width: 100vw; height: 100vh; height: 100dvh; overflow: hidden`.
- All typography uses `clamp()` for responsive scaling.
- Scroll-snap (`scroll-snap-type: y mandatory; scroll-snap-align: start`).
- IntersectionObserver-driven `.visible` class for reveal animations.
- `@media (prefers-reduced-motion: reduce)` support.
- Breakpoints at 700px, 600px, 500px height + 600px width.

## Deploy (Phase 5)

```bash
cd <local-clone>
git add -A
git commit -m "..."
git push -u origin main          # first push; subsequent pushes auto-deploy

# First-time Vercel setup:
vercel link --yes --project <slug>
vercel deploy --prod --yes
vercel git connect               # wire up auto-deploy
```

Subsequent revisions: `git push` and Vercel redeploys automatically. Return the live URL plus the commit SHA.

## Hard stops (never proceed)

- Brand source is missing or ambiguous → STOP, ask.
- Repo target unclear (don't know if it's a new repo, existing repo, or which subfolder) → STOP, ask.
- Operator's deploy pattern unknown → STOP, ask.
- Existing brand spec contains "never" rules → check every output against them before declaring done.
- The deck would land anywhere in a knowledge vault (`atlas/`, `intel/`, `gtd/`, `personal/`, `system/`) → STOP, ask. Decks live in code repos.

## Cleanup (Phase 6)

- If the operator used a CLI-uploaded Vercel project from before this skill existed, ask whether to delete that project and reuse its URL via the new git-driven project.
- If the deck started in a temp/wrong location, ask before relocating.

## What this skill does NOT do

- Does not pick the brand. Operator names it.
- Does not invent tokens, fonts, components, or class systems.
- Does not deploy via direct CLI uploads when an operator has a git-driven pattern.
- Does not write to the operator's knowledge vault.
- Does not duplicate brand assets into the deck repo beyond what the brand's BRAND.md prescribes.

## Related

- [[no-silent-scaffolding]] — the operator-permission gate this skill operates under
- [[type-scaffolding]] — schema design discipline
- A brand-hardcoded deck variant, if one exists for a recurring brand — use it when working in that brand to skip the recon step
- `/frontend-slides` (gstack) — generic HTML slide generator; this skill borrows its viewport-fitting substrate but replaces its deploy and brand assumptions

## Source

- Operator instruction 2026-05-28 — scaffolded after an incident where a branded deck was created with: a silent vault folder, CLI-uploaded Vercel deploy, and brand details reconstructed from memory instead of adapting from the canonical brand snippets. Full audit and resolution in the originating Claude session.

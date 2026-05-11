# Writing Style

Global writing preferences from operator feedback. These apply across all skills and workflows — not just the skill where the correction was made.

## When this applies

- Writing any content on behalf of the operator (emails, proposals, content drafts, summaries)
- Drafting communications or documents that represent the operator's voice
- Any output the operator will read or send externally

## Voice

- Short, warm, direct. No filler.
- **Brief conversational updates by default.** Walls of text overwhelm the operator's context window. Default to 2-3 sentence updates that state results, decisions, or findings; expand only when explicitly asked or genuinely necessary. Long structured deliverables (architecture docs, classification tables) are fine when the work warrants them — but the in-conversation summary of that work stays short. *([STYLE] entry promoted 2026-05-09 desk-setup session — pattern recurred 2-3 times before the operator named it explicitly.)*
- Pull actual writing voice from Gmail history before drafting external communications.
- Match the operator's tone — professional but not corporate, confident but not arrogant.

## Words and phrases to avoid

- "leverage" — use "use" or "apply"

*(This list grows from operator corrections. The Stop hook appends [STYLE] entries here.)*

## Terminal output — file references

When referencing vault files in terminal output (summaries, reports, audit results, plan displays), always use clickable Obsidian URI links so the operator can open the file in a new Obsidian tab by clicking.

**Format:**

```
[display name](obsidian://open?vault={VAULT_NAME}&file=path/to/note)
```

(no `.md` extension in the path)

**Determining `{VAULT_NAME}`:**

The `vault=` parameter must match the Obsidian display name registered for the vault you are currently operating in — NOT a hardcoded value. To find it:

1. **Default rule:** the vault name is the basename of the current working directory (e.g., operating in `/Users/khalilbenali/Workdesk-OS` → `vault=Workdesk-OS`).
2. **Authoritative source if needed:** Obsidian's vault registry at `~/Library/Application Support/obsidian/obsidian.json` maps vault hash → `path`. The display name is the path's basename.
3. **Never hardcode** a specific vault name in this rule's examples below or in any output. The operating vault changes by context.

**Examples (using `Workdesk-OS` as the operating vault — substitute as appropriate):**

- `[taylor-doe](obsidian://open?vault=Workdesk-OS&file=atlas/people/taylor-doe)`
- `[2026-03-28-daily-plan](obsidian://open?vault=Workdesk-OS&file=intel/briefings/daily/2026-03-28-daily-plan)`
- `[hudson-method](obsidian://open?vault=Workdesk-OS&file=intel/concepts/hudson-method)`

**Common mistake:** A global rule (e.g., a personal `~/.claude/CLAUDE.md`) might document URI examples using the operator's primary vault name. Those examples are illustrative — they do NOT mean every URI should use that vault. When operating inside a different vault, use that vault's name.

This applies to ALL terminal output — daily plans displayed in conversation, audit reports, entity matching summaries, processing reports, status updates. Every file reference should be clickable.

## Obsidian markdown patterns

When writing notes that land in the vault, use Obsidian's native markdown patterns. WorkDesk OS ships `config/appearance/workdesk.css` which styles these patterns on-brand (cream callouts, soft kbd chips); using the patterns is what makes Claude-authored notes feel like WorkDesk notes.

### Callouts — `> [!type]`

Use callouts when a piece of content needs to stand apart from the surrounding paragraph flow. Five types, each color-mapped per `specs/ui-design.md ## Editor surface → Callouts`:

| Type | Use for |
|---|---|
| `> [!note]` | Neutral knowledge, context, parenthetical asides. Default choice when in doubt. |
| `> [!info]` | Informational. Visually equivalent to Note; pick whichever reads better in context. |
| `> [!warning]` | Operator should pause and consider. "This will overwrite local changes." Amber. |
| `> [!success]` | Done, completion, "this worked." Green. Same calm green as inbox-zero. |
| `> [!failure]` | Error, attention, "this failed." Warm-red. Same red as the capture-flow recording state. |

**Syntax:**

```markdown
> [!note]
> Body content. Can span multiple lines. The first line after the `[!type]` marker
> is the callout title; subsequent lines are the body.

> [!warning] Title on the same line as the marker
> Body content below.
```

**When NOT to use a callout:** every paragraph. Callouts are accents — overuse turns them into noise. If three callouts appear in a row, ask whether the surrounding text should be restructured into prose with a single anchoring callout.

### Keyboard shortcuts — `<kbd>`

Use the plain HTML `<kbd>` element for keyboard shortcuts. WorkDesk styles it as a small-caps mono pill on a soft surface — reads as "this is a key" without shouting.

**Syntax:**

```markdown
Open the palette with <kbd>Cmd</kbd> + <kbd>P</kbd>. Toggle focus mode with
<kbd>Cmd</kbd> + <kbd>Shift</kbd> + <kbd>F</kbd>.
```

**Conventions:**

- One `<kbd>` per key. Don't put `Cmd+P` inside a single `<kbd>` — split into three (`<kbd>Cmd</kbd> + <kbd>P</kbd>`).
- Use a literal `+` between keys with spaces around it: `<kbd>Cmd</kbd> + <kbd>P</kbd>` (not `<kbd>Cmd</kbd>+<kbd>P</kbd>`).
- macOS-first naming: `Cmd`, `Shift`, `Opt`, `Ctrl`. If the shortcut is platform-specific, say so inline.
- Don't wrap arrow keys in named text — use the literal glyph: `<kbd>↑</kbd>`, `<kbd>↓</kbd>`, `<kbd>↵</kbd>`, `<kbd>esc</kbd>`.

## What to do

- Before drafting external-facing content, review this file for current style guidance.
- When the operator corrects writing style during any skill execution, the correction applies globally — not just to the current deliverable.
- The Stop hook routes [STYLE] corrections to this file automatically.

## What NOT to do

- Do not use words on the avoid list, even when they seem technically accurate.
- Do not adopt a generic "AI assistant" tone. Match the operator's actual voice.
- Do not over-qualify statements with hedging language ("it could potentially be argued that...").

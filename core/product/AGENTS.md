# Workdesk

This vault turns what the owner saves, records and writes into one linked body of context. The owner and their agents work from it. This page is the whole rulebook.

## The folders

| Folder | Holds |
|---|---|
| `sources/` | What came in, kept as it arrived |
| `sources/recordings/` | Meeting recordings |
| `sources/links/` | Articles, posts, videos, podcasts, books |
| `sources/sessions/` | Agent sessions |
| `sources/captures/` | Things the owner captured |
| `objects/` | What the owner knows |
| `objects/people/` | People |
| `objects/companies/` | Companies |
| `objects/projects/` | One context note per project |
| `objects/terms/` | Words and phrases the owner tracks |
| `objects/concepts/` | Named ideas and who they come from |
| `objects/meetings/` | Meetings |
| `objects/decisions/` | Decisions |
| `objects/quotes/` | Exact words and their passage |
| `writing/` | The owner's daily note, journal, reading notes and memos |
| `signals/` | What Workdesk writes for the owner unasked |
| `signals/briefs/` | The daily brief |
| `signals/syntheses/` | What several sources say on one subject |
| `AGENTS.md` | This rulebook |
| `CLAUDE.md` | One line that loads this rulebook |
| `status.md` | What is running |

An object's type is its folder. Create no other folder. The hidden folders `.obsidian/`, `.claude/skills/` and `.agents/skills/` hold settings and skills. Leave them alone. Program code and logs live outside the vault.

## An object

1. The title. It is the object's exact name.
2. A summary.
3. `## Currently`, on people, companies and projects: one line per present fact, ending with its date and its source.
4. Other sections for its type.
5. `## History`, newest first. A history line is one dated line: what changed, from which passage, and whether it was stated, reported, inferred or a correction.

A passage is a marked block in a source, such as `^p0042`.

## The rules

**Sources**

1. Never edit, move, rename or delete a source.
2. Every statement you write points to the passage it came from. A quote matches its source word for word. What no source says, leave out or mark as inferred.

**Names and links**

3. Write a person's full name and an object's exact name, always. A program links every exact mention.
4. A first name on its own is never linked and never becomes a person. Leave it as plain text and say the full name is unknown. Do not guess.
5. One note per real thing. Look before anything new is made: use `wd find`, or the object's folder while that command is not built. People match on email, companies on web address.
6. Never merge two people or two companies unless the owner says so. If two notes look like the same person or company, do nothing and say so once.
7. Renames go through Obsidian, so every link follows. Never rename or move a note with a shell command or a file tool.
8. Every link opens a real note and has a real reason. No filler links.

**Objects**

9. Every object opens with a summary: three lines and 60 words at most.
10. `## History` is written by programs. Never edit it by hand.
11. A change to what an object says needs its history line in the same save. So make the change with a `wd` command, which writes both.
12. Programs write frontmatter. Add no key and invent no alias.
13. A fact under `## Currently` carries the date a source last stated it. A mention does not refresh it. People and companies are aging at 90 days and stale at 180. Projects are aging at 30 and stale at 90. When you use an aging or stale fact, say its date.
14. Nothing is deleted. Meetings, decisions and quotes stay true as dated history. A replaced decision points to the one that replaced it.
15. A program checks every note you write. Run `wd check .` after you write one and at the end of the session.

**The owner's**

16. `writing/` is the owner's. Read it. Never edit it, move it or add to it.
17. The owner corrects things by writing "fix:". A correction outranks every source, now and later. Apply it with `wd fix` and never overrule one.
18. A source or person with `private: true` is private. Its content never goes into a summary or a brief.
19. Nothing leaves the vault for another tool, service or message unless the owner sends it. One exception: the Linear alert, sent by a program once a day at most.
20. The vault holds no tasks. Write no to-do lists, statuses or due dates here. A promise the owner made shows in the brief.
21. `status.md` and everything under `signals/` are written by programs. Never edit them by hand.

## The commands

Run these from the vault's root. A command that writes takes `--dry-run` to show what it would do and `--apply` to do it.

| Command | Does |
|---|---|
| `wd find <name>` | Finds an object by name |
| `wd pack <name>` | Gathers the context on one object in one bundle |
| `wd fix "<text>"` | Applies a correction and records it as the owner's |
| `wd track "<phrase>"` | Creates a term and links its mentions |
| `wd status . --apply` | Writes `status.md` |
| `wd check .` | Checks the vault and the notes you wrote |
| `wd add` | Brings a source in and gives it its permanent place |
| `wd process` | Turns a meeting recording into objects and history lines |
| `wd link` | Links every exact mention of an object |

`wd brief` and `wd tick` run on a schedule. `wd init`, `wd graph-setting`, `wd score` and `wd install` are for setup. Run those only when the owner asks.

A command that is not built yet says so itself. Tell the owner in one plain sentence. Do not do its job by hand in a way that breaks a rule.

## Writing for the owner

- Plain words. Short sentences. The answer first.
- No em dashes.
- Full names and exact dates, not "recently".
- Say what you did and what you could not do. Then stop.

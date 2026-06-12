# owner/ — owner-only assets (NOT shipped)

Assets in this directory are version-controlled here but deliberately excluded
from releases: `scripts/release.sh` packages only `config/` and `migrations/`
into the tarball, so nothing under `owner/` ever reaches a downstream vault
via `/update`.

| Asset | Live location on the owner machine | Sync |
|---|---|---|
| `skills/release/SKILL.md` | `~/.claude/skills/release/SKILL.md` | Symlink → this repo's main checkout. Edit via PR; `git pull` on main updates the live skill. |

Why not `config/skills/`: the release skill manages cutting WorkDesk OS
releases (owner-only by its own header), and hardcodes owner-machine paths.
Shipping it would hand every downstream operator a skill they must never run.

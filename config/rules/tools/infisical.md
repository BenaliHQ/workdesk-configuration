# Infisical — Tool Reference

Open-source secrets management platform. Stores API keys and tokens (not human logins — that belongs in a password manager), scopes them per client, shares them with technical contractors, and injects them into CLI/agent workloads at runtime.

WorkDesk-OS ships the Infisical foundation in `config/scripts/` and `config/infisical/`. Tool-specific layers (gws, qbo, codex, …) ride on top of this foundation in their own releases.

## Access Method

CLI binary: `/opt/homebrew/bin/infisical` (install via `npm install -g @infisical/cli`).

Default backend: Infisical Cloud at `https://app.infisical.com`. Override with `--domain` flag or `INFISICAL_API_URL` env var if/when self-hosted.

## Setup

Run once per machine:

```bash
bash config/scripts/bootstrap-infisical.sh
```

This walks you through: filling in the three Infisical-related fields in `operator-profile.md`, storing a Universal Auth machine identity's credentials in macOS Keychain, mounting the RAM disk, rendering concrete `agent.yaml` and LaunchAgent plists from the shipped templates, and loading the LaunchAgents.

Idempotent — re-run any time to recover from drift or to advance after editing the profile.

## Common Commands

| Command | What it does | Example |
|---|---|---|
| `infisical login` | Interactive browser login (rarely needed once UA identity is set up) | `infisical login` |
| `bash config/scripts/infisical-names.sh` | List secret NAMES from your personal project without leaking values into the shell | `bash config/scripts/infisical-names.sh` |
| `infisical secrets get <KEY> --projectId=... --env=prod --plain` | Fetch one secret value, no table formatting | `infisical secrets get PERSONAL_STRIPE_API_KEY --projectId=$INFISICAL_PERSONAL_PROJECT_ID --env=prod --plain` |
| `infisical secrets set <KEY>=<value> --projectId=... --env=prod` | Create or update a secret | `infisical secrets set PERSONAL_STRIPE_API_KEY=rk_live_... --projectId=... --env=prod` |
| `infisical run --projectId=... --env=prod -- <command>` | Inject every secret as env vars into a process | `infisical run --projectId=$INFISICAL_PERSONAL_PROJECT_ID --env=prod -- claude` |
| `infisical scan git-changes` | Scan repo / diff for leaked secrets | `infisical scan git-changes` |

The convenience helper `config/scripts/infisical-names.sh` defaults to the project ID set in `operator-profile.md` and is safe to run from a Claude Code session — it strips the value column from the listing.

## Authentication

- **Operator workstation:** the Universal Auth machine identity created during bootstrap. Credentials live in macOS Keychain (encrypted at rest, unlocked at login).
- **Machines / agents / cron:** create a separate Universal Auth identity per agent role (not one global identity) so rotation is scoped. Same flow as the workstation identity.

The agent process (`infisical-agent-run.sh`, started by `~/Library/LaunchAgents/com.benali.workdesk.infisical-agent.plist`) pulls the UA creds from Keychain at login, writes them to a RAM disk, and execs `infisical agent --config config/infisical/agent.yaml`. Nothing static touches the SSD.

## Project structure

One Infisical project per client (`client-<slug>`) plus one project per teammate for non-client static keys. Per-project access control is Infisical's strongest scoping mechanism — folder-scoping is more ergonomic but coarser.

| Prefix in use | Container | Why |
|---|---|---|
| `PERSONAL_<SERVICE>_<KEY_TYPE>` | Each operator's own project (one per teammate) | Project boundary is the scope. Keep the `PERSONAL_` prefix inside it for consistency across operators. |
| `CLIENT_<SLUG>_<SERVICE>_<KEY_TYPE>` | One project per client | Per-client access scoping is the whole point. |

**Project ID lookup:**

- **Personal project:** stored in `operator-profile.md` frontmatter as `infisical-project-id:`. Read at runtime by `config/scripts/lib/operator-config.sh` as `$INFISICAL_PERSONAL_PROJECT_ID`.
- **Client projects:** project ID lives in each client's `atlas/clients/<slug>/_status.md` frontmatter (`infisical-project-id:`). Skills working on a known client read it from there.

If you maintain a cross-project index, put it at `config/state/infisical-projects.md` — this template doesn't ship one, since the source of truth lives in operator-profile + per-client status files.

## Known Limitations

> [!warning]
> **Free tier caps.** Project count, user count, and certain feature gates make the free tier impractical at 8+ active clients. Plan on paid tier or self-host from day one of real client work.

- **Network required for cloud commands.** No offline mode; if Infisical Cloud is unreachable, `secrets get` fails. At boot, the agent can't render templates — tools depending on rendered files start in a broken state. Mitigate with backups of the relevant `~/Library/Application Support/<tool>.bak.*` directories until you've validated reboot under degraded conditions.
- **No human-login story.** Passwords, 2FA seeds, recovery codes, dashboard logins — those belong in a password manager, not Infisical. Resist the urge to put them here "to have one tool."
- **Audit log is read-only insurance.** It only helps if you actually check it during offboarding. Revoking access without rotating exposed keys is theater.

## Common Mistakes

- **Running `infisical secrets` (full listing) in an agent session.** The default CLI output renders a table with values inline — every secret value lands in the agent's context. For presence checks, use `config/scripts/infisical-names.sh`. For reading one key, use `infisical secrets get <KEY> --projectId=... --env=... --plain`. `--plain` prints values without table formatting. Never use the bare `infisical secrets` command when an agent (or anything that retains output) is watching.
- **Flat naming without the `CLIENT_/PERSONAL_` prefix.** Twenty keys deep, you can't tell what belongs to whom.
- **One global Universal Auth identity for every machine workload.** Rotating one breaks everything. Scope per agent/role.
- **Treating offboarding revocation as sufficient.** When a contractor leaves, audit-log every key they had read access to and **rotate them all**. Revocation alone is theater.
- **Big-bang migration of all existing `.env` keys.** Migrate one client end-to-end first to validate the pattern. Backfill the rest as engagements touch them.
- **Pushing OAuth refresh tokens without a round-trip script.** OAuth refresh tokens belong in Infisical *if* (a) the Infisical Agent renders them onto the RAM disk at boot and (b) a re-push script runs after every `<tool> auth login` so the stored value doesn't go stale. Without (b), every re-auth silently desyncs Infisical from local state — next reboot reverts to the stale token.

## The Agent + RAM-disk pattern (file-based consumers)

For CLIs that authenticate via OAuth and read their state from a file path on disk, the pattern is:

1. **Bootstrap secret in Keychain.** A Universal Auth machine identity (`client-id` + `client-secret`) lives in macOS Keychain — the only persistent secret on the SSD, encrypted at rest by the OS.
2. **RAM disk at login.** A LaunchAgent (`com.benali.workdesk.ramdisk.plist`) mounts `/Volumes/wd-ramdisk` via `hdiutil`.
3. **Agent renders to RAM disk.** A second LaunchAgent (`com.benali.workdesk.infisical-agent.plist`) starts the Infisical Agent, which pulls UA creds from Keychain, writes them to the ramdisk (still in RAM), then renders templated files into `/Volumes/wd-ramdisk/<tool>/`.
4. **Tool dir symlinked to RAM disk.** The CLI's expected data dir (e.g., `~/Library/Application Support/gws`) is symlinked to its directory under `/Volumes/wd-ramdisk/`. The CLI never knows.
5. **Re-push after re-auth.** After any `<tool> auth login`, a tool-specific push script captures the new local state, base64s any binary blobs, and pushes back to Infisical so the next reboot renders the current values.

Each tool layer (gws, qbo, codex, …) ships its own `*-post-render.sh`, `*-push-tokens-to-infisical.sh`, and agent.yaml template snippet that gets appended to the operator's concrete `config/infisical/agent.yaml` by the tool's setup script.

## Detection clause

Surface proactively when:

- The operator references a static API key sitting in a plaintext `.env` that's about to be shared with a contractor — propose moving it to Infisical instead of copying it.
- The operator starts a new client engagement requiring shared API keys or tokens — propose creating a `client-<slug>` project as part of scaffolding.
- The operator mentions rotating a key — check if it's in Infisical and propose `infisical secrets set` followed by an audit-log review.
- A skill needs to call a third-party service requiring an API key — propose `infisical run -- <command>` to inject it at runtime instead of reading from a `.env`.
- The operator offboards a contractor — propose pulling the Infisical audit log for that user's read history and rotating every key they touched.
- The operator references a CLI tool that reads OAuth state from disk — propose extending the Agent + RAM-disk pattern to that tool (if a tool-layer release doesn't already cover it).

## Sources

- Infisical CLI docs: https://github.com/infisical/cli
- Infisical Agent docs: https://infisical.com/docs/integrations/platforms/infisical-agent
- Verify installed version with `infisical --version` (minimum supported: 0.43.85).

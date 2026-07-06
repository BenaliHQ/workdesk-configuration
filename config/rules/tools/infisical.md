# Infisical — Tool Reference

Open-source secrets management platform. Stores API keys and tokens (not human logins — that belongs in a password manager), scopes them per client, shares them with technical contractors, and serves as the synced backup for tool auth state (gws, qbo, codex, …) so a new or wiped machine can restore without redoing every OAuth flow.

WorkDesk-OS ships the Infisical foundation in `config/scripts/`. Tool-specific layers (gws, qbo, codex, …) ride on top of this foundation in their own releases.

## Access Method

CLI binary: `/opt/homebrew/bin/infisical` (install via `npm install -g @infisical/cli`).

Default backend: Infisical Cloud at `https://app.infisical.com`. Override with `--domain` flag or `INFISICAL_API_URL` env var if/when self-hosted.

## Authentication — user login, nothing else

WorkDesk uses **your own Infisical account via `infisical login`** (browser flow). The CLI stores a user session locally; every fetch, push, and `infisical run` rides that session.

**Do not create a machine identity.** WorkDesk's architecture has no daemons or unattended workloads that talk to Infisical — every call happens in an interactive session (yours or an agent's shell inside your login session), so user auth covers everything. Machine identities were part of a retired boot-time-agent pattern (removed 2026-07-06) and setting one up now would just add an unused credential to rotate.

Two properties of user sessions to design around:

- **Sessions expire** (typically after a few weeks). The symptom: `infisical secrets get` fails or the CLI tries to open its interactive login wizard. The fix is always the same: `infisical login`, then retry.
- **The CLI drops into an interactive wizard when unauthenticated.** In a script or agent context that wizard hangs or sprays ANSI codes instead of failing. Every scripted call should redirect stdin from `/dev/null` — `infisical secrets get KEY ... --plain </dev/null` — so an expired session fails fast with a detectable error instead.

## Setup

Run once per machine:

```bash
bash config/scripts/bootstrap-infisical.sh
```

This walks you through: filling in the Infisical-related fields in `operator-profile.md`, logging in via the browser (`infisical login`), and verifying your personal project is reachable.

Idempotent — re-run any time (including after a session expires) to recover.

## Common Commands

| Command | What it does | Example |
|---|---|---|
| `infisical login` | Browser login; establishes/renews the user session | `infisical login` |
| `bash config/scripts/infisical-names.sh` | List secret NAMES from your personal project without leaking values into the shell | `bash config/scripts/infisical-names.sh` |
| `infisical secrets get <KEY> --projectId=... --env=prod --plain` | Fetch one secret value, no table formatting | `infisical secrets get PERSONAL_STRIPE_API_KEY --projectId=$INFISICAL_PERSONAL_PROJECT_ID --env=prod --plain </dev/null` |
| `infisical secrets set <KEY>=<value> --projectId=... --env=prod` | Create or update a secret | `infisical secrets set PERSONAL_STRIPE_API_KEY=rk_live_... --projectId=... --env=prod` |
| `infisical run --projectId=... --env=prod -- <command>` | Inject every secret as env vars into a process | `infisical run --projectId=$INFISICAL_PERSONAL_PROJECT_ID --env=prod -- claude` |
| `infisical scan git-changes` | Scan repo / diff for leaked secrets | `infisical scan git-changes` |

The convenience helper `config/scripts/infisical-names.sh` defaults to the project ID set in `operator-profile.md` and is safe to run from a Claude Code session — it strips the value column from the listing.

Scripted fetch pattern (what tool layers and skills should use):

```bash
export INFISICAL_DISABLE_UPDATE_CHECK=true
KEY=$(infisical secrets get PERSONAL_EXAMPLE_API_KEY \
  --projectId=$INFISICAL_PERSONAL_PROJECT_ID --env=prod --plain </dev/null 2>/dev/null)
```

(`</dev/null` = fail fast instead of interactive wizard; `INFISICAL_DISABLE_UPDATE_CHECK` = keep the CLI's update banner out of captured stdout. Some keys still warrant a shape check — e.g. `grep '^sk_'` — as defense against any residual banner noise.)

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

## The tool-state sync pattern (file-based consumers)

For CLIs that authenticate via OAuth and keep their state in files on disk (gws, qbo, codex), the pattern is:

1. **State lives in the tool's normal on-disk location** (`~/Library/Application Support/gws/`, `~/.codex/auth.json`, …). FileVault provides encryption at rest; sensitive files get `chmod 600`.
2. **Infisical holds a synced copy.** Each tool layer ships a `*-push-to-infisical.sh` script that mirrors the current state (base64-encoding binary blobs) into the operator's personal project. Shell wrappers fire the push after any call that rotates a token; a periodic `wd-state-sync` pass (where installed) catches rotations that happen outside the wrapper.
3. **Restore on demand.** A new machine (or wiped state) restores by running the tool's setup script (e.g. `setup-gws.sh`), which pulls the synced copy from Infisical via your user session — no browser OAuth redo unless Infisical's copy is missing or stale.
4. **Re-push after re-auth.** After every `<tool> auth login`, run the tool's push script so the stored value doesn't go stale. Without it, every re-auth silently desyncs Infisical from local state — and a future restore hands you a dead token.

## Known Limitations

> [!warning]
> **Free tier caps.** Project count, user count, and certain feature gates make the free tier impractical at 8+ active clients. Plan on paid tier or self-host from day one of real client work.

- **User sessions expire.** Expect to re-run `infisical login` every few weeks. Push scripts log failures (`system/log/*-push.log`) rather than dying loudly — check them if tokens seem stale, and treat a run of `FAILED to push` lines as "re-login now."
- **Network required for cloud commands.** No offline mode; if Infisical Cloud is unreachable, `secrets get` fails. Tools keep working off their local on-disk state — only sync/restore is affected.
- **No human-login story.** Passwords, 2FA seeds, recovery codes, dashboard logins — those belong in a password manager, not Infisical. Resist the urge to put them here "to have one tool."
- **Audit log is read-only insurance.** It only helps if you actually check it during offboarding. Revoking access without rotating exposed keys is theater.

## Common Mistakes

- **Running `infisical secrets` (full listing) in an agent session.** The default CLI output renders a table with values inline — every secret value lands in the agent's context. For presence checks, use `config/scripts/infisical-names.sh`. For reading one key, use `infisical secrets get <KEY> --projectId=... --env=... --plain`. Never use the bare `infisical secrets` command when an agent (or anything that retains output) is watching.
- **Scripted calls without `</dev/null`.** An expired session turns the call into an interactive wizard that hangs the script or sprays ANSI codes into captured output. Redirect stdin from `/dev/null` so it fails fast.
- **Creating a machine identity because a tutorial suggested it.** WorkDesk doesn't use them; see Authentication above.
- **Flat naming without the `CLIENT_/PERSONAL_` prefix.** Twenty keys deep, you can't tell what belongs to whom.
- **Treating offboarding revocation as sufficient.** When a contractor leaves, audit-log every key they had read access to and **rotate them all**. Revocation alone is theater.
- **Big-bang migration of all existing `.env` keys.** Migrate one client end-to-end first to validate the pattern. Backfill the rest as engagements touch them.
- **Pushing OAuth state without wiring the re-push step.** OAuth refresh tokens belong in Infisical *if* a push script runs after every `<tool> auth login` so the stored value doesn't go stale. Without it, restore-from-Infisical hands back a dead token.

## Detection clause

Surface proactively when:

- The operator references a static API key sitting in a plaintext `.env` that's about to be shared with a contractor — propose moving it to Infisical instead of copying it.
- The operator starts a new client engagement requiring shared API keys or tokens — propose creating a `client-<slug>` project as part of scaffolding.
- The operator mentions rotating a key — check if it's in Infisical and propose `infisical secrets set` followed by an audit-log review.
- A skill needs to call a third-party service requiring an API key — propose `infisical run -- <command>` or a `</dev/null`-guarded `secrets get` to inject it at runtime instead of reading from a `.env`.
- The operator offboards a contractor — propose pulling the Infisical audit log for that user's read history and rotating every key they touched.
- An Infisical call fails or tries to open a login wizard — the user session has expired; propose `infisical login` rather than debugging the key.
- The operator references a CLI tool that reads OAuth state from disk — propose extending the tool-state sync pattern to that tool (if a tool-layer release doesn't already cover it).

## Sources

- Infisical CLI docs: https://github.com/infisical/cli
- Verify installed version with `infisical --version` (minimum supported: 0.43.85).
- Architecture note: the original foundation (2026-05/06) used a Universal Auth machine identity + boot-time `infisical agent` rendering tool state onto a RAM disk. Retired 2026-07-06 in favor of user-login auth + on-disk state + push/restore sync — simpler, no identity to rotate, no daemon to break. If you find references to `wd-ramdisk`, machine identities, or `agent.yaml` in older notes, they describe the retired pattern.

#!/usr/bin/env bash
# init.sh — WorkDesk OS install orchestrator
#
# Per [[specs/workdesk-init]] r5 (locked 2026-04-29). Phase A install bedrock.
# Closes bugs C1, C5, C6, C7, H7. Touches C2, M1.
#
# Single user-visible install entry. Operator pre-installs Obsidian + Claude
# Code; this script verifies them, downloads the pinned tarball, runs
# bootstrap.sh, vendors BRAT (the only bundled plugin), registers the vault,
# exits. Operators install additional plugins (workdesk-terminal, surface
# appearance, etc.) opt-in via BRAT from inside Obsidian.
#
# Invocation:
#   curl -fsSL https://raw.githubusercontent.com/BenaliHQ/workdesk-os/v1.1.0/init.sh | bash
#
# All optional inputs via env vars; no flags read from stdin (curl-pipe safe):
#   WORKDESK_VAULT_PATH   path to install vault   (default: ~/Workdesk-OS/)
#   WORKDESK_REF          git tag / branch        (default: tag from curl URL or 'main')
#   WORKDESK_INIT_DRYRUN  if set non-empty, plan only, no writes
#   WORKDESK_INIT_FORCE   if set non-empty, reuse non-empty vault per ownership list
#   WORKDESK_INIT_OPEN    if set non-empty, `open -a Obsidian <path>` on success

set -euo pipefail

# ---- constants ---------------------------------------------------------------

REPO_OWNER="BenaliHQ"
REPO_NAME="workdesk-os"
DEFAULT_VAULT_PATH="$HOME/Workdesk-OS"
DEFAULT_REF="main"

PLUGIN_IDS=(
  "obsidian42-brat"
)

# ---- io helpers --------------------------------------------------------------

log_step()   { printf '[step] %s\n' "$*"; }
log_info()   { printf '       %s\n' "$*"; }
log_dryrun() { printf '[dry]  %s\n' "$*"; }
fail()       { printf '\n[ERROR] %s\n\n[recover] %s\n' "$1" "${2:-Inspect $INSTALL_LOG and retry.}" >&2; exit 1; }

INSTALL_LOG=""  # set after vault path resolved

log_install() {
  # YYYY-MM-DD HH:MM:SS | step | status | detail
  local step="$1" status="$2" detail="${3:-}"
  [[ -n "$INSTALL_LOG" ]] || return 0
  printf '%s | %s | %s | %s\n' \
    "$(date '+%Y-%m-%d %H:%M:%S')" "$step" "$status" "$detail" >> "$INSTALL_LOG"
}

# ---- input parsing -----------------------------------------------------------

VAULT_PATH="${WORKDESK_VAULT_PATH:-$DEFAULT_VAULT_PATH}"
REF="${WORKDESK_REF:-$DEFAULT_REF}"
DRY_RUN="${WORKDESK_INIT_DRYRUN:-}"
FORCE="${WORKDESK_INIT_FORCE:-}"
OPEN_AFTER="${WORKDESK_INIT_OPEN:-}"

# Expand leading ~ in vault path (parameter substitution).
VAULT_PATH="${VAULT_PATH/#\~/$HOME}"

# ---- version_ge --------------------------------------------------------------
# Compare dotted version strings. Returns 0 if $1 >= $2, 1 if $1 < $2,
# 2 if either input has empty/non-numeric segments (caller surfaces a clear
# "could not parse version" error).
version_ge() {
  # Reject empty inputs as malformed (returns 2) before splitting, so callers
  # can distinguish "could not parse" from "less than".
  [[ -n "$1" && -n "$2" ]] || return 2
  # Split inputs on '.' into arrays. Note: `local IFS=. f=($1)` on one line
  # does NOT work — bash evaluates the array assignment with the OLD IFS
  # before applying the new one, yielding a single-element array. Split the
  # IFS change into its own statement before the array splits.
  local IFS=.
  local f=($1) r=($2) i max a b
  max=${#f[@]}
  (( ${#r[@]} > max )) && max=${#r[@]}
  for (( i=0; i<max; i++ )); do
    a=${f[i]:-0}
    b=${r[i]:-0}
    [[ "$a" =~ ^[0-9]+$ ]] || return 2
    [[ "$b" =~ ^[0-9]+$ ]] || return 2
    (( 10#$a > 10#$b )) && return 0
    (( 10#$a < 10#$b )) && return 1
  done
  return 0
}

# ---- json helpers (plutil only) ---------------------------------------------

# JSON parse check. macOS plutil quirks across versions:
#   plutil -lint rejects JSON on macOS 26.4.1 (only xml1/binary plists)
#   plutil -p   accepts JSON on macOS 26 but not consistently on macOS 14
# `plutil -convert json -o /dev/null <file>` round-trips through the JSON
# converter and is supported across macOS 11+; non-zero exit on invalid input.
json_ok() {
  plutil -convert json -o /dev/null "$1" >/dev/null 2>&1
}

# Atomic JSON write: caller passes a target path and writes content via stdin.
# We write to <target>.tmp.<pid>, parse-check, then mv.
json_atomic_write() {
  local target="$1"
  local tmp="${target}.tmp.$$"
  cat > "$tmp"
  if ! json_ok "$tmp"; then
    rm -f "$tmp"
    fail "Failed to write valid JSON to $target" "Inspect upstream input."
  fi
  mv "$tmp" "$target"
}

# ---- platform check ----------------------------------------------------------

find_obsidian_app() {
  # 1) mdfind LaunchServices lookup
  local app
  app=$(mdfind "kMDItemCFBundleIdentifier == 'md.obsidian'" 2>/dev/null | head -n1)
  if [[ -n "$app" && -d "$app" ]]; then
    printf '%s' "$app"
    return 0
  fi
  # 2) /Applications fallback
  if [[ -d "/Applications/Obsidian.app" ]]; then
    printf '%s' "/Applications/Obsidian.app"
    return 0
  fi
  # 3) ~/Applications fallback
  if [[ -d "$HOME/Applications/Obsidian.app" ]]; then
    printf '%s' "$HOME/Applications/Obsidian.app"
    return 0
  fi
  return 1
}

required_obsidian_version() {
  # Read max minAppVersion across the vendored plugin manifests.
  # At platform-check time we don't yet have the source tree; this function
  # is called *after* repo-fetched. We accept the source root as $1.
  local src="$1"
  local max="0.0.0" v
  local id
  for id in "${PLUGIN_IDS[@]}"; do
    local manifest="$src/vendor/plugins/$id/manifest.json"
    [[ -f "$manifest" ]] || continue
    v=$(plutil -extract minAppVersion raw "$manifest" 2>/dev/null) || continue
    if version_ge "$v" "$max"; then
      max="$v"
    fi
  done
  printf '%s' "$max"
}

# ---- 9-step state machine ----------------------------------------------------

STATE_FILE=""  # set after vault path created

state_mark() {
  local step="$1"
  [[ -n "$STATE_FILE" ]] || return 0
  printf '%s | %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$step" >> "$STATE_FILE"
}

state_marked() {
  local step="$1"
  [[ -f "$STATE_FILE" ]] || return 1
  grep -q "| $step\$" "$STATE_FILE"
}

state_unmark() {
  local step="$1"
  [[ -f "$STATE_FILE" ]] || return 0
  local tmp="$STATE_FILE.tmp.$$"
  grep -v "| $step\$" "$STATE_FILE" > "$tmp" || true
  mv "$tmp" "$STATE_FILE"
}

# ---- step 1: platform-check --------------------------------------------------

obsidian_effective_version() {
  # Obsidian self-updates its runtime by writing obsidian-<version>.asar into
  # ~/Library/Application Support/obsidian/ — the bundle's Info.plist
  # CFBundleShortVersionString stays at the installer version, which can lag
  # by months. The effective running version is max(installer, latest-asar).
  local app="$1"
  local installer
  installer=$(plutil -extract CFBundleShortVersionString raw "$app/Contents/Info.plist" 2>/dev/null) \
    || installer=""

  local latest_asar=""
  local asar_dir="$HOME/Library/Application Support/obsidian"
  if [[ -d "$asar_dir" ]]; then
    # Match obsidian-<digits.digits.digits>.asar (skip pre-release tags).
    local f v
    for f in "$asar_dir"/obsidian-*.asar; do
      [[ -f "$f" ]] || continue
      v=$(basename "$f" | sed -E 's/^obsidian-([0-9]+(\.[0-9]+)*).asar$/\1/')
      [[ "$v" =~ ^[0-9]+(\.[0-9]+)*$ ]] || continue
      if [[ -z "$latest_asar" ]] || version_ge "$v" "$latest_asar"; then
        latest_asar="$v"
      fi
    done
  fi

  # Pick the higher of the two.
  if [[ -n "$installer" && -n "$latest_asar" ]]; then
    if version_ge "$installer" "$latest_asar"; then
      printf '%s' "$installer"
    else
      printf '%s' "$latest_asar"
    fi
  elif [[ -n "$latest_asar" ]]; then
    printf '%s' "$latest_asar"
  else
    printf '%s' "$installer"
  fi
}

step_platform_check() {
  log_step "platform-check"

  # Claude Code CLI
  if ! command -v claude >/dev/null 2>&1; then
    fail "Claude Code is required." "Install from https://claude.com/claude-code, then re-run."
  fi
  log_info "claude: $(command -v claude)"

  # Obsidian.app
  local app
  if ! app=$(find_obsidian_app); then
    fail "Obsidian not found." "Download from https://obsidian.md/download (drag to Applications, open it once), then re-run."
  fi
  log_info "Obsidian: $app"

  # Obsidian quarantine check (recursive). xattr -pr exits non-zero when attr
  # absent; treat empty stdout as clean regardless of exit code.
  local qstdout
  qstdout=$(xattr -pr com.apple.quarantine "$app" 2>/dev/null || true)
  if [[ -n "$qstdout" && "$qstdout" == *com.apple.quarantine* ]]; then
    fail "Obsidian is quarantined (never launched)." "Open Obsidian once and approve macOS prompts, then quit and re-run."
  fi

  # Obsidian version. Honor the auto-updated runtime (obsidian-X.Y.Z.asar in
  # ~/Library/Application Support/obsidian/) over the bundle Info.plist if
  # higher — the asar is what Obsidian actually loads at runtime.
  local found
  found=$(obsidian_effective_version "$app")
  if [[ -z "$found" ]]; then
    fail "Could not parse Obsidian version." "Inspect $app/Contents/Info.plist and ~/Library/Application Support/obsidian/obsidian-*.asar."
  fi
  log_info "Obsidian effective version: $found"
  OBSIDIAN_APP="$app"
  OBSIDIAN_VERSION="$found"

  # Obsidian must not be running (registry-write safety later).
  if pgrep -x Obsidian >/dev/null; then
    fail "Obsidian is currently running." "Quit Obsidian, then re-run this install."
  fi

  state_mark "platform-check"
  log_install "platform-check" "ok" "obsidian=$found app=$app"
}

# ---- step 2: vault-created ---------------------------------------------------

step_vault_created() {
  log_step "vault-created at $VAULT_PATH"

  if [[ -e "$VAULT_PATH" ]]; then
    # Reject symlinks immediately — pwd -P canonicalization is below.
    if [[ -L "$VAULT_PATH" ]]; then
      fail "Vault path must not be a symlink." "Resolve to a real path and retry."
    fi

    # Existing-content policy.
    local has_obsidian=""
    [[ -d "$VAULT_PATH/.obsidian" ]] && has_obsidian="yes"

    if [[ -n "$has_obsidian" && -z "$FORCE" ]]; then
      fail "Vault already exists at $VAULT_PATH." "Choose another path with WORKDESK_VAULT_PATH=... or pass WORKDESK_INIT_FORCE=1 to reuse."
    fi
    if [[ -n "$has_obsidian" && -n "$FORCE" ]]; then
      log_info "WARN: --force enabled. Will merge into existing vault per ownership list."
    fi
  else
    if [[ -n "$DRY_RUN" ]]; then
      log_dryrun "mkdir -p $VAULT_PATH (chmod 0755)"
    else
      mkdir -p "$VAULT_PATH"
      chmod 0755 "$VAULT_PATH"
    fi
  fi

  # Canonicalize. cd-pwd-P resolves symlinks in parents and gets absolute path.
  # We previously rejected any path whose canonical form differed from its
  # logical form, but on macOS /tmp is a symlink to /private/tmp (and other
  # system aliases exist), so that check misfired for any /tmp-rooted path.
  # Direct symlinks at the vault path itself are rejected above via [[ -L ]].
  # Ancestor symlinks resolve safely through canonicalization.
  if [[ -d "$VAULT_PATH" ]]; then
    VAULT_PATH=$(cd "$VAULT_PATH" && pwd -P)
  fi

  log_info "canonical: $VAULT_PATH"

  # Set up state + log paths now that vault exists.
  if [[ -z "$DRY_RUN" ]]; then
    mkdir -p "$VAULT_PATH/config/state"
    STATE_FILE="$VAULT_PATH/config/state/install.md"
    INSTALL_LOG="$VAULT_PATH/config/state/install.log"
    touch "$STATE_FILE" "$INSTALL_LOG"
  fi

  state_mark "vault-created"
  log_install "vault-created" "ok" "$VAULT_PATH"
}

# ---- step 3: repo-fetched ----------------------------------------------------

SRC_DIR=""
TARBALL_SHA=""

step_repo_fetched() {
  log_step "repo-fetched at ref=$REF"

  local source_root="$VAULT_PATH/config/source"
  local tarball_url="https://github.com/$REPO_OWNER/$REPO_NAME/archive/refs/tags/${REF}.tar.gz"
  # If REF doesn't look like a tag (e.g., main, a branch), use the heads/ URL.
  if [[ ! "$REF" =~ ^v?[0-9] ]]; then
    tarball_url="https://github.com/$REPO_OWNER/$REPO_NAME/archive/refs/heads/${REF}.tar.gz"
  fi

  if [[ -n "$DRY_RUN" ]]; then
    log_dryrun "curl + tar from $tarball_url into $source_root"
    # In dry-run, point SRC_DIR at a local checkout if we're inside one, so
    # downstream steps can reason about vendored artifacts without fetching.
    if [[ -d "$(dirname "$0")/vendor/plugins" ]]; then
      SRC_DIR=$(cd "$(dirname "$0")" && pwd)
      log_info "(dry-run) using local checkout as SRC_DIR=$SRC_DIR"
    else
      SRC_DIR="<unfetched-source-root>"
      log_info "(dry-run) SRC_DIR placeholder (no local vendor/ found nearby)"
    fi
    return 0
  fi

  mkdir -p "$source_root"

  # Validate any existing fetched source.
  local existing_marker_sha=""
  if [[ -d "$source_root" ]]; then
    local existing_top
    existing_top=$(find "$source_root" -mindepth 1 -maxdepth 1 -type d | head -n1)
    if [[ -n "$existing_top" && -f "$existing_top/.workdesk-tarball-sha" && -f "$existing_top/bootstrap.sh" && -d "$existing_top/vendor/plugins" ]]; then
      existing_marker_sha=$(cat "$existing_top/.workdesk-tarball-sha" 2>/dev/null || echo "")
      local recorded_sha=""
      if [[ -f "$STATE_FILE" ]]; then
        recorded_sha=$(grep '| repo-fetched-sha=' "$STATE_FILE" | tail -n1 | sed 's/.*repo-fetched-sha=//')
      fi
      if [[ -n "$existing_marker_sha" && "$existing_marker_sha" == "$recorded_sha" ]]; then
        SRC_DIR="$existing_top"
        TARBALL_SHA="$existing_marker_sha"
        log_info "reusing existing source at $SRC_DIR (sha matches)"
        state_mark "repo-fetched"
        log_install "repo-fetched" "ok-cached" "sha=$TARBALL_SHA"
        return 0
      fi
      log_info "existing source tree present but sha mismatch; deleting before re-extract"
      rm -rf "$existing_top"
    fi
  fi

  local tmpfile
  tmpfile=$(mktemp -t workdesk-init-tarball).tar.gz
  # Use indirection so the trap firing after function exit doesn't trip
  # set -u when the local var has gone out of scope.
  trap '[[ -n "${tmpfile:-}" ]] && rm -f "$tmpfile"' RETURN

  log_info "downloading $tarball_url"
  curl -fsSL "$tarball_url" -o "$tmpfile" \
    || fail "Could not download $tarball_url" "Check network or report."

  TARBALL_SHA=$(shasum -a 256 "$tmpfile" | awk '{print $1}')
  log_info "tarball sha256 = $TARBALL_SHA"

  # Determine extracted top-level dir from tarball contents (don't hardcode).
  local top_count
  top_count=$(tar -tzf "$tmpfile" | cut -d/ -f1 | sort -u | wc -l | awk '{print $1}')
  if [[ "$top_count" -ne 1 ]]; then
    fail "Tarball has $top_count top-level entries (expected 1)." "Tarball at $tarball_url may be malformed; report."
  fi
  local extracted_top
  extracted_top=$(tar -tzf "$tmpfile" | head -1 | cut -d/ -f1)
  log_info "tarball top-level = $extracted_top"

  tar -xzf "$tmpfile" -C "$source_root"
  SRC_DIR="$source_root/$extracted_top"

  if [[ ! -f "$SRC_DIR/bootstrap.sh" || ! -d "$SRC_DIR/vendor/plugins" ]]; then
    fail "Extracted source at $SRC_DIR missing bootstrap.sh or vendor/plugins/" "Tarball may be from an unexpected ref ($REF)."
  fi

  printf '%s' "$TARBALL_SHA" > "$SRC_DIR/.workdesk-tarball-sha"
  log_install "repo-fetched-sha=$TARBALL_SHA" "info" ""
  state_mark "repo-fetched"
  log_install "repo-fetched" "ok" "src=$SRC_DIR sha=$TARBALL_SHA"
}

# ---- step 4: bootstrap-ran ---------------------------------------------------

step_bootstrap_ran() {
  log_step "bootstrap-ran"

  if state_marked "bootstrap-ran" \
    && [[ -d "$VAULT_PATH/config" && -f "$VAULT_PATH/.claude/settings.json" && -d "$VAULT_PATH/.obsidian" ]]; then
    log_info "already complete"
    return 0
  fi
  state_unmark "bootstrap-ran"

  if [[ -n "$DRY_RUN" ]]; then
    log_dryrun "bash $SRC_DIR/bootstrap.sh $VAULT_PATH"
    return 0
  fi

  bash "$SRC_DIR/bootstrap.sh" "$VAULT_PATH" </dev/null \
    || fail "bootstrap.sh failed." "Inspect $INSTALL_LOG and the terminal output above."

  state_mark "bootstrap-ran"
  log_install "bootstrap-ran" "ok" ""
}

# ---- step 5: plugins-vendored ------------------------------------------------

step_plugins_vendored() {
  log_step "plugins-vendored (1 plugin)"

  local plugins_dst="$VAULT_PATH/.obsidian/plugins"

  for id in "${PLUGIN_IDS[@]}"; do
    local src="$SRC_DIR/vendor/plugins/$id"
    local dst="$plugins_dst/$id"
    local upstream="$src/UPSTREAM.md"

    if [[ ! -d "$src" ]]; then
      if [[ -n "$DRY_RUN" ]]; then
        log_dryrun "would verify SHA256 + cp $src → $dst"
        continue
      fi
      fail "Vendored plugin missing: $src" "Tarball may be incomplete."
    fi

    # Verify each artifact's SHA256 against UPSTREAM.md. The table format:
    #   | `main.js` | `<sha256>` |
    local artifact
    for artifact in main.js manifest.json styles.css; do
      [[ -f "$src/$artifact" ]] || continue
      local actual_sha expected_sha
      actual_sha=$(shasum -a 256 "$src/$artifact" | awk '{print $1}')
      expected_sha=$(grep -E "\`$artifact\`" "$upstream" | grep -oE '[a-f0-9]{64}' | head -n1)
      if [[ -z "$expected_sha" ]]; then
        fail "UPSTREAM.md for $id missing SHA256 for $artifact" "Run scripts/refresh-vendored-plugins.sh and recommit."
      fi
      if [[ "$actual_sha" != "$expected_sha" ]]; then
        fail "Plugin $id $artifact SHA256 mismatch (got $actual_sha expected $expected_sha)" "Re-clone or report."
      fi
    done

    # Validate manifest parseability.
    json_ok "$src/manifest.json" || fail "Vendored manifest invalid: $src/manifest.json" "Re-clone or report."

    if [[ -n "$DRY_RUN" ]]; then
      log_dryrun "cp -R $src $dst"
      continue
    fi

    mkdir -p "$plugins_dst"
    if [[ -d "$dst" ]]; then
      # Overwrite per ownership list — only main.js / manifest.json / styles.css.
      cp "$src/main.js" "$dst/main.js"
      cp "$src/manifest.json" "$dst/manifest.json"
      [[ -f "$src/styles.css" ]] && cp "$src/styles.css" "$dst/styles.css"
    else
      mkdir -p "$dst"
      cp "$src/main.js" "$dst/main.js"
      cp "$src/manifest.json" "$dst/manifest.json"
      [[ -f "$src/styles.css" ]] && cp "$src/styles.css" "$dst/styles.css"
    fi
    log_info "  ✓ $id"
  done

  # Now that we have the source tree's manifests, run Obsidian min-version check.
  if [[ -n "$DRY_RUN" && ! -d "$SRC_DIR/vendor/plugins" ]]; then
    log_dryrun "(dry-run) skipping Obsidian min-version check — no source tree"
    state_mark "plugins-vendored"
    return 0
  fi
  local required
  required=$(required_obsidian_version "$SRC_DIR")
  log_info "max plugin minAppVersion = $required (Obsidian = $OBSIDIAN_VERSION)"
  case $(version_ge "$OBSIDIAN_VERSION" "$required"; echo $?) in
    0) ;;
    1) fail "Obsidian version $OBSIDIAN_VERSION is older than required $required." "Update Obsidian, then re-run." ;;
    2) fail "Could not parse Obsidian version ($OBSIDIAN_VERSION) or required version ($required)." "Inspect or report." ;;
  esac

  state_mark "plugins-vendored"
  log_install "plugins-vendored" "ok" "${#PLUGIN_IDS[@]} plugin(s)"
}

# ---- step 6: community-plugins-enabled --------------------------------------

step_community_plugins_enabled() {
  log_step "community-plugins-enabled"

  local cp_file="$VAULT_PATH/.obsidian/community-plugins.json"

  if [[ -n "$DRY_RUN" ]]; then
    log_dryrun "merge ${#PLUGIN_IDS[@]} id(s) into $cp_file"
    return 0
  fi

  # Build a deduped union of existing ids + our 7. plutil's `-insert N
  # -string ... -append` is unreliable on some macOS versions (Trace/BPT trap)
  # so we collect ids in a bash array, dedupe, then write the JSON literal
  # directly — one shot, no incremental plutil mutations.
  local merged=()
  if [[ -f "$cp_file" ]] && json_ok "$cp_file"; then
    local i=0 val
    while val=$(plutil -extract "$i" raw "$cp_file" 2>/dev/null); do
      merged+=("$val")
      i=$((i+1))
    done
  fi

  local id present
  for id in "${PLUGIN_IDS[@]}"; do
    present=""
    for existing in ${merged[@]+"${merged[@]}"}; do
      [[ "$existing" == "$id" ]] && { present="yes"; break; }
    done
    [[ -z "$present" ]] && merged+=("$id")
  done

  # Compose the JSON array literal manually — ids are plain ASCII plugin slugs,
  # no escaping needed.
  local tmp="$cp_file.tmp.$$"
  {
    printf '['
    local first=1
    for id in "${merged[@]}"; do
      [[ "$first" -eq 1 ]] && first=0 || printf ','
      printf '"%s"' "$id"
    done
    printf ']'
  } > "$tmp"

  json_ok "$tmp" || { rm -f "$tmp"; fail "community-plugins.json write produced invalid JSON" "Inspect $tmp"; }
  mv "$tmp" "$cp_file"

  state_mark "community-plugins-enabled"
  log_install "community-plugins-enabled" "ok" "${#PLUGIN_IDS[@]} id(s) merged"
}

# ---- step 7: brat-seeded -----------------------------------------------------

step_brat_seeded() {
  log_step "brat-seeded"

  local brat_dir="$VAULT_PATH/.obsidian/plugins/obsidian42-brat"
  local data_json="$brat_dir/data.json"
  local fixture="$SRC_DIR/vendor/plugins/obsidian42-brat/data.json.fixture"

  # Pre-write version check: vendored manifest must match the version the
  # fixture was generated against. Spec pins this to 2.0.4 — bumping BRAT
  # without regenerating the fixture would silently apply a stale schema.
  local vendored_version=""
  if [[ -f "$brat_dir/manifest.json" ]]; then
    vendored_version=$(plutil -extract version raw "$brat_dir/manifest.json" 2>/dev/null || echo "")
  elif [[ -n "$DRY_RUN" ]]; then
    log_dryrun "would verify BRAT vendored manifest version == 2.0.4"
    state_mark "brat-seeded"
    return 0
  fi
  if [[ -z "$vendored_version" ]]; then
    fail "Could not read BRAT vendored manifest version" "Tarball may be incomplete."
  fi
  if [[ "$vendored_version" != "2.0.4" ]]; then
    fail "BRAT vendored version is $vendored_version, fixture pinned to 2.0.4" "Re-vendor the fixture before installing (scripts/regenerate-brat-fixture.sh)."
  fi

  if [[ ! -f "$fixture" ]]; then
    if [[ -n "$DRY_RUN" ]]; then
      log_dryrun "would copy BRAT fixture from $fixture → $data_json"
      state_mark "brat-seeded"
      return 0
    fi
    fail "BRAT fixture missing at $fixture" "Tarball may be incomplete."
  fi

  if [[ -n "$DRY_RUN" ]]; then
    log_dryrun "cp $fixture $data_json"
    return 0
  fi

  # Atomic copy
  local tmp="$data_json.tmp.$$"
  cp "$fixture" "$tmp"
  json_ok "$tmp" || { rm -f "$tmp"; fail "BRAT fixture is not valid JSON" "Re-vendor."; }

  # Validate required structural keys in the source-of-truth fixture.
  # As of v1.4.0, pluginList and pluginSubListFrozenVersion ship EMPTY — BRAT
  # is the only bundled plugin and operators install everything else opt-in
  # via BRAT's "Add a beta plugin" command. Validate the keys exist and are
  # arrays of length 0.
  local pl_count psl_count
  pl_count=$(plutil -extract pluginList raw "$tmp" 2>/dev/null | wc -l | tr -d ' ')
  psl_count=$(plutil -extract pluginSubListFrozenVersion raw "$tmp" 2>/dev/null | wc -l | tr -d ' ')
  # plutil -extract on an empty array emits a single empty line; non-empty arrays emit one line per element.
  # Treat both 0 and 1 as "empty-shaped"; reject if any element is present beyond that.
  local pl_first psl_first
  pl_first=$(plutil -extract pluginList.0 raw "$tmp" 2>/dev/null) || pl_first=""
  psl_first=$(plutil -extract pluginSubListFrozenVersion.0.repo raw "$tmp" 2>/dev/null) || psl_first=""
  if [[ -n "$pl_first" ]]; then
    rm -f "$tmp"
    fail "BRAT fixture pluginList is non-empty ('$pl_first'); v1.4.0 ships empty for opt-in plugin install" "Re-vendor — see scripts/regenerate-brat-fixture.sh."
  fi
  if [[ -n "$psl_first" ]]; then
    rm -f "$tmp"
    fail "BRAT fixture pluginSubListFrozenVersion is non-empty ('$psl_first'); v1.4.0 ships empty for opt-in plugin install" "Re-vendor — see scripts/regenerate-brat-fixture.sh."
  fi

  mv "$tmp" "$data_json"

  state_mark "brat-seeded"
  log_install "brat-seeded" "ok" "empty plugin list — operators install opt-in via BRAT"
}

# ---- step 8: obsidian-vault-registered ---------------------------------------

step_obsidian_vault_registered() {
  log_step "obsidian-vault-registered"

  local registry="$HOME/Library/Application Support/obsidian/obsidian.json"

  if pgrep -x Obsidian >/dev/null; then
    fail "Obsidian started running mid-install." "Quit Obsidian and re-run."
  fi

  if [[ -n "$DRY_RUN" ]]; then
    log_dryrun "register $VAULT_PATH in $registry"
    return 0
  fi

  mkdir -p "$(dirname "$registry")"
  if [[ ! -f "$registry" ]]; then
    printf '{"vaults":{}}' > "$registry"
  fi

  json_ok "$registry" \
    || fail "Obsidian's vault registry at $registry is malformed." "Inspect or remove it before retrying."

  local tmp="$registry.tmp.$$"
  cp "$registry" "$tmp"

  # Ensure vaults key exists and is a dict.
  if ! plutil -extract vaults json -o - "$tmp" >/dev/null 2>&1; then
    plutil -insert vaults -dictionary "$tmp"
  fi

  # Duplicate-path detection.
  local existing_id="" canonical="$VAULT_PATH"
  local ids
  ids=$(plutil -extract vaults json -o - "$tmp" 2>/dev/null \
    | grep -oE '"[a-f0-9]{16}"' | tr -d '"' || true)
  for vid in $ids; do
    local p
    p=$(plutil -extract "vaults.$vid.path" raw "$tmp" 2>/dev/null) || continue
    if [[ "$p" == "$canonical" ]]; then
      existing_id="$vid"
      break
    fi
  done

  if [[ -n "$existing_id" ]]; then
    log_info "vault already registered as id $existing_id; reusing"
  else
    local new_id
    new_id=$(openssl rand -hex 8)
    local now_millis=$(( $(date +%s) * 1000 ))
    plutil -insert "vaults.$new_id" -dictionary "$tmp"
    plutil -insert "vaults.$new_id.path" -string "$canonical" "$tmp"
    plutil -insert "vaults.$new_id.ts" -integer "$now_millis" "$tmp"
    log_info "registered new vault id $new_id"
  fi

  json_ok "$tmp" || { rm -f "$tmp"; fail "registry update produced invalid JSON" "Inspect $tmp"; }
  mv "$tmp" "$registry"

  state_mark "obsidian-vault-registered"
  log_install "obsidian-vault-registered" "ok" ""
}

# ---- step 9: install-complete ------------------------------------------------

step_install_complete() {
  log_step "install-complete (re-validating all artifacts)"

  # In dry-run, no files were written by prior steps — skip the artifact
  # re-validation but still mark the step so the dry-run completes cleanly
  # (exit 0). The README documents --dry-run as a preview; it must not fail.
  if [[ -n "$DRY_RUN" ]]; then
    log_dryrun "(dry-run) skipping artifact re-validation"
    state_mark "install-complete"
    return 0
  fi

  # Re-check every prior step's artifacts at the moment of marker write.
  [[ -d "$VAULT_PATH/config" ]] || fail "config/ missing" "Re-run init.sh."
  [[ -f "$VAULT_PATH/.claude/settings.json" ]] || fail ".claude/settings.json missing" "Re-run init.sh."
  for id in "${PLUGIN_IDS[@]}"; do
    [[ -f "$VAULT_PATH/.obsidian/plugins/$id/manifest.json" ]] \
      || fail "Plugin $id manifest missing" "Re-run init.sh."
  done
  json_ok "$VAULT_PATH/.obsidian/community-plugins.json" \
    || fail "community-plugins.json invalid" "Re-run init.sh."
  json_ok "$VAULT_PATH/.obsidian/plugins/obsidian42-brat/data.json" \
    || fail "BRAT data.json invalid" "Re-run init.sh."
  json_ok "$HOME/Library/Application Support/obsidian/obsidian.json" \
    || fail "obsidian.json registry invalid" "Re-run init.sh."

  state_mark "install-complete"
  log_install "install-complete" "ok" ""
}

# ---- main --------------------------------------------------------------------

main() {
  if [[ -n "$DRY_RUN" ]]; then
    printf '\nWorkDesk OS init.sh — DRY RUN (no writes)\n\n'
  fi

  step_platform_check
  step_vault_created
  step_repo_fetched
  step_bootstrap_ran
  step_plugins_vendored
  step_community_plugins_enabled
  step_brat_seeded
  step_obsidian_vault_registered
  step_install_complete

  printf '\nWorkDesk installed at %s.\nOpen Obsidian, then run /onboarding in the terminal panel.\n\n' "$VAULT_PATH"

  if [[ -n "$OPEN_AFTER" && -z "$DRY_RUN" ]]; then
    open -a Obsidian "$VAULT_PATH"
  fi
}

main "$@"

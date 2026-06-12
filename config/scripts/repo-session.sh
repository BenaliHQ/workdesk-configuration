#!/usr/bin/env bash
# repo-session.sh - isolate repo work across simultaneous agent sessions.

set -euo pipefail
IFS=$'\n\t'

WORKTREES_ROOT="${WORKTREES_ROOT:-$HOME/code/.worktrees}"
REGISTRY="$WORKTREES_ROOT/.registry"
LOCKS="$WORKTREES_ROOT/.locks"

log() { printf '%s\n' "$*"; }
err() { printf '%s\n' "$*" >&2; }
die() { err "$*"; exit 1; }

require() {
  command -v "$1" >/dev/null 2>&1 || die "I need '$1' to do that, but it is not installed."
}

ensure_dirs() {
  mkdir -p "$REGISTRY" "$LOCKS"
}

now_epoch() {
  date +%s
}

lowercase() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

normalize_task() {
  local task
  task="$(lowercase "$1")"
  if [[ ! "$task" =~ ^[a-z0-9-]+$ ]]; then
    die "Please use a short task name with only lowercase letters, numbers, and hyphens."
  fi
  printf '%s\n' "$task"
}

normalize_agent() {
  local agent
  agent="$(lowercase "$1")"
  if [[ ! "$agent" =~ ^[a-z0-9-]+$ ]]; then
    die "Please use an agent name with only letters, numbers, and hyphens."
  fi
  printf '%s\n' "$agent"
}

resolve_agent() {
  local explicit="${1:-}"
  if [[ -n "$explicit" ]]; then
    normalize_agent "$explicit"
  elif [[ -n "${REPO_SESSION_AGENT:-}" ]]; then
    normalize_agent "$REPO_SESSION_AGENT"
  elif [[ -n "${CLAUDECODE:-}" ]]; then
    printf 'claude\n'
  elif env | grep -q '^CODEX_'; then
    printf 'codex\n'
  else
    printf 'agent\n'
  fi
}

resolve_repo() {
  local repo="$1"
  local path
  if [[ -d "$repo" ]]; then
    path="$(cd "$repo" && pwd -P)"
  elif [[ -d "$HOME/code/$repo" ]]; then
    path="$(cd "$HOME/code/$repo" && pwd -P)"
  else
    die "I don't know a repo called $repo."
  fi

  git -C "$path" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || die "$repo is not a Git repo I can work with."
  printf '%s\n' "$path"
}

json_get() {
  local file="$1"
  local key="$2"
  python3 - "$file" "$key" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)
    value = data
    for part in sys.argv[2].split("."):
        if not isinstance(value, dict):
            value = ""
            break
        value = value.get(part, "")
    if value is None:
        value = ""
    print(value)
except Exception:
    print("")
PY
}

write_lease() {
  local lease="$1"
  local repo_name="$2"
  local repo_path="$3"
  local task="$4"
  local agent="$5"
  local branch="$6"
  local worktree="$7"
  local created="$8"
  local last_used="$9"

  mkdir -p "$(dirname "$lease")"
  LEASE_PATH="$lease" \
  LEASE_REPO="$repo_name" \
  LEASE_REPO_PATH="$repo_path" \
  LEASE_TASK="$task" \
  LEASE_AGENT="$agent" \
  LEASE_BRANCH="$branch" \
  LEASE_WORKTREE="$worktree" \
  LEASE_CREATED="$created" \
  LEASE_LAST_USED="$last_used" \
  LEASE_PID="$$" \
  python3 - <<'PY'
import json
import os

path = os.environ["LEASE_PATH"]
data = {
    "repo": os.environ["LEASE_REPO"],
    "repo_path": os.environ["LEASE_REPO_PATH"],
    "task": os.environ["LEASE_TASK"],
    "agent": os.environ["LEASE_AGENT"],
    "branch": os.environ["LEASE_BRANCH"],
    "worktree": os.environ["LEASE_WORKTREE"],
    "created": int(os.environ["LEASE_CREATED"]),
    "last_used": int(os.environ["LEASE_LAST_USED"]),
    "pid": int(os.environ["LEASE_PID"]),
}
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, sort_keys=True)
    f.write("\n")
os.replace(tmp, path)
PY
}

touch_lease() {
  local lease="$1"
  local now
  now="$(now_epoch)"
  LEASE_PATH="$lease" LEASE_LAST_USED="$now" LEASE_PID="$$" python3 - <<'PY'
import json
import os

path = os.environ["LEASE_PATH"]
try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception:
    data = {}
now = int(os.environ["LEASE_LAST_USED"])
data["last_used"] = now
data["pid"] = int(os.environ["LEASE_PID"])
data.setdefault("created", now)
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, sort_keys=True)
    f.write("\n")
os.replace(tmp, path)
PY
}

lease_paths_sorted() {
  [[ -d "$REGISTRY" ]] || return 0
  python3 - "$REGISTRY" <<'PY'
import glob
import json
import os
import sys

rows = []
for path in glob.glob(os.path.join(sys.argv[1], "*.json")):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        created = int(data.get("created") or 0)
    except Exception:
        created = 0
    rows.append((created, path))
for _, path in sorted(rows):
    print(path)
PY
}

human_age() {
  local seconds="$1"
  case "$seconds" in
    ''|*[!0-9]*) seconds=0 ;;
  esac
  if [[ "$seconds" -lt 0 ]]; then
    seconds=0
  fi
  if [[ "$seconds" -lt 60 ]]; then
    printf '%ss\n' "$seconds"
  elif [[ "$seconds" -lt 3600 ]]; then
    printf '%sm\n' "$((seconds / 60))"
  elif [[ "$seconds" -lt 86400 ]]; then
    printf '%sh\n' "$((seconds / 3600))"
  else
    printf '%sd\n' "$((seconds / 86400))"
  fi
}

format_time() {
  python3 - "$1" <<'PY'
from datetime import datetime
import sys

try:
    value = int(sys.argv[1])
    print(datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S"))
except Exception:
    print("unknown time")
PY
}

mtime_epoch() {
  local path="$1"
  if stat -f %m "$path" >/dev/null 2>&1; then
    stat -f %m "$path"
  elif stat -c %Y "$path" >/dev/null 2>&1; then
    stat -c %Y "$path"
  else
    printf '0\n'
  fi
}

pid_alive() {
  local pid="$1"
  case "$pid" in
    ''|*[!0-9]*) return 1 ;;
  esac
  kill -0 "$pid" >/dev/null 2>&1
}

branch_exists() {
  local repo="$1"
  local branch="$2"
  git -C "$repo" show-ref --verify --quiet "refs/heads/$branch"
}

default_branch_for() {
  local repo="$1"
  local remote_head
  remote_head="$(git -C "$repo" symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || true)"
  case "$remote_head" in
    origin/*) printf '%s\n' "${remote_head#origin/}" ;;
    *) printf 'main\n' ;;
  esac
}

warn_shared_state() {
  local repo_path="$1"
  local repo_name="$2"
  local default_branch="$3"
  local dirty
  local ahead

  dirty="$(git -C "$repo_path" status --porcelain --untracked-files=normal 2>/dev/null || true)"
  if [[ -n "$dirty" ]]; then
    log "Heads up: the main copy of $repo_name has unsaved changes (probably another session). Your new workspace is separate from it - leaving it alone."
  fi

  if git -C "$repo_path" show-ref --verify --quiet "refs/heads/$default_branch" \
    && git -C "$repo_path" show-ref --verify --quiet "refs/remotes/origin/$default_branch"; then
    ahead="$(git -C "$repo_path" rev-list "origin/$default_branch..$default_branch" --count 2>/dev/null || printf '0')"
    if [[ "$ahead" =~ ^[0-9]+$ ]] && [[ "$ahead" -gt 0 ]]; then
      log "Heads up: $repo_name's local $default_branch has $ahead commits that haven't been shared yet (another session's work in progress). Your workspace is based on the shared version, so you're safe - but don't copy files from the main checkout."
    fi
  fi
}

cmd_start() {
  require git
  require python3
  ensure_dirs

  local agent_flag=""
  local args=()
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --agent)
        shift
        [[ "$#" -gt 0 ]] || die "Please say which agent to use after --agent."
        agent_flag="$1"
        ;;
      *)
        args+=("$1")
        ;;
    esac
    shift
  done

  [[ "${#args[@]}" -eq 2 ]] || die "Use: repo-session.sh start <repo> <task>"

  local repo_arg="${args[0]}"
  local task
  local agent
  local repo_path
  local repo_name
  local default_branch
  local wt_path
  local branch
  local lease
  local now
  local lease_branch
  local lease_agent
  local current_branch

  task="$(normalize_task "${args[1]}")"
  agent="$(resolve_agent "$agent_flag")"
  repo_path="$(resolve_repo "$repo_arg")"
  repo_name="$(basename "$repo_path")"
  wt_path="$WORKTREES_ROOT/$repo_name/$task"
  branch="$agent/$task"
  lease="$REGISTRY/$repo_name--$task.json"

  if ! git -C "$repo_path" fetch origin --quiet; then
    log "Heads up: I could not refresh $repo_name from the shared remote, so I am using the best local copy of the shared version."
  fi

  default_branch="$(default_branch_for "$repo_path")"
  warn_shared_state "$repo_path" "$repo_name" "$default_branch"

  if [[ -f "$lease" && -d "$wt_path" ]]; then
    lease_branch="$(json_get "$lease" branch)"
    current_branch="$(git -C "$wt_path" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
    if [[ -n "$lease_branch" && "$current_branch" == "$lease_branch" ]]; then
      log "Resuming your existing workspace for '$task'."
      touch_lease "$lease"
      log "WORKTREE=$wt_path"
      return 0
    fi
  fi

  git -C "$repo_path" worktree prune >/dev/null 2>&1 || true

  if [[ -f "$lease" ]]; then
    lease_branch="$(json_get "$lease" branch)"
    lease_agent="$(json_get "$lease" agent)"
    if [[ -n "$lease_branch" ]]; then
      branch="$lease_branch"
    fi
    if [[ -n "$lease_agent" ]]; then
      agent="$lease_agent"
    fi
  fi

  if [[ -e "$wt_path" ]]; then
    die "A workspace already exists at $wt_path, but it is not in a clean resumable state."
  fi

  mkdir -p "$(dirname "$wt_path")"
  if branch_exists "$repo_path" "$branch"; then
    git -C "$repo_path" worktree add "$wt_path" "$branch" >/dev/null \
      || die "I could not reopen the existing workspace for '$task'."
  else
    git -C "$repo_path" show-ref --verify --quiet "refs/remotes/origin/$default_branch" \
      || die "I could not find the shared $default_branch version for $repo_name."
    git -C "$repo_path" worktree add "$wt_path" -b "$branch" "origin/$default_branch" >/dev/null \
      || die "I could not create a private workspace for '$task'."
  fi

  now="$(now_epoch)"
  write_lease "$lease" "$repo_name" "$repo_path" "$task" "$agent" "$branch" "$wt_path" "$now" "$now"

  log "You're set up in your own private copy of $repo_name for '$task'."
  log "Nothing you do here can collide with any other session."
  log "When the work is ready, run: repo-session.sh finish $task"
  log "WORKTREE=$wt_path"
}

print_locks() {
  [[ -d "$LOCKS" ]] || return 0
  local lockdir
  local printed=0
  local name
  local meta
  local agent
  local started
  local now
  local age

  now="$(now_epoch)"
  while IFS= read -r lockdir; do
    [[ -n "$lockdir" ]] || continue
    meta="$lockdir/meta.json"
    name="$(basename "$lockdir" .lock)"
    agent="unknown"
    started=""
    if [[ -f "$meta" ]]; then
      agent="$(json_get "$meta" agent)"
      started="$(json_get "$meta" started)"
      [[ -n "$agent" ]] || agent="unknown"
    fi
    case "$started" in
      ''|*[!0-9]*) age="unknown" ;;
      *) age="$(human_age "$((now - started))")" ;;
    esac
    if [[ "$printed" -eq 0 ]]; then
      log ""
      log "Held resources:"
      printf '%-22s %-12s %-6s %s\n' "RESOURCE" "HELD BY" "AGE" "PATH"
      printed=1
    fi
    printf '%-22s %-12s %-6s %s\n' "$name" "$agent" "$age" "$lockdir"
  done < <(find "$LOCKS" -type d -name '*.lock' -print | LC_ALL=C sort)
}

cmd_status() {
  require python3
  ensure_dirs

  local lease
  local worktree
  local agent
  local task
  local repo
  local last_used
  local now
  local age
  local active=0

  now="$(now_epoch)"
  while IFS= read -r lease; do
    [[ -n "$lease" ]] || continue
    worktree="$(json_get "$lease" worktree)"
    if [[ -z "$worktree" || ! -d "$worktree" ]]; then
      rm -f -- "$lease"
      continue
    fi

    if [[ "$active" -eq 0 ]]; then
      printf '%-10s %-22s %-18s %-6s %s\n' "AGENT" "TASK" "REPO" "AGE" "WORKTREE"
    fi
    active=$((active + 1))
    agent="$(json_get "$lease" agent)"
    task="$(json_get "$lease" task)"
    repo="$(json_get "$lease" repo)"
    last_used="$(json_get "$lease" last_used)"
    case "$last_used" in
      ''|*[!0-9]*) age="unknown" ;;
      *) age="$(human_age "$((now - last_used))")" ;;
    esac
    printf '%-10s %-22s %-18s %-6s %s\n' "$agent" "$task" "$repo" "$age" "$worktree"
  done < <(lease_paths_sorted)

  if [[ "$active" -eq 0 ]]; then
    log "No active workspaces. Everything is tidy."
  fi
  print_locks
}

locate_lease() {
  local target="$1"
  local found=""
  local count=0
  local lease
  local task
  local worktree
  local target_path

  ensure_dirs
  if [[ "$target" == */* || -d "$target" ]]; then
    if [[ -d "$target" ]]; then
      target_path="$(cd "$target" && pwd -P)"
    else
      target_path="$target"
    fi
    while IFS= read -r lease; do
      worktree="$(json_get "$lease" worktree)"
      if [[ "$worktree" == "$target_path" ]]; then
        found="$lease"
        count=$((count + 1))
      fi
    done < <(lease_paths_sorted)
  else
    task="$(normalize_task "$target")"
    while IFS= read -r lease; do
      found="$lease"
      count=$((count + 1))
    done < <(find "$REGISTRY" -type f -name "*--$task.json" -print | LC_ALL=C sort)
  fi

  if [[ "$count" -eq 0 ]]; then
    die "I don't see an active workspace for $target."
  elif [[ "$count" -gt 1 ]]; then
    die "More than one active workspace matches $target. Use the full workspace path."
  fi
  printf '%s\n' "$found"
}

worktree_dirty() {
  local worktree="$1"
  [[ -n "$(git -C "$worktree" status --porcelain --untracked-files=normal 2>/dev/null || true)" ]]
}

cmd_finish() {
  require git
  ensure_dirs

  local target=""
  local create_pr=1
  local keep=0
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --no-pr) create_pr=0 ;;
      --keep) keep=1 ;;
      *)
        if [[ -n "$target" ]]; then
          die "Use: repo-session.sh finish <task-or-workspace> [--no-pr] [--keep]"
        fi
        target="$1"
        ;;
    esac
    shift
  done
  [[ -n "$target" ]] || die "Use: repo-session.sh finish <task-or-workspace> [--no-pr] [--keep]"

  local lease
  local worktree
  local repo_path
  local task
  local branch
  local pr_url=""

  lease="$(locate_lease "$target")"
  worktree="$(json_get "$lease" worktree)"
  repo_path="$(json_get "$lease" repo_path)"
  task="$(json_get "$lease" task)"
  branch="$(json_get "$lease" branch)"

  [[ -d "$worktree" ]] || die "That private workspace is gone, so there is nothing to finish."
  if worktree_dirty "$worktree"; then
    die "There are unsaved changes in this workspace. Commit them first (or ask your agent to), then run finish again."
  fi

  log "Handing off '$task' for review..."
  git -C "$worktree" push -u origin "$branch" >/dev/null \
    || die "I could not hand off this workspace because the upload failed."

  if [[ "$create_pr" -eq 1 ]]; then
    if command -v gh >/dev/null 2>&1; then
      set +e
      pr_url="$(cd "$worktree" && gh pr create --fill 2>/dev/null)"
      set -e
    fi
    if [[ -n "$pr_url" ]]; then
      log "Review request opened: $pr_url"
    else
      log "The branch '$branch' is uploaded. Open a review request from it when you're ready."
    fi
  else
    log "The branch '$branch' is uploaded."
  fi

  if [[ "$keep" -eq 0 ]]; then
    git -C "$repo_path" worktree remove "$worktree" >/dev/null 2>&1 \
      || die "The work was handed off, but I could not clean up the private workspace."
  else
    log "I left the private workspace in place: $worktree"
  fi
  rm -f -- "$lease"
  log "Work on '$task' has been handed off for review. Your private workspace is cleaned up."
}

cmd_cleanup() {
  require git
  require python3
  ensure_dirs

  local days=7
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --days)
        shift
        [[ "$#" -gt 0 ]] || die "Please give a number of days after --days."
        days="$1"
        ;;
      *)
        die "Use: repo-session.sh cleanup [--days N]"
        ;;
    esac
    shift
  done
  case "$days" in
    ''|*[!0-9]*) die "Please give cleanup days as a whole number." ;;
  esac

  local now
  local cutoff
  local repos_file
  local lease
  local last_used
  local worktree
  local repo_path
  local task
  local reaped=0
  local skipped=0
  local pruned=0

  now="$(now_epoch)"
  cutoff="$((now - (days * 86400)))"
  repos_file="$(mktemp "${TMPDIR:-/tmp}/repo-session-repos.XXXXXX")"
  trap 'rm -f "$repos_file"' EXIT

  while IFS= read -r lease; do
    [[ -n "$lease" ]] || continue
    worktree="$(json_get "$lease" worktree)"
    repo_path="$(json_get "$lease" repo_path)"
    task="$(json_get "$lease" task)"
    last_used="$(json_get "$lease" last_used)"
    [[ -n "$repo_path" ]] && printf '%s\n' "$repo_path" >> "$repos_file"

    if [[ -z "$worktree" || ! -d "$worktree" ]]; then
      rm -f -- "$lease"
      pruned=$((pruned + 1))
      continue
    fi
    case "$last_used" in
      ''|*[!0-9]*) continue ;;
    esac
    if [[ "$last_used" -ge "$cutoff" ]]; then
      continue
    fi
    if worktree_dirty "$worktree"; then
      log "Skipping '$task' because it has unsaved changes."
      skipped=$((skipped + 1))
      continue
    fi
    if git -C "$repo_path" worktree remove "$worktree" >/dev/null 2>&1; then
      rm -f -- "$lease"
      reaped=$((reaped + 1))
    else
      log "Skipping '$task' because I could not clean up its private workspace safely."
      skipped=$((skipped + 1))
    fi
  done < <(lease_paths_sorted)

  LC_ALL=C sort -u "$repos_file" | while IFS= read -r repo_path; do
    [[ -n "$repo_path" && -d "$repo_path" ]] || continue
    git -C "$repo_path" worktree prune >/dev/null 2>&1 || true
  done

  rm -f -- "$repos_file"
  trap - EXIT
  log "Cleaned up $reaped old workspace(s). Skipped $skipped with unsaved changes. Pruned $pruned missing record(s)."
}

validate_lock_name() {
  local name="$1"
  if [[ ! "$name" =~ ^[A-Za-z0-9._-]+$ ]]; then
    die "Please use a resource name with only letters, numbers, dots, underscores, and hyphens."
  fi
}

write_lock_meta() {
  local lockdir="$1"
  local owner_pid="$2"
  local agent="$3"
  local started="$4"

  LOCK_META="$lockdir/meta.json" \
  LOCK_PID="$owner_pid" \
  LOCK_AGENT="$agent" \
  LOCK_STARTED="$started" \
  python3 - <<'PY'
import json
import os

path = os.environ["LOCK_META"]
data = {
    "pid": int(os.environ["LOCK_PID"]),
    "agent": os.environ["LOCK_AGENT"],
    "started": int(os.environ["LOCK_STARTED"]),
}
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, sort_keys=True)
    f.write("\n")
os.replace(tmp, path)
PY
}

acquire_lock() {
  require python3
  ensure_dirs

  local name="$1"
  local owner_pid="$2"
  local agent
  local timeout
  local deadline
  local lockdir
  local meta
  local holder_pid
  local holder_agent
  local holder_started
  local last_holder_agent="another session"
  local last_holder_started=""
  local meta_present
  local meta_mtime
  local stale_note=""
  local now
  local waited=0

  validate_lock_name "$name"
  agent="$(resolve_agent "")"
  timeout="${REPO_SESSION_LOCK_TIMEOUT:-300}"
  case "$timeout" in
    ''|*[!0-9]*) timeout=300 ;;
  esac
  deadline="$(( $(now_epoch) + timeout ))"
  lockdir="$LOCKS/$name.lock"
  meta="$lockdir/meta.json"

  while :; do
    now="$(now_epoch)"
    if [[ "$waited" -eq 1 && "$now" -ge "$deadline" ]]; then
      die "Resource '$name' is in use by $last_holder_agent (since $(format_time "$last_holder_started")). Try again later or run: repo-session.sh lock-release $name if you're sure it's stuck."
    fi

    if mkdir "$lockdir" 2>/dev/null; then
      write_lock_meta "$lockdir" "$owner_pid" "$agent" "$(now_epoch)"
      if [[ -n "$stale_note" ]]; then
        log "$stale_note"
      fi
      return 0
    fi

    holder_pid=""
    holder_agent="another session"
    holder_started=""
    meta_present=0
    if [[ -f "$meta" ]]; then
      meta_present=1
      holder_pid="$(json_get "$meta" pid)"
      holder_agent="$(json_get "$meta" agent)"
      holder_started="$(json_get "$meta" started)"
      [[ -n "$holder_agent" ]] || holder_agent="another session"
    fi
    last_holder_agent="$holder_agent"
    last_holder_started="$holder_started"
    waited=1

    now="$(now_epoch)"
    if [[ "$meta_present" -eq 1 && -z "$holder_pid" ]]; then
      meta_mtime="$(mtime_epoch "$meta")"
      if [[ "$meta_mtime" =~ ^[0-9]+$ ]] && [[ "$((now - meta_mtime))" -lt 2 ]]; then
        sleep 1
        continue
      fi
    fi

    if [[ "$meta_present" -eq 1 ]] && ! pid_alive "$holder_pid"; then
      rm -rf -- "$lockdir"
      stale_note="I took over a stale lock from $holder_agent (pid dead)."
      continue
    fi

    if [[ "$now" -ge "$deadline" ]]; then
      die "Resource '$name' is in use by $holder_agent (since $(format_time "$holder_started")). Try again later or run: repo-session.sh lock-release $name if you're sure it's stuck."
    fi
    sleep 1
  done
}

release_lock() {
  local name="$1"
  local owner_pid="$2"
  local force="$3"
  local quiet="$4"
  local lockdir
  local meta
  local holder_pid
  local holder_agent

  validate_lock_name "$name"
  lockdir="$LOCKS/$name.lock"
  meta="$lockdir/meta.json"
  if [[ ! -d "$lockdir" ]]; then
    [[ "$quiet" -eq 1 ]] || log "Resource '$name' is already free."
    return 0
  fi

  holder_pid=""
  holder_agent="another session"
  if [[ -f "$meta" ]]; then
    holder_pid="$(json_get "$meta" pid)"
    holder_agent="$(json_get "$meta" agent)"
    [[ -n "$holder_agent" ]] || holder_agent="another session"
  fi

  if [[ "$force" -eq 1 || "$holder_pid" == "$owner_pid" ]] || ! pid_alive "$holder_pid"; then
    rm -rf -- "$lockdir"
    if [[ "$quiet" -eq 0 ]]; then
      log "Resource '$name' is free now."
    fi
  else
    die "Resource '$name' is in use by $holder_agent. I did not release it."
  fi
}

cmd_lock() {
  [[ "$#" -ge 3 ]] || die "Use: repo-session.sh lock <name> -- <command...>"
  local name="$1"
  shift
  [[ "${1:-}" == "--" ]] || die "Use: repo-session.sh lock <name> -- <command...>"
  shift
  [[ "$#" -gt 0 ]] || die "Use: repo-session.sh lock <name> -- <command...>"

  local rc
  acquire_lock "$name" "$$"
  trap 'release_lock "$name" "$$" 0 1 >/dev/null 2>&1 || true' EXIT HUP INT TERM
  set +e
  "$@"
  rc=$?
  set -e
  trap - EXIT HUP INT TERM
  release_lock "$name" "$$" 0 1 >/dev/null 2>&1 || true
  return "$rc"
}

cmd_lock_acquire() {
  [[ "$#" -eq 1 ]] || die "Use: repo-session.sh lock-acquire <name>"
  acquire_lock "$1" "$$"
  log "Resource '$1' is ready."
}

cmd_lock_release() {
  [[ "$#" -ge 1 ]] || die "Use: repo-session.sh lock-release <name> [--force]"
  local name="$1"
  local force=0
  shift
  while [[ "$#" -gt 0 ]]; do
    case "$1" in
      --force) force=1 ;;
      *) die "Use: repo-session.sh lock-release <name> [--force]" ;;
    esac
    shift
  done
  release_lock "$name" "$$" "$force" 0
}

usage() {
  cat <<'EOF'
Use: repo-session.sh <command>

Commands:
  start <repo> <task> [--agent X]
  status
  finish <task-or-workspace> [--no-pr] [--keep]
  cleanup [--days N]
  lock <name> -- <command...>
  lock-acquire <name>
  lock-release <name> [--force]
EOF
}

main() {
  local cmd="${1:-}"
  if [[ -z "$cmd" ]]; then
    usage
    exit 1
  fi
  shift
  case "$cmd" in
    start) cmd_start "$@" ;;
    status) [[ "$#" -eq 0 ]] || die "Use: repo-session.sh status"; cmd_status ;;
    finish) cmd_finish "$@" ;;
    cleanup) cmd_cleanup "$@" ;;
    lock) cmd_lock "$@" ;;
    lock-acquire) cmd_lock_acquire "$@" ;;
    lock-release) cmd_lock_release "$@" ;;
    -h|--help|help) usage ;;
    *) die "I don't know the repo-session command '$cmd'." ;;
  esac
}

main "$@"

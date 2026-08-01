#!/usr/bin/env python3
"""Detect new work appearing in ClickUp and flag it as a vault project candidate.

Snapshots the ClickUp space/folder/list inventory, diffs it against the last
snapshot at config/state/clickup-inventory.json, and writes a [REVIEW] inbox
item for anything new that isn't already tracked as a vault project.

Read-only against ClickUp. The only writes are to the vault (inbox items and
the state file).

Usage:
  python3 config/scripts/clickup-new-work.py              # detect + flag
  python3 config/scripts/clickup-new-work.py --seed       # baseline, no inbox items
  python3 config/scripts/clickup-new-work.py --dry-run    # report, write nothing
  python3 config/scripts/clickup-new-work.py --space "Client Work"

First run with no existing state seeds the baseline silently — otherwise every
folder in the workspace would land in the inbox at once.
"""

import argparse
import datetime as dt
import difflib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API2 = "https://api.clickup.com/api/v2"
CONFIG = os.path.expanduser("~/.clickup-cli.yaml")
VAULT = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
STATE = os.path.join(VAULT, "config", "state", "clickup-inventory.json")
INBOX = os.path.join(VAULT, "gtd", "inbox")

# Lists ClickUp folders carry by convention rather than as new work of their own.
# A folder's own arrival is the signal; these siblings aren't separately notable.
ROUTINE_LIST = re.compile(
    r"^(task list|meeting list|meetings|deliverables( \d{4})?|"
    r"[a-z ]*task list|[a-z ]*meeting list|[a-z ]*meetings|"
    r"[a-z ]*deliverables( \d{4})?|"
    r"inbox|next actions|waiting on|waiting on/delegated|someday maybe|"
    r"reference|projects list|daily reports|list)$",
    re.I,
)

# Spaces that are personal GTD boards or template scaffolding, not project work.
# Teammates' own GTD spaces would otherwise flood the inbox with Next Actions /
# Someday Maybe lists that have nothing to do with the operator's projects.
EXCLUDED_SPACE = re.compile(r"^(GTD\b|Templates & Processes$)", re.I)


def die(msg):
    print(f"clickup-new-work: {msg}", file=sys.stderr)
    sys.exit(1)


def get_token():
    tok = os.environ.get("CLICKUP_TOKEN")
    if tok:
        return tok.strip()
    if os.path.exists(CONFIG):
        with open(CONFIG) as fh:
            for line in fh:
                if line.strip().startswith("token:"):
                    return line.split(":", 1)[1].strip().strip("\"'")
    die(f"no token found (set $CLICKUP_TOKEN or add `token:` to {CONFIG})")


def api(token, path, params=None):
    url = f"{API2}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
    req = urllib.request.Request(url, headers={"Authorization": token})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            die("401 unauthorized — regenerate the ClickUp token at "
                "ClickUp > Settings > Apps and update ~/.clickup-cli.yaml")
        return {"_error": f"HTTP {exc.code}"}
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"_error": str(exc)}


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)


def fetch_inventory(token, wanted_spaces, all_spaces=False):
    teams = api(token, "/team").get("teams") or []
    if not teams:
        die("no workspaces returned — check the token")
    workspace = teams[0]

    spaces = api(token, f"/team/{workspace['id']}/space",
                 {"archived": "false"}).get("spaces") or []
    if wanted_spaces:
        spaces = [s for s in spaces
                  if s["name"] in wanted_spaces or s["id"] in wanted_spaces]
        if not spaces:
            die(f"no space matched {wanted_spaces}")
    elif not all_spaces:
        spaces = [s for s in spaces if not EXCLUDED_SPACE.match(s["name"])]

    inv = {"workspace": {"id": workspace["id"], "name": workspace["name"]},
           "spaces": {}, "folders": {}, "lists": {}}

    for sp in spaces:
        inv["spaces"][sp["id"]] = {"name": sp["name"]}

        for f in api(token, f"/space/{sp['id']}/folder").get("folders") or []:
            inv["folders"][f["id"]] = {
                "name": f["name"], "space": sp["name"], "space_id": sp["id"],
            }
            for l in f.get("lists") or []:
                inv["lists"][l["id"]] = {
                    "name": l["name"], "space": sp["name"],
                    "folder": f["name"], "folder_id": f["id"],
                    "task_count": l.get("task_count"),
                }

        for l in api(token, f"/space/{sp['id']}/list",
                     {"archived": "false"}).get("lists") or []:
            inv["lists"][l["id"]] = {
                "name": l["name"], "space": sp["name"],
                "folder": None, "folder_id": None,
                "task_count": l.get("task_count"),
            }

    return inv


def existing_project_slugs():
    """Vault project + client slugs, so already-tracked work isn't re-flagged."""
    slugs = set()
    for root in ("atlas/clients", "atlas/businesses", "gtd/projects",
                 "atlas/projects"):
        base = os.path.join(VAULT, root)
        if not os.path.isdir(base):
            continue
        for entry in os.listdir(base):
            path = os.path.join(base, entry)
            if not os.path.isdir(path):
                continue
            slugs.add(entry)
            projects = os.path.join(path, "projects")
            if os.path.isdir(projects):
                slugs.update(p for p in os.listdir(projects)
                             if os.path.isdir(os.path.join(projects, p)))
    return slugs


def tracked_match(name, slugs):
    """Return the vault slug that plausibly already covers this ClickUp name."""
    slug = slugify(name)
    if slug in slugs:
        return slug
    for s in slugs:
        if slug and (slug in s or s in slug) and min(len(slug), len(s)) >= 5:
            return s
    close = difflib.get_close_matches(slug, slugs, n=1, cutoff=0.82)
    return close[0] if close else None


def load_state():
    if os.path.exists(STATE):
        with open(STATE) as fh:
            return json.load(fh)
    return None


def save_state(inv, flagged):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    payload = {
        "last-scan": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "workspace": inv["workspace"],
        "space_ids": sorted(inv["spaces"]),
        "folder_ids": sorted(inv["folders"]),
        "list_ids": sorted(inv["lists"]),
        "flagged": sorted(flagged),
    }
    with open(STATE, "w") as fh:
        json.dump(payload, fh, indent=2)


def inbox_item(kind, entity, inv, tracked):
    """Render a [REVIEW] inbox item per the inbox-item-format rule."""
    today = dt.date.today().isoformat()
    name = entity["name"]
    slug = slugify(name)

    if kind == "folder":
        child_lists = [l["name"] for l in inv["lists"].values()
                       if l.get("folder_id") == entity["id"]]
        title = f"New ClickUp folder — {name}"
        what = (f"A new folder **{name}** appeared in the *{entity['space']}* space"
                f" in ClickUp.")
        detail = ("\n".join(f"- {c}" for c in sorted(child_lists))
                  or "- no lists in it yet")
        detail_head = "Lists inside it"
    else:
        title = f"New ClickUp list — {name}"
        parent = entity.get("folder") or f"{entity['space']} (no folder)"
        what = (f"A new list **{name}** appeared under *{parent}* in ClickUp"
                f" with {entity.get('task_count') or 0} tasks.")
        detail = f"- Space: {entity['space']}\n- Folder: {entity.get('folder') or '—'}"
        detail_head = "Where it sits"

    body = [
        "---",
        "type: inbox-item",
        "prefix: REVIEW",
        f"created: {today}",
        "source: clickup-new-work",
        f"clickup-{kind}-id: \"{entity['id']}\"",
        "---",
        f"# [REVIEW] {title}",
        "",
        "## Operator review",
        "",
        "- ",
        "",
        "---",
        "",
        "## What showed up",
        "",
        what,
        "",
        f"## {detail_head}",
        "",
        detail,
        "",
        "## Is this a vault project?",
        "",
    ]

    if tracked:
        body += [
            f"Possibly already tracked as `{tracked}` in the vault. If that's the "
            "same work, say so and I'll link the ClickUp IDs into that project's "
            "`_status.md` instead of creating a new folder.",
            "",
        ]
    else:
        body += [
            "Nothing in the vault looks like it covers this yet. If it's real work "
            "worth tracking, say the word and I'll scaffold the full project folder "
            "(brief, status, plan, notes, reference, specs, deliverables, archive) "
            "seeded from the ClickUp tasks — routed to `atlas/clients/` for client "
            "work, `atlas/businesses/` for your own businesses' work, or "
            "`gtd/projects/` if it's your own.",
            "",
        ]

    body += [
        "If it's routine ClickUp housekeeping, tell me to drop it and I won't flag "
        "it again.",
        "",
        "---",
        "",
        f"*Detected by `config/scripts/clickup-new-work.py` on {today}. "
        "Read-only scan of the ClickUp inventory.*",
        "",
    ]
    return slug, "\n".join(body)


def main():
    p = argparse.ArgumentParser(
        description="Flag new ClickUp work as vault project candidates.")
    p.add_argument("--seed", action="store_true",
                   help="record the current inventory as baseline, write no inbox items")
    p.add_argument("--dry-run", action="store_true",
                   help="report what would be flagged, write nothing")
    p.add_argument("--space", action="append", default=[],
                   help="restrict to this space name or ID (repeatable)")
    p.add_argument("--include-routine-lists", action="store_true",
                   help="also flag Task List / Meeting List / Deliverables siblings")
    p.add_argument("--all-spaces", action="store_true",
                   help="include personal GTD and template spaces (excluded by default)")
    args = p.parse_args()

    token = get_token()
    inv = fetch_inventory(token, args.space, args.all_spaces)
    prior = load_state()

    if prior is None and not args.dry_run:
        save_state(inv, flagged=[])
        print(f"clickup-new-work: baseline seeded — "
              f"{len(inv['spaces'])} spaces, {len(inv['folders'])} folders, "
              f"{len(inv['lists'])} lists. Future runs flag only what's new.")
        return

    if args.seed:
        save_state(inv, flagged=(prior or {}).get("flagged", []))
        print("clickup-new-work: baseline re-seeded; nothing flagged.")
        return

    prior = prior or {"folder_ids": [], "list_ids": [], "flagged": []}
    known_folders = set(prior.get("folder_ids") or [])
    known_lists = set(prior.get("list_ids") or [])
    flagged = set(prior.get("flagged") or [])

    new_folders = [dict(id=i, **d) for i, d in inv["folders"].items()
                   if i not in known_folders and i not in flagged]
    new_folder_ids = {f["id"] for f in new_folders}

    new_lists = []
    for i, d in inv["lists"].items():
        if i in known_lists or i in flagged:
            continue
        if d.get("folder_id") in new_folder_ids:
            continue  # its folder is the signal; don't double-flag
        if not args.include_routine_lists and ROUTINE_LIST.match(d["name"] or ""):
            continue
        new_lists.append(dict(id=i, **d))

    candidates = ([("folder", f) for f in new_folders]
                  + [("list", l) for l in new_lists])

    if not candidates:
        if not args.dry_run:
            save_state(inv, flagged)
        print("clickup-new-work: nothing new.")
        return

    slugs = existing_project_slugs()
    os.makedirs(INBOX, exist_ok=True)
    today = dt.date.today().isoformat()
    written = []

    for kind, entity in candidates:
        tracked = tracked_match(entity["name"], slugs)
        slug, content = inbox_item(kind, entity, inv, tracked)
        path = os.path.join(INBOX, f"{today}-clickup-{slug}.md")
        label = f"{kind}: {entity['name']}"
        if tracked:
            label += f"  (maybe already tracked as {tracked})"

        if args.dry_run:
            print(f"  would flag → {label}")
            continue
        if os.path.exists(path):
            print(f"  skip (inbox item already exists) → {label}")
            flagged.add(entity["id"])
            continue
        with open(path, "w") as fh:
            fh.write(content)
        written.append(os.path.relpath(path, VAULT))
        flagged.add(entity["id"])
        print(f"  flagged → {label}")

    if args.dry_run:
        print(f"clickup-new-work: {len(candidates)} candidate(s), dry run — "
              "nothing written.")
        return

    save_state(inv, flagged)
    print(f"clickup-new-work: {len(written)} inbox item(s) written.")


if __name__ == "__main__":
    main()

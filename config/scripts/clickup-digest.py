#!/usr/bin/env python3
"""Read-only ClickUp activity digest for WorkDesk.

Pulls what the team did and said in a time window so Claude can synthesize it:
task movement (created / updated / closed), task comments, and Chat channel
messages. Writes structured JSON to stdout (or markdown with --markdown).

Read-only by design: no POST, PUT, PATCH, or DELETE anywhere in this file.

Usage:
  python3 config/scripts/clickup-digest.py --days 3
  python3 config/scripts/clickup-digest.py --days 7 --space "Client Work" --markdown
  python3 config/scripts/clickup-digest.py --since 2026-07-28 --include-dms

Token resolution order:
  1. $CLICKUP_TOKEN
  2. token: field in ~/.clickup-cli.yaml
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API2 = "https://api.clickup.com/api/v2"
API3 = "https://api.clickup.com/api/v3"
CONFIG = os.path.expanduser("~/.clickup-cli.yaml")


def die(msg):
    print(f"clickup-digest: {msg}", file=sys.stderr)
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


def api(token, url, params=None):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
    req = urllib.request.Request(url, headers={"Authorization": token})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:300]
        if exc.code == 401:
            die("401 unauthorized — the ClickUp personal token is invalid or revoked. "
                "Regenerate at ClickUp > Settings > Apps and update ~/.clickup-cli.yaml.")
        return {"_error": f"HTTP {exc.code}", "_body": body}
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"_error": str(exc)}


def ms(when):
    return int(when.timestamp() * 1000)


def human(ms_ts):
    if not ms_ts:
        return None
    return dt.datetime.fromtimestamp(int(ms_ts) / 1000).strftime("%Y-%m-%d %H:%M")


def resolve_window(args):
    if args.since:
        start = dt.datetime.strptime(args.since, "%Y-%m-%d")
    else:
        start = dt.datetime.now() - dt.timedelta(days=args.days)
    return start


def get_workspace(token, wanted):
    data = api(token, f"{API2}/team")
    teams = data.get("teams") or []
    if not teams:
        die(f"no workspaces returned ({data.get('_error', 'empty response')})")
    if wanted:
        for t in teams:
            if wanted in (t["id"], t["name"]):
                return t
        die(f"workspace {wanted!r} not found (have: {', '.join(t['name'] for t in teams)})")
    return teams[0]


def member_map(workspace):
    out = {}
    for m in workspace.get("members") or []:
        u = m.get("user") or {}
        if u.get("id"):
            out[str(u["id"])] = u.get("username") or u.get("email") or str(u["id"])
    return out


MENTION = re.compile(r"\[@([^\]]+)\]\(#user_mention#(\d+)\)")
ATTACHMENT = re.compile(r"!\[[^\]]*\]\((https?://[^)]+)\)")


def clean_text(text, names):
    if not text:
        return ""
    text = MENTION.sub(lambda m: f"@{names.get(m.group(2), m.group(1))}", text)
    text = ATTACHMENT.sub("[attachment]", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def space_ids(token, workspace_id, wanted):
    data = api(token, f"{API2}/team/{workspace_id}/space", {"archived": "false"})
    spaces = data.get("spaces") or []
    if not wanted:
        return {s["id"]: s["name"] for s in spaces}
    picked = {s["id"]: s["name"] for s in spaces
              if s["name"] in wanted or s["id"] in wanted}
    if not picked:
        die(f"no space matched {wanted} (have: {', '.join(s['name'] for s in spaces)})")
    return picked


def fetch_tasks(token, workspace_id, start, spaces, names):
    """Tasks touched in the window, via the filtered team-tasks endpoint."""
    params = {
        "date_updated_gt": ms(start),
        "subtasks": "true",
        "include_closed": "true",
        "page": 0,
    }
    if spaces:
        params["space_ids[]"] = list(spaces)
    tasks, seen = [], set()
    while params["page"] < 10:  # 100/page; 1000 tasks is far past a useful digest
        data = api(token, f"{API2}/team/{workspace_id}/task", params)
        batch = data.get("tasks")
        if batch is None:
            if not tasks:
                return [], data.get("_error") or str(data)[:200]
            break
        for t in batch:
            if t["id"] in seen:
                continue
            seen.add(t["id"])
            assignees = [names.get(str(a.get("id")), a.get("username"))
                         for a in (t.get("assignees") or [])]
            status = (t.get("status") or {})
            tasks.append({
                "id": t["id"],
                "name": t.get("name"),
                "status": status.get("status"),
                "status_type": status.get("type"),
                "closed": status.get("type") in ("closed", "done"),
                "list": (t.get("list") or {}).get("name"),
                "folder": (t.get("folder") or {}).get("name"),
                "space": spaces.get((t.get("space") or {}).get("id"),
                                    (t.get("space") or {}).get("id")),
                "assignees": [a for a in assignees if a],
                "created": human(t.get("date_created")),
                "updated": human(t.get("date_updated")),
                "closed_at": human(t.get("date_closed")),
                "due": human(t.get("due_date")),
                "url": t.get("url"),
            })
        if len(batch) < 100:
            break
        params["page"] += 1
    tasks.sort(key=lambda t: t["updated"] or "", reverse=True)
    return tasks, None


def fetch_comments(token, tasks, start, names, cap):
    """Comments posted in the window, on the tasks that moved."""
    cutoff, out = ms(start), []
    for t in tasks[:cap]:
        data = api(token, f"{API2}/task/{t['id']}/comment")
        for c in data.get("comments") or []:
            if int(c.get("date") or 0) < cutoff:
                continue
            user = c.get("user") or {}
            out.append({
                "task": t["name"],
                "task_url": t["url"],
                "list": t["list"],
                "author": names.get(str(user.get("id")), user.get("username")),
                "at": human(c.get("date")),
                "text": clean_text(c.get("comment_text"), names),
            })
    out.sort(key=lambda c: c["at"] or "", reverse=True)
    return out


def fetch_chat(token, workspace_id, start, names, include_dms, per_channel):
    """Chat channel messages in the window."""
    cutoff = ms(start)
    data = api(token, f"{API3}/workspaces/{workspace_id}/chat/channels",
               {"limit": 100})
    channels = data.get("data")
    if channels is None:
        return [], data.get("_error") or str(data)[:200]
    out = []
    for ch in channels:
        if ch.get("type") != "CHANNEL" and not include_dms:
            continue
        if int(ch.get("latest_comment_at") or 0) < cutoff:
            continue
        msgs = api(token,
                   f"{API3}/workspaces/{workspace_id}/chat/channels/{ch['id']}/messages",
                   {"limit": per_channel})
        for m in msgs.get("data") or []:
            if int(m.get("date") or 0) < cutoff:
                continue
            author = (m.get("user") or {}).get("id") or m.get("user_id")
            out.append({
                "channel": ch.get("name") or f"({ch.get('type','dm').lower()})",
                "channel_type": ch.get("type"),
                "author": names.get(str(author), str(author) if author else "unknown"),
                "at": human(m.get("date")),
                "text": clean_text(m.get("content"), names),
                "replies": m.get("reply_count") or 0,
            })
    out.sort(key=lambda m: m["at"] or "", reverse=True)
    return out, None


def render_markdown(d):
    w, lines = d["window"], []
    lines.append(f"# ClickUp activity — {w['start']} → {w['end']}")
    lines.append("")
    lines.append(f"Workspace: {d['workspace']['name']} · "
                 f"spaces: {', '.join(d['scope']['spaces']) or 'all'}")
    lines.append("")

    closed = [t for t in d["tasks"] if t["closed"]]
    moved = [t for t in d["tasks"] if not t["closed"]]

    lines.append(f"## Checked off ({len(closed)})")
    lines.append("")
    for t in closed or []:
        who = ", ".join(t["assignees"]) or "unassigned"
        lines.append(f"- **{t['name']}** — {t['status']} · {who} · {t['list']} "
                     f"· closed {t['closed_at'] or t['updated']}")
    if not closed:
        lines.append("- nothing closed in this window")
    lines.append("")

    lines.append(f"## Tasks that moved ({len(moved)})")
    lines.append("")
    for t in moved:
        who = ", ".join(t["assignees"]) or "unassigned"
        lines.append(f"- **{t['name']}** — `{t['status']}` · {who} · {t['list']} "
                     f"· updated {t['updated']}")
    if not moved:
        lines.append("- no task movement in this window")
    lines.append("")

    lines.append(f"## Chat ({len(d['chat'])} messages)")
    lines.append("")
    by_channel = {}
    for m in d["chat"]:
        by_channel.setdefault(m["channel"], []).append(m)
    for channel, msgs in by_channel.items():
        lines.append(f"### #{channel}")
        for m in sorted(msgs, key=lambda x: x["at"] or ""):
            body = m["text"].replace("\n", "\n  ")
            lines.append(f"- **{m['author']}** ({m['at']}): {body}")
        lines.append("")
    if not by_channel:
        lines.append("- no chat activity in this window")
        lines.append("")

    lines.append(f"## Task comments ({len(d['comments'])})")
    lines.append("")
    for c in d["comments"]:
        body = c["text"].replace("\n", " ")
        lines.append(f"- **{c['author']}** on *{c['task']}* ({c['at']}): {body}")
    if not d["comments"]:
        lines.append("- no comments in this window")
    lines.append("")

    if d.get("errors"):
        lines.append("## Fetch errors")
        lines.append("")
        for k, v in d["errors"].items():
            lines.append(f"- {k}: {v}")
        lines.append("")

    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="Read-only ClickUp activity digest.")
    p.add_argument("--days", type=int, default=3, help="lookback window (default 3)")
    p.add_argument("--since", help="explicit start date, YYYY-MM-DD (overrides --days)")
    p.add_argument("--workspace", help="workspace name or ID (default: first)")
    p.add_argument("--space", action="append", default=[],
                   help="restrict to this space name or ID (repeatable)")
    p.add_argument("--include-dms", action="store_true",
                   help="include direct messages in the chat section")
    p.add_argument("--no-chat", action="store_true", help="skip chat entirely")
    p.add_argument("--no-comments", action="store_true", help="skip task comments")
    p.add_argument("--comment-cap", type=int, default=40,
                   help="max tasks to pull comments for (default 40)")
    p.add_argument("--chat-limit", type=int, default=50,
                   help="messages fetched per channel (default 50)")
    p.add_argument("--markdown", action="store_true", help="render markdown instead of JSON")
    args = p.parse_args()

    token = get_token()
    start = resolve_window(args)
    workspace = get_workspace(token, args.workspace)
    names = member_map(workspace)
    spaces = space_ids(token, workspace["id"], args.space)

    errors = {}
    tasks, err = fetch_tasks(token, workspace["id"], start, spaces, names)
    if err:
        errors["tasks"] = err

    comments = []
    if not args.no_comments and tasks:
        comments = fetch_comments(token, tasks, start, names, args.comment_cap)

    chat = []
    if not args.no_chat:
        chat, err = fetch_chat(token, workspace["id"], start, names,
                               args.include_dms, args.chat_limit)
        if err:
            errors["chat"] = err

    payload = {
        "window": {
            "start": start.strftime("%Y-%m-%d %H:%M"),
            "end": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "days": args.days if not args.since else None,
        },
        "workspace": {"id": workspace["id"], "name": workspace["name"]},
        "scope": {"spaces": sorted(spaces.values()), "include_dms": args.include_dms},
        "tasks": tasks,
        "comments": comments,
        "chat": chat,
        "errors": errors,
    }

    if args.markdown:
        print(render_markdown(payload))
    else:
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

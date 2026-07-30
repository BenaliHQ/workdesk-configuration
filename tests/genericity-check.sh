#!/usr/bin/env bash
# Reject owner-specific values in the exact config tree shipped by release.sh.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT

mkdir -p "$stage/workdesk"
rsync -a \
  --exclude='defaults/' \
  --exclude='state/' \
  --exclude='snapshots/' \
  --exclude='.DS_Store' \
  "$repo_root/config/" "$stage/workdesk/"

python3 - "$stage/workdesk" "$repo_root/tests/genericity-allowlist.txt" <<'PY'
from pathlib import Path
import re
import sys

shipped_root = Path(sys.argv[1])
allowlist_path = Path(sys.argv[2])

allowlist = []
for line_number, raw_line in enumerate(
    allowlist_path.read_text(encoding="utf-8").splitlines(), start=1
):
    pattern = raw_line.partition("#")[0].strip()
    if not pattern:
        continue
    try:
        allowlist.append(re.compile(pattern))
    except re.error as exc:
        print(
            f"{allowlist_path}:{line_number}: invalid allowlist regex: {exc}",
            file=sys.stderr,
        )
        sys.exit(2)

forbidden = [
    re.compile(r"/Users/[A-Za-z0-9_-]+"),
    re.compile(r"khalil", re.IGNORECASE),
    re.compile(r"khalilbenali", re.IGNORECASE),
    re.compile(r"khalils-vault", re.IGNORECASE),
    re.compile(r"benali\.com", re.IGNORECASE),
    re.compile(r"demandcast", re.IGNORECASE),
    re.compile(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
        r"[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        re.IGNORECASE,
    ),
]
zero_uuid = "00000000-0000-0000-0000-000000000000"
violations = []

for path in sorted(candidate for candidate in shipped_root.rglob("*") if candidate.is_file()):
    relative_path = path.relative_to(shipped_root)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    for line_number, line in enumerate(lines, start=1):
        candidate = f"config/{relative_path}:{line_number}:{line}"
        if any(pattern.search(candidate) for pattern in allowlist):
            continue

        matches = (
            match.group(0)
            for pattern in forbidden
            for match in pattern.finditer(line)
        )
        if any(match.lower() != zero_uuid for match in matches):
            violations.append(candidate)

if violations:
    print("Genericity check failed; owner-specific values remain in shipped config:")
    for violation in violations:
        print(violation)
    sys.exit(1)

print("Genericity check passed.")
PY

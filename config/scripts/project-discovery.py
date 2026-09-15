#!/usr/bin/env python3
"""Read-only enumeration of canonical Workdesk project folders."""
import argparse
import json
from pathlib import Path


def projects(root):
    seen = set()
    for pattern in ('gtd/projects/*', 'atlas/clients/*/projects/*',
                    'atlas/businesses/*/projects/*',
                    'atlas/businesses/*/initiatives/*/projects/*'):
        for p in sorted(root.glob(pattern)):
            if not p.is_dir() or p.name.startswith(('_', '.')) or p.is_symlink():
                continue
            key = str(p.resolve())
            if key not in seen:
                seen.add(key)
                yield str(p.relative_to(root))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    if not (root / 'config').is_dir():
        parser.error('Expected a Workdesk vault')
    print(json.dumps(list(projects(root)), indent=2))

#!/usr/bin/env python3
"""Plan explicit link rewrites before ontology moves; apply with hash checks."""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote, quote


def sha(data):
    return hashlib.sha256(data).hexdigest()


def mapped(name, moves):
    for row in moves:
        if name == row['from'] or name.startswith(row['from'] + '/'):
            name = row['to'] + name[len(row['from']):]
    return name


def plan_links(root, manifest):
    moves = manifest['moves']
    names = set()
    for zone in ['atlas', 'gtd', 'intel', 'system', 'config']:
        for base, dirs, files in os.walk(root / zone):
            dirs[:] = [d for d in dirs if not (Path(base) / d).is_symlink() and d not in ('node_modules', '__pycache__')]
            names.update(str((Path(base) / f).relative_to(root)) for f in files)
    basenames = defaultdict(list)
    for name in names:
        basenames[Path(name).name].append(name)
    def resolve(target, source):
        target = unquote(target)
        candidates = []
        if target.startswith(('./', '../')):
            candidates.append(os.path.normpath(str(Path(source).parent / target)))
        elif '/' in target:
            candidates.extend([target.lstrip('/'), str(Path(source).parent / target)])
        else:
            candidates.append(str(Path(source).parent / target))
            matches = basenames.get(target, []) + basenames.get(target + '.md', [])
            if len(matches) == 1:
                candidates.extend(matches)
        for candidate in candidates:
            for suffix in ('', '.md'):
                if candidate + suffix in names:
                    return candidate + suffix
        return None
    changes = []
    for name in sorted(names):
        parts = Path(name).parts
        if not name.endswith('.md') or parts[0] not in ('atlas', 'gtd', 'intel'):
            continue
        if any(p in ('_archive', 'archive', 'reliability', 'node_modules') for p in parts):
            continue
        p = root / name
        if p.is_symlink():
            continue
        raw = p.read_bytes()
        text = raw.decode('utf-8')
        new_name = mapped(name, moves)
        def wiki(m):
            full = m[1]
            target, sep, label = full.partition('|')
            target, anchor_sep, anchor = target.partition('#')
            old = resolve(target, name)
            if old is None:
                return m[0]
            new = mapped(old, moves)
            if new == old and new_name == name:
                return m[0]
            target = new.removesuffix('.md')
            return '[[' + target + (anchor_sep + anchor if anchor_sep else '') + (sep + label if sep else '') + ']]'
        def md(m):
            target = m[2]
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
                return m[0]
            target, marker, anchor = target.partition('#')
            old = resolve(target.strip('<>'), name)
            if old is None:
                return m[0]
            new = mapped(old, moves)
            if new == old and new_name == name:
                return m[0]
            rel = quote(os.path.relpath(new, Path(new_name).parent), safe='/.-_')
            return '[' + m[1] + '](' + rel + (marker + anchor if marker else '') + ')'
        # Preserve fenced code examples and raw source quotations verbatim.
        chunks = re.split(r'(```[\s\S]*?```|~~~[\s\S]*?~~~)', text)
        for i in range(0, len(chunks), 2):
            chunks[i] = re.sub(r'\[\[([^\]\n]+)\]\]', wiki, chunks[i])
            chunks[i] = re.sub(r'\[([^\]\n]*)\]\(([^)\n]+)\)', md, chunks[i])
        new_text = ''.join(chunks)
        if new_text != text:
            changes.append({'path': new_name, 'original_path': name, 'before': sha(raw),
                            'after': sha(new_text.encode()), 'text': new_text})
    return {'root': str(root), 'changes': changes}


def apply_links(root, plan):
    if plan['root'] != str(root):
        raise ValueError('Wrong vault')
    for row in plan['changes']:
        p = root / row['path']
        if p.is_symlink() or not p.resolve().is_relative_to(root) or Path(row['path']).parts[0] not in ('atlas', 'gtd', 'intel'):
            raise ValueError('Unsafe target')
        if sha(p.read_bytes()) != row['before']:
            raise ValueError('Concurrent change: ' + row['path'])
    for row in plan['changes']:
        p = root / row['path']
        if sha(p.read_bytes()) != row['before']:
            raise ValueError('Concurrent change: ' + row['path'])
        p.write_text(row['text'])


def main():
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument('mode', choices=['plan', 'apply'])
    a.add_argument('--root', type=Path, required=True)
    a.add_argument('--moves', type=Path)
    a.add_argument('--output', type=Path, required=True)
    args = a.parse_args()
    root = args.root.resolve()
    if args.mode == 'plan':
        plan = plan_links(root, json.loads(args.moves.read_text()))
        with args.output.open('x') as f:
            json.dump(plan, f, indent=2)
        print(json.dumps({'changed_files': len(plan['changes'])}))
    else:
        apply_links(root, json.loads(args.output.read_text()))


if __name__ == '__main__':
    main()

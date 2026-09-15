#!/usr/bin/env python3
"""Explicit, opt-in ontology migration. Never invoked by the update installer.

Plan first, then apply that exact manifest. Original bytes and a journal are kept
outside the vault. Existing targets and edits since planning abort the operation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def safe(root, name):
    p = root / name
    if Path(name).is_absolute() or '..' in Path(name).parts:
        raise ValueError('Unsafe relative path: ' + name)
    if Path(name).parts[0] not in ('atlas', 'gtd', 'intel', 'system'):
        raise ValueError('Unsupported migration zone: ' + name)
    if not p.resolve().is_relative_to(root):
        raise ValueError('Path escapes vault: ' + name)
    return p


def project_dirs(root):
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
                yield p


def make_plan(root, relocations):
    moves = []
    # Rename container documents first. Old names remain filesystem aliases.
    containers = set(project_dirs(root))
    for pattern in ('atlas/businesses/*', 'atlas/clients/*',
                    'atlas/businesses/*/initiatives/*'):
        containers.update(p for p in root.glob(pattern) if p.is_dir() and not p.is_symlink())
    for folder in sorted(containers):
        for old, new in (('_brief.md', 'brief.md'), ('_status.md', 'status.md')):
            src, dst = folder / old, folder / new
            if src.is_file() and not src.is_symlink():
                if dst.exists() or dst.is_symlink():
                    raise ValueError('Both document names exist: ' + str(folder))
                moves.append({'from': str(src.relative_to(root)), 'to': str(dst.relative_to(root)), 'alias': True})
    for old, new in [('gtd/actions/waiting', 'gtd/waiting'),
                     ('system/_processing', 'system/processing'),
                     ('system/log', 'system/logs')]:
        src, dst = safe(root, old), safe(root, new)
        if src.exists() and not src.is_symlink():
            if dst.exists() or dst.is_symlink():
                raise ValueError('Destination already exists: ' + new)
            moves.append({'from': old, 'to': new, 'alias': True})
    next_dir = root / 'gtd/actions/next'
    if next_dir.is_dir() and not next_dir.is_symlink():
        for src in sorted(next_dir.iterdir()):
            if src.name == 'index.md' or src.is_symlink():
                continue
            dst = root / 'gtd/actions' / src.name
            if dst.exists() or dst.is_symlink():
                raise ValueError('Action filename collision: ' + src.name)
            moves.append({'from': str(src.relative_to(root)), 'to': str(dst.relative_to(root)), 'alias': True})
    for old, new in relocations.items():
        src, dst = safe(root, old), safe(root, new)
        if src.is_symlink():
            if src.resolve() != dst.resolve():
                raise ValueError('Unexpected compatibility target: ' + old)
            continue
        if not src.exists():
            raise ValueError('Missing relocation source: ' + old)
        if dst.exists() or dst.is_symlink():
            raise ValueError('Destination exists: ' + new)
        moves.append({'from': old, 'to': new, 'alias': True})
    files = {}
    inventories = {}
    for row in moves:
        src = safe(root, row['from'])
        if src.is_dir():
            inventories[row['from']] = sorted(str(p.relative_to(src)) for p in src.rglob('*'))
        for f in ([src] if src.is_file() else src.rglob('*')):
            if f.is_file() and not f.is_symlink():
                files[str(f.relative_to(root))] = digest(f)
    return {'version': 1, 'root': str(root), 'moves': moves, 'source_hashes': files, 'source_inventories': inventories}


def apply(root, plan, backup):
    if plan['root'] != str(root) or plan['version'] != 1:
        raise ValueError('Manifest belongs to another vault/version')
    if backup.exists() or backup.resolve().is_relative_to(root):
        raise ValueError('Backup must be a new directory outside the vault')
    for name, expected in plan['source_hashes'].items():
        if digest(safe(root, name)) != expected:
            raise ValueError('Source changed after planning: ' + name)
    for name, expected in plan.get('source_inventories', {}).items():
        src = safe(root, name)
        if sorted(str(p.relative_to(src)) for p in src.rglob('*')) != expected:
            raise ValueError('Source inventory changed after planning: ' + name)
    for row in plan['moves']:
        src, dst = safe(root, row['from']), safe(root, row['to'])
        if not src.exists() or src.is_symlink() or dst.exists() or dst.is_symlink():
            raise ValueError('Move precondition changed: ' + row['from'])
    backup.mkdir(parents=True)
    (backup / 'manifest.json').write_text(json.dumps(plan, indent=2) + '\n')
    with tarfile.open(backup / 'sources.tar', 'w') as archive:
        # Capture each source once, including empty directories and metadata.
        selected = []
        for row in sorted(plan['moves'], key=lambda x: len(Path(x['from']).parts)):
            name = row['from']
            if not any(Path(name).is_relative_to(Path(parent)) for parent in selected):
                archive.add(safe(root, name), arcname=name)
                selected.append(name)
    with tarfile.open(backup / 'sources.tar') as archive:
        for name, expected in plan['source_hashes'].items():
            data = archive.extractfile(name).read()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError('Backup verification failed: ' + name)
    journal = backup / 'journal.jsonl'
    for row in plan['moves']:
        src, dst = safe(root, row['from']), safe(root, row['to'])
        # Recheck all original files still under this source immediately before move.
        for name, expected in plan['source_hashes'].items():
            if Path(name) == Path(row['from']) or Path(name).is_relative_to(Path(row['from'])):
                original = root / name
                if original.exists() and digest(original) != expected:
                    raise ValueError('Concurrent edit detected: ' + name)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() or dst.is_symlink():
            raise ValueError('Destination appeared during migration: ' + str(dst))
        src.rename(dst)
        with journal.open('a') as handle:
            handle.write(json.dumps({'event': 'moved', **row}) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
        if row['alias']:
            src.symlink_to(os.path.relpath(dst, src.parent), target_is_directory=dst.is_dir())
    (backup / 'complete.json').write_text(json.dumps({'complete': True, 'moves': len(plan['moves'])}) + '\n')


def verify(root, plan):
    failures = []
    # Longest original prefix maps each original file to its eventual canonical path.
    def mapped(name):
        for row in plan['moves']:
            old, new = row['from'], row['to']
            if name == old or name.startswith(old + '/'):
                name = new + name[len(old):]
        return name
    for old, expected in plan['source_hashes'].items():
        new = mapped(old)
        p = safe(root, new)
        if not p.is_file() or digest(p) != expected:
            failures.append(new)
    for row in plan['moves']:
        src = root / row['from']
        if row['alias'] and (not src.is_symlink() or not src.exists()):
            failures.append('alias: ' + row['from'])
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['plan', 'apply', 'verify', 'projects'])
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--relocations', type=Path)
    parser.add_argument('--backup', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if not (root / 'config').is_dir():
        parser.error('Expected a Workdesk vault with config')
    if args.mode == 'projects':
        print(json.dumps([str(p.relative_to(root)) for p in project_dirs(root)], indent=2))
        return
    if args.manifest is None:
        parser.error('--manifest is required')
    if args.mode == 'plan':
        relocations = json.loads(args.relocations.read_text()) if args.relocations else {}
        plan = make_plan(root, relocations)
        with args.manifest.open('x') as handle:
            json.dump(plan, handle, indent=2)
        print(json.dumps({'moves': len(plan['moves']), 'files': len(plan['source_hashes'])}))
    elif args.mode == 'apply':
        if not args.backup:
            parser.error('--backup required')
        apply(root, json.loads(args.manifest.read_text()), args.backup)
    else:
        failures = verify(root, json.loads(args.manifest.read_text()))
        print(json.dumps({'pass': not failures, 'failures': failures}, indent=2))
        raise SystemExit(bool(failures))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Create missing navigation indexes only. Existing hand-written indexes win."""
import argparse
import os
from pathlib import Path
import re
from urllib.parse import quote

PURPOSES = {
    'atlas': 'Sourced knowledge, relationships, businesses and owned work.',
    'gtd': 'Commitments, tracked dependencies, possibilities and personal reference.',
    'intel': 'Interpretation, research and source-linked synthesis.',
    'system': 'Captured sources and operational evidence.',
    'config': 'Shared definitions, workflows, integrations and application wiring.',
    'businesses': 'Businesses owned or operated.', 'clients': 'Engagement relationships and delivery.',
    'companies': 'Organization identity independent of an engagement.',
    'people': 'Sourced context about people and relationships.',
    'meetings': 'Conversation outcomes linked to original sources.', 'decisions': 'Sourced durable decisions.',
    'initiatives': 'Sustained focuses for improvement.', 'projects': 'Bounded outcomes with their own plans and status.',
    'notes': 'Working notes, brainstorms and scoped reviews.', 'reference': 'Supporting inputs and retained references.',
    'specs': 'Detailed executable plans for phases and deliverables.', 'deliverables': 'Final artifacts or their authoritative links.',
    'repo': 'Repository references and implementation handoff.',
    'inbox': 'Unclarified captures and review pointers.', 'actions': 'Executable next actions.',
    'waiting': 'Dependencies and commitments awaiting others.', 'someday': 'Possibilities without current commitment.',
    'concepts': 'Durable ideas and frameworks.', 'research': 'Investigations supported by evidence.',
    'briefings': 'Time- or purpose-specific views.', 'syntheses': 'Source-linked interpretation and applicability.',
    'vault-improvements': 'Sourced proposals for improving Workdesk.',
    'intake': 'Captures awaiting classification or verified processing.', 'bookmarks': 'Captured posts and articles.',
    'transcripts': 'Raw meeting conversations.', 'session-log': 'Available AI conversations and processing receipts.',
    'processing': 'Coordination, deferred updates and recovery.', 'logs': 'Operational diagnostics and execution history.',
    'events': 'Structured activity recorded by hooks.',
    'rules': 'Shared agent behavior and constraints.', 'skills': 'Canonical reusable workflows.',
    'agents': 'Specialist roles.', 'objects': 'Managed record definitions.', 'sources': 'Input formats and processing contracts.',
    'practices': 'Personal practice definitions.', 'signals': 'Generated analysis and briefing definitions.',
    'templates': 'Starting documents.', 'tools': 'Integration setup and access evidence.',
    'automations': 'Schedules, designated runners and verification receipts.', 'adapters': 'Application-specific wiring to shared sources.',
    'claude': 'Claude entry points, skill discovery and native configuration.',
    'codex': 'Codex entry points, skill discovery and native configuration.',
    'grok': 'Grok Build integration information; readiness requires runtime verification.',
    'scripts': 'Executable workflow support and hooks.', 'shell': 'Terminal environment helpers.',
    'appearance': 'Workdesk styling.', 'obsidian-defaults': 'Seed/default editor configuration.',
    'statusline': 'Terminal status display.', 'defaults': 'Product update baselines; not an editing surface.',
    'source': 'Bundled product source material, distinct from sources.',
    'state': 'Machine-maintained checkpoints and setup records.'
}
FILES = {'brief.md': 'Purpose, scope, principles and outcome.', 'status.md': 'Current phase, blockers and next action.',
         'plan.md': 'Overall sequence and completion conditions.', 'AGENTS.md': 'Shared/local agent entry instructions.',
         'CLAUDE.md': 'Claude instruction adapter.', 'field-guide.md': 'Jobs and boundaries of every part of Workdesk.',
         'operator-policy.md': 'Private shared operator agreements.', 'operator-profile.md': 'Operator context and preferences.',
         'VERSION': 'Installed product version.', 'SKILL.md': 'Workflow instructions and invocation metadata.'}
SKIP = {'_archive', 'archive', 'reliability', 'node_modules', 'vendor', '.git', '__pycache__', 'defaults', 'source', 'state'}


def title(p):
    return p.stem.replace('-', ' ').replace('_', ' ').strip().capitalize()


def create_index(folder, root):
    target = folder / 'index.md'
    if target.exists() or target.is_symlink():
        return False
    lines = ['# ' + ('Workdesk' if folder == root else title(folder)), '',
             PURPOSES.get(folder.name, 'Context and material owned by this scope.'), '']
    if folder != root:
        lines += ['[Parent](../index.md)', '']
    else:
        if (root / 'field-guide.md').is_file():
            lines += ['[Field guide](field-guide.md)', '']
        lines += ['Personal is the read-only private writing zone. Existing application and backup directories remain infrastructure.', '']
    for p in sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if p.is_symlink() or p.name.startswith('.') or p.name == 'index.md':
            continue
        if p.is_dir():
            link = p.name + '/index.md' if (p / 'index.md').exists() else p.name + '/'
            desc = PURPOSES.get(p.name, 'Material for ' + title(p) + '.')
        else:
            link = p.name
            desc = FILES.get(p.name, 'Stored ' + (p.suffix.lstrip('.') or 'configuration') + ' record.')
        lines.append('- [' + p.name + '](' + quote(link, safe='/.-_') + ') ' + desc)
    target.write_text('\n'.join(lines) + '\n')
    return True


def generate(root):
    folders = {root}
    for zone in ['atlas', 'gtd', 'intel']:
        for base, dirs, files in os.walk(root / zone):
            dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith('.') and not (Path(base)/d).is_symlink()
                       and not d.startswith('okf-bundle')]
            folders.add(Path(base))
    for zone in ['config', 'system']:
        base = root / zone
        folders.add(base)
        if base.exists():
            folders.update(p for p in base.iterdir() if p.is_dir() and not p.is_symlink() and p.name not in SKIP and not p.name.startswith('.'))
    adapters = root / 'config/adapters'
    if adapters.exists():
        folders.update(p for p in adapters.iterdir() if p.is_dir())
    created = []
    for folder in sorted(folders, key=lambda p: -len(p.parts)):
        if folder.is_dir() and create_index(folder, root):
            created.append(str((folder/'index.md').relative_to(root)))
    return created


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    import json
    print(json.dumps(generate(args.root.resolve()), indent=2))

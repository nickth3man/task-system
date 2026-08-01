#!/usr/bin/env python3
"""Create a task record from the template with the mechanical fields filled in.

Everything derivable from the configuration, the clock, or the arguments is
substituted here. What remains is the content only a human or an agent reasoning
about the work can supply, and it is listed on exit.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import re
import shutil
import sys

import yaml

from generate_index import (
    DEFAULT_INSTANCE_ROOT,
    build_index,
    load_yaml,
    render,
    repo_path,
)

TASK_ID_RE = re.compile(r'^(?P<prefix>[A-Z]+)-(?P<year>\d{4})-(?P<sequence>\d+)$')
SLUG_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
PLACEHOLDER_RE = re.compile(r'__REQUIRED_[A-Z0-9_]*__')
TASK_TYPES = (
    'feature', 'bugfix', 'refactor', 'performance', 'security', 'audit',
    'research', 'documentation', 'dependency', 'data', 'ui_ux', 'scaffolding',
    'other',
)
# Mirrors validate.LITE_REQUIRED_FILES.
LITE_FILES = (
    'task.yaml', 'task.md', 'findings.md', 'plan.md', 'verification.md', 'completion.md',
)


class TaskFailure(Exception):
    """Raised for an input error that should be reported without a traceback."""


def timestamp(timezone: str) -> str:
    """Local-offset ISO timestamp, preferring the configured IANA zone."""
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(timezone)).isoformat(timespec='seconds')
    except Exception:
        # Windows has no system tz database unless `tzdata` is installed.
        return datetime.now().astimezone().isoformat(timespec='seconds')


def existing_ids(*roots: Path) -> set[str]:
    found: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for task_file in root.rglob('task.yaml'):
            try:
                data = load_yaml(task_file)
            except ValueError:
                continue
            value = data.get('id')
            if isinstance(value, str):
                found.add(value)
    return found


def allocate_id(config: dict, taken: set[str], year: int) -> str:
    identifiers = config.get('identifiers') if isinstance(config.get('identifiers'), dict) else {}
    prefix = identifiers.get('prefix') if isinstance(identifiers.get('prefix'), str) else 'TASK'
    width = identifiers.get('sequence_width')
    width = width if isinstance(width, int) and width > 0 else 3

    highest = 0
    for value in taken:
        match = TASK_ID_RE.match(value)
        if match and match.group('prefix') == prefix and int(match.group('year')) == year:
            highest = max(highest, int(match.group('sequence')))
    return f'{prefix}-{year}-{str(highest + 1).zfill(width)}'


def substitutions(
    task_id: str,
    slug: str,
    title: str,
    now: str,
    config: dict,
    actor: str,
    source_reference: str,
    original_request: str,
) -> dict[str, str]:
    repository = config.get('repository') if isinstance(config.get('repository'), dict) else {}
    return {
        'TASK_ID': task_id,
        'SLUG': slug,
        'TITLE': title,
        'CREATED_AT': now,
        'UPDATED_AT': now,
        'ACTOR': actor,
        'SOURCE_REFERENCE': source_reference,
        'ORIGINAL_REQUEST': original_request,
        'REPOSITORY_NAME': str(repository.get('name', '')),
        'DEFAULT_BRANCH': str(repository.get('default_branch', '')),
    }


def apply(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace(f'__REQUIRED_{key}__', value)
    return text


def lite_profile_types(config: dict) -> set[str]:
    lifecycle = config.get('lifecycle') if isinstance(config.get('lifecycle'), dict) else {}
    allowed = lifecycle.get('lite_profile_task_types')
    if not isinstance(allowed, list):
        return set()
    return {item for item in allowed if isinstance(item, str)}


def prune_to_lite(task_dir: Path) -> list[str]:
    """Drop artifacts the lite profile does not require."""
    removed: list[str] = []
    for path in sorted(task_dir.iterdir()):
        if path.is_dir() and path.name == 'evidence':
            shutil.rmtree(path)
            removed.append(f'{path.name}/')
        elif path.is_file() and path.name not in LITE_FILES:
            path.unlink()
            removed.append(path.name)
    return removed


def remaining_placeholders(task_dir: Path) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in sorted(task_dir.rglob('*')):
        if not path.is_file() or path.suffix not in {'.md', '.yaml'}:
            continue
        names = sorted(set(PLACEHOLDER_RE.findall(path.read_text(encoding='utf-8'))))
        if names:
            found[path.name] = names
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', default='.', help='Repository root.')
    parser.add_argument(
        '--instance-root', default=DEFAULT_INSTANCE_ROOT, help='Live instance root.'
    )
    parser.add_argument('--slug', required=True, help='Kebab-case slug, e.g. fix-login-retry.')
    parser.add_argument('--title', required=True, help='One-line task title.')
    parser.add_argument('--id', help='Task ID. Allocated from existing records when omitted.')
    parser.add_argument('--type', choices=TASK_TYPES, default='feature', help='Task type.')
    parser.add_argument('--actor', default='agent', help='Who is recording the task.')
    parser.add_argument(
        '--source-reference',
        default='Requested in chat',
        help='Where this task came from.',
    )
    parser.add_argument(
        '--original-request',
        help='The request verbatim. Left as a placeholder when omitted.',
    )
    parser.add_argument('--dry-run', action='store_true', help='Report actions only.')
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve(strict=False)
    instance_root = repo_path(repo_root, args.instance_root).resolve(strict=False)

    try:
        if not SLUG_RE.match(args.slug):
            raise TaskFailure(f'slug must be kebab-case: {args.slug}')

        config_path = instance_root / 'config.yaml'
        if not config_path.is_file():
            raise TaskFailure(f'missing {config_path}; run scripts/init.py first')
        config = load_yaml(config_path)

        paths = config.get('paths')
        if not isinstance(paths, dict):
            raise TaskFailure(f'{config_path}: paths must be a mapping')
        active_root = repo_path(repo_root, str(paths.get('active'))).resolve(strict=False)
        archive_root = repo_path(repo_root, str(paths.get('archive'))).resolve(strict=False)
        template_root = repo_path(repo_root, str(paths.get('template'))).resolve(strict=False)
        if not template_root.is_dir():
            raise TaskFailure(f'task template not found: {template_root}')

        timezone = config.get('timezone')
        now = timestamp(timezone if isinstance(timezone, str) else 'UTC')
        taken = existing_ids(active_root, archive_root)

        task_id = args.id or allocate_id(config, taken, datetime.now().year)
        if not TASK_ID_RE.match(task_id):
            raise TaskFailure(f'malformed task ID: {task_id}')
        if task_id in taken:
            raise TaskFailure(f'task ID already in use: {task_id}')

        task_dir = active_root / f'{task_id}-{args.slug}'
        if task_dir.exists():
            raise TaskFailure(f'task directory already exists: {task_dir}')

        values = substitutions(
            task_id,
            args.slug,
            args.title,
            now,
            config,
            args.actor,
            args.source_reference,
            args.original_request or '__REQUIRED_ORIGINAL_REQUEST__',
        )

        if args.dry_run:
            print(f'Would create {task_dir} from {template_root}')
            return 0

        shutil.copytree(template_root, task_dir)
        for path in sorted(task_dir.rglob('*')):
            if not path.is_file() or path.suffix not in {'.md', '.yaml'}:
                continue
            path.write_text(
                apply(path.read_text(encoding='utf-8'), values),
                encoding='utf-8',
                newline='\n',
            )

        task_file = task_dir / 'task.yaml'
        task = task_file.read_text(encoding='utf-8')
        task = task.replace('type: "feature"', f'type: "{args.type}"', 1)
        task_file.write_text(task, encoding='utf-8', newline='\n')

        lite = args.type in lite_profile_types(config)
        pruned = prune_to_lite(task_dir) if lite else []

        index_path, data = build_index(repo_root, instance_root)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(render(data), encoding='utf-8', newline='\n')
    except (TaskFailure, OSError, ValueError, yaml.YAMLError) as exc:
        print(f'Task creation failed: {exc}', file=sys.stderr)
        return 1

    print(f'Created {task_dir}')
    if pruned:
        print(f'Lite profile ({args.type}): omitted {", ".join(pruned)}')
    print(f'Updated {index_path}')

    outstanding = remaining_placeholders(task_dir)
    total = sum(len(names) for names in outstanding.values())
    if not total:
        print('\nNo placeholders remain.')
        return 0

    print(f'\n{total} placeholder(s) still need content:')
    for name, names in outstanding.items():
        print(f'  {name}: {", ".join(names)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

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
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from common import PLACEHOLDER_RE
from generate_index import (
    DEFAULT_INSTANCE_ROOT,
    build_index,
    load_yaml,
    render,
    repo_path,
)

TASK_ID_RE = re.compile(r'^(?P<prefix>[A-Z]+)-(?P<year>\d{4})-(?P<sequence>\d+)$')
SLUG_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
TASK_TYPES = (
    'feature', 'bugfix', 'refactor', 'performance', 'security', 'audit',
    'research', 'documentation', 'dependency', 'data', 'ui_ux', 'scaffolding',
    'other',
)



class TaskFailure(Exception):
    """Raised for an input error that should be reported without a traceback."""


def timestamp(timezone: str) -> str:
    """
    Generate a local-offset ISO 8601 timestamp for the requested IANA timezone.
    
    Parameters:
    	timezone (str): IANA timezone name to use for the timestamp.
    
    Returns:
    	str: Timestamp with seconds precision and a numeric UTC offset; uses the system-local timezone when the requested timezone is unavailable.
    """
    try:
        return datetime.now(ZoneInfo(timezone)).isoformat(timespec='seconds')
    except (ZoneInfoNotFoundError, ValueError) as exc:
        # Windows has no system tz database unless `tzdata` is installed.
        print(f'warning: timezone {timezone!r} unusable ({exc}); using local offset',
              file=sys.stderr)
        return datetime.now().astimezone().isoformat(timespec='seconds')


def existing_ids(*roots: Path) -> set[str]:
    """
    Collect task identifiers from valid task definition files under the specified directories.
    
    Parameters:
    	*roots (Path): Directories to search recursively for task definition files.
    
    Returns:
    	set[str]: The task identifiers found in valid YAML files.
    """
    found: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for task_file in root.rglob('task.yaml'):
            try:
                data = load_yaml(task_file)
            except ValueError:
                continue
            if not isinstance(data, dict):
                continue
            value = data.get('id')
            if isinstance(value, str):
                found.add(value)
    return found


def allocate_id(config: dict, taken: set[str], year: int) -> str:
    """
    Allocate the next task identifier for the specified year.
    
    Parameters:
    	config (dict): Repository configuration containing optional identifier settings.
    	taken (set[str]): Existing task identifiers to inspect.
    	year (int): Year included in the generated identifier.
    
    Returns:
    	str: The next identifier using the configured prefix and sequence width.
    """
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
    """
    Build placeholder values for a task record from task metadata and repository configuration.
    
    Parameters:
    	task_id (str): Identifier assigned to the task.
    	slug (str): URL-safe task slug.
    	title (str): Task title.
    	now (str): Timestamp used for creation and update fields.
    	config (dict): Repository configuration containing optional repository metadata.
    	actor (str): Person or system creating the task.
    	source_reference (str): Reference to the task's source.
    	original_request (str): Original task request.
    
    Returns:
    	dict[str, str]: Placeholder names mapped to their substituted string values.
    """
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


def yaml_scalar(value: str) -> str:
    """Escape a value for insertion into a double-quoted YAML scalar."""
    return (
        value.replace('\\', '\\\\')
        .replace('"', '\\"')
        .replace('\n', '\\n')
        .replace('\r', '\\r')
        .replace('\t', '\\t')
    )


def apply(text: str, values: dict[str, str]) -> str:
    """Replace required placeholders in text with their corresponding values.
    
    Parameters:
        text (str): Text containing required placeholders.
        values (dict[str, str]): Mapping of placeholder names to replacement values.
    
    Returns:
        str: Text with matching required placeholders replaced.
    """
    for key, value in values.items():
        text = text.replace(f'__REQUIRED_{key}__', value)
    return text


def remaining_placeholders(task_dir: Path) -> dict[str, list[str]]:
    """
    Find unresolved required placeholders in Markdown and YAML files within a task directory.
    
    Parameters:
        task_dir (Path): Directory containing the task files to scan.
    
    Returns:
        dict[str, list[str]]: Mapping of filenames to their unresolved placeholder names.
    """
    found: dict[str, list[str]] = {}
    for path in sorted(task_dir.rglob('*')):
        if not path.is_file() or path.suffix not in {'.md', '.yaml'}:
            continue
        names = sorted(set(PLACEHOLDER_RE.findall(path.read_text(encoding='utf-8'))))
        if names:
            found[path.name] = names
    return found


def main() -> int:
    """
    Create a task record from the configured template and update the task index.
    
    Returns:
    	int: `0` when the task is created or the dry run succeeds; `1` when task creation fails.
    """
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
    created_task_dir: Path | None = None

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
        resolved: dict[str, Path] = {}
        for key in ('active', 'archive', 'template'):
            value = paths.get(key)
            if not isinstance(value, str) or not value.strip():
                raise TaskFailure(f'{config_path}: paths.{key} must be a non-empty string')
            resolved[key] = repo_path(repo_root, value).resolve(strict=False)
        active_root = resolved['active']
        archive_root = resolved['archive']
        template_root = resolved['template']
        if not template_root.is_dir():
            raise TaskFailure(f'task template not found: {template_root}')

        timezone = config.get('timezone')
        now = timestamp(timezone if isinstance(timezone, str) else 'UTC')
        taken = existing_ids(active_root, archive_root)

        task_id = args.id or allocate_id(config, taken, int(now[:4]))
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
        # Only claim the directory for cleanup once this invocation created it, so a
        # destination collision does not delete a concurrent creation's output.
        created_task_dir = task_dir
        yaml_values = {k: yaml_scalar(v) for k, v in values.items()}
        for path in sorted(task_dir.rglob('*')):
            if not path.is_file() or path.suffix not in {'.md', '.yaml'}:
                continue
            applicable = yaml_values if path.suffix == '.yaml' else values
            path.write_text(
                apply(path.read_text(encoding='utf-8'), applicable),
                encoding='utf-8',
                newline='\n',
            )

        task_file = task_dir / 'task.yaml'
        task = task_file.read_text(encoding='utf-8')
        marker = 'type: "feature"'
        if marker not in task:
            raise TaskFailure(f'{task_file}: expected {marker!r} to set the task type')
        task = task.replace(marker, f'type: "{args.type}"', 1)
        task_file.write_text(task, encoding='utf-8', newline='\n')

        # Verify the written task.yaml parses cleanly before committing.
        load_yaml(task_file)

        index_path, data = build_index(repo_root, instance_root)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(render(data), encoding='utf-8', newline='\n')
    except (TaskFailure, OSError, ValueError, yaml.YAMLError) as exc:
        if created_task_dir is not None and created_task_dir.exists():
            shutil.rmtree(created_task_dir, ignore_errors=True)
            print(f'Removed partial task directory {created_task_dir}', file=sys.stderr)
        print(f'Task creation failed: {exc}', file=sys.stderr)
        return 1

    print(f'Created {task_dir}')
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

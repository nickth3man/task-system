#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

import yaml


INDEX_HEADER = '# GENERATED VIEW ONLY. The authoritative state is each task.yaml.\n'

# The bundle is the replaceable product directory; the instance holds live state.
DEFAULT_BUNDLE_ROOT = '.tasks'
DEFAULT_INSTANCE_ROOT = '.project-tasks'


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open('r', encoding='utf-8') as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ValueError(f'{path}: invalid YAML: {exc}') from exc
    if not isinstance(data, dict):
        raise ValueError(f'{path}: expected a YAML mapping')
    return data


def repo_path(repo_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def safe_relative(repo_root: Path, path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    resolved_root = repo_root.resolve(strict=False)
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        return resolved_path.as_posix()


def ensure_within(path: Path, root: Path, label: str) -> None:
    resolved_path = path.resolve(strict=False)
    resolved_root = root.resolve(strict=False)
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f'{label} resolves outside {resolved_root}') from exc


def require_nonempty_string(config: dict[str, Any], key: str, config_path: Path) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f'{config_path}: {key} must be a non-empty string')
    return value


def task_entries(
    repo_root: Path,
    root: Path,
    archived: bool,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    resolved_root = root.resolve(strict=False)
    if not resolved_root.exists():
        return entries

    for task_file in sorted(resolved_root.rglob('task.yaml')):
        ensure_within(task_file, resolved_root, f'task file {task_file}')
        task = load_yaml(task_file)
        entries.append(
            {
                'id': task.get('id'),
                'slug': task.get('slug'),
                'title': task.get('title'),
                'status': task.get('status'),
                'path': safe_relative(repo_root, task_file.parent),
                'archived': archived,
            }
        )
    return sorted(entries, key=lambda item: (str(item.get('id')), str(item.get('path'))))


def build_index(
    repo_root: Path,
    instance_root: Path,
) -> tuple[Path, dict[str, Any]]:
    config_path = instance_root / 'config.yaml'
    config = load_yaml(config_path)
    schema_version = require_nonempty_string(config, 'schema_version', config_path)
    task_system_version = require_nonempty_string(
        config, 'task_system_version', config_path
    )

    paths = config.get('paths')
    if not isinstance(paths, dict):
        raise ValueError(f'{config_path}: paths must be a mapping')

    resolved: dict[str, Path] = {}
    for key in ('active', 'archive', 'index'):
        value = paths.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f'{config_path}: paths.{key} must be a non-empty string')
        target = repo_path(repo_root, value).resolve(strict=False)
        ensure_within(target, instance_root, f'paths.{key}')
        resolved[key] = target

    data = {
        'schema_version': schema_version,
        'task_system_version': task_system_version,
        'active': task_entries(repo_root, resolved['active'], archived=False),
        'archived': task_entries(repo_root, resolved['archive'], archived=True),
    }
    return resolved['index'], data


def render(data: dict[str, Any]) -> str:
    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    return INDEX_HEADER + body


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate a deterministic task index.')
    parser.add_argument('--repo-root', default='.', help='Repository root.')
    parser.add_argument(
        '--instance-root',
        default=DEFAULT_INSTANCE_ROOT,
        help='Live task instance root.',
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Fail when the checked-in index differs.',
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve(strict=False)
    instance_root = repo_path(repo_root, args.instance_root).resolve(strict=False)
    try:
        index_path, data = build_index(repo_root, instance_root)
        expected = render(data)
        if args.check:
            actual = index_path.read_text(encoding='utf-8') if index_path.exists() else ''
            if actual != expected:
                print(
                    f'Index is stale: {safe_relative(repo_root, index_path)}',
                    file=sys.stderr,
                )
                return 1
            print(f'Index is current: {safe_relative(repo_root, index_path)}')
            return 0

        index_path.parent.mkdir(parents=True, exist_ok=True)
        # newline='\n' keeps the generated index byte-identical across platforms.
        index_path.write_text(expected, encoding='utf-8', newline='\n')
        print(f'Wrote {safe_relative(repo_root, index_path)}')
        return 0
    except (OSError, ValueError) as exc:
        print(f'Index generation failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

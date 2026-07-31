#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

import yaml


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
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError as exc:
        raise ValueError(f'{label} resolves outside {root}') from exc


def task_entries(
    repo_root: Path,
    root: Path,
    archived: bool,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not root.exists():
        return entries
    for task_file in sorted(root.rglob('task.yaml')):
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
    config = load_yaml(instance_root / 'config.yaml')
    paths = config.get('paths')
    if not isinstance(paths, dict):
        raise ValueError(f'{instance_root / "config.yaml"}: paths must be a mapping')

    resolved: dict[str, Path] = {}
    for key in ('active', 'archive', 'index'):
        value = paths.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(
                f'{instance_root / "config.yaml"}: paths.{key} must be a non-empty string'
            )
        target = repo_path(repo_root, value).resolve(strict=False)
        ensure_within(target, instance_root, f'paths.{key}')
        resolved[key] = target

    data = {
        'schema_version': config.get('schema_version'),
        'task_system_version': config.get('task_system_version'),
        'active': task_entries(repo_root, resolved['active'], archived=False),
        'archived': task_entries(repo_root, resolved['archive'], archived=True),
    }
    return resolved['index'], data


def render(data: dict[str, Any]) -> str:
    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    return '# GENERATED VIEW ONLY. The authoritative state is each task.yaml.\n' + body


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate a deterministic task index.')
    parser.add_argument('--repo-root', default='.', help='Repository root.')
    parser.add_argument('--instance-root', default='.tasks', help='Task instance root.')
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
        index_path.write_text(expected, encoding='utf-8')
        print(f'Wrote {safe_relative(repo_root, index_path)}')
        return 0
    except (OSError, ValueError) as exc:
        print(f'Index generation failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

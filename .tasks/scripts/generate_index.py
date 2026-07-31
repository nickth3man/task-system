#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open('r', encoding='utf-8') as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f'{path} must contain a YAML mapping')
    return data


def repo_path(repo_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def task_entries(repo_root: Path, root: Path, archived: bool) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not root.exists():
        return entries
    for task_file in sorted(root.rglob('task.yaml')):
        task = load_yaml(task_file)
        entries.append({'id': task.get('id'), 'slug': task.get('slug'), 'title': task.get('title'), 'status': task.get('status'), 'path': task_file.parent.resolve().relative_to(repo_root.resolve()).as_posix(), 'archived': archived})
    return sorted(entries, key=lambda item: (str(item.get('id')), str(item.get('path'))))


def build_index(repo_root: Path, instance_root: Path) -> tuple[Path, dict[str, Any]]:
    config = load_yaml(instance_root / 'config.yaml')
    paths = config['paths']
    active_root = repo_path(repo_root, paths['active'])
    archive_root = repo_path(repo_root, paths['archive'])
    index_path = repo_path(repo_root, paths['index'])
    data = {'schema_version': config['schema_version'], 'task_system_version': config['task_system_version'], 'active': task_entries(repo_root, active_root, archived=False), 'archived': task_entries(repo_root, archive_root, archived=True)}
    return index_path, data


def render(data: dict[str, Any]) -> str:
    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    return '# GENERATED VIEW ONLY. The authoritative state is each task.yaml.\n' + body


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate a deterministic task index.')
    parser.add_argument('--repo-root', default='.', help='Repository root.')
    parser.add_argument('--instance-root', default='.tasks', help='Task instance root.')
    parser.add_argument('--check', action='store_true', help='Fail when the checked-in index differs.')
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    instance_root = repo_path(repo_root, args.instance_root)
    index_path, data = build_index(repo_root, instance_root)
    expected = render(data)
    if args.check:
        actual = index_path.read_text(encoding='utf-8') if index_path.exists() else ''
        if actual != expected:
            print(f'Index is stale: {index_path.relative_to(repo_root)}', file=sys.stderr)
            return 1
        print(f'Index is current: {index_path.relative_to(repo_root)}')
        return 0
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(expected, encoding='utf-8')
    print(f'Wrote {index_path.relative_to(repo_root)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

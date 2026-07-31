#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
import yaml

from generate_index import build_index, render, repo_path

REQUIRED_ARTIFACTS = {'task.yaml','task.md','assessment.md','research.md','links.md','findings.md','plan.md','implementation-log.md','verification.md','review.md','completion.md'}
CONFLICT_RE = re.compile(r'(?m)^(?:<<<<<<< .+|=======|>>>>>>> .+)$')
PLACEHOLDER = '__REQUIRED_'
HEX64 = re.compile(r'^[0-9a-f]{64}$')

class ValidationFailure(Exception):
    pass

def load_yaml(path: Path) -> dict[str, Any]:
    with path.open('r', encoding='utf-8') as handle: data = yaml.safe_load(handle)
    if not isinstance(data, dict): raise ValidationFailure(f'{path}: expected a YAML mapping')
    return data

def load_json(path: Path) -> dict[str, Any]:
    with path.open('r', encoding='utf-8') as handle: data = json.load(handle)
    if not isinstance(data, dict): raise ValidationFailure(f'{path}: expected a JSON object')
    return data

def validate_schema(data: dict[str, Any], schema: dict[str, Any], label: str, errors: list[str]) -> None:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(validator.iter_errors(data), key=lambda item: list(item.path)):
        location = '.'.join(str(part) for part in error.path) or '<root>'
        errors.append(f'{label}: schema error at {location}: {error.message}')

def contains_placeholder(value: Any) -> bool:
    if isinstance(value, str): return PLACEHOLDER in value
    if isinstance(value, dict): return any(contains_placeholder(item) for item in value.values())
    if isinstance(value, list): return any(contains_placeholder(item) for item in value)
    return False

def digest(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()

def relative(repo_root: Path, path: Path) -> str:
    try: return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError: return path.as_posix()

def validate_template(repo_root: Path, template_root: Path, config_schema: dict[str, Any], task_schema: dict[str, Any], errors: list[str]) -> None:
    required = ['AGENTS.md','README.md','VERSION','config.yaml','index.yaml','requirements.txt','schemas/config.schema.json','schemas/task.schema.json','scripts/validate.py','scripts/generate_index.py','templates/AGENTS.md','templates/task/task.yaml','templates/github/workflows/validate-task-system.yml']
    for item in required:
        if not (template_root / item).exists(): errors.append(f'template missing required file: {relative(repo_root, template_root / item)}')
    config_path = template_root / 'config.yaml'
    if config_path.exists():
        config = load_yaml(config_path); validate_schema(config, config_schema, relative(repo_root, config_path), errors)
        if config.get('mode') != 'template': errors.append(f'{relative(repo_root, config_path)}: mode must be template')
        if not contains_placeholder(config.get('repository', {})): errors.append(f'{relative(repo_root, config_path)}: template repository values must remain placeholders')
        expected_prefix = f'{relative(repo_root, template_root)}/'
        for key in ('active','archive','template','index'):
            value = str(config.get('paths', {}).get(key, ''))
            if not value.startswith(expected_prefix): errors.append(f'{relative(repo_root, config_path)}: paths.{key} must stay inside {relative(repo_root, template_root)}')
    for area in ('active','archive'):
        task_files = list((template_root / area).rglob('task.yaml')) if (template_root / area).exists() else []
        if task_files: errors.append(f'{relative(repo_root, template_root / area)} must contain no live task records')
    task_template = template_root / 'templates/task/task.yaml'
    if task_template.exists():
        task = load_yaml(task_template)
        if not contains_placeholder(task): errors.append(f'{relative(repo_root, task_template)} must retain required placeholders')

def validate_approval(name: str, approval: dict[str, Any], task_dir: Path, task: dict[str, Any], errors: list[str]) -> None:
    if approval.get('status') != 'approved': return
    for field in ('approved_by','approved_at','evidence'):
        if not approval.get(field): errors.append(f'{task["id"]}: approved {name} approval missing {field}')
    if name in ('findings','plan'):
        if not isinstance(approval.get('revision'), int): errors.append(f'{task["id"]}: approved {name} approval missing revision')
        value = approval.get('artifact_sha256')
        if not isinstance(value, str) or not HEX64.match(value): errors.append(f'{task["id"]}: approved {name} approval missing valid artifact_sha256')
        artifact = task_dir / f'{name}.md'
        if artifact.exists() and value != digest(artifact): errors.append(f'{task["id"]}: {name} approval digest does not match {artifact.name}')
    if name in ('pull_request','merge') and not approval.get('head_sha'): errors.append(f'{task["id"]}: approved {name} approval missing head_sha')

def validate_task(repo_root: Path, task_file: Path, archived: bool, schema: dict[str, Any], errors: list[str]) -> str | None:
    task = load_yaml(task_file); label = relative(repo_root, task_file); validate_schema(task, schema, label, errors)
    task_id = task.get('id')
    if not isinstance(task_id, str): return None
    task_dir = task_file.parent; expected_dir = f'{task_id}-{task.get("slug")}'
    if task_dir.name != expected_dir: errors.append(f'{label}: directory must be named {expected_dir}')
    present = {path.name for path in task_dir.iterdir() if path.is_file()}; missing = sorted(REQUIRED_ARTIFACTS - present)
    if missing: errors.append(f'{task_id}: missing required artifacts: {", ".join(missing)}')
    if contains_placeholder(task): errors.append(f'{task_id}: live task contains an unreplaced placeholder')
    status = task.get('status')
    if archived and status != 'archived': errors.append(f'{task_id}: archived directory requires status archived')
    if not archived and status == 'archived': errors.append(f'{task_id}: archived status is not allowed under active path')
    history = task.get('state_history') or []
    if history and history[-1].get('to') != status: errors.append(f'{task_id}: final state_history destination must equal status')
    criteria = task.get('acceptance_criteria') or []; criterion_ids = [item.get('id') for item in criteria]
    if len(criterion_ids) != len(set(criterion_ids)): errors.append(f'{task_id}: duplicate acceptance criterion IDs')
    plan_steps = task.get('plan_steps') or []; plan_ids = [item.get('id') for item in plan_steps]
    if len(plan_ids) != len(set(plan_ids)): errors.append(f'{task_id}: duplicate plan step IDs')
    criterion_set = set(criterion_ids)
    for step in plan_steps:
        for criterion in step.get('supports', []):
            if criterion not in criterion_set: errors.append(f'{task_id}: {step.get("id")} references missing criterion {criterion}')
    approvals = task.get('approvals') or {}
    for name in ('findings','plan','pull_request','merge'): validate_approval(name, approvals.get(name, {}), task_dir, task, errors)
    blocker = task.get('blocker') or {}
    if status == 'blocked':
        for field in ('entered_from_status','reason','since','required_user_decision','resume_status'):
            if not blocker.get(field): errors.append(f'{task_id}: blocked task missing blocker.{field}')
    return task_id

def validate_instance(repo_root: Path, instance_root: Path, config_schema: dict[str, Any], task_schema: dict[str, Any], errors: list[str]) -> None:
    config_path = instance_root / 'config.yaml'
    if not config_path.exists(): errors.append(f'live instance missing {relative(repo_root, config_path)}'); return
    config = load_yaml(config_path); validate_schema(config, config_schema, relative(repo_root, config_path), errors)
    if config.get('mode') != 'live': errors.append(f'{relative(repo_root, config_path)}: mode must be live')
    if contains_placeholder(config): errors.append(f'{relative(repo_root, config_path)}: live configuration contains placeholders')
    instance_rel = relative(repo_root, instance_root)
    for key in ('active','archive','index'):
        value = str(config.get('paths', {}).get(key, ''))
        if not value.startswith(f'{instance_rel}/'): errors.append(f'{relative(repo_root, config_path)}: paths.{key} must stay inside {instance_rel}')
    if config.get('paths', {}).get('template') != '.tasks/templates/task': errors.append(f'{relative(repo_root, config_path)}: paths.template must reference .tasks/templates/task')
    active_root = repo_path(repo_root, config['paths']['active']); archive_root = repo_path(repo_root, config['paths']['archive']); ids: list[str] = []
    for task_file in sorted(active_root.rglob('task.yaml')) if active_root.exists() else []:
        task_id = validate_task(repo_root, task_file, False, task_schema, errors)
        if task_id: ids.append(task_id)
    for task_file in sorted(archive_root.rglob('task.yaml')) if archive_root.exists() else []:
        task_id = validate_task(repo_root, task_file, True, task_schema, errors)
        if task_id: ids.append(task_id)
    if len(ids) != len(set(ids)): errors.append(f'{instance_rel}: duplicate task IDs across active and archive')
    try:
        index_path, data = build_index(repo_root, instance_root); expected = render(data); actual = index_path.read_text(encoding='utf-8') if index_path.exists() else ''
        if actual != expected: errors.append(f'{relative(repo_root, index_path)} is stale; run generate_index.py')
    except Exception as exc: errors.append(f'{instance_rel}: unable to verify index: {exc}')

def scan_conflicts(repo_root: Path, errors: list[str]) -> None:
    excluded = {'.git','.venv','__pycache__'}
    for path in repo_root.rglob('*'):
        if not path.is_file() or any(part in excluded for part in path.parts): continue
        try: text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError: continue
        if CONFLICT_RE.search(text): errors.append(f'{relative(repo_root, path)} contains an unresolved merge-conflict marker')

def main() -> int:
    parser = argparse.ArgumentParser(description='Validate a task-system template and live task instance.')
    parser.add_argument('--repo-root', default='.'); parser.add_argument('--template-root', default='.tasks'); parser.add_argument('--instance-root', default='.tasks'); parser.add_argument('--template-only', action='store_true'); args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve(); template_root = repo_path(repo_root, args.template_root); instance_root = repo_path(repo_root, args.instance_root); errors: list[str] = []
    try:
        config_schema = load_json(template_root / 'schemas/config.schema.json'); task_schema = load_json(template_root / 'schemas/task.schema.json')
        validate_template(repo_root, template_root, config_schema, task_schema, errors)
        if not args.template_only: validate_instance(repo_root, instance_root, config_schema, task_schema, errors)
        scan_conflicts(repo_root, errors)
    except (OSError, ValueError, yaml.YAMLError, json.JSONDecodeError, ValidationFailure) as exc: errors.append(str(exc))
    if errors:
        print('Task-system validation failed:', file=sys.stderr)
        for error in errors: print(f'- {error}', file=sys.stderr)
        return 1
    print(f'Template valid: {relative(repo_root, template_root)}')
    if not args.template_only: print(f'Live instance valid: {relative(repo_root, instance_root)}')
    return 0

if __name__ == '__main__': raise SystemExit(main())

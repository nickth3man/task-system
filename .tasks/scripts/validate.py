#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker
import yaml

from generate_index import build_index, render, repo_path

TASK_MARKDOWN_ARTIFACTS = (
    'task.md',
    'assessment.md',
    'research.md',
    'links.md',
    'findings.md',
    'plan.md',
    'implementation-log.md',
    'verification.md',
    'review.md',
    'completion.md',
)
ACTIVE_REQUIRED_FILES = ('task.yaml', *TASK_MARKDOWN_ARTIFACTS)
ACTIVE_REQUIRED_DIRECTORIES = ('evidence/screenshots',)
TEMPLATE_REQUIRED_FILES = (
    'AGENTS.md',
    'README.md',
    'VERSION',
    'config.yaml',
    'index.yaml',
    'requirements.txt',
    'schemas/config.schema.json',
    'schemas/task.schema.json',
    'scripts/validate.py',
    'scripts/generate_index.py',
    'templates/AGENTS.md',
    'templates/github/workflows/validate-task-system.yml',
    'templates/task/task.yaml',
    *(f'templates/task/{name}' for name in TASK_MARKDOWN_ARTIFACTS),
)
TEMPLATE_REQUIRED_DIRECTORIES = ('active', 'archive', 'templates/task/evidence/screenshots')

NORMAL_STATES = (
    'draft',
    'assessing',
    'researching',
    'awaiting_findings_approval',
    'planning',
    'awaiting_plan_approval',
    'approved',
    'creating_branch',
    'implementing',
    'testing',
    'committing',
    'reviewing',
    'pushing',
    'awaiting_pr_approval',
    'creating_pr',
    'waiting_for_ci',
    'awaiting_merge_approval',
    'merging',
    'completing',
    'completed',
    'archived',
)
EXCEPTIONAL_STATES = {'blocked', 'failed', 'cancelled', 'superseded'}
KNOWN_STATES = set(NORMAL_STATES) | EXCEPTIONAL_STATES
NORMAL_TRANSITIONS = {
    current: following for current, following in zip(NORMAL_STATES, NORMAL_STATES[1:])
}
CORRECTION_TRANSITIONS = {
    ('reviewing', 'implementing'),
    ('pushing', 'waiting_for_ci'),
    ('waiting_for_ci', 'implementing'),
    ('awaiting_merge_approval', 'implementing'),
}

APPROVAL_GATES = {
    'findings': set(NORMAL_STATES[NORMAL_STATES.index('planning') :]),
    'plan': set(NORMAL_STATES[NORMAL_STATES.index('approved') :]),
    'pull_request': set(NORMAL_STATES[NORMAL_STATES.index('creating_pr') :]),
    'merge': set(NORMAL_STATES[NORMAL_STATES.index('merging') :]),
}
MERGE_READY_STATES = {'awaiting_merge_approval', 'merging', 'completing', 'completed', 'archived'}
MERGED_STATES = {'completed', 'archived'}

CONFLICT_RE = re.compile(r'(?m)^(?:<<<<<<< .+|=======|>>>>>>> .+)$')
PLACEHOLDER = '__REQUIRED_'
HEX64 = re.compile(r'^[0-9a-f]{64}$')


class ValidationFailure(Exception):
    """Raised for an input error that should be reported without a traceback."""


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open('r', encoding='utf-8') as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ValidationFailure(f'{path}: invalid YAML: {exc}') from exc
    if not isinstance(data, dict):
        raise ValidationFailure(f'{path}: expected a YAML mapping')
    return data


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open('r', encoding='utf-8') as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValidationFailure(f'{path}: invalid JSON: {exc}') from exc
    if not isinstance(data, dict):
        raise ValidationFailure(f'{path}: expected a JSON object')
    return data


def validate_schema(
    data: dict[str, Any],
    schema: dict[str, Any],
    label: str,
    errors: list[str],
) -> None:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(validator.iter_errors(data), key=lambda item: list(item.path)):
        location = '.'.join(str(part) for part in error.path) or '<root>'
        errors.append(f'{label}: schema error at {location}: {error.message}')


def contains_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return PLACEHOLDER in value
    if isinstance(value, dict):
        return any(contains_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_placeholder(item) for item in value)
    return False


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(repo_root: Path, path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    resolved_root = repo_root.resolve(strict=False)
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        return resolved_path.as_posix()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def configured_path(
    repo_root: Path,
    raw_value: Any,
    label: str,
    errors: list[str],
) -> Path | None:
    if not isinstance(raw_value, str) or not raw_value:
        errors.append(f'{label}: expected a non-empty path string')
        return None
    return repo_path(repo_root, raw_value).resolve(strict=False)


def require_paths(
    root: Path,
    files: Iterable[str],
    directories: Iterable[str],
    repo_root: Path,
    errors: list[str],
    prefix: str,
) -> None:
    for item in files:
        path = root / item
        if not path.is_file():
            errors.append(f'{prefix} missing required file: {relative(repo_root, path)}')
    for item in directories:
        path = root / item
        if not path.is_dir():
            errors.append(f'{prefix} missing required directory: {relative(repo_root, path)}')


def validate_template(
    repo_root: Path,
    template_root: Path,
    config_schema: dict[str, Any],
    errors: list[str],
) -> None:
    require_paths(
        template_root,
        TEMPLATE_REQUIRED_FILES,
        TEMPLATE_REQUIRED_DIRECTORIES,
        repo_root,
        errors,
        'template',
    )

    config_path = template_root / 'config.yaml'
    if config_path.is_file():
        config = load_yaml(config_path)
        validate_schema(config, config_schema, relative(repo_root, config_path), errors)
        if config.get('mode') != 'template':
            errors.append(f'{relative(repo_root, config_path)}: mode must be template')
        if not contains_placeholder(config.get('repository', {})):
            errors.append(
                f'{relative(repo_root, config_path)}: template repository values '
                'must remain placeholders'
            )
        if not contains_placeholder(config.get('timezone')):
            errors.append(
                f'{relative(repo_root, config_path)}: template timezone must remain a placeholder'
            )

        paths = config.get('paths')
        if not isinstance(paths, dict):
            errors.append(f'{relative(repo_root, config_path)}: paths must be a mapping')
        else:
            for key in ('active', 'archive', 'template', 'index'):
                target = configured_path(
                    repo_root,
                    paths.get(key),
                    f'{relative(repo_root, config_path)}: paths.{key}',
                    errors,
                )
                if target is not None and not is_within(target, template_root):
                    errors.append(
                        f'{relative(repo_root, config_path)}: paths.{key} must stay inside '
                        f'{relative(repo_root, template_root)}'
                    )

    for area in ('active', 'archive'):
        area_root = template_root / area
        task_files = list(area_root.rglob('task.yaml')) if area_root.exists() else []
        if task_files:
            errors.append(
                f'{relative(repo_root, area_root)} must contain no live task records'
            )

    task_template_root = template_root / 'templates/task'
    task_yaml = task_template_root / 'task.yaml'
    if task_yaml.is_file():
        task = load_yaml(task_yaml)
        if not contains_placeholder(task):
            errors.append(
                f'{relative(repo_root, task_yaml)} must retain required placeholders'
            )
    for name in TASK_MARKDOWN_ARTIFACTS:
        artifact = task_template_root / name
        if artifact.is_file() and PLACEHOLDER not in artifact.read_text(encoding='utf-8'):
            errors.append(
                f'{relative(repo_root, artifact)} must retain required placeholders'
            )


def validate_approval(
    name: str,
    approval: dict[str, Any],
    task_dir: Path,
    task: dict[str, Any],
    errors: list[str],
) -> None:
    if approval.get('status') != 'approved':
        return

    task_id = str(task.get('id', '<unknown>'))
    for field in ('approved_by', 'approved_at', 'evidence'):
        if not approval.get(field):
            errors.append(f'{task_id}: approved {name} approval missing {field}')

    revisions = task.get('revisions')
    if not isinstance(revisions, dict):
        errors.append(f'{task_id}: revisions must be a mapping')
        return

    current_task_revision = revisions.get('task')
    current_findings_revision = revisions.get('findings')
    current_plan_revision = revisions.get('plan')

    if approval.get('task_revision') != current_task_revision:
        errors.append(
            f'{task_id}: approved {name} approval task_revision must equal '
            f'revisions.task ({current_task_revision})'
        )

    if name in ('findings', 'plan'):
        expected_revision = (
            current_findings_revision if name == 'findings' else current_plan_revision
        )
        if approval.get('revision') != expected_revision:
            errors.append(
                f'{task_id}: approved {name} approval revision must equal '
                f'revisions.{name} ({expected_revision})'
            )
        if approval.get('findings_revision') != current_findings_revision:
            errors.append(
                f'{task_id}: approved {name} approval findings_revision must equal '
                f'revisions.findings ({current_findings_revision})'
            )
        value = approval.get('artifact_sha256')
        if not isinstance(value, str) or not HEX64.fullmatch(value):
            errors.append(
                f'{task_id}: approved {name} approval missing valid artifact_sha256'
            )
        artifact = task_dir / f'{name}.md'
        if artifact.is_file() and value != digest(artifact):
            errors.append(
                f'{task_id}: {name} approval digest does not match {artifact.name}'
            )
        return

    if approval.get('findings_revision') != current_findings_revision:
        errors.append(
            f'{task_id}: approved {name} approval findings_revision must equal '
            f'revisions.findings ({current_findings_revision})'
        )

    git_data = task.get('git') if isinstance(task.get('git'), dict) else {}
    pull_request = (
        task.get('pull_request') if isinstance(task.get('pull_request'), dict) else {}
    )
    candidate_head = git_data.get('candidate_head_sha')
    expected_head = candidate_head
    if name == 'merge':
        expected_head = pull_request.get('head_sha') or candidate_head

    if not expected_head:
        errors.append(f'{task_id}: approved {name} approval has no current candidate head')
    elif approval.get('head_sha') != expected_head:
        errors.append(
            f'{task_id}: approved {name} approval head_sha must equal current '
            f'candidate head {expected_head}'
        )

    if name == 'merge':
        checks = pull_request.get('checks')
        if not isinstance(checks, dict) or checks.get('status') != 'passed':
            errors.append(
                f'{task_id}: merge approval requires passed checks for the approved head'
            )


def allowed_transition(previous: str, following: str) -> bool:
    if NORMAL_TRANSITIONS.get(previous) == following:
        return True
    if (previous, following) in CORRECTION_TRANSITIONS:
        return True
    if previous == 'blocked' and following in KNOWN_STATES - {'draft'}:
        return True
    if previous not in {'archived', 'failed', 'cancelled', 'superseded'}:
        return following in EXCEPTIONAL_STATES
    return False


def validate_history(task_id: str, task: dict[str, Any], errors: list[str]) -> set[str]:
    history = task.get('state_history')
    if not isinstance(history, list) or not history:
        errors.append(f'{task_id}: state_history must contain at least one entry')
        return set()

    first = history[0]
    if not isinstance(first, dict) or first.get('from') is not None or first.get('to') != 'draft':
        errors.append(f'{task_id}: state_history must start with null -> draft')

    reached: set[str] = set()
    previous_to: str | None = None
    for index, entry in enumerate(history):
        if not isinstance(entry, dict):
            errors.append(f'{task_id}: state_history[{index}] must be a mapping')
            continue
        source = entry.get('from')
        destination = entry.get('to')
        if isinstance(destination, str):
            reached.add(destination)
        if destination not in KNOWN_STATES:
            errors.append(
                f'{task_id}: state_history[{index}] has unknown destination {destination}'
            )
        if index > 0:
            if source != previous_to:
                errors.append(
                    f'{task_id}: state_history[{index}].from must equal previous '
                    f'destination {previous_to}'
                )
            if (
                isinstance(source, str)
                and isinstance(destination, str)
                and not allowed_transition(source, destination)
            ):
                errors.append(
                    f'{task_id}: invalid lifecycle transition {source} -> {destination}'
                )
        previous_to = destination if isinstance(destination, str) else None

    status = task.get('status')
    if previous_to != status:
        errors.append(
            f'{task_id}: final state_history destination must equal status {status}'
        )
    return reached


def validate_artifacts(
    repo_root: Path,
    task_dir: Path,
    task_id: str,
    task: dict[str, Any],
    archived: bool,
    config: dict[str, Any],
    errors: list[str],
) -> None:
    if archived:
        archive_config = config.get('archive')
        preserve = archive_config.get('preserve') if isinstance(archive_config, dict) else None
        required_files = (
            tuple(item for item in preserve if isinstance(item, str))
            if isinstance(preserve, list)
            else ('task.yaml', 'task.md', 'completion.md')
        )
        if 'task.yaml' not in required_files:
            required_files = ('task.yaml', *required_files)
        required_directories: tuple[str, ...] = ()
    else:
        required_files = ACTIVE_REQUIRED_FILES
        required_directories = ACTIVE_REQUIRED_DIRECTORIES

    require_paths(
        task_dir,
        required_files,
        required_directories,
        repo_root,
        errors,
        task_id,
    )

    for name in TASK_MARKDOWN_ARTIFACTS:
        artifact = task_dir / name
        if artifact.is_file() and PLACEHOLDER in artifact.read_text(encoding='utf-8'):
            errors.append(
                f'{task_id}: live artifact {name} contains an unreplaced placeholder'
            )

    task_md = task_dir / 'task.md'
    verification_md = task_dir / 'verification.md'
    completion_md = task_dir / 'completion.md'
    plan_md = task_dir / 'plan.md'
    texts: dict[str, str] = {}
    for path in (task_md, verification_md, completion_md, plan_md):
        if path.is_file():
            texts[path.name] = path.read_text(encoding='utf-8')

    criteria = task.get('acceptance_criteria')
    if isinstance(criteria, list):
        for criterion in criteria:
            if not isinstance(criterion, dict) or not isinstance(criterion.get('id'), str):
                continue
            criterion_id = criterion['id']
            for name in ('task.md', 'verification.md', 'completion.md'):
                if name in texts and criterion_id not in texts[name]:
                    errors.append(
                        f'{task_id}: {name} does not reference acceptance criterion '
                        f'{criterion_id}'
                    )

    plan_steps = task.get('plan_steps')
    if isinstance(plan_steps, list) and 'plan.md' in texts:
        for step in plan_steps:
            if not isinstance(step, dict) or not isinstance(step.get('id'), str):
                continue
            if step['id'] not in texts['plan.md']:
                errors.append(
                    f'{task_id}: plan.md does not reference plan step {step["id"]}'
                )


def require_approval(
    task_id: str,
    approvals: dict[str, Any],
    name: str,
    reached: set[str],
    errors: list[str],
) -> None:
    if not reached.intersection(APPROVAL_GATES[name]):
        return
    approval = approvals.get(name)
    if not isinstance(approval, dict) or approval.get('status') != 'approved':
        errors.append(
            f'{task_id}: lifecycle reached a state requiring approved {name} approval'
        )


def validate_merge_readiness(
    task_id: str,
    task: dict[str, Any],
    errors: list[str],
) -> None:
    status = task.get('status')
    if status not in MERGE_READY_STATES:
        return

    criteria = task.get('acceptance_criteria')
    if isinstance(criteria, list):
        for criterion in criteria:
            if not isinstance(criterion, dict):
                continue
            criterion_id = criterion.get('id', '<unknown>')
            criterion_status = criterion.get('status')
            if criterion_status not in {'passed', 'not_applicable'}:
                errors.append(
                    f'{task_id}: {criterion_id} must be passed or not_applicable '
                    f'before {status}'
                )
            evidence = criterion.get('evidence')
            if not isinstance(evidence, list) or not evidence:
                errors.append(
                    f'{task_id}: {criterion_id} requires verification evidence before {status}'
                )

    plan_steps = task.get('plan_steps')
    if isinstance(plan_steps, list):
        for step in plan_steps:
            if not isinstance(step, dict):
                continue
            if step.get('status') not in {'completed', 'not_applicable'}:
                errors.append(
                    f'{task_id}: {step.get("id", "<unknown>")} must be completed or '
                    f'not_applicable before {status}'
                )

    pull_request = (
        task.get('pull_request') if isinstance(task.get('pull_request'), dict) else {}
    )
    checks = pull_request.get('checks')
    if not isinstance(checks, dict) or checks.get('status') != 'passed':
        errors.append(f'{task_id}: {status} requires passed pull-request checks')

    if status in MERGED_STATES:
        if pull_request.get('state') != 'merged':
            errors.append(f'{task_id}: {status} requires a merged pull request')
        merge = task.get('merge') if isinstance(task.get('merge'), dict) else {}
        for field in ('commit_sha', 'merged_at', 'merged_by'):
            if not merge.get(field):
                errors.append(f'{task_id}: {status} requires merge.{field}')


def validate_task(
    repo_root: Path,
    task_file: Path,
    archived: bool,
    schema: dict[str, Any],
    config: dict[str, Any],
    errors: list[str],
) -> str | None:
    task = load_yaml(task_file)
    label = relative(repo_root, task_file)
    validate_schema(task, schema, label, errors)

    task_id = task.get('id')
    if not isinstance(task_id, str):
        return None

    task_dir = task_file.parent
    expected_dir = f'{task_id}-{task.get("slug")}'
    if task_dir.name != expected_dir:
        errors.append(f'{label}: directory must be named {expected_dir}')

    validate_artifacts(repo_root, task_dir, task_id, task, archived, config, errors)
    if contains_placeholder(task):
        errors.append(f'{task_id}: live task contains an unreplaced placeholder')

    status = task.get('status')
    if archived and status != 'archived':
        errors.append(f'{task_id}: archived directory requires status archived')
    if not archived and status == 'archived':
        errors.append(f'{task_id}: archived status is not allowed under active path')

    reached = validate_history(task_id, task, errors)

    criteria = task.get('acceptance_criteria')
    criterion_ids: list[Any] = []
    if isinstance(criteria, list):
        criterion_ids = [item.get('id') for item in criteria if isinstance(item, dict)]
    if len(criterion_ids) != len(set(criterion_ids)):
        errors.append(f'{task_id}: duplicate acceptance criterion IDs')

    plan_steps = task.get('plan_steps')
    plan_ids: list[Any] = []
    if isinstance(plan_steps, list):
        plan_ids = [item.get('id') for item in plan_steps if isinstance(item, dict)]
    if len(plan_ids) != len(set(plan_ids)):
        errors.append(f'{task_id}: duplicate plan step IDs')

    criterion_set = set(criterion_ids)
    if isinstance(plan_steps, list):
        for step in plan_steps:
            if not isinstance(step, dict):
                continue
            supports = step.get('supports')
            if not isinstance(supports, list) or not supports:
                errors.append(f'{task_id}: {step.get("id")} must support at least one criterion')
                continue
            for criterion in supports:
                if criterion not in criterion_set:
                    errors.append(
                        f'{task_id}: {step.get("id")} references missing criterion '
                        f'{criterion}'
                    )

    approvals = task.get('approvals')
    if not isinstance(approvals, dict):
        approvals = {}
        errors.append(f'{task_id}: approvals must be a mapping')
    for name in ('findings', 'plan', 'pull_request', 'merge'):
        approval = approvals.get(name)
        if not isinstance(approval, dict):
            approval = {}
        validate_approval(name, approval, task_dir, task, errors)
        require_approval(task_id, approvals, name, reached, errors)

    validate_merge_readiness(task_id, task, errors)

    blocker = task.get('blocker')
    if status == 'blocked':
        if not isinstance(blocker, dict):
            errors.append(f'{task_id}: blocked task requires blocker metadata')
        else:
            for field in (
                'entered_from_status',
                'reason',
                'since',
                'required_user_decision',
                'resume_status',
            ):
                if not blocker.get(field):
                    errors.append(f'{task_id}: blocked task missing blocker.{field}')

    return task_id


def validate_instance(
    repo_root: Path,
    template_root: Path,
    instance_root: Path,
    config_schema: dict[str, Any],
    task_schema: dict[str, Any],
    errors: list[str],
) -> None:
    config_path = instance_root / 'config.yaml'
    if not config_path.is_file():
        errors.append(f'live instance missing {relative(repo_root, config_path)}')
        return

    config = load_yaml(config_path)
    validate_schema(config, config_schema, relative(repo_root, config_path), errors)
    if config.get('mode') != 'live':
        errors.append(f'{relative(repo_root, config_path)}: mode must be live')
    if contains_placeholder(config):
        errors.append(
            f'{relative(repo_root, config_path)}: live configuration contains placeholders'
        )

    paths = config.get('paths')
    if not isinstance(paths, dict):
        errors.append(f'{relative(repo_root, config_path)}: paths must be a mapping')
        return

    resolved: dict[str, Path] = {}
    for key in ('active', 'archive', 'index'):
        target = configured_path(
            repo_root,
            paths.get(key),
            f'{relative(repo_root, config_path)}: paths.{key}',
            errors,
        )
        if target is None:
            continue
        resolved[key] = target
        if not is_within(target, instance_root):
            errors.append(
                f'{relative(repo_root, config_path)}: paths.{key} must stay inside '
                f'{relative(repo_root, instance_root)}'
            )

    task_template = configured_path(
        repo_root,
        paths.get('template'),
        f'{relative(repo_root, config_path)}: paths.template',
        errors,
    )
    expected_template = (template_root / 'templates/task').resolve(strict=False)
    if task_template is not None and task_template != expected_template:
        errors.append(
            f'{relative(repo_root, config_path)}: paths.template must resolve to '
            f'{relative(repo_root, expected_template)}'
        )

    if not {'active', 'archive', 'index'}.issubset(resolved):
        return

    active_root = resolved['active']
    archive_root = resolved['archive']
    ids: list[str] = []
    active_files = sorted(active_root.rglob('task.yaml')) if active_root.exists() else []
    archive_files = sorted(archive_root.rglob('task.yaml')) if archive_root.exists() else []
    for task_file in active_files:
        task_id = validate_task(
            repo_root,
            task_file,
            False,
            task_schema,
            config,
            errors,
        )
        if task_id:
            ids.append(task_id)
    for task_file in archive_files:
        task_id = validate_task(
            repo_root,
            task_file,
            True,
            task_schema,
            config,
            errors,
        )
        if task_id:
            ids.append(task_id)
    if len(ids) != len(set(ids)):
        errors.append(
            f'{relative(repo_root, instance_root)}: duplicate task IDs across active and archive'
        )

    try:
        index_path, data = build_index(repo_root, instance_root)
        expected = render(data)
        actual = index_path.read_text(encoding='utf-8') if index_path.exists() else ''
        if actual != expected:
            errors.append(
                f'{relative(repo_root, index_path)} is stale; run generate_index.py'
            )
    except (OSError, ValueError, ValidationFailure) as exc:
        errors.append(
            f'{relative(repo_root, instance_root)}: unable to verify index: {exc}'
        )


def scan_conflicts(repo_root: Path, errors: list[str]) -> None:
    excluded = {'.git', '.venv', '__pycache__'}
    for path in repo_root.rglob('*'):
        if not path.is_file() or any(part in excluded for part in path.parts):
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        if CONFLICT_RE.search(text):
            errors.append(
                f'{relative(repo_root, path)} contains an unresolved merge-conflict marker'
            )


def select_modes(
    template_root: Path,
    instance_root: Path,
    template_only: bool,
    instance_only: bool,
) -> tuple[bool, bool]:
    if template_only:
        return True, False
    if instance_only:
        return False, True
    if template_root.resolve(strict=False) != instance_root.resolve(strict=False):
        return True, True

    config = load_yaml(instance_root / 'config.yaml')
    mode = config.get('mode')
    if mode == 'template':
        return True, False
    if mode == 'live':
        return False, True
    raise ValidationFailure(
        f'{instance_root / "config.yaml"}: same-root validation requires mode '
        'template or live, or an explicit --template-only/--instance-only flag'
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Validate a task-system template and/or live task instance.'
    )
    parser.add_argument('--repo-root', default='.', help='Repository root.')
    parser.add_argument('--template-root', default='.tasks', help='Bundle/template root.')
    parser.add_argument('--instance-root', default='.tasks', help='Live instance root.')
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        '--template-only',
        action='store_true',
        help='Validate only the pristine distributable template.',
    )
    mode_group.add_argument(
        '--instance-only',
        action='store_true',
        help='Validate only an initialized live instance.',
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve(strict=False)
    template_root = repo_path(repo_root, args.template_root).resolve(strict=False)
    instance_root = repo_path(repo_root, args.instance_root).resolve(strict=False)
    errors: list[str] = []

    validate_template_mode = False
    validate_instance_mode = False
    try:
        validate_template_mode, validate_instance_mode = select_modes(
            template_root,
            instance_root,
            args.template_only,
            args.instance_only,
        )
        config_schema = load_json(template_root / 'schemas/config.schema.json')
        task_schema = load_json(template_root / 'schemas/task.schema.json')
        if validate_template_mode:
            validate_template(repo_root, template_root, config_schema, errors)
        if validate_instance_mode:
            validate_instance(
                repo_root,
                template_root,
                instance_root,
                config_schema,
                task_schema,
                errors,
            )
        scan_conflicts(repo_root, errors)
    except (OSError, ValueError, ValidationFailure) as exc:
        errors.append(str(exc))

    if errors:
        print('Task-system validation failed:', file=sys.stderr)
        for error in errors:
            print(f'- {error}', file=sys.stderr)
        return 1

    if validate_template_mode:
        print(f'Template valid: {relative(repo_root, template_root)}')
    if validate_instance_mode:
        print(f'Live instance valid: {relative(repo_root, instance_root)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

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

from common import (
    LITE_REQUIRED_DIRECTORIES,
    LITE_REQUIRED_FILES,
    PLACEHOLDER,
    PLACEHOLDER_RE,
)
from generate_index import (
    DEFAULT_BUNDLE_ROOT,
    DEFAULT_INSTANCE_ROOT,
    build_index,
    render,
    repo_path,
)


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
# The lite profile folds assessment and research into findings.md and drops the
# active-only working files. completion.md stays so archived records remain
# self-describing. Every approval and traceability rule is unchanged.
TEMPLATE_REQUIRED_FILES = (
    '.gitignore',
    'AGENTS.md',
    'README.md',
    'VERSION',
    'requirements.txt',
    'schemas/config.schema.json',
    'schemas/task.schema.json',
    'scripts/common.py',
    'scripts/validate.py',
    'scripts/generate_index.py',
    'scripts/init.py',
    'scripts/new_task.py',
    'scripts/upgrade.py',
    'tests/test_tools.py',
    'templates/AGENTS.md',
    'templates/instance/config.yaml',
    'templates/github/workflows/validate-task-system.yml',
    'templates/task/task.yaml',
    *(f'templates/task/{name}' for name in TASK_MARKDOWN_ARTIFACTS),
)
TEMPLATE_REQUIRED_DIRECTORIES = (
    'templates/task/evidence/screenshots',
    'tests',
)
# The bundle is the replaceable product. Live task state must never live inside
# it, or upgrading the bundle would destroy the repository's task records.
TEMPLATE_FORBIDDEN_DIRECTORIES = ('active', 'archive')
TEMPLATE_FORBIDDEN_FILES = ('config.yaml', 'index.yaml')
LIVE_STATE_PATH_KEYS = ('active', 'archive', 'index')

# `init.py --prune-install-files` drops everything only needed at install time
# and leaves this marker behind, so a pruned bundle still validates.
BUNDLE_PRUNED_MARKER = '.pruned'
INSTALL_ONLY_FILES = (
    'README.md',
    'scripts/init.py',
    'tests/test_tools.py',
    'templates/AGENTS.md',
    'templates/instance/config.yaml',
    'templates/github/workflows/validate-task-system.yml',
)
INSTALL_ONLY_DIRECTORIES = ('tests',)

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
TERMINAL_STATES = {'completed', 'archived', 'failed', 'cancelled', 'superseded'}

APPROVAL_GATES = {
    'findings': set(NORMAL_STATES[NORMAL_STATES.index('planning') :]),
    'plan': set(NORMAL_STATES[NORMAL_STATES.index('approved') :]),
    'pull_request': set(NORMAL_STATES[NORMAL_STATES.index('creating_pr') :]),
    'merge': set(NORMAL_STATES[NORMAL_STATES.index('merging') :]),
}
MERGE_READY_STATES = {
    'awaiting_merge_approval',
    'merging',
    'completing',
    'completed',
    'archived',
}
MERGED_STATES = {'completed', 'archived'}

# A bare `=======` line is also a Markdown setext heading and an ordinary ASCII
# divider, so it is never sufficient on its own. A start or end marker is enough
# to identify an unresolved or partially resolved conflict.
CONFLICT_START_RE = re.compile(r'(?m)^<<<<<<<(?: .*)?$')
CONFLICT_END_RE = re.compile(r'(?m)^>>>>>>>(?: .*)?$')
MAX_REPORTED_PLACEHOLDERS = 5
HEX64 = re.compile(r'^[0-9a-f]{64}$')
# A root instruction file that still points at these is describing a pre-4.0
# layout, where live state lived inside the bundle.
REMOVED_BUNDLE_PATHS = ('config.yaml', 'index.yaml', 'active', 'archive')
STATED_VERSION_RE = re.compile(
    r'task[ -]system version[^0-9]{0,12}(\d+)\.(\d+)\.(\d+)', re.IGNORECASE
)


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
    """
    Validate data against a JSON Schema and record each validation error.
    
    Parameters:
    	data (dict[str, Any]): Data to validate.
    	schema (dict[str, Any]): JSON Schema to apply.
    	label (str): Label identifying the validated data in error messages.
    	errors (list[str]): List to receive formatted validation errors.
    """
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(validator.iter_errors(data), key=lambda item: list(item.path)):
        location = '.'.join(str(part) for part in error.path) or '<root>'
        errors.append(f'{label}: schema error at {location}: {error.message}')


def placeholder_locations(text: str) -> list[str]:
    """Return `line:TOKEN` strings for every placeholder left in `text`."""
    found: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for match in PLACEHOLDER_RE.finditer(line):
            found.append(f'{number}:{match.group(0)}')
    return found


def summarize(items: list[str]) -> str:
    """
    Summarize a list of items, limiting the displayed entries to the configured maximum.
    
    Parameters:
    	items (list[str]): Items to summarize.
    
    Returns:
    	str: A comma-separated summary, including the count of omitted items when applicable.
    """
    shown = ', '.join(items[:MAX_REPORTED_PLACEHOLDERS])
    remaining = len(items) - MAX_REPORTED_PLACEHOLDERS
    return f'{shown} (and {remaining} more)' if remaining > 0 else shown


def placeholder_keys(value: Any, prefix: str = '') -> list[str]:
    """Return dotted key paths whose value still holds a placeholder."""
    found: list[str] = []
    if isinstance(value, str):
        if PLACEHOLDER in value:
            found.append(prefix or '<root>')
    elif isinstance(value, dict):
        for key, item in value.items():
            found.extend(placeholder_keys(item, f'{prefix}.{key}' if prefix else str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(placeholder_keys(item, f'{prefix}[{index}]'))
    return found


def contains_placeholder(value: Any) -> bool:
    """Determine whether a value or any nested item contains a placeholder."""
    if isinstance(value, str):
        return PLACEHOLDER in value
    if isinstance(value, dict):
        return any(contains_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_placeholder(item) for item in value)
    return False


def digest(path: Path) -> str:
    """Hash normalized content so an approval survives a CRLF checkout."""
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def relative(repo_root: Path, path: Path) -> str:
    """
    Return a POSIX-format path relative to the repository root when possible.
    
    Parameters:
    	repo_root (Path): Repository root used as the reference path.
    	path (Path): Path to convert.
    
    Returns:
    	str: Repository-relative path, or the resolved absolute path when the path is outside the repository root.
    """
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


def references_id(text: str, identifier: str) -> bool:
    """
    Determine whether text contains an identifier as a standalone token.
    
    Parameters:
    	text (str): Text to search.
    	identifier (str): Identifier to find.
    
    Returns:
    	bool: `true` if the identifier appears as a standalone token, `false` otherwise.
    """
    pattern = rf'(?<![A-Za-z0-9_-]){re.escape(identifier)}(?![A-Za-z0-9_-])'
    return re.search(pattern, text) is not None


def validate_path_layout(
    repo_root: Path,
    config_path: Path,
    paths: dict[str, Any],
    bundle_root: Path,
    errors: list[str],
) -> None:
    """
    Validate bundle and live-state path separation.
    
    Parameters:
        repo_root (Path): Repository root used to resolve configured paths.
        config_path (Path): Path to the configuration file being validated.
        paths (dict[str, Any]): Configured template and live-state paths.
        bundle_root (Path): Root directory of the replaceable bundle.
        errors (list[str]): Collection to which validation errors are appended.
    """
    label = relative(repo_root, config_path)
    task_template = configured_path(
        repo_root,
        paths.get('template'),
        f'{label}: paths.template',
        errors,
    )
    expected_template = (bundle_root / 'templates/task').resolve(strict=False)
    if task_template is not None and task_template != expected_template:
        errors.append(
            f'{label}: paths.template must resolve to '
            f'{relative(repo_root, expected_template)}'
        )

    for key in LIVE_STATE_PATH_KEYS:
        target = configured_path(repo_root, paths.get(key), f'{label}: paths.{key}', errors)
        if target is not None and is_within(target, bundle_root):
            errors.append(
                f'{label}: paths.{key} must stay outside the bundle at '
                f'{relative(repo_root, bundle_root)} so the bundle can be replaced '
                'on upgrade'
            )


def validate_template(
    repo_root: Path,
    template_root: Path,
    config_schema: dict[str, Any],
    errors: list[str],
) -> None:
    """
    Validate the bundle template structure, configuration, and required placeholders.
    
    Parameters:
        repo_root (Path): Repository root used to report paths and resolve configured locations.
        template_root (Path): Root directory of the bundle template.
        config_schema (dict[str, Any]): Schema used to validate the template instance configuration.
        errors (list[str]): List to which validation errors are appended.
    """
    pruned = (template_root / BUNDLE_PRUNED_MARKER).is_file()
    required_files = tuple(
        name for name in TEMPLATE_REQUIRED_FILES
        if not (pruned and name in INSTALL_ONLY_FILES)
    )
    required_directories = tuple(
        name for name in TEMPLATE_REQUIRED_DIRECTORIES
        if not (pruned and name in INSTALL_ONLY_DIRECTORIES)
    )
    require_paths(
        template_root,
        required_files,
        required_directories,
        repo_root,
        errors,
        'bundle',
    )

    for name in TEMPLATE_FORBIDDEN_DIRECTORIES:
        path = template_root / name
        if path.is_dir():
            errors.append(
                f'bundle must not contain live task state: '
                f'{relative(repo_root, path)}'
            )
    for name in TEMPLATE_FORBIDDEN_FILES:
        path = template_root / name
        if path.is_file():
            errors.append(
                f'bundle must not contain live instance files: '
                f'{relative(repo_root, path)}'
            )

    config_path = template_root / 'templates/instance/config.yaml'
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
            bundle_root = configured_path(
                repo_root,
                paths.get('bundle'),
                f'{relative(repo_root, config_path)}: paths.bundle',
                errors,
            )
            if bundle_root is not None:
                if bundle_root != template_root.resolve(strict=False):
                    errors.append(
                        f'{relative(repo_root, config_path)}: paths.bundle must resolve '
                        f'to the bundle under validation '
                        f'({relative(repo_root, template_root)})'
                    )
                validate_path_layout(repo_root, config_path, paths, bundle_root, errors)

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


def requires_ci(config: dict[str, Any]) -> bool:
    """
    Determine whether GitHub pull-request checks are required for merge validation.
    
    Parameters:
        config (dict[str, Any]): Repository and GitHub configuration.
    
    Returns:
        bool: `true` when the repository provider is GitHub and GitHub checks are enabled; `false` otherwise.
    """
    repository = config.get('repository')
    github = config.get('github')
    provider = repository.get('provider') if isinstance(repository, dict) else None
    enabled = github.get('enabled') if isinstance(github, dict) else None
    return provider == 'github' and enabled is not False


def validate_approval(
    name: str,
    approval: dict[str, Any],
    task_dir: Path,
    task: dict[str, Any],
    errors: list[str],
    ci_required: bool = True,
) -> None:
    """
    Validate an approved task gate against its task metadata and artifacts.
    
    Parameters:
    	name (str): Approval gate name, such as `findings`, `plan`, `pull_request`, or `merge`.
    	approval (dict[str, Any]): Approval data to validate.
    	task_dir (Path): Directory containing the task artifacts.
    	task (dict[str, Any]): Task metadata and revision information.
    	errors (list[str]): Collection to which validation errors are appended.
    	ci_required (bool): Whether merge approval must include matching pull-request and passed CI checks.
    """
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
    if not isinstance(candidate_head, str) or not candidate_head:
        errors.append(f'{task_id}: approved {name} approval has no current candidate head')
        return

    expected_head = candidate_head
    if name == 'merge' and ci_required:
        pr_head = pull_request.get('head_sha')
        if not isinstance(pr_head, str) or not pr_head:
            errors.append(f'{task_id}: merge approval requires pull_request.head_sha')
        elif pr_head != candidate_head:
            errors.append(
                f'{task_id}: merge approval requires pull_request.head_sha to equal '
                f'git.candidate_head_sha ({candidate_head})'
            )

    if approval.get('head_sha') != expected_head:
        errors.append(
            f'{task_id}: approved {name} approval head_sha must equal current '
            f'candidate head {expected_head}'
        )

    if name == 'merge' and ci_required:
        checks = pull_request.get('checks')
        if not isinstance(checks, dict) or checks.get('status') != 'passed':
            errors.append(
                f'{task_id}: merge approval requires passed checks for the approved head'
            )


def allowed_transition(
    previous: str,
    following: str,
    blocked_resume_status: str | None,
) -> bool:
    if NORMAL_TRANSITIONS.get(previous) == following:
        return True
    if (previous, following) in CORRECTION_TRANSITIONS:
        return True
    if previous == 'blocked':
        return (
            blocked_resume_status is not None
            and following == blocked_resume_status
            and following in NORMAL_STATES
            and following not in {'completed', 'archived'}
        )
    if previous not in TERMINAL_STATES:
        return following in EXCEPTIONAL_STATES
    return False


def validate_history(task_id: str, task: dict[str, Any], errors: list[str]) -> set[str]:
    """
    Validate a task's lifecycle history and collect its recorded states.
    
    Parameters:
        task_id (str): Identifier used to label validation errors.
        task (dict[str, Any]): Task data containing lifecycle history and status.
        errors (list[str]): Collection to which validation errors are appended.
    
    Returns:
        set[str]: States recorded as history destinations.
    """
    history = task.get('state_history')
    if not isinstance(history, list) or not history:
        errors.append(f'{task_id}: state_history must contain at least one entry')
        return set()

    blocker = task.get('blocker') if isinstance(task.get('blocker'), dict) else {}
    resume_value = blocker.get('resume_status')
    blocked_resume_status = resume_value if isinstance(resume_value, str) else None

    first = history[0]
    if (
        not isinstance(first, dict)
        or first.get('from') is not None
        or first.get('to') != 'draft'
    ):
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
                and not allowed_transition(source, destination, blocked_resume_status)
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


def uses_lite_profile(task: dict[str, Any], config: dict[str, Any]) -> bool:
    """
    Determine whether a task uses the configured lite artifact profile.
    
    Parameters:
    	task (dict[str, Any]): Task data containing its type.
    	config (dict[str, Any]): Configuration containing lifecycle settings.
    
    Returns:
    	bool: `true` if the task type is listed in `lite_profile_task_types`, `false` otherwise.
    """
    lifecycle = config.get('lifecycle')
    allowed = lifecycle.get('lite_profile_task_types') if isinstance(lifecycle, dict) else None
    if not isinstance(allowed, list):
        return False
    return task.get('type') in {item for item in allowed if isinstance(item, str)}


def validate_artifacts(
    repo_root: Path,
    task_dir: Path,
    task_id: str,
    task: dict[str, Any],
    archived: bool,
    config: dict[str, Any],
    errors: list[str],
) -> None:
    """
    Validate a task's required artifacts and their references.
    
    Parameters:
    	task_dir (Path): Directory containing the task artifacts.
    	task_id (str): Identifier used in validation errors.
    	task (dict[str, Any]): Task metadata, including acceptance criteria and plan steps.
    	archived (bool): Whether the task is archived.
    """
    lite = uses_lite_profile(task, config)
    if archived:
        archive_config = config.get('archive')
        preserve = archive_config.get('preserve') if isinstance(archive_config, dict) else None
        required_files = (
            tuple(item for item in preserve if isinstance(item, str))
            if isinstance(preserve, list)
            else ('task.yaml', 'task.md', 'completion.md')
        )
        if lite:
            required_files = tuple(
                name for name in required_files if name in LITE_REQUIRED_FILES
            )
        if 'task.yaml' not in required_files:
            required_files = ('task.yaml', *required_files)
        required_directories: tuple[str, ...] = ()
    elif lite:
        required_files = LITE_REQUIRED_FILES
        required_directories = LITE_REQUIRED_DIRECTORIES
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
        if not artifact.is_file():
            continue
        found = placeholder_locations(artifact.read_text(encoding='utf-8'))
        if found:
            errors.append(
                f'{task_id}: {name} has {len(found)} unreplaced placeholder(s) at '
                f'{summarize(found)}'
            )

    paths = {
        name: task_dir / name
        for name in ('task.md', 'verification.md', 'completion.md', 'plan.md')
    }
    texts = {
        name: path.read_text(encoding='utf-8')
        for name, path in paths.items()
        if path.is_file()
    }

    criteria = task.get('acceptance_criteria')
    if isinstance(criteria, list):
        for criterion in criteria:
            if not isinstance(criterion, dict):
                continue
            criterion_id = criterion.get('id')
            if not isinstance(criterion_id, str):
                continue
            for name in ('task.md', 'verification.md', 'completion.md'):
                if name in texts and not references_id(texts[name], criterion_id):
                    errors.append(
                        f'{task_id}: {name} does not reference acceptance criterion '
                        f'{criterion_id}'
                    )

    plan_steps = task.get('plan_steps')
    if isinstance(plan_steps, list) and 'plan.md' in texts:
        for step in plan_steps:
            if not isinstance(step, dict):
                continue
            plan_id = step.get('id')
            if not isinstance(plan_id, str):
                continue
            if not references_id(texts['plan.md'], plan_id):
                errors.append(
                    f'{task_id}: plan.md does not reference plan step {plan_id}'
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
    ci_required: bool = True,
) -> None:
    """
    Validate acceptance criteria, plan steps, CI checks, and merge metadata required for a task's merge-ready status.
    
    Parameters:
    	task_id (str): Identifier used to report validation errors.
    	task (dict[str, Any]): Task data to validate.
    	errors (list[str]): Collection to which validation errors are appended.
    	ci_required (bool): Whether passed CI checks and a merged pull request are required.
    
    """
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
    if ci_required:
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


def string_ids(items: Any, field: str = 'id') -> list[str]:
    if not isinstance(items, list):
        return []
    return [
        value
        for item in items
        if isinstance(item, dict)
        for value in [item.get(field)]
        if isinstance(value, str)
    ]


def validate_blocker(
    task_id: str,
    task: dict[str, Any],
    reached: set[str],
    errors: list[str],
) -> None:
    blocker = task.get('blocker')
    status = task.get('status')
    if 'blocked' not in reached:
        if isinstance(blocker, dict) and blocker.get('is_blocked'):
            errors.append(f'{task_id}: blocker.is_blocked is true without a blocked state')
        return

    if not isinstance(blocker, dict):
        errors.append(f'{task_id}: blocked history requires blocker metadata')
        return

    entered_from = blocker.get('entered_from_status')
    resume_status = blocker.get('resume_status')
    if not isinstance(entered_from, str) or entered_from not in NORMAL_STATES:
        errors.append(f'{task_id}: blocker.entered_from_status must be a normal state')
    if not isinstance(resume_status, str) or resume_status not in NORMAL_STATES:
        errors.append(f'{task_id}: blocker.resume_status must be a normal state')
    entered_from_is_terminal = (
        isinstance(entered_from, str) and entered_from in {'completed', 'archived'}
    )
    resume_status_is_terminal = (
        isinstance(resume_status, str) and resume_status in {'completed', 'archived'}
    )
    if entered_from_is_terminal or resume_status_is_terminal:
        errors.append(f'{task_id}: blocker cannot enter from or resume to a terminal state')
    if isinstance(entered_from, str) and resume_status != entered_from:
        errors.append(
            f'{task_id}: blocker.resume_status must equal blocker.entered_from_status'
        )

    history = task.get('state_history')
    blocked_entries = (
        [entry for entry in history if isinstance(entry, dict) and entry.get('to') == 'blocked']
        if isinstance(history, list)
        else []
    )
    if blocked_entries and blocked_entries[-1].get('from') != entered_from:
        errors.append(
            f'{task_id}: blocker.entered_from_status must match the latest transition '
            'into blocked'
        )

    if status == 'blocked':
        if blocker.get('is_blocked') is not True:
            errors.append(f'{task_id}: blocked status requires blocker.is_blocked true')
        for field in ('reason', 'since', 'required_user_decision'):
            if not blocker.get(field):
                errors.append(f'{task_id}: blocked task missing blocker.{field}')
    else:
        if blocker.get('is_blocked') is not False:
            errors.append(f'{task_id}: resumed task requires blocker.is_blocked false')
        for field in ('resolved_at', 'resolution'):
            if not blocker.get(field):
                errors.append(f'{task_id}: resumed task missing blocker.{field}')


def validate_task(
    repo_root: Path,
    task_file: Path,
    archived: bool,
    schema: dict[str, Any],
    config: dict[str, Any],
    errors: list[str],
) -> str | None:
    """
    Validate a task definition, its artifacts, lifecycle, approvals, and merge readiness.
    
    Parameters:
    	repo_root (Path): Root directory used to report task-relative paths.
    	task_file (Path): Path to the task definition file.
    	archived (bool): Whether the task is located in the archive.
    	schema (dict[str, Any]): Schema used to validate the task definition.
    	config (dict[str, Any]): Task-system configuration used for validation rules.
    	errors (list[str]): Collection to which validation errors are appended.
    
    Returns:
    	str | None: The task identifier when it is valid enough to identify the task; otherwise, `None`.
    """
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
    stale_keys = placeholder_keys(task)
    if stale_keys:
        errors.append(
            f'{task_id}: task.yaml has unreplaced placeholders at {summarize(stale_keys)}'
        )

    status = task.get('status')
    if archived and status != 'archived':
        errors.append(f'{task_id}: archived directory requires status archived')
    if not archived and status == 'archived':
        errors.append(f'{task_id}: archived status is not allowed under active path')

    reached = validate_history(task_id, task, errors)

    criteria = task.get('acceptance_criteria')
    criterion_ids = string_ids(criteria)
    if len(criterion_ids) != len(set(criterion_ids)):
        errors.append(f'{task_id}: duplicate acceptance criterion IDs')

    plan_steps = task.get('plan_steps')
    plan_ids = string_ids(plan_steps)
    if len(plan_ids) != len(set(plan_ids)):
        errors.append(f'{task_id}: duplicate plan step IDs')

    criterion_set = set(criterion_ids)
    if isinstance(plan_steps, list):
        for step in plan_steps:
            if not isinstance(step, dict):
                continue
            plan_id = step.get('id') if isinstance(step.get('id'), str) else '<unknown>'
            supports = step.get('supports')
            if not isinstance(supports, list) or not supports:
                errors.append(f'{task_id}: {plan_id} must support at least one criterion')
                continue
            for criterion in supports:
                if not isinstance(criterion, str):
                    continue
                if criterion not in criterion_set:
                    errors.append(
                        f'{task_id}: {plan_id} references missing criterion {criterion}'
                    )

    ci_required = requires_ci(config)
    approvals = task.get('approvals')
    if not isinstance(approvals, dict):
        approvals = {}
        errors.append(f'{task_id}: approvals must be a mapping')
    for name in ('findings', 'plan', 'pull_request', 'merge'):
        approval = approvals.get(name)
        if not isinstance(approval, dict):
            approval = {}
        validate_approval(name, approval, task_dir, task, errors, ci_required)
        require_approval(task_id, approvals, name, reached, errors)

    validate_merge_readiness(task_id, task, errors, ci_required)
    validate_blocker(task_id, task, reached, errors)
    return task_id


def validate_instructions(
    repo_root: Path,
    instructions_path: Path,
    bundle_root: Path,
    instance_root: Path,
    installed_version: str | None,
    errors: list[str],
) -> None:
    """
    Validate the root instruction file and its references to the installed task system.
    
    Parameters:
        repo_root (Path): Repository root used to display relative paths.
        instructions_path (Path): Path to the root instruction file.
        bundle_root (Path): Installed task bundle root.
        instance_root (Path): Live task instance root.
        installed_version (str | None): Installed task-system version, when available.
        errors (list[str]): Collection to which validation errors are appended.
    """
    label = relative(repo_root, instructions_path)
    if not instructions_path.is_file():
        errors.append(
            f'missing agent instruction file {label}; nothing directs an agent to '
            'the task system'
        )
        return

    try:
        text = instructions_path.read_text(encoding='utf-8')
    except (UnicodeDecodeError, OSError) as exc:
        errors.append(
            f'unreadable agent instruction file {label}: {exc}; the task system '
            'cannot be validated'
        )
        return
    bundle = relative(repo_root, bundle_root)
    instance = relative(repo_root, instance_root)

    if not text.strip():
        errors.append(
            f'{label} is empty; run scripts/init.py --install-root-agents to write '
            'the task-system section'
        )
        return

    if f'{bundle}/AGENTS.md' not in text:
        errors.append(f'{label} does not reference {bundle}/AGENTS.md')
    if instance not in text:
        errors.append(
            f'{label} does not reference the live instance {instance}; it may describe '
            'a previous installation'
        )

    for name in REMOVED_BUNDLE_PATHS:
        stale = f'{bundle}/{name}'
        if re.search(rf'(?<![\w./-]){re.escape(stale)}(?=$|[^\w./-])', text):
            errors.append(
                f'{label} references {stale}, which no longer exists; live state '
                f'moved to {instance}'
            )

    match = STATED_VERSION_RE.search(text)
    if match and installed_version:
        stated_major = match.group(1)
        installed_major = installed_version.split('.')[0]
        if stated_major != installed_major:
            stated = '.'.join(match.group(1, 2, 3))
            errors.append(
                f'{label} states task-system version {stated}, but version '
                f'{installed_version} is installed'
            )


def validate_instance(
    repo_root: Path,
    instance_root: Path,
    config_schema: dict[str, Any],
    task_schema: dict[str, Any],
    errors: list[str],
) -> None:
    """
    Validate a live task-system instance and report configuration, layout, task, and index errors.
    
    Parameters:
    	repo_root (Path): Repository root used to resolve and report paths.
    	instance_root (Path): Root directory of the live instance.
    	config_schema (dict[str, Any]): Schema used to validate the instance configuration.
    	task_schema (dict[str, Any]): Schema used to validate task files.
    	errors (list[str]): Collection to which validation errors are appended.
    """
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
    for key in LIVE_STATE_PATH_KEYS:
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

    bundle_root = configured_path(
        repo_root,
        paths.get('bundle'),
        f'{relative(repo_root, config_path)}: paths.bundle',
        errors,
    )
    if bundle_root is not None:
        if not bundle_root.is_dir():
            errors.append(
                f'{relative(repo_root, config_path)}: paths.bundle does not exist: '
                f'{relative(repo_root, bundle_root)}'
            )
        validate_path_layout(repo_root, config_path, paths, bundle_root, errors)

    instructions_path = configured_path(
        repo_root,
        paths.get('instructions'),
        f'{relative(repo_root, config_path)}: paths.instructions',
        errors,
    )
    if instructions_path is not None and bundle_root is not None:
        version_file = bundle_root / 'VERSION'
        installed_version = (
            version_file.read_text(encoding='utf-8').strip()
            if version_file.is_file()
            else None
        )
        validate_instructions(
            repo_root,
            instructions_path,
            bundle_root,
            instance_root,
            installed_version,
            errors,
        )

    if not set(LIVE_STATE_PATH_KEYS).issubset(resolved):
        return

    active_root = resolved['active']
    archive_root = resolved['archive']
    ids: list[str] = []
    active_files = sorted(active_root.rglob('task.yaml')) if active_root.exists() else []
    archive_files = sorted(archive_root.rglob('task.yaml')) if archive_root.exists() else []
    for task_file, archived in [
        *((path, False) for path in active_files),
        *((path, True) for path in archive_files),
    ]:
        root = archive_root if archived else active_root
        if not is_within(task_file, root):
            errors.append(
                f'{relative(repo_root, task_file)} resolves outside configured '
                f'{"archive" if archived else "active"} root'
            )
            continue
        task_id = validate_task(
            repo_root,
            task_file,
            archived,
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


def scan_conflicts(repo_root: Path, roots: Iterable[Path], errors: list[str]) -> None:
    """
    Scan the selected task-system roots for files containing unresolved merge-conflict markers.
    
    Parameters:
        repo_root (Path): Repository root used to report file locations.
        roots (Iterable[Path]): Task-system directories to scan.
        errors (list[str]): Collection to which conflict findings are appended.
    """
    excluded = {'.git', '.venv', '__pycache__'}
    seen: set[Path] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob('*')):
            resolved = path.resolve(strict=False)
            if not path.is_file() or resolved in seen:
                continue
            if any(part in excluded for part in path.parts):
                continue
            seen.add(resolved)
            try:
                text = path.read_text(encoding='utf-8')
            except (UnicodeDecodeError, OSError):
                continue
            if CONFLICT_START_RE.search(text) or CONFLICT_END_RE.search(text):
                errors.append(
                    f'{relative(repo_root, path)} contains an unresolved merge-conflict marker'
                )


def select_modes(
    template_root: Path,
    instance_root: Path,
    template_only: bool,
    instance_only: bool,
) -> tuple[bool, bool]:
    """
    Selects which task-system roots to validate based on the requested mode.
    
    Parameters:
    	template_root (Path): Path to the task-system bundle.
    	instance_root (Path): Path to the live task instance.
    	template_only (bool): Whether to validate only the bundle.
    	instance_only (bool): Whether to validate only the live instance.
    
    Returns:
    	tuple[bool, bool]: A pair indicating whether to validate the bundle and live instance, respectively.
    
    Raises:
    	ValidationFailure: If both roots resolve to the same directory while validating both.
    """
    if template_only:
        return True, False
    if instance_only:
        return False, True
    if template_root.resolve(strict=False) == instance_root.resolve(strict=False):
        raise ValidationFailure(
            f'{template_root}: the bundle and the live instance must be separate '
            'directories; run scripts/init.py to create a live instance outside '
            'the bundle'
        )
    return True, True


def main() -> int:
    """
    Run the task-system validator for the selected bundle and live instance modes.
    
    Returns:
    	int: `1` if validation errors occur, `0` otherwise.
    """
    parser = argparse.ArgumentParser(
        description='Validate a task-system bundle and/or live task instance.'
    )
    parser.add_argument('--repo-root', default='.', help='Repository root.')
    parser.add_argument(
        '--template-root',
        '--bundle-root',
        dest='template_root',
        default=DEFAULT_BUNDLE_ROOT,
        help='Bundle root (the distributable product directory).',
    )
    parser.add_argument(
        '--instance-root',
        default=DEFAULT_INSTANCE_ROOT,
        help='Live instance root (config, index, active and archive records).',
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        '--template-only',
        action='store_true',
        help='Validate only the pristine distributable bundle.',
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
        scanned: list[Path] = []
        if validate_template_mode:
            validate_template(repo_root, template_root, config_schema, errors)
            scanned.append(template_root)
        if validate_instance_mode:
            validate_instance(
                repo_root,
                instance_root,
                config_schema,
                task_schema,
                errors,
            )
            scanned.append(instance_root)
        scan_conflicts(repo_root, scanned, errors)
    except (OSError, ValueError, ValidationFailure) as exc:
        errors.append(str(exc))

    if errors:
        print('Task-system validation failed:', file=sys.stderr)
        for error in errors:
            print(f'- {error}', file=sys.stderr)
        return 1

    if validate_template_mode:
        print(f'Bundle valid: {relative(repo_root, template_root)}')
    if validate_instance_mode:
        print(f'Live instance valid: {relative(repo_root, instance_root)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Initialize a live task-system instance next to the distributable bundle.

The bundle (``.tasks/`` by default) stays a replaceable product directory. This
script creates the live instance (``.project-tasks/`` by default) that holds the
repository's configuration, index, and task records.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

from common import replace_path_in_text
from generate_index import (
    DEFAULT_BUNDLE_ROOT,
    DEFAULT_INSTANCE_ROOT,
    build_index,
    render,
    repo_path,
)


TEMPLATE_CONFIG = 'templates/instance/config.yaml'
TEMPLATE_ROOT_AGENTS = 'templates/AGENTS.md'
TASK_SYSTEM_HEADING = '## Task system'
TEMPLATE_WORKFLOW = 'templates/github/workflows/validate-task-system.yml'
WORKFLOW_DESTINATION = '.github/workflows/validate-task-system.yml'
PRUNED_MARKER = '.pruned'

# Removed by --prune-install-files. Everything here is only needed while
# installing or while developing the bundle itself.
INSTALL_ONLY_PATHS = (
    'README.md',
    'tests',
    'scripts/init.py',
    'templates/AGENTS.md',
    'templates/github',
    'templates/instance',
)


class InitFailure(Exception):
    """Raised for an input error that should be reported without a traceback."""


def git(repo_root: Path, *args: str) -> str | None:
    """
    Run a Git command in a repository and return its trimmed output.
    
    Parameters:
        repo_root (Path): Repository directory in which to run the command.
        *args (str): Arguments passed to Git.
    
    Returns:
        str | None: The command's trimmed standard output, or `None` if Git cannot run, fails, or produces no output.
    """
    try:
        result = subprocess.run(
            ['git', *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def detect_repository_name(repo_root: Path) -> str:
    """Determine the repository name from its origin URL or directory name.
    
    Parameters:
    	repo_root (Path): The repository root directory.
    
    Returns:
    	str: The repository name, without a trailing `.git` suffix.
    """
    url = git(repo_root, 'remote', 'get-url', 'origin')
    if url:
        name = url.rstrip('/').rsplit('/', 1)[-1]
        if name.endswith('.git'):
            name = name[: -len('.git')]
        if name:
            return name
    return repo_root.name


def detect_default_branch(repo_root: Path) -> str:
    """Determine the repository's default branch.
    
    Returns:
    	str: The branch referenced by `origin/HEAD`, the current branch, or `main` when neither is available.
    """
    head = git(repo_root, 'symbolic-ref', '--short', 'refs/remotes/origin/HEAD')
    if head:
        return head.rsplit('/', 1)[-1]
    return git(repo_root, 'branch', '--show-current') or 'main'


def detect_provider(repo_root: Path) -> str:
    """Determine the repository hosting provider from its origin URL.
    
    Parameters:
        repo_root (Path): Path to the repository.
    
    Returns:
        str: ``"github"`` when the origin URL contains ``github.com``; ``"other"`` otherwise.
    """
    url = git(repo_root, 'remote', 'get-url', 'origin') or ''
    return 'github' if 'github.com' in url else 'other'


def detect_interpreter() -> str:
    """Select the platform-appropriate Python interpreter command.
    
    Returns:
    	str: `python` on Windows or `python3` on other platforms.
    """
    return 'python' if sys.platform == 'win32' else 'python3'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    """
    Replace exactly one occurrence of a required string.
    
    Parameters:
        text (str): Text containing the expected occurrence.
        old (str): String to replace.
        new (str): Replacement string.
        label (str): Description used in the error message.
    
    Returns:
        str: Text with the single occurrence replaced.
    
    Raises:
        InitFailure: If the target string occurs zero or multiple times.
    """
    count = text.count(old)
    if count != 1:
        raise InitFailure(
            f'{label}: expected exactly one occurrence of {old!r}, found {count}'
        )
    return text.replace(old, new)


def render_config(
    template_text: str,
    *,
    bundle: str,
    instance: str,
    repository_name: str,
    default_branch: str,
    timezone: str,
    remote: str,
    provider: str,
    github_enabled: bool,
    interpreter: str,
    instructions: str = 'AGENTS.md',
) -> str:
    """
    Render a live task-system configuration from a template.
    
    Parameters:
        template_text (str): Template configuration text.
        bundle (str): Path to the distributable bundle.
        instance (str): Path to the live task-system instance.
        repository_name (str): Repository name to include in the configuration.
        default_branch (str): Repository's default branch.
        timezone (str): Configuration timezone.
        remote (str): Git remote name.
        provider (str): Repository hosting provider.
        github_enabled (bool): Whether GitHub integration is enabled.
        interpreter (str): Interpreter command used by the task system.
        instructions (str): Agent-instructions file name.
    
    Returns:
        str: Rendered live configuration text.
    """
    text = template_text
    text = replace_once(text, 'mode: "template"', 'mode: "live"', 'config')
    text = replace_once(
        text, 'instructions: "AGENTS.md"', f'instructions: "{instructions}"', 'config'
    )
    text = replace_once(text, 'provider: "github"', f'provider: "{provider}"', 'config')
    text = replace_once(text, 'remote: "origin"', f'remote: "{remote}"', 'config')
    text = replace_once(
        text,
        '  enabled: true',
        f'  enabled: {"true" if github_enabled else "false"}',
        'config',
    )
    text = text.replace('__REQUIRED_TIMEZONE__', timezone)
    text = text.replace('__REQUIRED_REPOSITORY_NAME__', repository_name)
    text = text.replace('__REQUIRED_DEFAULT_BRANCH__', default_branch)

    # Longest first: ".project-tasks" must not be partially rewritten.
    if instance != DEFAULT_INSTANCE_ROOT:
        text = text.replace(DEFAULT_INSTANCE_ROOT, instance)
    if bundle != DEFAULT_BUNDLE_ROOT:
        text = text.replace(f'{DEFAULT_BUNDLE_ROOT}/', f'{bundle}/')
        text = replace_once(
            text, f'bundle: "{DEFAULT_BUNDLE_ROOT}"', f'bundle: "{bundle}"', 'config'
        )
    if interpreter != 'python3':
        text = text.replace('python3 ', f'{interpreter} ')
    return text


def substitute_paths(text: str, bundle: str, instance: str, interpreter: str) -> str:
    """Replace default task-system paths and interpreter references with configured values.
    
    Parameters:
        text (str): Template text to update.
        bundle (str): Configured bundle path.
        instance (str): Configured instance path.
        interpreter (str): Configured Python interpreter command.
    
    Returns:
        str: Text containing the configured paths and interpreter references.
    """
    if instance != DEFAULT_INSTANCE_ROOT:
        text = replace_path_in_text(text, DEFAULT_INSTANCE_ROOT, instance)
    if bundle != DEFAULT_BUNDLE_ROOT:
        text = replace_path_in_text(text, DEFAULT_BUNDLE_ROOT, bundle)
    if interpreter != 'python3':
        text = text.replace('python3 ', f'{interpreter} ')
    return text


def task_system_section(template_text: str) -> str:
    """Extract the `## Task system` section from the root AGENTS.md template."""
    start = template_text.find(TASK_SYSTEM_HEADING)
    if start < 0:
        raise InitFailure(f'{TEMPLATE_ROOT_AGENTS} has no {TASK_SYSTEM_HEADING} section')
    following = template_text.find('\n## ', start + len(TASK_SYSTEM_HEADING))
    end = len(template_text) if following < 0 else following + 1
    return template_text[start:end].rstrip() + '\n'


def install_instructions(
    path: Path,
    template_text: str,
    bundle: str,
    instance: str,
    interpreter: str,
    force: bool,
    dry_run: bool,
    actions: list[str],
) -> None:
    """
    Create or update the repository's instruction file while preserving existing content.
    
    Parameters:
        path (Path): Path to the instruction file.
        template_text (str): Instruction template to render and write.
        bundle (str): Bundle path substituted into the template.
        instance (str): Live instance path substituted into the template.
        interpreter (str): Interpreter command substituted into the template.
        force (bool): Whether to replace an existing nonempty file.
        dry_run (bool): Whether to record actions without writing files.
        actions (list[str]): List to which planned or performed actions are appended.
    """
    rendered = substitute_paths(template_text, bundle, instance, interpreter)
    existing = path.read_text(encoding='utf-8') if path.is_file() else None
    # An empty file carries no instructions to preserve, so treat it as absent
    # rather than appending a lone section onto nothing.
    if existing is None or not existing.strip():
        write_file(path, rendered, dry_run, actions)
        return

    if force:
        actions.append(f'overwrite {path} (--force)')
        if not dry_run:
            path.write_text(rendered, encoding='utf-8', newline='\n')
        return

    if f'{bundle}/AGENTS.md' in existing:
        actions.append(f'skip {path} (already references {bundle}/AGENTS.md)')
        return

    section = task_system_section(rendered)
    actions.append(f'append {TASK_SYSTEM_HEADING} section to {path}')
    if dry_run:
        return
    separator = '' if existing.endswith('\n\n') else '\n' if existing.endswith('\n') else '\n\n'
    path.write_text(existing + separator + section, encoding='utf-8', newline='\n')


def write_file(path: Path, text: str, dry_run: bool, actions: list[str]) -> None:
    """
    Record a file write action and optionally write UTF-8 text to the specified path.
    
    Parameters:
    	path (Path): Destination file path.
    	text (str): Content to write.
    	dry_run (bool): Whether to record the action without modifying the filesystem.
    	actions (list[str]): Collection to which the planned write action is appended.
    """
    actions.append(f'write {path}')
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')


def main() -> int:
    """
    Initialize a live task-system instance from the distributable bundle.
    
    Returns:
    	int: 0 on success, or 1 when initialization fails.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', default='.', help='Repository root.')
    parser.add_argument(
        '--bundle-root',
        default=DEFAULT_BUNDLE_ROOT,
        help='Where the copied bundle lives.',
    )
    parser.add_argument(
        '--instance-root',
        default=DEFAULT_INSTANCE_ROOT,
        help='Where live task state will live. Must be outside the bundle.',
    )
    parser.add_argument('--repository-name', help='Defaults to the origin remote name.')
    parser.add_argument('--default-branch', help='Defaults to the detected default branch.')
    parser.add_argument('--timezone', default='UTC', help='IANA timezone. Default UTC.')
    parser.add_argument('--remote', default='origin', help='Git remote name.')
    parser.add_argument(
        '--provider',
        choices=('github', 'other', 'auto'),
        default='auto',
        help='Forge provider. "other" disables pull-request check gating.',
    )
    parser.add_argument(
        '--no-github-checks',
        action='store_true',
        help='Run the lifecycle without requiring green pull-request checks.',
    )
    parser.add_argument(
        '--install-root-agents',
        action='store_true',
        help=(
            'Install the agent instruction file. An existing file is appended to, '
            'never replaced, unless --force is given.'
        ),
    )
    parser.add_argument(
        '--instruction-file',
        default='AGENTS.md',
        help=(
            'Repository-root instruction file your agent actually reads '
            '(AGENTS.md, CLAUDE.md, .github/copilot-instructions.md, ...).'
        ),
    )
    parser.add_argument(
        '--install-workflow',
        action='store_true',
        help=f'Write {WORKFLOW_DESTINATION}.',
    )
    parser.add_argument(
        '--prune-install-files',
        action='store_true',
        help='Delete install-only files from the bundle after initialization.',
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite an existing live configuration and instruction file.',
    )
    parser.add_argument('--dry-run', action='store_true', help='Report actions only.')
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve(strict=False)
    bundle_root = repo_path(repo_root, args.bundle_root).resolve(strict=False)
    instance_root = repo_path(repo_root, args.instance_root).resolve(strict=False)
    actions: list[str] = []

    try:
        if not bundle_root.is_dir():
            raise InitFailure(f'bundle not found: {bundle_root}')
        if instance_root == bundle_root:
            raise InitFailure('the live instance must not be the bundle directory')
        try:
            instance_root.relative_to(bundle_root)
        except ValueError:
            pass
        else:
            raise InitFailure(
                f'the live instance must stay outside the bundle: {instance_root}'
            )

        template_config = bundle_root / TEMPLATE_CONFIG
        if not template_config.is_file():
            raise InitFailure(f'missing {template_config}')

        config_path = instance_root / 'config.yaml'
        if config_path.exists() and not args.force:
            raise InitFailure(
                f'{config_path} already exists; pass --force to overwrite it'
            )

        provider = (
            detect_provider(repo_root) if args.provider == 'auto' else args.provider
        )
        github_enabled = provider == 'github' and not args.no_github_checks
        bundle_value = args.bundle_root.replace('\\', '/').rstrip('/')
        instance_value = args.instance_root.replace('\\', '/').rstrip('/')
        interpreter = detect_interpreter()

        config_text = render_config(
            template_config.read_text(encoding='utf-8'),
            bundle=bundle_value,
            instance=instance_value,
            repository_name=args.repository_name or detect_repository_name(repo_root),
            default_branch=args.default_branch or detect_default_branch(repo_root),
            timezone=args.timezone,
            remote=args.remote,
            provider=provider,
            github_enabled=github_enabled,
            interpreter=interpreter,
            instructions=args.instruction_file.replace('\\', '/'),
        )
        if '__REQUIRED_' in config_text:
            raise InitFailure('config still contains placeholders after substitution')
        write_file(config_path, config_text, args.dry_run, actions)

        for area in ('active', 'archive'):
            keep = instance_root / area / '.gitkeep'
            write_file(keep, '', args.dry_run, actions)

        if args.install_root_agents:
            root_agents = bundle_root / TEMPLATE_ROOT_AGENTS
            if not root_agents.is_file():
                raise InitFailure(f'missing {root_agents}')
            install_instructions(
                repo_root / args.instruction_file,
                root_agents.read_text(encoding='utf-8'),
                bundle_value,
                instance_value,
                interpreter,
                args.force,
                args.dry_run,
                actions,
            )

        if args.install_workflow:
            workflow_template = bundle_root / TEMPLATE_WORKFLOW
            if not workflow_template.is_file():
                raise InitFailure(f'missing {workflow_template}')
            workflow_text = substitute_paths(
                workflow_template.read_text(encoding='utf-8'),
                bundle_value,
                instance_value,
                interpreter,
            )
            write_file(
                repo_root / WORKFLOW_DESTINATION, workflow_text, args.dry_run, actions
            )

        if not args.dry_run:
            index_path, data = build_index(repo_root, instance_root)
            index_path.parent.mkdir(parents=True, exist_ok=True)
            index_path.write_text(render(data), encoding='utf-8', newline='\n')
            actions.append(f'write {index_path}')
        else:
            actions.append(f'write {instance_root / "index.yaml"}')

        if args.prune_install_files:
            for name in INSTALL_ONLY_PATHS:
                target = bundle_root / name
                if not target.exists():
                    continue
                actions.append(f'remove {target}')
                if args.dry_run:
                    continue
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            write_file(
                bundle_root / PRUNED_MARKER,
                'Install-only files were removed by scripts/init.py.\n',
                args.dry_run,
                actions,
            )
    except (InitFailure, OSError, ValueError) as exc:
        print(f'Initialization failed: {exc}', file=sys.stderr)
        return 1

    prefix = 'Would ' if args.dry_run else ''
    for action in actions:
        print(f'{prefix}{action}')
    if not args.dry_run:
        print()
        print('Next steps:')
        if args.install_root_agents:
            print(
                f'- Replace any remaining __REQUIRED_* values in {args.instruction_file}.'
            )
        else:
            print(
                f'- Copy {bundle_root / TEMPLATE_ROOT_AGENTS} to {args.instruction_file}, '
                'or merge its task-system section into your existing agent instructions.'
            )
        print(f'- Fill in commands.lint/typecheck/unit_test in {config_path}.')
        print(f'- Create a task: {interpreter} {bundle_value}/scripts/new_task.py --help')
        print(
            f'- Validate: {interpreter} {bundle_value}/scripts/validate.py '
            f'--instance-only --instance-root {instance_value}'
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

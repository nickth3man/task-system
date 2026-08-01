#!/usr/bin/env python3
"""Bring an existing installation up to the bundle's version.

Replace the bundle directory with a newer one, then run this. It moves live state
out of the bundle if it was ever kept there, adds configuration keys the new
version requires, repairs the mechanical references in the agent instruction
file, and regenerates the index.

It never edits task records, and it never changes a value you already set.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys
from typing import Any

import yaml

from generate_index import (
    DEFAULT_BUNDLE_ROOT,
    DEFAULT_INSTANCE_ROOT,
    build_index,
    load_yaml,
    render,
    repo_path,
)

TEMPLATE_CONFIG = 'templates/instance/config.yaml'
LIVE_STATE_KEYS = ('active', 'archive', 'index')
LEGACY_BUNDLE_ENTRIES = ('config.yaml', 'index.yaml', 'active', 'archive')
INSTRUCTION_CANDIDATES = (
    'AGENTS.md',
    'CLAUDE.md',
    '.github/copilot-instructions.md',
)
# Where the safe upgrade value differs from the template default. Opting an
# existing installation into the lite profile would retroactively relax the
# artifact requirements of tasks already in flight.
UPGRADE_DEFAULTS: dict[tuple[str, ...], Any] = {
    ('lifecycle', 'lite_profile_task_types'): [],
}


class UpgradeFailure(Exception):
    """Raised for an input error that should be reported without a traceback."""


def version_tuple(value: str) -> tuple[int, ...]:
    """
    Parse a dotted version string into integer components.
    
    Parameters:
        value (str): The version string to parse.
    
    Returns:
        tuple[int, ...]: The version components as integers.
    
    Raises:
        UpgradeFailure: If the version contains a component that is not an integer.
    """
    try:
        return tuple(int(part) for part in value.strip().split('.'))
    except ValueError as exc:
        raise UpgradeFailure(f'malformed version: {value!r}') from exc


def posix(repo_root: Path, path: Path) -> str:
    """
    Convert a path to POSIX notation, relative to the repository when possible.
    
    Parameters:
    	repo_root (Path): Repository root used as the base for relative paths.
    	path (Path): Path to convert.
    
    Returns:
    	str: The path in POSIX notation, relative to `repo_root` when it is within the repository; otherwise, its absolute POSIX path.
    """
    resolved = path.resolve(strict=False)
    try:
        return resolved.relative_to(repo_root.resolve(strict=False)).as_posix()
    except ValueError:
        return resolved.as_posix()


def locate_config(bundle_root: Path, instance_root: Path) -> tuple[Path, bool]:
    """Return the live config path and whether it still lives inside the bundle."""
    current = instance_root / 'config.yaml'
    if current.is_file():
        return current, False
    legacy = bundle_root / 'config.yaml'
    if legacy.is_file() and load_yaml(legacy).get('mode') == 'live':
        return legacy, True
    raise UpgradeFailure(
        f'no live configuration at {current} or {legacy}; run scripts/init.py to '
        'install the task system first'
    )


def missing_keys(
    template: Any,
    live: Any,
    trail: tuple[str, ...] = (),
) -> list[tuple[tuple[str, ...], Any]]:
    """
    Find configuration keys that are missing from the live configuration.
    
    Missing keys are returned with their nested paths and template values, using
    upgrade-specific defaults when configured.
    
    Parameters:
        template (Any): Template configuration to compare.
        live (Any): Existing live configuration.
        trail (tuple[str, ...]): Prefix for nested key paths.
    
    Returns:
        list[tuple[tuple[str, ...], Any]]: Missing key paths paired with values to assign.
    """
    if not isinstance(template, dict) or not isinstance(live, dict):
        return []
    found: list[tuple[tuple[str, ...], Any]] = []
    for key, value in template.items():
        path = (*trail, str(key))
        if key not in live:
            found.append((path, UPGRADE_DEFAULTS.get(path, value)))
        else:
            found.extend(missing_keys(value, live[key], path))
    return found


def assign(config: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    """
    Assign a value at a nested path in a configuration mapping.
    
    Parameters:
    	config (dict[str, Any]): The configuration mapping to update.
    	path (tuple[str, ...]): The sequence of keys identifying the target entry.
    	value (Any): The value to assign.
    """
    target = config
    for key in path[:-1]:
        node = target.get(key)
        if not isinstance(node, dict):
            node = {}
            target[key] = node
        target = node
    target[path[-1]] = value


def rewrite_paths(
    config: dict[str, Any],
    repo_root: Path,
    bundle_root: Path,
    instance_root: Path,
) -> list[str]:
    """
    Redirect live-state paths from the bundle directory to the instance directory.
    
    Parameters:
    	config (dict[str, Any]): Configuration containing live-state paths.
    	repo_root (Path): Repository root used to normalize paths.
    	bundle_root (Path): Bundle directory containing legacy live state.
    	instance_root (Path): Directory receiving the live state.
    
    Returns:
    	list[str]: Descriptions of each path that was updated.
    """
    paths = config.get('paths')
    if not isinstance(paths, dict):
        return []
    bundle = posix(repo_root, bundle_root)
    instance = posix(repo_root, instance_root)
    changed: list[str] = []
    for key in LIVE_STATE_KEYS:
        value = paths.get(key)
        if not isinstance(value, str):
            continue
        normalized = value.replace('\\', '/')
        if normalized == bundle or normalized.startswith(f'{bundle}/'):
            updated = instance + normalized[len(bundle):]
            paths[key] = updated
            changed.append(f'paths.{key}: {value} -> {updated}')
    return changed


def rewrite_commands(
    config: dict[str, Any],
    repo_root: Path,
    bundle_root: Path,
    instance_root: Path,
) -> list[str]:
    """
    Update command definitions that reference bundle paths to use the instance root.
    
    Parameters:
    	config (dict[str, Any]): Configuration containing command definitions.
    	repo_root (Path): Repository root used to normalize paths.
    	bundle_root (Path): Bundle directory containing legacy paths.
    	instance_root (Path): Instance directory that should replace bundle references.
    
    Returns:
    	list[str]: Configuration paths of the command definitions that were changed.
    """
    commands = config.get('commands')
    if not isinstance(commands, dict):
        return []
    bundle = posix(repo_root, bundle_root)
    instance = posix(repo_root, instance_root)
    changed: list[str] = []
    for key, value in list(commands.items()):
        if not isinstance(value, str):
            continue
        updated = value
        for old in (f'{bundle}/active', f'{bundle}/archive', f'{bundle}/index.yaml'):
            updated = updated.replace(old, instance + old[len(bundle):])
        updated = updated.replace(f'--instance-root {bundle}', f'--instance-root {instance}')
        if updated != value:
            commands[key] = updated
            changed.append(f'commands.{key}')
    return changed


def detect_instruction_file(repo_root: Path) -> str:
    """
    Selects the instruction file used by the repository.
    
    Parameters:
    	repo_root (Path): Root directory of the repository.
    
    Returns:
    	str: The first existing candidate instruction filename, or the default candidate when none exists.
    """
    for candidate in INSTRUCTION_CANDIDATES:
        if (repo_root / candidate).is_file():
            return candidate
    return INSTRUCTION_CANDIDATES[0]


def repair_instructions(
    text: str,
    repo_root: Path,
    bundle_root: Path,
    instance_root: Path,
    installed_version: str,
) -> tuple[str, list[str]]:
    """
    Repair stale bundle paths and task-system version references in instruction text.
    
    Parameters:
        text (str): Instruction text to update.
        repo_root (Path): Repository root used to represent paths consistently.
        bundle_root (Path): Existing bundle directory referenced by stale entries.
        instance_root (Path): Instance directory that should replace bundle references.
        installed_version (str): Task-system version to write into recognized version statements.
    
    Returns:
        tuple[str, list[str]]: The repaired instruction text and descriptions of the changes made.
    """
    import re

    bundle = posix(repo_root, bundle_root)
    instance = posix(repo_root, instance_root)
    changed: list[str] = []
    updated = text
    for name in LEGACY_BUNDLE_ENTRIES:
        stale = f'{bundle}/{name}'
        if stale in updated:
            updated = updated.replace(stale, f'{instance}/{name}')
            changed.append(f'{stale} -> {instance}/{name}')

    pattern = re.compile(r'(task[ -]system version[^0-9]{0,12})(\d+\.\d+\.\d+)', re.IGNORECASE)

    def replace(match: re.Match[str]) -> str:
        """
        Replace a recognized task-system version with the installed version.
        
        Parameters:
        	match (re.Match[str]): A match containing the version statement and its stated version.
        
        Returns:
        	str: The original text when the version is current; otherwise, the version statement with the installed version.
        """
        if match.group(2) == installed_version:
            return match.group(0)
        changed.append(f'stated version {match.group(2)} -> {installed_version}')
        return f'{match.group(1)}{installed_version}'

    updated = pattern.sub(replace, updated)
    return updated, changed


def main() -> int:
    """
    Upgrade the task-system installation to the bundle version.
    
    The upgrade migrates legacy live state, updates configuration and instruction
    references, regenerates the index, and preserves the previous configuration as
    a backup. With ``--dry-run``, reports planned changes without modifying files.
    
    Returns:
        int: ``0`` when the upgrade succeeds or is already current, otherwise ``1``.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', default='.', help='Repository root.')
    parser.add_argument('--bundle-root', default=DEFAULT_BUNDLE_ROOT, help='Bundle root.')
    parser.add_argument(
        '--instance-root',
        default=DEFAULT_INSTANCE_ROOT,
        help='Where live state should end up.',
    )
    parser.add_argument('--dry-run', action='store_true', help='Report the plan only.')
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve(strict=False)
    bundle_root = repo_path(repo_root, args.bundle_root).resolve(strict=False)
    instance_root = repo_path(repo_root, args.instance_root).resolve(strict=False)
    actions: list[str] = []

    try:
        version_file = bundle_root / 'VERSION'
        if not version_file.is_file():
            raise UpgradeFailure(f'no bundle at {bundle_root}')
        installed = version_file.read_text(encoding='utf-8').strip()

        template_path = bundle_root / TEMPLATE_CONFIG
        if not template_path.is_file():
            raise UpgradeFailure(f'missing {template_path}')
        template = load_yaml(template_path)

        config_path, legacy = locate_config(bundle_root, instance_root)
        config = load_yaml(config_path)
        current = str(config.get('task_system_version', '0.0.0'))
        if version_tuple(current) > version_tuple(installed):
            raise UpgradeFailure(
                f'installed records are version {current}, newer than the bundle '
                f'({installed}); this tool does not downgrade'
            )
        if version_tuple(current) == version_tuple(installed) and not legacy:
            print(f'Already at version {installed}. Nothing to upgrade.')
            return 0

        moves: list[tuple[Path, Path]] = []
        if legacy:
            for name in LEGACY_BUNDLE_ENTRIES:
                source = bundle_root / name
                if not source.exists():
                    continue
                destination = instance_root / name
                if destination.exists():
                    raise UpgradeFailure(f'cannot move {source}: {destination} exists')
                moves.append((source, destination))
                actions.append(f'move {posix(repo_root, source)} -> {posix(repo_root, destination)}')
            config_path = instance_root / 'config.yaml'

        added = missing_keys(template, config)
        for path, value in added:
            assign(config, path, value)
            actions.append(f'add {".".join(path)} = {value!r}')

        if 'bundle' not in config.get('paths', {}):
            assign(config, ('paths', 'bundle'), posix(repo_root, bundle_root))
        if 'instructions' not in config.get('paths', {}):
            assign(config, ('paths', 'instructions'), detect_instruction_file(repo_root))

        for note in rewrite_paths(config, repo_root, bundle_root, instance_root):
            actions.append(f'rewrite {note}')
        for note in rewrite_commands(config, repo_root, bundle_root, instance_root):
            actions.append(f'rewrite {note}')

        config['schema_version'] = template.get('schema_version', installed)
        config['task_system_version'] = installed
        actions.append(f'set task_system_version = {installed}')

        instructions_value = config.get('paths', {}).get('instructions')
        instructions_path = repo_path(repo_root, str(instructions_value))
        instructions_text = None
        if instructions_path.is_file():
            original = instructions_path.read_text(encoding='utf-8')
            instructions_text, repairs = repair_instructions(
                original, repo_root, bundle_root, instance_root, installed
            )
            for note in repairs:
                actions.append(f'instructions: {note}')
            if instructions_text == original:
                instructions_text = None

        if args.dry_run:
            print(f'Upgrade {current} -> {installed} (dry run)')
            for action in actions:
                print(f'  would {action}')
            return 0

        for source, destination in moves:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))

        config_path.parent.mkdir(parents=True, exist_ok=True)
        if config_path.is_file():
            backup = config_path.with_suffix('.yaml.bak')
            shutil.copyfile(config_path, backup)
            actions.append(f'back up {posix(repo_root, backup)}')
        config_path.write_text(
            yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
            encoding='utf-8',
            newline='\n',
        )

        if instructions_text is not None:
            instructions_path.write_text(instructions_text, encoding='utf-8', newline='\n')

        index_path, data = build_index(repo_root, instance_root)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(render(data), encoding='utf-8', newline='\n')
        actions.append(f'regenerate {posix(repo_root, index_path)}')
    except (UpgradeFailure, OSError, ValueError, yaml.YAMLError) as exc:
        print(f'Upgrade failed: {exc}', file=sys.stderr)
        return 1

    print(f'Upgraded {current} -> {installed}')
    for action in actions:
        print(f'  {action}')
    print()
    print('Comments in config.yaml were not preserved; the previous file is kept as')
    print(f'{posix(repo_root, config_path)}.bak. Review the diff, then validate:')
    print(
        f'  python3 {posix(repo_root, bundle_root)}/scripts/validate.py '
        f'--instance-only --instance-root {posix(repo_root, instance_root)}'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

from __future__ import annotations

import re
import sys
from pathlib import Path


PLACEHOLDER = '__REQUIRED_'
PLACEHOLDER_RE = re.compile(r'__REQUIRED_\S*')
LITE_REQUIRED_FILES = (
    'task.yaml',
    'task.md',
    'findings.md',
    'plan.md',
    'verification.md',
    'completion.md',
)
LITE_REQUIRED_DIRECTORIES: tuple[str, ...] = ()


def detect_interpreter() -> str:
    """Return the conventional Python command for the current platform."""
    return 'python' if sys.platform == 'win32' else 'python3'


def normalize_path(value: str) -> str:
    """Normalize a repository-relative path token to POSIX separators."""
    return value.replace('\\', '/')


def path_is_rooted_at(value: str, root: str) -> bool:
    """Return whether a path equals or is below a root path token."""
    normalized = normalize_path(value)
    normalized_root = normalize_path(root).rstrip('/')
    return normalized == normalized_root or normalized.startswith(f'{normalized_root}/')


def replace_path_prefix(value: str, old_root: str, new_root: str) -> str:
    """Replace an old path root only when the value is rooted at it."""
    normalized = normalize_path(value)
    old = normalize_path(old_root).rstrip('/')
    new = normalize_path(new_root).rstrip('/')
    if not path_is_rooted_at(normalized, old):
        return value
    return new + normalized[len(old):]


def replace_path_in_text(text: str, old_path: str, new_path: str) -> str:
    """Replace a path token in text only at path and token boundaries."""
    old = normalize_path(old_path).rstrip('/')
    new = normalize_path(new_path).rstrip('/')
    escaped = re.escape(old).replace('/', r'[/\\]')
    pattern = re.compile(
        rf'(?<![A-Za-z0-9_.-]){escaped}'
        r'(?=$|[/\\]|[\s"\'`,;])'
    )
    return pattern.sub(new, text)

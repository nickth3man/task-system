#!/usr/bin/env python3
"""Generate the derived .tasks/index.yaml file deterministically."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".tasks" / "config.yaml"
HEADER = (
    "# GENERATED VIEW ONLY. Run: python scripts/generate_index.py\n"
    "# Task records are authoritative; this file is navigation only.\n"
)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a YAML mapping")
    return data


def collect_tasks(directory: Path, root: Path) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    if not directory.exists():
        return tasks

    for task_file in sorted(directory.rglob("task.yaml")):
        data = load_yaml(task_file)
        tasks.append(
            {
                "id": data.get("id"),
                "title": data.get("title"),
                "status": data.get("status"),
                "path": task_file.parent.relative_to(root).as_posix(),
            }
        )
    return sorted(tasks, key=lambda item: (str(item.get("id")), item["path"]))


def render_index(root: Path = ROOT) -> str:
    config = load_yaml(root / ".tasks" / "config.yaml")
    paths = config["paths"]
    payload = {
        "schema_version": config["schema_version"],
        "task_system_version": config["task_system_version"],
        "active": collect_tasks(root / paths["active"], root),
        "archived": collect_tasks(root / paths["archive"], root),
    }
    body = yaml.safe_dump(
        payload,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    return HEADER + body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if .tasks/index.yaml is not the generated form",
    )
    args = parser.parse_args()

    expected = render_index(ROOT)
    index_path = ROOT / ".tasks" / "index.yaml"

    if args.check:
        actual = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
        if actual != expected:
            print(
                ".tasks/index.yaml is stale; run python scripts/generate_index.py",
                file=sys.stderr,
            )
            return 1
        print("Task index is current.")
        return 0

    index_path.write_text(expected, encoding="utf-8")
    print(f"Wrote {index_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

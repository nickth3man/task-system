#!/usr/bin/env python3
"""Validate task-system structure, schemas, semantics, and generated files."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from generate_index import render_index

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / ".tasks"
CONFIG_PATH = TASKS / "config.yaml"
CONFIG_SCHEMA_PATH = TASKS / "schemas" / "config.schema.json"
TASK_SCHEMA_PATH = TASKS / "schemas" / "task.schema.json"
INDEX_PATH = TASKS / "index.yaml"

ACTIVE_REQUIRED = {
    "task.yaml",
    "task.md",
    "assessment.md",
    "research.md",
    "links.md",
    "findings.md",
    "plan.md",
    "implementation-log.md",
    "verification.md",
    "review.md",
    "completion.md",
}

CONFLICT_MARKERS = ("<" * 7, "=" * 7, ">" * 7)
SHA_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
DIGEST_RE = re.compile(r"^[0-9a-fA-F]{64}$")
NORMAL_ORDER = [
    "draft",
    "assessing",
    "researching",
    "awaiting_findings_approval",
    "planning",
    "awaiting_plan_approval",
    "approved",
    "creating_branch",
    "implementing",
    "testing",
    "committing",
    "reviewing",
    "pushing",
    "awaiting_pr_approval",
    "creating_pr",
    "waiting_for_ci",
    "awaiting_merge_approval",
    "merging",
    "completing",
    "completed",
    "archived",
]
EXCEPTIONAL = {"blocked", "failed", "cancelled", "superseded"}
ALLOWED_TRANSITIONS = {
    (NORMAL_ORDER[i], NORMAL_ORDER[i + 1]) for i in range(len(NORMAL_ORDER) - 1)
}
ALLOWED_TRANSITIONS |= {
    ("reviewing", "implementing"),
    ("waiting_for_ci", "implementing"),
}


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def schema_errors(instance: Any, schema: dict[str, Any], label: str) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{label}:{location}: {error.message}")
    return errors


def task_files(config: dict[str, Any]) -> list[tuple[str, Path]]:
    result: list[tuple[str, Path]] = []
    for kind in ("active", "archive"):
        base = ROOT / config["paths"][kind]
        if base.exists():
            result.extend((kind, path) for path in sorted(base.rglob("task.yaml")))
    return result


def approval_complete(approval: dict[str, Any], kind: str) -> bool:
    common = (
        approval.get("status") == "approved"
        and isinstance(approval.get("approved_by"), str)
        and bool(approval["approved_by"].strip())
        and approval.get("approved_at") is not None
        and approval.get("source") == "chat"
        and isinstance(approval.get("evidence"), str)
        and bool(approval["evidence"].strip())
        and isinstance(approval.get("task_revision"), int)
    )
    if not common:
        return False
    if kind in {"findings", "plan"}:
        return (
            isinstance(approval.get("revision"), int)
            and isinstance(approval.get("artifact_sha256"), str)
            and bool(DIGEST_RE.fullmatch(approval["artifact_sha256"]))
        )
    return isinstance(approval.get("head_sha"), str) and bool(
        SHA_RE.fullmatch(approval["head_sha"])
    )


def validate_transitions(task: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    history = task.get("state_history", [])
    previous_to: str | None = None
    for index, entry in enumerate(history):
        source = entry.get("from")
        target = entry.get("to")
        if index == 0 and source not in {None, "draft"}:
            errors.append(f"{label}:state_history[{index}] must start from null or draft")
        if previous_to is not None and source != previous_to:
            errors.append(
                f"{label}:state_history[{index}] from={source!r} does not match prior to={previous_to!r}"
            )
        if source is not None and target not in EXCEPTIONAL and source not in EXCEPTIONAL:
            if (source, target) not in ALLOWED_TRANSITIONS:
                errors.append(
                    f"{label}:state_history[{index}] disallowed transition {source} -> {target}"
                )
        previous_to = target

    if history and history[-1].get("to") != task.get("status"):
        errors.append(f"{label}: final state_history target must equal status")
    if task.get("status") != "draft" and not history:
        errors.append(f"{label}: non-draft task must have state_history")
    return errors


def validate_approval_bindings(task: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    approvals = task["approvals"]
    revisions = task["revisions"]

    for kind, approval in approvals.items():
        if approval.get("status") == "approved" and not approval_complete(approval, kind):
            errors.append(f"{label}: approved {kind} approval is incomplete")
    findings = approvals["findings"]
    if findings.get("status") == "approved":
        findings_path = Path(label).parent / "findings.md"
        actual_findings = ROOT / findings_path
        if actual_findings.exists():
            digest = hashlib.sha256(actual_findings.read_bytes()).hexdigest()
            if findings.get("artifact_sha256") != digest:
                errors.append(f"{label}: findings approval digest does not match findings.md")
        if findings.get("revision") != revisions["findings"]:
            errors.append(f"{label}: findings approval revision is stale")
        if findings.get("findings_revision") != revisions["findings"]:
            errors.append(f"{label}: findings approval must bind findings_revision")
        if findings.get("task_revision") != revisions["task"]:
            errors.append(f"{label}: findings approval must bind current task_revision")

    plan = approvals["plan"]
    if plan.get("status") == "approved":
        plan_path = Path(label).parent / "plan.md"
        actual_plan = ROOT / plan_path
        if actual_plan.exists():
            digest = hashlib.sha256(actual_plan.read_bytes()).hexdigest()
            if plan.get("artifact_sha256") != digest:
                errors.append(f"{label}: plan approval digest does not match plan.md")
        if plan.get("revision") != revisions["plan"]:
            errors.append(f"{label}: plan approval revision is stale")
        if plan.get("plan_revision") != revisions["plan"]:
            errors.append(f"{label}: plan approval must bind plan_revision")
        if plan.get("findings_revision") != revisions["findings"]:
            errors.append(f"{label}: plan approval must bind current findings_revision")
        if plan.get("task_revision") != revisions["task"]:
            errors.append(f"{label}: plan approval must bind current task_revision")

    pr_approval = approvals["pull_request"]
    if pr_approval.get("status") == "approved":
        expected = task["pull_request"].get("head_sha") or task["git"].get("head_sha")
        if pr_approval.get("head_sha") != expected:
            errors.append(f"{label}: PR approval does not bind the current pushed/PR head")
        if pr_approval.get("plan_revision") != revisions["plan"]:
            errors.append(f"{label}: PR approval must bind current plan_revision")

    merge = approvals["merge"]
    if merge.get("status") == "approved":
        if merge.get("head_sha") != task["pull_request"].get("head_sha"):
            errors.append(f"{label}: merge approval does not bind current PR head")
        if task["pull_request"]["checks"].get("status") != "passed":
            errors.append(f"{label}: merge approval requires passed PR checks")

    return errors


def validate_task_semantics(kind: str, path: Path, task: dict[str, Any]) -> list[str]:
    label = rel(path)
    errors: list[str] = []

    def contains_required(value: Any) -> bool:
        if isinstance(value, str):
            return "__REQUIRED_" in value
        if isinstance(value, list):
            return any(contains_required(item) for item in value)
        if isinstance(value, dict):
            return any(contains_required(item) for item in value.values())
        return False

    if contains_required(task):
        errors.append(f"{label}: live task contains unreplaced __REQUIRED_*__ values")

    expected_dir = f"{task['id']}-{task['slug']}"
    if path.parent.name != expected_dir:
        errors.append(f"{label}: directory must be named {expected_dir}")

    missing = ACTIVE_REQUIRED - {item.name for item in path.parent.iterdir() if item.is_file()}
    if kind == "active" and missing:
        errors.append(f"{label}: missing active artifacts: {', '.join(sorted(missing))}")

    criterion_ids = [item["id"] for item in task["acceptance_criteria"]]
    if len(criterion_ids) != len(set(criterion_ids)):
        errors.append(f"{label}: duplicate acceptance-criterion IDs")

    plan_ids = [item["id"] for item in task["plan_steps"]]
    if len(plan_ids) != len(set(plan_ids)):
        errors.append(f"{label}: duplicate plan-step IDs")
    known_criteria = set(criterion_ids)
    for step in task["plan_steps"]:
        unknown = set(step["supports"]) - known_criteria
        if unknown:
            errors.append(
                f"{label}: {step['id']} references unknown criteria {sorted(unknown)}"
            )

    errors.extend(validate_transitions(task, label))
    errors.extend(validate_approval_bindings(task, label))

    status = task["status"]
    normal_position = NORMAL_ORDER.index(status) if status in NORMAL_ORDER else -1
    if normal_position >= NORMAL_ORDER.index("planning") and not approval_complete(
        task["approvals"]["findings"], "findings"
    ):
        errors.append(f"{label}: status {status} requires approved findings")
    if normal_position >= NORMAL_ORDER.index("approved") and not approval_complete(
        task["approvals"]["plan"], "plan"
    ):
        errors.append(f"{label}: status {status} requires approved plan")
    if task["pull_request"]["state"] != "not_created" and not approval_complete(
        task["approvals"]["pull_request"], "pull_request"
    ):
        errors.append(f"{label}: created PR requires PR-creation approval")
    if status in {"merging", "completing", "completed", "archived"} and not approval_complete(
        task["approvals"]["merge"], "merge"
    ):
        errors.append(f"{label}: status {status} requires merge approval")

    if normal_position >= NORMAL_ORDER.index("planning") and not task["plan_steps"]:
        errors.append(f"{label}: status {status} requires plan_steps")

    if status in {"merging", "completing", "completed", "archived"}:
        bad = [item["id"] for item in task["acceptance_criteria"] if item["status"] != "passed"]
        if bad:
            errors.append(f"{label}: merge/completion requires passed criteria: {bad}")

    if status in {"completed", "archived"}:
        if task["pull_request"]["state"] != "merged":
            errors.append(f"{label}: completed/archived task requires merged implementation PR")
        if not task["merge"].get("commit_sha") or not task["merge"].get("merged_at"):
            errors.append(f"{label}: completed/archived task requires implementation merge metadata")

    if kind == "active" and status == "archived":
        errors.append(f"{label}: archived status cannot remain under active path")
    if kind == "archive":
        if status != "archived" or task["archive"]["status"] != "archived":
            errors.append(f"{label}: archived directory requires archived task and archive status")
        if task["archive"].get("path") != path.parent.relative_to(ROOT).as_posix():
            errors.append(f"{label}: archive.path must equal the actual archive directory")

    blocker = task["blocker"]
    if status == "blocked":
        required = (
            blocker.get("is_blocked") is True,
            blocker.get("entered_from_status") is not None,
            bool(blocker.get("reason")),
            blocker.get("since") is not None,
            bool(blocker.get("required_user_decision")),
            blocker.get("resume_status") is not None,
        )
        if not all(required):
            errors.append(f"{label}: blocked task is missing blocker/resume metadata")
    elif blocker.get("is_blocked"):
        errors.append(f"{label}: blocker.is_blocked is true while status is {status}")

    archive = task["archive"]
    if archive["status"] in {"pr_open", "archived"}:
        auth = archive["authorization"]
        if auth.get("mode") == "not_started" or not auth.get("source_approval_head_sha"):
            errors.append(f"{label}: archival PR requires recorded authorization")
        apr = archive["pull_request"]
        if not apr.get("number") or not apr.get("url") or not apr.get("head_sha"):
            errors.append(f"{label}: archival PR metadata is incomplete")

    return errors


def iter_text_files() -> Iterable[Path]:
    ignored_parts = {".git", "__pycache__"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in ignored_parts for part in path.parts):
            continue
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        yield path


def main() -> int:
    errors: list[str] = []

    try:
        config = load_yaml(CONFIG_PATH)
        config_schema = load_json(CONFIG_SCHEMA_PATH)
        task_schema = load_json(TASK_SCHEMA_PATH)
    except Exception as exc:
        print(f"Failed to load configuration or schemas: {exc}", file=sys.stderr)
        return 1

    errors.extend(schema_errors(config, config_schema, rel(CONFIG_PATH)))

    live_config_text = CONFIG_PATH.read_text(encoding="utf-8")
    if "__REQUIRED_" in live_config_text or "replace-with" in live_config_text:
        errors.append(f"{rel(CONFIG_PATH)}: live configuration contains placeholders")

    seen_ids: dict[str, str] = {}
    for kind, path in task_files(config):
        try:
            task = load_yaml(path)
        except Exception as exc:
            errors.append(f"{rel(path)}: YAML parse failed: {exc}")
            continue
        errors.extend(schema_errors(task, task_schema, rel(path)))
        if not isinstance(task, dict) or "id" not in task:
            continue
        task_id = str(task["id"])
        if task_id in seen_ids:
            errors.append(f"duplicate task ID {task_id}: {seen_ids[task_id]} and {rel(path)}")
        else:
            seen_ids[task_id] = rel(path)
        if not schema_errors(task, task_schema, rel(path)):
            errors.extend(validate_task_semantics(kind, path, task))

    for path in iter_text_files():
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in CONFLICT_MARKERS):
            errors.append(f"{rel(path)}: unresolved merge-conflict marker")

    expected_index = render_index(ROOT)
    actual_index = INDEX_PATH.read_text(encoding="utf-8") if INDEX_PATH.exists() else ""
    if actual_index != expected_index:
        errors.append(".tasks/index.yaml is stale; run python scripts/generate_index.py")

    # Ensure the live VERSION and configuration agree.
    version = (TASKS / "VERSION").read_text(encoding="utf-8").strip()
    if version != config.get("task_system_version"):
        errors.append(".tasks/VERSION does not match config.task_system_version")

    if errors:
        print("Task-system validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Task-system validation passed.")
    print(f"Validated {len(seen_ids)} live task record(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

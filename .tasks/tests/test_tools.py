from __future__ import annotations

import importlib
from pathlib import Path
import sys
import tempfile
import unittest

import yaml

SCRIPT_DIR = Path(__file__).resolve().parents[1] / 'scripts'
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

generate_index = importlib.import_module('generate_index')
validate = importlib.import_module('validate')


class GenerateIndexTests(unittest.TestCase):
    def test_missing_versions_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            instance_root = repo_root / '.tasks'
            (instance_root / 'active').mkdir(parents=True)
            (instance_root / 'archive').mkdir()
            (instance_root / 'config.yaml').write_text(
                yaml.safe_dump(
                    {
                        'paths': {
                            'active': '.tasks/active',
                            'archive': '.tasks/archive',
                            'index': '.tasks/index.yaml',
                        }
                    },
                    sort_keys=False,
                ),
                encoding='utf-8',
            )

            with self.assertRaisesRegex(ValueError, 'schema_version'):
                generate_index.build_index(repo_root, instance_root)

    def test_symlinked_task_file_outside_instance_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            active_root = repo_root / '.tasks' / 'active'
            task_dir = active_root / 'TASK-2026-001-symlink-test'
            task_dir.mkdir(parents=True)
            outside = repo_root / 'outside-task.yaml'
            outside.write_text('id: TASK-2026-001\n', encoding='utf-8')
            link = task_dir / 'task.yaml'
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f'symlinks are unavailable: {exc}')

            with self.assertRaisesRegex(ValueError, 'resolves outside'):
                generate_index.task_entries(repo_root, active_root, archived=False)


class ValidatorTests(unittest.TestCase):
    def _make_template(self, repo_root: Path) -> Path:
        template_root = repo_root / '.tasks'
        required_files = set(validate.TEMPLATE_REQUIRED_FILES)
        for relative_path in required_files:
            path = template_root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            if relative_path == 'config.yaml':
                path.write_text(
                    yaml.safe_dump(
                        {
                            'schema_version': '3.0.0',
                            'task_system_version': '3.0.0',
                            'mode': 'template',
                            'timezone': '__REQUIRED_TIMEZONE__',
                            'repository': {
                                'name': '__REQUIRED_REPOSITORY_NAME__',
                                'default_branch': '__REQUIRED_DEFAULT_BRANCH__',
                            },
                            'paths': {
                                'active': '.tasks/active',
                                'archive': '.tasks/archive',
                                'template': '.tasks/templates/task',
                                'index': '.tasks/index.yaml',
                            },
                        },
                        sort_keys=False,
                    ),
                    encoding='utf-8',
                )
            elif relative_path == 'index.yaml':
                path.write_text(
                    '# GENERATED VIEW ONLY. The authoritative state is each task.yaml.\n'
                    'schema_version: 3.0.0\n'
                    'task_system_version: 3.0.0\n'
                    'active:\n'
                    '- id: TASK-2026-999\n'
                    'archived: []\n',
                    encoding='utf-8',
                )
            elif relative_path == 'templates/task/task.yaml':
                path.write_text('id: __REQUIRED_TASK_ID__\n', encoding='utf-8')
            elif relative_path.startswith('templates/task/') and relative_path.endswith('.md'):
                path.write_text('__REQUIRED_FIELD__\n', encoding='utf-8')
            else:
                path.write_text('placeholder\n', encoding='utf-8')

        for relative_path in validate.TEMPLATE_REQUIRED_DIRECTORIES:
            (template_root / relative_path).mkdir(parents=True, exist_ok=True)
        return template_root

    def test_template_index_must_be_the_generated_empty_view(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            template_root = self._make_template(repo_root)
            errors: list[str] = []

            validate.validate_template(
                repo_root,
                template_root,
                {'type': 'object'},
                errors,
            )

            self.assertTrue(
                any('generated empty template index' in error for error in errors),
                errors,
            )

    def test_merge_approval_rejects_mismatched_pr_and_candidate_heads(self) -> None:
        task = {
            'id': 'TASK-2026-001',
            'revisions': {'task': 1, 'findings': 1, 'plan': 1},
            'git': {'candidate_head_sha': 'a' * 40},
            'pull_request': {
                'head_sha': 'b' * 40,
                'checks': {'status': 'passed'},
            },
        }
        approval = {
            'status': 'approved',
            'task_revision': 1,
            'findings_revision': 1,
            'head_sha': 'b' * 40,
            'approved_by': 'user',
            'approved_at': '2026-07-31T00:00:00Z',
            'evidence': 'approved in chat',
        }
        errors: list[str] = []

        validate.validate_approval(
            'merge',
            approval,
            Path('.'),
            task,
            errors,
        )

        self.assertTrue(
            any(
                'pull_request.head_sha to equal git.candidate_head_sha' in error
                for error in errors
            ),
            errors,
        )

    def test_malformed_ids_and_supports_do_not_raise_type_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            task_dir = repo_root / 'active' / 'TASK-2026-001-malformed-record'
            task_dir.mkdir(parents=True)
            for name in validate.ACTIVE_REQUIRED_FILES:
                path = task_dir / name
                if name == 'task.yaml':
                    continue
                path.write_text('No required placeholders.\n', encoding='utf-8')
            (task_dir / 'evidence' / 'screenshots').mkdir(parents=True)
            task = {
                'id': 'TASK-2026-001',
                'slug': 'malformed-record',
                'status': 'draft',
                'state_history': [
                    {
                        'at': '2026-07-31T00:00:00Z',
                        'from': None,
                        'to': 'draft',
                        'actor': 'agent',
                        'reason': 'test',
                    }
                ],
                'acceptance_criteria': [
                    {'id': ['unhashable'], 'status': 'pending', 'evidence': []}
                ],
                'plan_steps': [
                    {
                        'id': {'unhashable': True},
                        'status': 'pending',
                        'supports': [['nested']],
                    }
                ],
                'approvals': {},
                'blocker': {'is_blocked': False},
            }
            task_file = task_dir / 'task.yaml'
            task_file.write_text(yaml.safe_dump(task, sort_keys=False), encoding='utf-8')
            errors: list[str] = []

            validate.validate_task(
                repo_root,
                task_file,
                archived=False,
                schema={'type': 'object'},
                config={},
                errors=errors,
            )

            self.assertIsInstance(errors, list)

    def test_malformed_blocker_states_do_not_raise_type_error(self) -> None:
        task = {
            'status': 'blocked',
            'blocker': {
                'is_blocked': True,
                'entered_from_status': ['implementing'],
                'resume_status': {'state': 'implementing'},
                'reason': 'test',
                'since': '2026-07-31T00:00:00Z',
                'required_user_decision': 'test',
            },
        }
        errors: list[str] = []

        validate.validate_blocker(
            'TASK-2026-001',
            task,
            {'blocked'},
            errors,
        )

        self.assertTrue(
            any('entered_from_status must be a normal state' in error for error in errors),
            errors,
        )
        self.assertTrue(
            any('resume_status must be a normal state' in error for error in errors),
            errors,
        )

    def test_traceability_matching_is_token_bounded(self) -> None:
        self.assertFalse(validate.references_id('Only AC-010 is present.', 'AC-01'))
        self.assertTrue(validate.references_id('Criterion `AC-01` is present.', 'AC-01'))
        self.assertFalse(validate.references_id('Only PLAN-010 is present.', 'PLAN-01'))
        self.assertTrue(validate.references_id('Step PLAN-01 is present.', 'PLAN-01'))

    def test_blocked_transition_only_resumes_to_nonterminal_recorded_state(self) -> None:
        self.assertTrue(validate.allowed_transition('blocked', 'implementing', 'implementing'))
        self.assertFalse(validate.allowed_transition('blocked', 'testing', 'implementing'))
        self.assertFalse(validate.allowed_transition('blocked', 'completed', 'completed'))
        self.assertFalse(validate.allowed_transition('blocked', 'archived', 'archived'))

    def test_completed_can_only_transition_to_archived(self) -> None:
        self.assertTrue(validate.allowed_transition('completed', 'archived', None))
        self.assertFalse(validate.allowed_transition('completed', 'failed', None))
        self.assertFalse(validate.allowed_transition('completed', 'blocked', None))


if __name__ == '__main__':
    unittest.main()

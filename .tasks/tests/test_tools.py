from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
import importlib
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml

SCRIPT_DIR = Path(__file__).resolve().parents[1] / 'scripts'
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

generate_index = importlib.import_module('generate_index')
validate = importlib.import_module('validate')
init = importlib.import_module('init')
new_task = importlib.import_module('new_task')
upgrade = importlib.import_module('upgrade')

BUNDLE_ROOT = Path(__file__).resolve().parents[1]

TEMPLATE_PATHS = {
    'bundle': '.tasks',
    'instructions': 'AGENTS.md',
    'active': '.project-tasks/active',
    'archive': '.project-tasks/archive',
    'template': '.tasks/templates/task',
    'index': '.project-tasks/index.yaml',
}


def run_cli(module, argv: list[str]) -> tuple[int, str, str]:
    """Run a script's `main()` with `argv`, capturing its exit code and output."""
    stdout = io.StringIO()
    stderr = io.StringIO()
    with mock.patch.object(sys, 'argv', ['prog', *argv]):
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = module.main()
    return code, stdout.getvalue(), stderr.getvalue()


def _git_available() -> bool:
    return shutil.which('git') is not None


class GenerateIndexTests(unittest.TestCase):
    def test_missing_versions_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            instance_root = repo_root / '.project-tasks'
            (instance_root / 'active').mkdir(parents=True)
            (instance_root / 'archive').mkdir()
            (instance_root / 'config.yaml').write_text(
                yaml.safe_dump({'paths': TEMPLATE_PATHS}, sort_keys=False),
                encoding='utf-8',
            )

            with self.assertRaisesRegex(ValueError, 'schema_version'):
                generate_index.build_index(repo_root, instance_root)

    def test_symlinked_task_file_outside_instance_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            active_root = repo_root / '.project-tasks' / 'active'
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


class BundleLayoutTests(unittest.TestCase):
    def _make_bundle(self, repo_root: Path, paths: dict[str, str] | None = None) -> Path:
        bundle_root = repo_root / '.tasks'
        for relative_path in validate.TEMPLATE_REQUIRED_FILES:
            path = bundle_root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            if relative_path == 'templates/instance/config.yaml':
                path.write_text(
                    yaml.safe_dump(
                        {
                            'schema_version': '4.0.0',
                            'task_system_version': '4.0.0',
                            'mode': 'template',
                            'timezone': '__REQUIRED_TIMEZONE__',
                            'repository': {
                                'name': '__REQUIRED_REPOSITORY_NAME__',
                                'default_branch': '__REQUIRED_DEFAULT_BRANCH__',
                            },
                            'paths': dict(paths or TEMPLATE_PATHS),
                        },
                        sort_keys=False,
                    ),
                    encoding='utf-8',
                )
            elif relative_path == 'templates/task/task.yaml':
                path.write_text('id: __REQUIRED_TASK_ID__\n', encoding='utf-8')
            elif relative_path.startswith('templates/task/') and relative_path.endswith('.md'):
                path.write_text('__REQUIRED_FIELD__\n', encoding='utf-8')
            else:
                path.write_text('placeholder\n', encoding='utf-8')

        for relative_path in validate.TEMPLATE_REQUIRED_DIRECTORIES:
            (bundle_root / relative_path).mkdir(parents=True, exist_ok=True)
        return bundle_root

    def _validate(self, repo_root: Path, bundle_root: Path) -> list[str]:
        errors: list[str] = []
        validate.validate_template(repo_root, bundle_root, {'type': 'object'}, errors)
        return errors

    def test_pristine_bundle_validates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            bundle_root = self._make_bundle(repo_root)

            self.assertEqual(self._validate(repo_root, bundle_root), [])

    def test_bundle_may_not_contain_live_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            bundle_root = self._make_bundle(repo_root)
            (bundle_root / 'active').mkdir()
            (bundle_root / 'config.yaml').write_text('mode: live\n', encoding='utf-8')

            errors = self._validate(repo_root, bundle_root)

            self.assertTrue(
                any('must not contain live task state' in error for error in errors),
                errors,
            )
            self.assertTrue(
                any('must not contain live instance files' in error for error in errors),
                errors,
            )

    def test_live_state_paths_inside_the_bundle_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            inside = dict(TEMPLATE_PATHS)
            inside['active'] = '.tasks/active'
            bundle_root = self._make_bundle(repo_root, inside)

            errors = self._validate(repo_root, bundle_root)

            self.assertTrue(
                any(
                    'paths.active must stay outside the bundle' in error
                    for error in errors
                ),
                errors,
            )

    def test_bundle_missing_install_files_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            bundle_root = self._make_bundle(repo_root)
            (bundle_root / 'scripts/init.py').unlink()

            errors = self._validate(repo_root, bundle_root)

            self.assertTrue(
                any('scripts/init.py' in error for error in errors), errors
            )


class ConflictScanTests(unittest.TestCase):
    def _scan(self, root: Path, roots: list[Path] | None = None) -> list[str]:
        errors: list[str] = []
        validate.scan_conflicts(root, roots if roots is not None else [root], errors)
        return errors

    def test_setext_heading_is_not_a_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'guide.md').write_text(
                'Installation\n=======\n\nRun it.\n', encoding='utf-8'
            )

            self.assertEqual(self._scan(root), [])

    def test_paired_markers_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'merged.py').write_text(
                '<<<<<<< HEAD\na = 1\n=======\na = 2\n>>>>>>> feature\n',
                encoding='utf-8',
            )

            errors = self._scan(root)

            self.assertTrue(
                any('unresolved merge-conflict marker' in error for error in errors),
                errors,
            )

    def test_scan_is_limited_to_the_given_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            scanned = repo_root / '.project-tasks'
            scanned.mkdir()
            (scanned / 'kept.md').write_text('clean\n', encoding='utf-8')
            elsewhere = repo_root / 'node_modules'
            elsewhere.mkdir()
            (elsewhere / 'vendored.js').write_text(
                '<<<<<<< HEAD\nx\n=======\ny\n>>>>>>> other\n', encoding='utf-8'
            )

            self.assertEqual(self._scan(repo_root, [scanned]), [])

    def test_lone_start_marker_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'partial.md').write_text(
                '<<<<<<< HEAD\nsome text\n', encoding='utf-8'
            )

            errors = self._scan(root)

            self.assertTrue(
                any('unresolved merge-conflict marker' in error for error in errors),
                errors,
            )

    def test_lone_end_marker_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'partial.md').write_text(
                'some text\n>>>>>>> feature\n', encoding='utf-8'
            )

            errors = self._scan(root)

            self.assertTrue(
                any('unresolved merge-conflict marker' in error for error in errors),
                errors,
            )


class CiGatingTests(unittest.TestCase):
    def _merge_ready_task(self) -> dict:
        return {
            'status': 'completed',
            'acceptance_criteria': [
                {'id': 'AC-01', 'status': 'passed', 'evidence': ['verification.md']}
            ],
            'plan_steps': [{'id': 'PLAN-01', 'status': 'completed', 'supports': ['AC-01']}],
            'pull_request': {'state': 'merged', 'checks': {'status': 'not_started'}},
            'merge': {
                'commit_sha': 'c' * 40,
                'merged_at': '2026-07-31T00:00:00Z',
                'merged_by': 'user',
            },
        }

    def test_requires_ci_follows_provider_and_enabled_flag(self) -> None:
        self.assertTrue(
            validate.requires_ci({'repository': {'provider': 'github'}, 'github': {}})
        )
        self.assertFalse(
            validate.requires_ci(
                {'repository': {'provider': 'github'}, 'github': {'enabled': False}}
            )
        )
        self.assertFalse(
            validate.requires_ci({'repository': {'provider': 'other'}, 'github': {}})
        )

    def test_merge_readiness_requires_checks_when_ci_is_required(self) -> None:
        errors: list[str] = []

        validate.validate_merge_readiness(
            'TASK-2026-001', self._merge_ready_task(), errors, ci_required=True
        )

        self.assertTrue(
            any('requires passed pull-request checks' in error for error in errors),
            errors,
        )

    def test_merge_readiness_skips_checks_without_ci(self) -> None:
        errors: list[str] = []

        validate.validate_merge_readiness(
            'TASK-2026-001', self._merge_ready_task(), errors, ci_required=False
        )

        self.assertEqual(errors, [])

    def test_merge_readiness_skips_merged_pull_request_without_ci(self) -> None:
        task = self._merge_ready_task()
        task['pull_request'] = {}
        errors: list[str] = []

        validate.validate_merge_readiness(
            'TASK-2026-001', task, errors, ci_required=False
        )

        self.assertEqual(errors, [])

    def test_merge_readiness_requires_merged_pull_request_with_ci(self) -> None:
        task = self._merge_ready_task()
        task['pull_request'] = {'state': 'open', 'checks': {'status': 'passed'}}
        errors: list[str] = []

        validate.validate_merge_readiness('TASK-2026-001', task, errors, ci_required=True)

        self.assertTrue(
            any('requires a merged pull request' in error for error in errors), errors
        )

    def test_merge_approval_binds_to_candidate_head_without_ci(self) -> None:
        task = {
            'id': 'TASK-2026-001',
            'revisions': {'task': 1, 'findings': 1, 'plan': 1},
            'git': {'candidate_head_sha': 'a' * 40},
            'pull_request': {'state': 'not_created', 'checks': {'status': 'not_started'}},
        }
        approval = {
            'status': 'approved',
            'task_revision': 1,
            'findings_revision': 1,
            'head_sha': 'a' * 40,
            'approved_by': 'user',
            'approved_at': '2026-07-31T00:00:00Z',
            'evidence': 'approved in chat',
        }
        errors: list[str] = []

        validate.validate_approval(
            'merge', approval, Path('.'), task, errors, ci_required=False
        )

        self.assertEqual(errors, [])

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

        validate.validate_approval('merge', approval, Path('.'), task, errors)

        self.assertTrue(
            any(
                'pull_request.head_sha to equal git.candidate_head_sha' in error
                for error in errors
            ),
            errors,
        )


class InitTests(unittest.TestCase):
    def _render(self, **overrides) -> str:
        arguments = {
            'bundle': '.tasks',
            'instance': '.project-tasks',
            'repository_name': 'demo',
            'default_branch': 'main',
            'timezone': 'UTC',
            'remote': 'origin',
            'provider': 'github',
            'github_enabled': True,
            'interpreter': 'python3',
        }
        arguments.update(overrides)
        template = (BUNDLE_ROOT / init.TEMPLATE_CONFIG).read_text(encoding='utf-8')
        return init.render_config(template, **arguments)

    def test_rendered_config_is_live_and_placeholder_free(self) -> None:
        text = self._render()
        config = yaml.safe_load(text)

        self.assertNotIn('__REQUIRED_', text)
        self.assertEqual(config['mode'], 'live')
        self.assertEqual(config['repository']['name'], 'demo')
        self.assertEqual(config['repository']['default_branch'], 'main')
        self.assertEqual(config['paths']['bundle'], '.tasks')

    def test_rendered_config_keeps_live_state_outside_the_bundle(self) -> None:
        config = yaml.safe_load(self._render(bundle='.bundle', instance='.work'))

        self.assertEqual(config['paths']['bundle'], '.bundle')
        self.assertEqual(config['paths']['template'], '.bundle/templates/task')
        self.assertEqual(config['paths']['active'], '.work/active')
        self.assertEqual(config['paths']['index'], '.work/index.yaml')

    def test_disabling_github_checks_is_recorded(self) -> None:
        config = yaml.safe_load(self._render(provider='other', github_enabled=False))

        self.assertEqual(config['repository']['provider'], 'other')
        self.assertFalse(config['github']['enabled'])
        self.assertFalse(validate.requires_ci(config))

    def test_windows_interpreter_is_substituted_in_commands(self) -> None:
        config = yaml.safe_load(self._render(interpreter='python'))

        self.assertTrue(config['commands']['generate_index'].startswith('python '))

    def test_rendered_commands_point_at_the_configured_bundle(self) -> None:
        config = yaml.safe_load(self._render(bundle='.bundle', instance='.work'))

        script_commands = {
            name: command
            for name, command in config['commands'].items()
            if command is not None and 'scripts/' in command
        }

        self.assertTrue(script_commands, config['commands'])
        for name, command in script_commands.items():
            with self.subTest(command=name):
                self.assertIn('.bundle/scripts/', command)
                self.assertNotIn('.project-tasks', command)
                if '--template-root' in command:
                    self.assertIn('--template-root .bundle', command)
                if '--instance-root' in command:
                    self.assertIn('--instance-root .work', command)


class InstructionFileTests(unittest.TestCase):
    def _check(self, contents: str | None, version: str = '4.0.0') -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            bundle_root = repo_root / '.tasks'
            bundle_root.mkdir()
            instance_root = repo_root / '.project-tasks'
            instance_root.mkdir()
            instructions = repo_root / 'AGENTS.md'
            if contents is not None:
                instructions.write_text(contents, encoding='utf-8')
            errors: list[str] = []
            validate.validate_instructions(
                repo_root, instructions, bundle_root, instance_root, version, errors
            )
            return errors

    def test_current_instruction_file_passes(self) -> None:
        text = (
            'Work follows `.tasks/AGENTS.md` and the live configuration in '
            '`.project-tasks/config.yaml`.\n'
        )

        self.assertEqual(self._check(text), [])

    def test_missing_instruction_file_is_reported(self) -> None:
        errors = self._check(None)

        self.assertTrue(
            any('nothing directs an agent' in error for error in errors), errors
        )

    def test_stale_pre_split_layout_is_reported(self) -> None:
        text = (
            'Work follows `.tasks/AGENTS.md` unless `.tasks/config.yaml` overrides it.\n'
            'Current state: task system version `1.0.0`, `.tasks/active` is empty.\n'
        )

        errors = self._check(text)

        self.assertTrue(
            any('.tasks/config.yaml, which no longer exists' in e for e in errors), errors
        )
        self.assertTrue(
            any('.tasks/active, which no longer exists' in e for e in errors), errors
        )
        self.assertTrue(
            any('does not reference the live instance' in e for e in errors), errors
        )

    def test_stale_pointer_below_a_removed_root_is_reported(self) -> None:
        text = (
            'Work follows `.tasks/AGENTS.md` with `.project-tasks/config.yaml`.\n'
            'The current record is `.tasks/active/TASK-2026-001/task.yaml`.\n'
        )

        errors = self._check(text)

        self.assertTrue(
            any('.tasks/active, which no longer exists' in e for e in errors), errors
        )

    def test_identifier_continuation_is_not_a_stale_pointer(self) -> None:
        text = (
            'Work follows `.tasks/AGENTS.md` with `.project-tasks/config.yaml`.\n'
            'Retired records live in `.tasks/archive-old`.\n'
        )

        self.assertEqual(self._check(text), [])

    def test_stale_stated_version_is_reported(self) -> None:
        text = (
            'Work follows `.tasks/AGENTS.md` with `.project-tasks/config.yaml`.\n'
            'Task system version 3.0.0 is installed.\n'
        )

        errors = self._check(text)

        self.assertEqual(len(errors), 1, errors)
        self.assertIn('states task-system version 3.0.0', errors[0])
        self.assertIn('version 4.0.0 is installed', errors[0])

    def test_matching_major_version_is_accepted(self) -> None:
        text = (
            'Work follows `.tasks/AGENTS.md` with `.project-tasks/config.yaml`.\n'
            'Task system version 4.1.2 is installed.\n'
        )

        self.assertEqual(self._check(text), [])


class PlaceholderReportingTests(unittest.TestCase):
    def test_locations_name_the_token_and_line(self) -> None:
        found = validate.placeholder_locations(
            'title: ok\nname: __REQUIRED_TITLE__\nid: __REQUIRED_TASK_ID__\n'
        )

        self.assertEqual(found, ['2:__REQUIRED_TITLE__', '3:__REQUIRED_TASK_ID__'])

    def test_summary_truncates_long_lists(self) -> None:
        summary = validate.summarize([f'{n}:__REQUIRED_X__' for n in range(9)])

        self.assertIn('(and 4 more)', summary)

    def test_keys_are_reported_as_dotted_paths(self) -> None:
        keys = validate.placeholder_keys(
            {'id': '__REQUIRED_TASK_ID__', 'repository': {'name': '__REQUIRED_NAME__'}}
        )

        self.assertEqual(sorted(keys), ['id', 'repository.name'])


class ArtifactProfileTests(unittest.TestCase):
    # What the retired lite profile used to accept for documentation tasks.
    REDUCED = (
        'task.yaml', 'task.md', 'findings.md', 'plan.md',
        'verification.md', 'completion.md',
    )

    def _artifact_errors(self, task_type: str, files: tuple[str, ...]) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            task_dir = repo_root / 'active' / 'TASK-2026-001-demo'
            task_dir.mkdir(parents=True)
            for name in files:
                (task_dir / name).write_text('content\n', encoding='utf-8')
            (task_dir / 'evidence' / 'screenshots').mkdir(parents=True)
            errors: list[str] = []
            validate.validate_artifacts(
                repo_root,
                task_dir,
                'TASK-2026-001',
                {'type': task_type},
                False,
                {},
                errors,
            )
            return errors

    def test_every_type_requires_the_same_artifacts(self) -> None:
        for task_type in ('documentation', 'dependency', 'feature'):
            with self.subTest(type=task_type):
                errors = self._artifact_errors(task_type, self.REDUCED)

                self.assertTrue(
                    any('assessment.md' in error for error in errors), errors
                )
                self.assertTrue(
                    any('implementation-log.md' in error for error in errors), errors
                )

    def test_the_full_set_satisfies_every_type(self) -> None:
        for task_type in ('documentation', 'feature'):
            with self.subTest(type=task_type):
                self.assertEqual(
                    self._artifact_errors(task_type, validate.ACTIVE_REQUIRED_FILES), []
                )


class NewTaskTests(unittest.TestCase):
    def test_id_allocation_continues_the_year_sequence(self) -> None:
        config = {'identifiers': {'prefix': 'TASK', 'sequence_width': 3}}

        self.assertEqual(
            new_task.allocate_id(config, {'TASK-2026-001', 'TASK-2026-004'}, 2026),
            'TASK-2026-005',
        )
        self.assertEqual(new_task.allocate_id(config, set(), 2026), 'TASK-2026-001')
        self.assertEqual(
            new_task.allocate_id(config, {'TASK-2025-009'}, 2026), 'TASK-2026-001'
        )

    def test_mechanical_placeholders_are_filled(self) -> None:
        values = new_task.substitutions(
            'TASK-2026-007',
            'demo-slug',
            'Demo title',
            '2026-07-31T09:00:00-04:00',
            {'repository': {'name': 'widget', 'default_branch': 'main'}},
            'agent',
            'Requested in chat',
            'Do the thing.',
        )
        template = (BUNDLE_ROOT / 'templates/task/task.yaml').read_text(encoding='utf-8')

        filled = new_task.apply(template, values)

        self.assertNotIn('__REQUIRED_', filled)
        record = yaml.safe_load(filled)
        self.assertEqual(record['id'], 'TASK-2026-007')
        self.assertEqual(record['slug'], 'demo-slug')
        self.assertEqual(record['branch']['name'], 'task/TASK-2026-007-demo-slug')
        self.assertEqual(record['repository']['name'], 'widget')

    def test_template_carries_exactly_the_required_artifacts(self) -> None:
        names = sorted(
            path.name
            for path in (BUNDLE_ROOT / 'templates/task').iterdir()
            if path.is_file()
        )

        self.assertEqual(names, sorted(validate.ACTIVE_REQUIRED_FILES))

    def test_timestamp_falls_back_when_timezone_is_unavailable(self) -> None:
        value = new_task.timestamp('Not/AZone')


    def test_yaml_scalar_escapes_special_characters(self) -> None:
        title = 'Fix "quoted" output with \\ backslash'
        escaped = new_task.yaml_scalar(title)
        self.assertIn('\\"', escaped)
        self.assertIn('\\\\', escaped)
        self.assertNotIn('\n', new_task.yaml_scalar('line1\nline2'))

    def test_substituted_yaml_parses_with_special_characters(self) -> None:
        values = new_task.substitutions(
            'TASK-2026-001', 'demo', 'He said "hi" and \\ left', '2026-07-31T00:00:00Z',
            {'repository': {'name': 'repo', 'default_branch': 'main'}},
            'agent', 'chat', 'Do the thing.',
        )
        yaml_values = {k: new_task.yaml_scalar(v) for k, v in values.items()}
        template = (
            'id: "__REQUIRED_TASK_ID__"\n'
            'title: "__REQUIRED_TITLE__"\n'
            'slug: "__REQUIRED_SLUG__"\n'
        )
        filled = new_task.apply(template, yaml_values)
        record = yaml.safe_load(filled)

        self.assertEqual(record['title'], 'He said "hi" and \\ left')

class InstallInstructionsTests(unittest.TestCase):
    TEMPLATE = (
        '# AGENTS.md\n\n## Project identity\n\n- Project: `__REQUIRED_PROJECT_NAME__`\n\n'
        '## Task system\n\nWork follows `.tasks/AGENTS.md` and `.project-tasks/config.yaml`.\n'
    )

    def _install(self, existing: str | None) -> tuple[str, list[str]]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'AGENTS.md'
            if existing is not None:
                path.write_text(existing, encoding='utf-8')
            actions: list[str] = []
            init.install_instructions(
                path, self.TEMPLATE, '.tasks', '.project-tasks', 'python3',
                False, actions,
            )
            return path.read_text(encoding='utf-8'), actions

    def test_absent_file_gets_only_the_task_system_section(self) -> None:
        text, actions = self._install(None)

        self.assertIn('## Task system', text)
        self.assertNotIn('## Project identity', text)
        self.assertTrue(any('append' in action for action in actions), actions)

    def test_existing_file_is_appended_to_not_replaced(self) -> None:
        existing = '# AGENTS.md\n\nOur house rules. Do not lose these.\n'

        text, actions = self._install(existing)

        self.assertIn('Our house rules. Do not lose these.', text)
        self.assertIn('## Task system', text)
        self.assertNotIn('## Project identity', text)
        self.assertTrue(any('append' in action for action in actions), actions)

    def test_a_long_existing_file_is_still_only_appended_to(self) -> None:
        existing = '# AGENTS.md\n\n' + ''.join(f'Rule {n}.\n' for n in range(500))

        text, actions = self._install(existing)

        self.assertTrue(text.startswith(existing), text[:80])
        self.assertIn('## Task system', text)
        self.assertTrue(any('append' in action for action in actions), actions)

    def test_blank_file_is_appended_to_not_overwritten(self) -> None:
        text, actions = self._install('   \n\n')

        self.assertIn('## Task system', text)
        self.assertNotIn('## Project identity', text)
        self.assertTrue(any('append' in action for action in actions), actions)

    def test_already_installed_file_is_left_alone(self) -> None:
        existing = '# AGENTS.md\n\nSee `.tasks/AGENTS.md` for the lifecycle.\n'

        text, actions = self._install(existing)

        self.assertEqual(text, existing)
        self.assertTrue(any('keep' in action for action in actions), actions)


class UpgradeTests(unittest.TestCase):
    def test_missing_keys_are_found_at_any_depth(self) -> None:
        template = {'a': 1, 'nested': {'kept': 2, 'added': 3}}
        live = {'a': 9, 'nested': {'kept': 8}}

        found = upgrade.missing_keys(template, live)

        self.assertEqual(found, [(('nested', 'added'), 3)])

    def test_retired_keys_are_removed(self) -> None:
        config = {
            'lifecycle': {
                'lite_profile_task_types': ['documentation'],
                'full_profile_required': True,
                'approval_source': 'chat',
            }
        }

        removed = upgrade.remove_retired(config)

        self.assertEqual(config['lifecycle'], {'approval_source': 'chat'})
        self.assertEqual(
            sorted(removed),
            ['lifecycle.full_profile_required', 'lifecycle.lite_profile_task_types'],
        )

    def test_removing_retired_keys_tolerates_absent_sections(self) -> None:
        config = {'repository': {'name': 'demo'}}

        self.assertEqual(upgrade.remove_retired(config), [])
        self.assertEqual(config, {'repository': {'name': 'demo'}})

    def test_missing_keys_carry_the_template_value(self) -> None:
        template = {'lifecycle': {'required_approvals': ['findings', 'plan']}}

        found = upgrade.missing_keys(template, {'lifecycle': {}})

        self.assertEqual(
            found, [(('lifecycle', 'required_approvals'), ['findings', 'plan'])]
        )

    def test_existing_values_are_never_replaced(self) -> None:
        template = {'github': {'enabled': True, 'ci_timeout_minutes': 90}}
        live = {'github': {'enabled': False}}
        config = dict(live)

        for path, value in upgrade.missing_keys(template, live):
            upgrade.assign(config, path, value)

        self.assertIs(config['github']['enabled'], False)
        self.assertEqual(config['github']['ci_timeout_minutes'], 90)

    def test_live_state_paths_are_moved_out_of_the_bundle(self) -> None:
        repo_root = Path('/repo')
        config = {
            'paths': {
                'active': '.tasks/active',
                'archive': '.tasks/archive',
                'index': '.tasks/index.yaml',
            }
        }

        changed = upgrade.rewrite_paths(
            config, repo_root, repo_root / '.tasks', repo_root / '.project-tasks'
        )

        self.assertEqual(config['paths']['active'], '.project-tasks/active')
        self.assertEqual(config['paths']['index'], '.project-tasks/index.yaml')
        self.assertEqual(len(changed), 3)

    def test_paths_already_outside_the_bundle_are_left_alone(self) -> None:
        repo_root = Path('/repo')
        config = {'paths': {'active': '.work/active', 'archive': '.work/archive',
                            'index': '.work/index.yaml'}}

        changed = upgrade.rewrite_paths(
            config, repo_root, repo_root / '.tasks', repo_root / '.project-tasks'
        )

        self.assertEqual(changed, [])
        self.assertEqual(config['paths']['active'], '.work/active')

    def test_instruction_repair_fixes_paths_and_version(self) -> None:
        repo_root = Path('/repo')
        text = (
            'Work follows `.tasks/AGENTS.md` unless `.tasks/config.yaml` overrides it.\n'
            'Task system version 3.0.0. Records live in `.tasks/active`.\n'
        )

        updated, changed = upgrade.repair_instructions(
            text, repo_root, repo_root / '.tasks', repo_root / '.project-tasks', '4.0.0'
        )

        self.assertIn('.project-tasks/config.yaml', updated)
        self.assertIn('.project-tasks/active', updated)
        self.assertIn('version 4.0.0', updated)
        self.assertIn('`.tasks/AGENTS.md`', updated)
        self.assertEqual(len(changed), 3)

    def test_instruction_repair_accepts_punctuated_version_statements(self) -> None:
        repo_root = Path('/repo')

        for statement in ('Task system version: 3.0.0', 'Task system version — 3.0.0'):
            with self.subTest(statement=statement):
                updated, changed = upgrade.repair_instructions(
                    f'{statement}\n',
                    repo_root,
                    repo_root / '.tasks',
                    repo_root / '.project-tasks',
                    '4.0.0',
                )

                self.assertIn('4.0.0', updated)
                self.assertNotIn('3.0.0', updated)
                self.assertEqual(changed, ['stated version 3.0.0 -> 4.0.0'])

    def test_instruction_repair_does_not_cross_lines(self) -> None:
        repo_root = Path('/repo')
        text = 'Task system version\n\n3.0.0 was released earlier.\n'

        updated, changed = upgrade.repair_instructions(
            text, repo_root, repo_root / '.tasks', repo_root / '.project-tasks', '4.0.0'
        )

        self.assertEqual(updated, text)
        self.assertEqual(changed, [])

    def test_repaired_instructions_satisfy_the_validator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            bundle_root = repo_root / '.tasks'
            instance_root = repo_root / '.project-tasks'
            bundle_root.mkdir()
            instance_root.mkdir()
            stale = (
                'Work follows `.tasks/AGENTS.md` unless `.tasks/config.yaml` overrides.\n'
                'Task system version 1.0.0. Records live in `.tasks/active` and '
                '`.tasks/archive`; `.tasks/index.yaml` is generated.\n'
            )
            repaired, _ = upgrade.repair_instructions(
                stale, repo_root, bundle_root, instance_root, '4.0.0'
            )
            path = repo_root / 'AGENTS.md'
            path.write_text(repaired, encoding='utf-8')
            errors: list[str] = []

            validate.validate_instructions(
                repo_root, path, bundle_root, instance_root, '4.0.0', errors
            )

            self.assertEqual(errors, [])

    def test_version_tuple_orders_releases(self) -> None:
        self.assertGreater(upgrade.version_tuple('5.0.0'), upgrade.version_tuple('4.0.0'))
        self.assertEqual(upgrade.version_tuple('4.0.0'), upgrade.version_tuple('4.0.0'))

    def test_upgrade_refuses_downgrade(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            bundle_root = repo_root / '.tasks'
            instance_root = repo_root / '.project-tasks'
            instance_root.mkdir(parents=True)
            (bundle_root / 'templates' / 'instance').mkdir(parents=True)
            (bundle_root / 'VERSION').write_text('3.0.0\n', encoding='utf-8')
            (bundle_root / 'templates/instance/config.yaml').write_text(
                'schema_version: "3.0.0"\ntask_system_version: "3.0.0"\n', encoding='utf-8'
            )
            (instance_root / 'config.yaml').write_text(
                yaml.safe_dump(
                    {'task_system_version': '4.0.0', 'paths': {}, 'schema_version': '4.0.0'},
                    sort_keys=False,
                ),
                encoding='utf-8',
            )
            old_argv = sys.argv
            sys.argv = [
                'upgrade.py', '--repo-root', str(repo_root),
                '--bundle-root', str(bundle_root),
                '--instance-root', str(instance_root),
            ]
            try:
                rc = upgrade.main()
            finally:
                sys.argv = old_argv

            self.assertEqual(rc, 1)


class EmptyInstructionFileTests(unittest.TestCase):
    def test_validator_names_the_real_problem(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            (repo_root / '.tasks').mkdir()
            (repo_root / '.project-tasks').mkdir()
            path = repo_root / 'AGENTS.md'
            path.write_text('   \n\n', encoding='utf-8')
            errors: list[str] = []

            validate.validate_instructions(
                repo_root, path, repo_root / '.tasks', repo_root / '.project-tasks',
                '4.0.0', errors,
            )

            self.assertEqual(len(errors), 1, errors)
            self.assertIn('is empty', errors[0])

    def test_init_fills_an_empty_file_without_leading_blank_lines(self) -> None:
        template = (
            '# AGENTS.md\n\n## Project identity\n\n- Project: `x`\n\n'
            '## Task system\n\nFollows `.tasks/AGENTS.md` and `.project-tasks/config.yaml`.\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'AGENTS.md'
            path.write_text('\n\n  \n', encoding='utf-8')
            actions: list[str] = []

            init.install_instructions(
                path, template, '.tasks', '.project-tasks', 'python3', False, actions
            )

            text = path.read_text(encoding='utf-8')
            self.assertTrue(text.startswith('## Task system'), text[:40])
            self.assertNotIn('## Project identity', text)


class ValidatorTests(unittest.TestCase):
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

    def test_same_root_bundle_and_instance_is_rejected(self) -> None:
        with self.assertRaisesRegex(validate.ValidationFailure, 'separate'):
            validate.select_modes(Path('.tasks'), Path('.tasks'), False, False)


class NewTaskEndToEndTests(unittest.TestCase):
    def _make_instance(self, repo_root: Path, **config_overrides) -> Path:
        instance_root = repo_root / '.project-tasks'
        (instance_root / 'active').mkdir(parents=True)
        (instance_root / 'archive').mkdir()
        config = {
            'schema_version': '4.0.0',
            'task_system_version': '4.0.0',
            'mode': 'live',
            'timezone': 'UTC',
            'repository': {'name': 'demo', 'default_branch': 'main', 'provider': 'other'},
            'identifiers': {'prefix': 'TASK', 'sequence_width': 3},
            'paths': {
                'bundle': str(BUNDLE_ROOT),
                'instructions': 'AGENTS.md',
                'active': str(instance_root / 'active'),
                'archive': str(instance_root / 'archive'),
                'template': str(BUNDLE_ROOT / 'templates/task'),
                'index': str(instance_root / 'index.yaml'),
            },
        }
        config.update(config_overrides)
        (instance_root / 'config.yaml').write_text(
            yaml.safe_dump(config, sort_keys=False), encoding='utf-8'
        )
        return instance_root

    def _run(self, repo_root: Path, instance_root: Path, *extra_args: str) -> tuple[int, str, str]:
        argv = [
            '--repo-root', str(repo_root),
            '--instance-root', str(instance_root),
            *extra_args,
        ]
        return run_cli(new_task, argv)

    def test_creates_a_task_and_updates_the_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            instance_root = self._make_instance(repo_root)
            year = datetime.now().year

            code, out, err = self._run(
                repo_root, instance_root, '--slug', 'demo-feature', '--title', 'Demo feature',
            )

            self.assertEqual(code, 0, err)
            task_dir = instance_root / 'active' / f'TASK-{year}-001-demo-feature'
            self.assertTrue(task_dir.is_dir())
            self.assertIn(f'Created {task_dir}', out)
            index_text = (instance_root / 'index.yaml').read_text(encoding='utf-8')
            self.assertIn('demo-feature', index_text)

    def test_rejects_a_non_kebab_case_slug(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            instance_root = self._make_instance(repo_root)

            code, out, err = self._run(
                repo_root, instance_root, '--slug', 'Not_Kebab', '--title', 'x',
            )

            self.assertEqual(code, 1)
            self.assertIn('kebab-case', err)
            self.assertEqual(list((instance_root / 'active').iterdir()), [])

    def test_dry_run_creates_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            instance_root = self._make_instance(repo_root)

            code, out, err = self._run(
                repo_root, instance_root,
                '--slug', 'dry-run-demo', '--title', 'Dry run demo', '--dry-run',
            )

            self.assertEqual(code, 0, err)
            self.assertIn('Would create', out)
            self.assertEqual(list((instance_root / 'active').iterdir()), [])

    def test_duplicate_explicit_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            instance_root = self._make_instance(repo_root)
            explicit_id = f'TASK-{datetime.now().year}-001'

            code, _, err = self._run(
                repo_root, instance_root,
                '--slug', 'first-task', '--title', 'First', '--id', explicit_id,
            )
            self.assertEqual(code, 0, err)

            code, _, err = self._run(
                repo_root, instance_root,
                '--slug', 'second-task', '--title', 'Second', '--id', explicit_id,
            )

            self.assertEqual(code, 1)
            self.assertIn('already in use', err)

    def test_ids_are_allocated_sequentially(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            instance_root = self._make_instance(repo_root)
            year = datetime.now().year

            for slug in ('first-task', 'second-task'):
                code, _, err = self._run(repo_root, instance_root, '--slug', slug, '--title', slug)
                self.assertEqual(code, 0, err)

            self.assertTrue(
                (instance_root / 'active' / f'TASK-{year}-001-first-task').is_dir()
            )
            self.assertTrue(
                (instance_root / 'active' / f'TASK-{year}-002-second-task').is_dir()
            )

    def test_every_type_gets_the_same_full_artifact_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            instance_root = self._make_instance(repo_root)
            year = datetime.now().year

            code, out, err = self._run(
                repo_root, instance_root,
                '--slug', 'docs-only', '--title', 'Docs', '--type', 'documentation',
            )

            self.assertEqual(code, 0, err)
            task_dir = instance_root / 'active' / f'TASK-{year}-001-docs-only'
            self.assertEqual(
                sorted(p.name for p in task_dir.iterdir() if p.is_file()),
                sorted(validate.ACTIVE_REQUIRED_FILES),
            )
            self.assertTrue((task_dir / 'evidence' / 'screenshots').is_dir())
            self.assertNotIn('Lite profile', out)

    def test_missing_config_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            instance_root = repo_root / '.project-tasks'
            instance_root.mkdir()

            code, out, err = self._run(
                repo_root, instance_root, '--slug', 'demo', '--title', 'Demo',
            )

            self.assertEqual(code, 1)
            self.assertIn('missing', err)
            self.assertIn('run scripts/init.py first', err)


class NewTaskHelperTests(unittest.TestCase):
    def test_existing_ids_scans_active_and_archive_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / 'active' / 'TASK-2026-001-demo'
            archive = root / 'archive' / 'TASK-2025-002-demo'
            active.mkdir(parents=True)
            archive.mkdir(parents=True)
            (active / 'task.yaml').write_text('id: TASK-2026-001\n', encoding='utf-8')
            (archive / 'task.yaml').write_text('id: TASK-2025-002\n', encoding='utf-8')

            found = new_task.existing_ids(root / 'active', root / 'archive')

            self.assertEqual(found, {'TASK-2026-001', 'TASK-2025-002'})

    def test_existing_ids_ignores_missing_and_malformed_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / 'active'
            active.mkdir()
            malformed = active / 'TASK-2026-001-bad'
            malformed.mkdir()
            (malformed / 'task.yaml').write_text('id: [unterminated\n', encoding='utf-8')

            found = new_task.existing_ids(active, root / 'missing-archive')

            self.assertEqual(found, set())

    def test_remaining_placeholders_lists_unfilled_tokens_by_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            task_dir = Path(directory) / 'TASK-2026-001-demo'
            task_dir.mkdir()
            (task_dir / 'task.md').write_text(
                '# Demo\n\n__REQUIRED_CRITERION_TITLE__\n__REQUIRED_COMMAND__\n',
                encoding='utf-8',
            )
            (task_dir / 'task.yaml').write_text('id: TASK-2026-001\n', encoding='utf-8')
            (task_dir / 'notes.txt').write_text('__REQUIRED_IGNORED__\n', encoding='utf-8')

            found = new_task.remaining_placeholders(task_dir)

            self.assertEqual(
                found['task.md'], ['__REQUIRED_COMMAND__', '__REQUIRED_CRITERION_TITLE__']
            )
            self.assertNotIn('task.yaml', found)
            self.assertNotIn('notes.txt', found)


class InitEndToEndTests(unittest.TestCase):
    def _copy_bundle(self, repo_root: Path) -> Path:
        bundle_root = repo_root / '.tasks'
        shutil.copytree(BUNDLE_ROOT / 'templates', bundle_root / 'templates')
        return bundle_root

    def _run(self, repo_root: Path, *extra_args: str) -> tuple[int, str, str]:
        return run_cli(init, ['--repo-root', str(repo_root), *extra_args])

    def test_creates_a_live_instance_with_agents_file_and_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            self._copy_bundle(repo_root)

            code, out, err = self._run(
                repo_root,
                '--repository-name', 'demo', '--default-branch', 'main',
                '--provider', 'other',
            )

            self.assertEqual(code, 0, err)
            config = yaml.safe_load(
                (repo_root / '.project-tasks' / 'config.yaml').read_text(encoding='utf-8')
            )
            self.assertEqual(config['mode'], 'live')
            self.assertEqual(config['repository']['name'], 'demo')
            self.assertEqual(config['paths']['instructions'], 'AGENTS.md')
            agents_text = (repo_root / 'AGENTS.md').read_text(encoding='utf-8')
            self.assertIn('## Task system', agents_text)
            self.assertTrue(
                (repo_root / '.github' / 'workflows' / 'validate-task-system.yml').is_file()
            )
            self.assertTrue((repo_root / '.project-tasks' / 'index.yaml').is_file())

    def test_a_new_repository_also_gets_the_example_instructions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            self._copy_bundle(repo_root)

            code, _, err = self._run(
                repo_root, '--repository-name', 'demo', '--default-branch', 'main',
                '--provider', 'other',
            )

            self.assertEqual(code, 0, err)
            example = repo_root / 'AGENTS.example.md'
            self.assertTrue(example.is_file())
            self.assertIn('## Project identity', example.read_text(encoding='utf-8'))

    def test_an_existing_agents_file_gets_no_example(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            self._copy_bundle(repo_root)
            existing = '# AGENTS.md\n\nHouse rules.\n'
            (repo_root / 'AGENTS.md').write_text(existing, encoding='utf-8')

            code, _, err = self._run(
                repo_root, '--repository-name', 'demo', '--default-branch', 'main',
                '--provider', 'other',
            )

            self.assertEqual(code, 0, err)
            self.assertFalse((repo_root / 'AGENTS.example.md').exists())
            text = (repo_root / 'AGENTS.md').read_text(encoding='utf-8')
            self.assertTrue(text.startswith(existing), text[:60])
            self.assertIn('## Task system', text)

    def test_rerunning_keeps_the_existing_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            self._copy_bundle(repo_root)
            first_code, _, first_err = self._run(
                repo_root, '--repository-name', 'demo', '--default-branch', 'main',
                '--provider', 'other',
            )
            self.assertEqual(first_code, 0, first_err)
            config_path = repo_root / '.project-tasks' / 'config.yaml'
            edited = config_path.read_text(encoding='utf-8').replace(
                'name: "demo"', 'name: "renamed-by-hand"'
            )
            config_path.write_text(edited, encoding='utf-8')

            code, out, err = self._run(
                repo_root, '--repository-name', 'other-name', '--default-branch', 'main',
                '--provider', 'other',
            )

            self.assertEqual(code, 0, err)
            self.assertIn('already initialized', out)
            self.assertEqual(config_path.read_text(encoding='utf-8'), edited)
            agents_text = (repo_root / 'AGENTS.md').read_text(encoding='utf-8')
            self.assertEqual(agents_text.count('## Task system'), 1)

    def test_dry_run_reports_actions_without_writing_anything(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            self._copy_bundle(repo_root)

            code, out, err = self._run(
                repo_root, '--repository-name', 'demo', '--default-branch', 'main',
                '--provider', 'other', '--dry-run',
            )

            self.assertEqual(code, 0, err)
            lines = [line for line in out.splitlines() if line]
            self.assertTrue(lines)
            self.assertTrue(all(line.startswith('Would ') for line in lines))
            self.assertFalse((repo_root / '.project-tasks').exists())
            self.assertFalse((repo_root / 'AGENTS.md').exists())

    def test_rejects_an_instance_root_inside_the_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            self._copy_bundle(repo_root)

            code, out, err = self._run(
                repo_root, '--instance-root', '.tasks/state',
                '--repository-name', 'demo', '--default-branch', 'main',
                '--provider', 'other',
            )

            self.assertEqual(code, 1)
            self.assertIn('must stay outside the bundle', err)

    def test_missing_bundle_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)

            code, out, err = self._run(
                repo_root, '--repository-name', 'demo', '--default-branch', 'main',
                '--provider', 'other',
            )

            self.assertEqual(code, 1)
            self.assertIn('bundle not found', err)


class InitDetectionTests(unittest.TestCase):
    def test_git_returns_none_outside_a_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)

            self.assertIsNone(init.git(repo_root, 'rev-parse', '--show-toplevel'))

    def test_git_returns_none_when_repo_root_does_not_exist(self) -> None:
        missing = Path('/nonexistent-path-for-init-git-tests')

        self.assertIsNone(init.git(missing, 'rev-parse', '--show-toplevel'))

    def test_detect_repository_name_falls_back_to_directory_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)

            self.assertEqual(init.detect_repository_name(repo_root), repo_root.name)

    def test_detect_default_branch_falls_back_to_main(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)

            self.assertEqual(init.detect_default_branch(repo_root), 'main')

    def test_detect_provider_falls_back_to_other_without_a_remote(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)

            self.assertEqual(init.detect_provider(repo_root), 'other')

    @unittest.skipUnless(_git_available(), 'git is not installed')
    def test_detect_repository_name_and_provider_from_github_remote(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            subprocess.run(['git', 'init', '-q'], cwd=repo_root, check=True)
            subprocess.run(
                ['git', 'remote', 'add', 'origin', 'https://github.com/acme/widget.git'],
                cwd=repo_root, check=True,
            )

            self.assertEqual(init.detect_repository_name(repo_root), 'widget')
            self.assertEqual(init.detect_provider(repo_root), 'github')

    @unittest.skipUnless(_git_available(), 'git is not installed')
    def test_detect_provider_is_other_for_a_non_github_remote(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            subprocess.run(['git', 'init', '-q'], cwd=repo_root, check=True)
            subprocess.run(
                ['git', 'remote', 'add', 'origin', 'https://gitlab.com/acme/widget.git'],
                cwd=repo_root, check=True,
            )

            self.assertEqual(init.detect_provider(repo_root), 'other')

    def test_replace_once_requires_exactly_one_match(self) -> None:
        self.assertEqual(init.replace_once('a=1', 'a=1', 'a=2', 'demo'), 'a=2')
        with self.assertRaisesRegex(init.InitFailure, 'found 0'):
            init.replace_once('a=1', 'missing', 'x', 'demo')
        with self.assertRaisesRegex(init.InitFailure, 'found 2'):
            init.replace_once('a=1 a=1', 'a=1', 'a=2', 'demo')

    def test_task_system_section_extracts_up_to_the_next_heading(self) -> None:
        template = (
            '# AGENTS.md\n\n## Task system\n\nFollow the rules.\n\n'
            '## Another section\n\nMore.\n'
        )

        section = init.task_system_section(template)

        self.assertEqual(section, '## Task system\n\nFollow the rules.\n')

    def test_task_system_section_missing_heading_raises(self) -> None:
        with self.assertRaisesRegex(init.InitFailure, 'Task system'):
            init.task_system_section('# AGENTS.md\n\nNo task-system section here.\n')


class UpgradeHelperTests(unittest.TestCase):
    def test_version_tuple_parses_dotted_versions(self) -> None:
        self.assertEqual(upgrade.version_tuple('4.0.0'), (4, 0, 0))
        self.assertEqual(upgrade.version_tuple(' 4.1.2 '), (4, 1, 2))

    def test_version_tuple_rejects_malformed_values(self) -> None:
        with self.assertRaisesRegex(upgrade.UpgradeFailure, 'malformed version'):
            upgrade.version_tuple('not-a-version')

    def test_posix_returns_a_relative_path_inside_the_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            target = repo_root / '.tasks' / 'active'

            self.assertEqual(upgrade.posix(repo_root, target), '.tasks/active')

    def test_posix_returns_an_absolute_path_outside_the_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory) / 'repo'
            repo_root.mkdir()
            outside = Path(directory) / 'elsewhere'

            self.assertEqual(upgrade.posix(repo_root, outside), outside.resolve().as_posix())

    def test_locate_config_prefers_the_instance_over_the_legacy_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            bundle_root = repo_root / '.tasks'
            instance_root = repo_root / '.project-tasks'
            bundle_root.mkdir()
            instance_root.mkdir()
            (instance_root / 'config.yaml').write_text('mode: live\n', encoding='utf-8')
            (bundle_root / 'config.yaml').write_text('mode: live\n', encoding='utf-8')

            path, legacy = upgrade.locate_config(bundle_root, instance_root)

            self.assertEqual(path, instance_root / 'config.yaml')
            self.assertFalse(legacy)

    def test_locate_config_falls_back_to_a_legacy_live_bundle_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            bundle_root = repo_root / '.tasks'
            instance_root = repo_root / '.project-tasks'
            bundle_root.mkdir()
            (bundle_root / 'config.yaml').write_text('mode: live\n', encoding='utf-8')

            path, legacy = upgrade.locate_config(bundle_root, instance_root)

            self.assertEqual(path, bundle_root / 'config.yaml')
            self.assertTrue(legacy)

    def test_locate_config_ignores_a_pristine_template_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            bundle_root = repo_root / '.tasks'
            instance_root = repo_root / '.project-tasks'
            bundle_root.mkdir()
            (bundle_root / 'config.yaml').write_text('mode: template\n', encoding='utf-8')

            with self.assertRaisesRegex(upgrade.UpgradeFailure, 'no live configuration'):
                upgrade.locate_config(bundle_root, instance_root)

    def test_rewrite_commands_updates_instance_root_flags(self) -> None:
        repo_root = Path('/repo')
        bundle_root = repo_root / '.tasks'
        instance_root = repo_root / '.project-tasks'
        config = {
            'commands': {
                'generate_index': (
                    'python3 .tasks/scripts/generate_index.py --instance-root .tasks'
                ),
                'validate': (
                    'python3 .tasks/scripts/validate.py --instance-root .tasks/active'
                ),
            }
        }

        changed = upgrade.rewrite_commands(config, repo_root, bundle_root, instance_root)

        self.assertIn('.project-tasks', config['commands']['validate'])
        self.assertIn('.project-tasks', config['commands']['generate_index'])
        self.assertEqual(sorted(changed), ['commands.generate_index', 'commands.validate'])

    def test_rewrite_commands_updates_legacy_paths_beside_instance_paths(self) -> None:
        repo_root = Path('/repo')
        bundle_root = repo_root / '.tasks'
        instance_root = repo_root / '.project-tasks'
        config = {
            'commands': {
                'validate': (
                    'python3 .tasks/scripts/validate.py --instance-root .project-tasks '
                    '--index .tasks/index.yaml'
                )
            }
        }

        changed = upgrade.rewrite_commands(config, repo_root, bundle_root, instance_root)

        self.assertNotIn('.tasks/index.yaml', config['commands']['validate'])
        self.assertIn('.project-tasks/index.yaml', config['commands']['validate'])
        self.assertEqual(changed, ['commands.validate'])

    def test_rewrite_commands_updates_paths_before_shell_delimiters(self) -> None:
        repo_root = Path('/repo')
        bundle_root = repo_root / '.tasks'
        instance_root = repo_root / '.project-tasks'
        config = {'commands': {'count': '(ls .tasks/active) | wc -l'}}

        changed = upgrade.rewrite_commands(config, repo_root, bundle_root, instance_root)

        self.assertEqual(config['commands']['count'], '(ls .project-tasks/active) | wc -l')
        self.assertEqual(changed, ['commands.count'])

    def test_rewrite_commands_is_a_noop_without_bundle_references(self) -> None:
        repo_root = Path('/repo')
        bundle_root = repo_root / '.tasks'
        instance_root = repo_root / '.project-tasks'
        config = {'commands': {'lint': 'ruff check .'}}

        changed = upgrade.rewrite_commands(config, repo_root, bundle_root, instance_root)

        self.assertEqual(changed, [])
        self.assertEqual(config['commands']['lint'], 'ruff check .')


class UpgradeEndToEndTests(unittest.TestCase):
    def _copy_bundle(self, repo_root: Path) -> Path:
        bundle_root = repo_root / '.tasks'
        shutil.copytree(BUNDLE_ROOT / 'templates', bundle_root / 'templates')
        shutil.copyfile(BUNDLE_ROOT / 'VERSION', bundle_root / 'VERSION')
        return bundle_root

    def _run(self, repo_root: Path, *extra_args: str) -> tuple[int, str, str]:
        return run_cli(upgrade, ['--repo-root', str(repo_root), *extra_args])

    def _base_config(self, version: str) -> dict:
        return {
            'schema_version': version,
            'task_system_version': version,
            'mode': 'live',
            'paths': {
                'bundle': '.tasks',
                'instructions': 'AGENTS.md',
                'active': '.project-tasks/active',
                'archive': '.project-tasks/archive',
                'template': '.tasks/templates/task',
                'index': '.project-tasks/index.yaml',
            },
        }

    def test_moves_legacy_live_state_out_of_the_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            bundle_root = self._copy_bundle(repo_root)
            installed_version = (bundle_root / 'VERSION').read_text(encoding='utf-8').strip()
            legacy_config = {
                'schema_version': '3.0.0',
                'task_system_version': '3.0.0',
                'mode': 'live',
                'timezone': 'UTC',
                'repository': {'name': 'demo', 'default_branch': 'main', 'provider': 'other'},
                'paths': {
                    'active': '.tasks/active',
                    'archive': '.tasks/archive',
                    'index': '.tasks/index.yaml',
                },
            }
            (bundle_root / 'config.yaml').write_text(
                yaml.safe_dump(legacy_config, sort_keys=False), encoding='utf-8'
            )
            (bundle_root / 'active').mkdir()
            (bundle_root / 'archive').mkdir()
            (bundle_root / 'index.yaml').write_text(
                'active: []\narchived: []\n', encoding='utf-8'
            )

            code, out, err = self._run(repo_root)

            self.assertEqual(code, 0, err)
            self.assertFalse((bundle_root / 'config.yaml').exists())
            self.assertFalse((bundle_root / 'active').exists())
            instance_root = repo_root / '.project-tasks'
            new_config = yaml.safe_load(
                (instance_root / 'config.yaml').read_text(encoding='utf-8')
            )
            self.assertEqual(new_config['task_system_version'], installed_version)
            self.assertEqual(new_config['paths']['active'], '.project-tasks/active')
            self.assertEqual(new_config['paths']['bundle'], '.tasks')
            self.assertTrue((instance_root / 'config.yaml.bak').is_file())

    def test_already_current_installation_is_a_noop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            self._copy_bundle(repo_root)
            instance_root = repo_root / '.project-tasks'
            instance_root.mkdir()
            installed = (BUNDLE_ROOT / 'VERSION').read_text(encoding='utf-8').strip()
            original_text = yaml.safe_dump(self._base_config(installed), sort_keys=False)
            (instance_root / 'config.yaml').write_text(original_text, encoding='utf-8')

            code, out, err = self._run(repo_root)

            self.assertEqual(code, 0, err)
            self.assertIn(f'Already at version {installed}', out)
            self.assertEqual(
                (instance_root / 'config.yaml').read_text(encoding='utf-8'), original_text
            )

    def test_downgrade_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            self._copy_bundle(repo_root)
            instance_root = repo_root / '.project-tasks'
            instance_root.mkdir()
            installed = (BUNDLE_ROOT / 'VERSION').read_text(encoding='utf-8').strip()
            newer = f'{int(installed.split(".")[0]) + 1}.0.0'
            (instance_root / 'config.yaml').write_text(
                yaml.safe_dump(self._base_config(newer), sort_keys=False), encoding='utf-8'
            )

            code, out, err = self._run(repo_root)

            self.assertEqual(code, 1)
            self.assertIn('does not downgrade', err)

    def test_dry_run_leaves_the_config_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            self._copy_bundle(repo_root)
            instance_root = repo_root / '.project-tasks'
            instance_root.mkdir()
            original_text = yaml.safe_dump(self._base_config('3.0.0'), sort_keys=False)
            (instance_root / 'config.yaml').write_text(original_text, encoding='utf-8')

            code, out, err = self._run(repo_root, '--dry-run')

            self.assertEqual(code, 0, err)
            self.assertIn('dry run', out)
            self.assertEqual(
                (instance_root / 'config.yaml').read_text(encoding='utf-8'), original_text
            )

    def test_missing_bundle_version_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            (repo_root / '.tasks').mkdir()

            code, out, err = self._run(repo_root)

            self.assertEqual(code, 1)
            self.assertIn('no bundle at', err)


class EndToEndPipelineTests(unittest.TestCase):
    def test_freshly_created_task_fails_validation_until_content_is_filled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            bundle_root = repo_root / '.tasks'
            shutil.copytree(BUNDLE_ROOT, bundle_root)

            init_code, _, init_err = run_cli(
                init,
                [
                    '--repo-root', str(repo_root),
                    '--repository-name', 'demo',
                    '--default-branch', 'main',
                    '--provider', 'other',
                ],
            )
            self.assertEqual(init_code, 0, init_err)

            new_task_code, new_task_out, new_task_err = run_cli(
                new_task,
                [
                    '--repo-root', str(repo_root),
                    '--slug', 'demo-feature',
                    '--title', 'Demo feature',
                ],
            )
            self.assertEqual(new_task_code, 0, new_task_err)
            self.assertIn('placeholder(s) still need content', new_task_out)

            errors: list[str] = []
            config_schema = validate.load_json(bundle_root / 'schemas/config.schema.json')
            task_schema = validate.load_json(bundle_root / 'schemas/task.schema.json')
            validate.validate_instance(
                repo_root,
                repo_root / '.project-tasks',
                config_schema,
                task_schema,
                errors,
            )

            self.assertTrue(
                any('unreplaced placeholder' in error for error in errors), errors
            )


class ValidateHelperAdditionalTests(unittest.TestCase):
    def test_digest_normalizes_crlf_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            unix_path = Path(directory) / 'unix.md'
            windows_path = Path(directory) / 'windows.md'
            unix_path.write_bytes(b'line one\nline two\n')
            windows_path.write_bytes(b'line one\r\nline two\r\n')

            self.assertEqual(validate.digest(unix_path), validate.digest(windows_path))

    def test_contains_placeholder_detects_nested_values(self) -> None:
        self.assertTrue(validate.contains_placeholder({'a': [{'b': '__REQUIRED_X__'}]}))
        self.assertTrue(validate.contains_placeholder(['ok', '__REQUIRED_Y__']))
        self.assertFalse(validate.contains_placeholder({'a': ['ok', {'b': 'fine'}]}))
        self.assertFalse(validate.contains_placeholder(42))

    def test_select_modes_validates_both_when_roots_differ(self) -> None:
        result = validate.select_modes(Path('.tasks'), Path('.project-tasks'), False, False)

        self.assertEqual(result, (True, True))

    def test_select_modes_respects_explicit_flags_even_with_the_same_root(self) -> None:
        self.assertEqual(
            validate.select_modes(Path('.tasks'), Path('.tasks'), True, False), (True, False)
        )
        self.assertEqual(
            validate.select_modes(Path('.tasks'), Path('.tasks'), False, True), (False, True)
        )


if __name__ == '__main__':
    unittest.main()

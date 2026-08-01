from __future__ import annotations

import importlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

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
        """
        Create a synthetic task bundle with the required template files and directories.
        
        Parameters:
        	repo_root (Path): Repository root in which to create the bundle.
        	paths (dict[str, str] | None): Optional path configuration for the generated template.
        
        Returns:
        	Path: The created bundle root.
        """
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
        """
        Validate a task bundle and collect any validation errors.
        
        Parameters:
        	repo_root (Path): Root directory of the repository.
        	bundle_root (Path): Root directory of the task bundle.
        
        Returns:
        	list[str]: Validation error messages.
        """
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

    def test_pruned_bundle_validates_without_install_only_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            bundle_root = self._make_bundle(repo_root)
            for name in init.INSTALL_ONLY_PATHS:
                target = bundle_root / name
                if target.is_dir():
                    for child in sorted(target.rglob('*'), reverse=True):
                        child.unlink() if child.is_file() else child.rmdir()
                    target.rmdir()
                elif target.is_file():
                    target.unlink()
            (bundle_root / validate.BUNDLE_PRUNED_MARKER).write_text(
                'pruned\n', encoding='utf-8'
            )

            self.assertEqual(self._validate(repo_root, bundle_root), [])

    def test_unpruned_bundle_missing_install_files_still_fails(self) -> None:
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
        """
        Scan the selected repository paths for unresolved merge conflicts.
        
        Parameters:
        	root (Path): Repository root to scan.
        	roots (list[Path] | None): Paths to scan within the repository; defaults to the root.
        
        Returns:
        	list[str]: Conflict descriptions found during the scan.
        """
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


class CiGatingTests(unittest.TestCase):
    def _merge_ready_task(self) -> dict:
        """
        Create a completed task record ready for merge-related validation.
        
        Returns:
        	dict: A task record with passed acceptance criteria, completed plan steps,
        		a non-created pull request, and merge metadata.
        """
        return {
            'status': 'completed',
            'acceptance_criteria': [
                {'id': 'AC-01', 'status': 'passed', 'evidence': ['verification.md']}
            ],
            'plan_steps': [{'id': 'PLAN-01', 'status': 'completed', 'supports': ['AC-01']}],
            'pull_request': {'state': 'not_created', 'checks': {'status': 'not_started'}},
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
        """
        Render the initialization configuration template with test-specific defaults.
        
        Parameters:
        	overrides: Configuration values that replace the default test values.
        
        Returns:
        	str: The rendered configuration text.
        """
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


class InstructionFileTests(unittest.TestCase):
    def _check(self, contents: str | None, version: str = '4.0.0') -> list[str]:
        """Validate instruction-file contents against a temporary task-system layout.
        
        Parameters:
        	contents (str | None): Instruction-file text to validate, or None to omit the file.
        	version (str): Expected task-system version.
        
        Returns:
        	list[str]: Validation error messages."""
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


class LiteProfileTests(unittest.TestCase):
    CONFIG = {'lifecycle': {'lite_profile_task_types': ['documentation', 'dependency']}}

    def test_profile_selection_follows_task_type(self) -> None:
        self.assertTrue(
            validate.uses_lite_profile({'type': 'documentation'}, self.CONFIG)
        )
        self.assertFalse(validate.uses_lite_profile({'type': 'feature'}, self.CONFIG))
        self.assertFalse(validate.uses_lite_profile({'type': 'documentation'}, {}))

    def _artifact_errors(self, task_type: str, files: tuple[str, ...]) -> list[str]:
        """
        Validate a synthetic task directory and return its artifact validation errors.
        
        Parameters:
            task_type (str): The configured type of task to validate.
            files (tuple[str, ...]): Artifact file names to create in the task directory.
        
        Returns:
            list[str]: Validation error messages.
        """
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
                self.CONFIG,
                errors,
            )
            return errors

    def test_lite_task_needs_only_the_reduced_set(self) -> None:
        self.assertEqual(
            self._artifact_errors('documentation', validate.LITE_REQUIRED_FILES), []
        )

    def test_full_task_still_needs_every_artifact(self) -> None:
        errors = self._artifact_errors('feature', validate.LITE_REQUIRED_FILES)

        self.assertTrue(
            any('assessment.md' in error for error in errors), errors
        )
        self.assertTrue(
            any('implementation-log.md' in error for error in errors), errors
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

    def test_lite_types_are_read_from_config(self) -> None:
        config = {'lifecycle': {'lite_profile_task_types': ['documentation']}}

        self.assertEqual(new_task.lite_profile_types(config), {'documentation'})
        self.assertEqual(new_task.lite_profile_types({}), set())

    def test_pruning_leaves_exactly_the_lite_artifact_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            task_dir = Path(directory) / 'TASK-2026-001-demo'
            shutil.copytree(BUNDLE_ROOT / 'templates/task', task_dir)

            removed = new_task.prune_to_lite(task_dir)

            self.assertEqual(
                sorted(p.name for p in task_dir.iterdir()),
                sorted(validate.LITE_REQUIRED_FILES),
            )
            self.assertIn('assessment.md', removed)
            self.assertIn('evidence/', removed)

    def test_lite_file_list_matches_the_validator(self) -> None:
        self.assertEqual(
            sorted(new_task.LITE_FILES), sorted(validate.LITE_REQUIRED_FILES)
        )

    def test_timestamp_falls_back_when_timezone_is_unavailable(self) -> None:
        value = new_task.timestamp('Not/AZone')

        self.assertRegex(value, r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')


class InstallInstructionsTests(unittest.TestCase):
    TEMPLATE = (
        '# AGENTS.md\n\n## Project identity\n\n- Project: `__REQUIRED_PROJECT_NAME__`\n\n'
        '## Task system\n\nWork follows `.tasks/AGENTS.md` and `.project-tasks/config.yaml`.\n'
    )

    def _install(self, existing: str | None, force: bool = False) -> tuple[str, list[str]]:
        """Install task-system instructions into a temporary AGENTS.md file.
        
        Parameters:
        	existing (str | None): Initial file contents, or None if the file should start absent.
        	force (bool): Whether to replace existing instructions.
        
        Returns:
        	tuple[str, list[str]]: The resulting file contents and recorded installation actions.
        """
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'AGENTS.md'
            if existing is not None:
                path.write_text(existing, encoding='utf-8')
            actions: list[str] = []
            init.install_instructions(
                path, self.TEMPLATE, '.tasks', '.project-tasks', 'python3',
                force, False, actions,
            )
            return path.read_text(encoding='utf-8'), actions

    def test_absent_file_gets_the_full_template(self) -> None:
        text, actions = self._install(None)

        self.assertIn('## Project identity', text)
        self.assertTrue(any('write' in action for action in actions), actions)

    def test_existing_file_is_appended_to_not_replaced(self) -> None:
        existing = '# AGENTS.md\n\nOur house rules. Do not lose these.\n'

        text, actions = self._install(existing)

        self.assertIn('Our house rules. Do not lose these.', text)
        self.assertIn('## Task system', text)
        self.assertNotIn('## Project identity', text)
        self.assertTrue(any('append' in action for action in actions), actions)

    def test_already_installed_file_is_left_alone(self) -> None:
        existing = '# AGENTS.md\n\nSee `.tasks/AGENTS.md` for the lifecycle.\n'

        text, actions = self._install(existing)

        self.assertEqual(text, existing)
        self.assertTrue(any('skip' in action for action in actions), actions)

    def test_force_replaces_the_file(self) -> None:
        text, actions = self._install('# AGENTS.md\n\nOld.\n', force=True)

        self.assertNotIn('Old.', text)
        self.assertTrue(any('overwrite' in action for action in actions), actions)


class UpgradeTests(unittest.TestCase):
    def test_missing_keys_are_found_at_any_depth(self) -> None:
        template = {'a': 1, 'nested': {'kept': 2, 'added': 3}}
        live = {'a': 9, 'nested': {'kept': 8}}

        found = upgrade.missing_keys(template, live)

        self.assertEqual(found, [(('nested', 'added'), 3)])

    def test_upgrade_defaults_override_template_values(self) -> None:
        template = {'lifecycle': {'lite_profile_task_types': ['documentation']}}

        found = upgrade.missing_keys(template, {'lifecycle': {}})

        self.assertEqual(found, [(('lifecycle', 'lite_profile_task_types'), [])])

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

    def test_downgrade_is_refused(self) -> None:
        self.assertGreater(upgrade.version_tuple('5.0.0'), upgrade.version_tuple('4.0.0'))
        self.assertEqual(upgrade.version_tuple('4.0.0'), upgrade.version_tuple('4.0.0'))

    def test_instruction_file_is_detected_from_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)

            self.assertEqual(upgrade.detect_instruction_file(repo_root), 'AGENTS.md')
            (repo_root / 'CLAUDE.md').write_text('rules\n', encoding='utf-8')
            self.assertEqual(upgrade.detect_instruction_file(repo_root), 'CLAUDE.md')


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

    def test_init_writes_the_full_template_over_an_empty_file(self) -> None:
        template = (
            '# AGENTS.md\n\n## Project identity\n\n- Project: `x`\n\n'
            '## Task system\n\nFollows `.tasks/AGENTS.md` and `.project-tasks/config.yaml`.\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'AGENTS.md'
            path.write_text('\n\n  \n', encoding='utf-8')
            actions: list[str] = []

            init.install_instructions(
                path, template, '.tasks', '.project-tasks', 'python3', False, False, actions
            )

            text = path.read_text(encoding='utf-8')
            self.assertIn('## Project identity', text)
            self.assertFalse(text.startswith('\n'))


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


if __name__ == '__main__':
    unittest.main()

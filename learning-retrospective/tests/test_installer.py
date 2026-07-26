"""Tests for transactional hook installation."""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent
INSTALLER_PATH = TESTS_DIR.parents[1] / "install.py"
SPEC = importlib.util.spec_from_file_location("learning_retrospective_installer", INSTALLER_PATH)
INSTALLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)


class HookInstallerTest(unittest.TestCase):
    def test_hook_install_preserves_active_config_and_updates_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hook_dir = root / "hooks"
            backup_root = root / "backups"
            hook_dir.mkdir()
            active = hook_dir / INSTALLER.ACTIVE_REVIEW_CONFIG
            active.write_text('{"preferred_model":"local-choice"}', encoding="utf-8")

            result = INSTALLER.install_hook_files(
                "codex", hook_dir, backup_root, "test-success"
            )

            self.assertEqual(
                active.read_text(encoding="utf-8"),
                '{"preferred_model":"local-choice"}',
            )
            for target in result["targets"]:
                self.assertTrue(target.is_file())
            self.assertNotIn(active, result["targets"])

    def test_security_notes_copies_are_identical(self):
        # Both copies are deliberate: the repo root for GitHub visibility, the
        # skill folder for self-containment of the installed artifact. This
        # guard turns silent drift between them into a test failure.
        root = TESTS_DIR.parents[1] / "SECURITY_NOTES.md"
        skill = TESTS_DIR.parents[0] / "SECURITY_NOTES.md"
        self.assertEqual(
            root.read_bytes(), skill.read_bytes(),
            "SECURITY_NOTES.md at repo root and in the skill folder must be "
            "byte-identical; edit both together",
        )

    def test_claude_config_omits_keys_that_detector_cannot_honor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hook_dir = root / "hooks"
            hook_dir.mkdir()

            INSTALLER.install_hook_files(
                "claude", hook_dir, root / "backups", "test-claude-config"
            )

            for name in (
                INSTALLER.ACTIVE_REVIEW_CONFIG,
                INSTALLER.INSTALLED_REVIEW_CONFIG_EXAMPLE,
            ):
                config = json.loads(
                    (hook_dir / name).read_text(encoding="utf-8")
                )
                self.assertEqual(
                    sorted(config),
                    sorted(INSTALLER.CLAUDE_REVIEW_CONFIG_KEYS),
                    f"{name} must not advertise Codex-only knobs",
                )

    def test_codex_config_keeps_every_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hook_dir = root / "hooks"
            hook_dir.mkdir()

            INSTALLER.install_hook_files(
                "codex", hook_dir, root / "backups", "test-codex-config"
            )

            source = json.loads(
                (INSTALLER.SKILL_SRC / "hooks" / INSTALLER.REVIEW_CONFIG_EXAMPLE)
                .read_text(encoding="utf-8")
            )
            installed = json.loads(
                (hook_dir / INSTALLER.ACTIVE_REVIEW_CONFIG)
                .read_text(encoding="utf-8")
            )
            self.assertEqual(installed, source)
            self.assertIn("review_backend", installed)

    def test_hook_install_rolls_back_partial_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hook_dir = root / "hooks"
            backup_root = root / "backups"
            hook_dir.mkdir()
            target_names = [
                *INSTALLER.HOOK_SUPPORT_FILES["codex"],
                INSTALLER.INSTALLED_REVIEW_CONFIG_EXAMPLE,
                INSTALLER.ACTIVE_REVIEW_CONFIG,
                INSTALLER.HOOK_SCRIPTS["codex"],
            ]
            before = {}
            for name in target_names:
                content = f"old-{name}"
                (hook_dir / name).write_text(content, encoding="utf-8")
                before[name] = content

            original_replace = os.replace
            calls = {"count": 0}

            def fail_second_replace(source, target):
                calls["count"] += 1
                if calls["count"] == 2:
                    raise OSError("synthetic activation failure")
                return original_replace(source, target)

            with mock.patch.object(
                INSTALLER.os, "replace", side_effect=fail_second_replace
            ):
                with self.assertRaisesRegex(
                    OSError, "synthetic activation failure"
                ):
                    INSTALLER.install_hook_files(
                        "codex", hook_dir, backup_root, "test-rollback"
                    )

            for name, content in before.items():
                self.assertEqual(
                    (hook_dir / name).read_text(encoding="utf-8"),
                    content,
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)

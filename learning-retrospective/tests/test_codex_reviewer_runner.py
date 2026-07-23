"""Unit tests for the opt-in Codex CLI semantic-review backend."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent
RUNNER_PATH = TESTS_DIR.parent / "hooks" / "retry-reviewer-codex-cli.py"
SPEC = importlib.util.spec_from_file_location("retry_reviewer_codex_cli", RUNNER_PATH)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class CodexReviewerRunnerTest(unittest.TestCase):
    def test_find_rollout_matches_year_month_day_layout(self):
        session_id = "019f90b2-a6b5-7e23-a654-246f812df5e4"
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            session_dir = home / ".codex" / "sessions" / "2026" / "07" / "24"
            session_dir.mkdir(parents=True)
            rollout = session_dir / f"rollout-test-{session_id}.jsonl"
            rollout.write_text("{}\n", encoding="utf-8")
            with mock.patch.object(Path, "home", return_value=home):
                found = RUNNER.find_rollout(session_id)
        self.assertEqual(found, rollout)

    def test_find_rollout_honors_codex_home(self):
        session_id = "019f90b2-a6b5-7e23-a654-246f812df5e4"
        with tempfile.TemporaryDirectory() as directory:
            codex_home = Path(directory) / "custom-codex"
            session_dir = codex_home / "sessions" / "2026" / "07" / "24"
            session_dir.mkdir(parents=True)
            rollout = session_dir / f"rollout-test-{session_id}.jsonl"
            rollout.write_text("{}\n", encoding="utf-8")
            with mock.patch.dict(
                os.environ, {"CODEX_HOME": str(codex_home)}, clear=False
            ):
                found = RUNNER.find_rollout(session_id)
        self.assertEqual(found, rollout)

    def test_redact_masks_common_credentials_and_bounds_text(self):
        secrets = [
            "OPENAI_API_KEY=sk-proj-abcdefghijklmnop",
            "AWS_ACCESS_KEY_ID=AKIAABCDEFGHIJKLMNOP",
            "DATABASE_URL=postgres://alice:private@db.example/test",
            "Cookie: session=private-cookie",
            "//registry.npmjs.org/:_authToken=npm-private-token",
            "--api-key command-line-secret",
            "Authorization: Bearer abc.def",
            "password=hunter2",
        ]
        redacted = RUNNER.redact("\n".join(secrets), 2000)
        for secret in (
            "sk-proj-abcdefghijklmnop",
            "AKIAABCDEFGHIJKLMNOP",
            "alice:private",
            "private-cookie",
            "npm-private-token",
            "command-line-secret",
            "abc.def",
            "hunter2",
        ):
            self.assertNotIn(secret, redacted)
        self.assertIn("<redacted>", redacted)

    def test_parse_codex_output_captures_real_thread_id(self):
        stdout = "\n".join([
            json.dumps({"type": "thread.started", "thread_id": "review-thread-1"}),
            json.dumps({
                "type": "item.completed",
                "item": {"type": "agent_message", "text": '{"ok":true}'},
            }),
        ])
        thread_id, final_text, used_tools = RUNNER.parse_codex_output(stdout)
        self.assertEqual(thread_id, "review-thread-1")
        self.assertEqual(final_text, '{"ok":true}')
        self.assertFalse(used_tools)

    def test_parse_codex_output_rejects_tool_using_reviewer(self):
        stdout = "\n".join([
            json.dumps({"type": "thread.started", "thread_id": "review-thread-2"}),
            json.dumps({
                "type": "item.started",
                "item": {"type": "command_execution", "command": "Get-ChildItem"},
            }),
        ])
        _, _, used_tools = RUNNER.parse_codex_output(stdout)
        self.assertTrue(used_tools)

    def test_validate_review_accepts_consistent_non_interrupt(self):
        manifest = {
            "evidence_mode": "activity_window",
            "events": [{"outcome": "unknown"}],
        }
        review = {
            "schema_version": 1,
            "request_id": "request-1",
            "classification": "novel_exploration",
            "confidence": 0.95,
            "same_failure_family": True,
            "prior_lesson_verified": False,
            "evidence_adequate": True,
            "should_interrupt": False,
            "reason": "User-requested successful probe",
            "recommended_action": "continue",
        }
        self.assertEqual(
            RUNNER.validate_review(review, "request-1", manifest),
            "",
        )

    def test_validate_review_rejects_known_loop_without_failed_tool_events(self):
        manifest = {
            "evidence_mode": "activity_window",
            "events": [{"outcome": "unknown"}],
        }
        review = {
            "schema_version": 1,
            "request_id": "request-2",
            "classification": "known_loop",
            "confidence": 0.99,
            "same_failure_family": True,
            "prior_lesson_verified": True,
            "evidence_adequate": True,
            "should_interrupt": True,
            "reason": "Repeated command",
            "recommended_action": "recall_lesson",
        }
        self.assertEqual(
            RUNNER.validate_review(
                review,
                "request-2",
                manifest,
                [{"outcome": "failed"}, {"outcome": "unknown"}],
                [{"source_id": "memory:lesson-1", "summary": "Use tool B"}],
            ),
            "known_loop_without_two_failed_tool_events",
        )

    def test_validate_review_rejects_known_loop_without_lesson_candidate(self):
        manifest = {
            "evidence_mode": "activity_window",
            "events": [{"outcome": "unknown"}, {"outcome": "unknown"}],
        }
        review = {
            "schema_version": 1,
            "request_id": "request-loop",
            "classification": "known_loop",
            "confidence": 0.95,
            "same_failure_family": True,
            "prior_lesson_verified": False,
            "evidence_adequate": True,
            "should_interrupt": True,
            "reason": "Two matching failed shell envelopes",
            "recommended_action": "recall_lesson",
        }
        self.assertEqual(
            RUNNER.validate_review(
                review,
                "request-loop",
                manifest,
                [{"outcome": "failed"}, {"outcome": "failed"}],
            ),
            "known_loop_without_prior_lesson_candidate",
        )

    def test_validate_review_accepts_known_loop_with_verified_lesson(self):
        manifest = {
            "evidence_mode": "activity_window",
            "events": [{"outcome": "unknown"}, {"outcome": "unknown"}],
        }
        review = {
            "schema_version": 1,
            "request_id": "request-known",
            "classification": "known_loop",
            "confidence": 0.95,
            "same_failure_family": True,
            "prior_lesson_verified": True,
            "evidence_adequate": True,
            "should_interrupt": True,
            "reason": "Two failed events match a current source-labelled lesson",
            "recommended_action": "recall_lesson",
        }
        self.assertEqual(
            RUNNER.validate_review(
                review,
                "request-known",
                manifest,
                [{"outcome": "failed"}, {"outcome": "failed"}],
                [{"source_id": "memory:lesson-1", "summary": "Use tool B"}],
            ),
            "",
        )

    def test_extract_rollout_evidence_uses_actual_tool_events(self):
        records = [
            {
                "type": "turn_context",
                "payload": {"cwd": "C:\\work"},
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Run a probe"}],
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "call_id": "call-1",
                    "arguments": json.dumps({
                        "command": "Write-Output probe  ",
                    }),
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call_output",
                    "call_id": "call-1",
                    "output": "Exit code: 0\nOutput:\nprobe",
                },
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout.jsonl"
            path.write_text(
                "\n".join(json.dumps(record) for record in records),
                encoding="utf-8",
            )
            goal, events = RUNNER.extract_rollout_evidence(path)
        self.assertEqual(goal, "Run a probe")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["command"], "Write-Output probe")
        self.assertIn("Exit code: 0", events[0]["outcome_excerpt"])
        self.assertEqual(events[0]["outcome"], "succeeded")
        self.assertEqual(events[0]["exit_code"], 0)
        self.assertEqual(events[0]["cwd"], "C:\\work")
        self.assertEqual(len(events[0]["command_signature"]), 12)

    def test_build_packet_matches_normalized_hook_signature(self):
        command = "Write-Output probe  "
        cwd = "C:\\work\\."
        manifest = {
            "request_id": "request-match",
            "events": [{
                "command_signature": RUNNER.command_signature(cwd, command),
            }],
        }
        request = {
            "manifest": manifest,
            "hook_payload": {
                "session_id": "not-a-real-session",
                "cwd": "C:\\ignored",
                "tool_input": {"command": command, "workdir": cwd},
                "tool_response": "Exit code: 1\nOutput:\nfailed",
            },
        }
        packet = RUNNER.build_review_packet(request)
        self.assertTrue(packet["manifest_matches_event_tail"])
        self.assertEqual(packet["prior_lesson_candidates"], [])
        self.assertEqual(packet["tool_events"][-1]["outcome"], "failed")
        self.assertEqual(packet["tool_events"][-1]["exit_code"], 1)

    def test_prepare_isolated_home_copies_only_auth(self):
        with tempfile.TemporaryDirectory() as directory:
            parent_home = Path(directory) / "parent"
            parent_home.mkdir()
            (parent_home / "auth.json").write_text(
                '{"auth_mode":"chatgpt"}', encoding="utf-8"
            )
            (parent_home / "AGENTS.md").write_text("private", encoding="utf-8")
            (parent_home / "skills").mkdir()
            target_root = Path(directory) / "target"
            target_root.mkdir()
            with mock.patch.dict(
                os.environ,
                {
                    "CODEX_HOME": str(parent_home),
                    "CODEX_API_KEY": "",
                    "CODEX_ACCESS_TOKEN": "",
                },
                clear=False,
            ):
                isolated = RUNNER.prepare_isolated_codex_home(target_root)
                names = {path.name for path in isolated.iterdir()}
        self.assertEqual(names, {"auth.json"})

    def test_prepare_isolated_home_fails_closed_without_auth(self):
        with tempfile.TemporaryDirectory() as directory:
            parent_home = Path(directory) / "parent"
            parent_home.mkdir()
            target_root = Path(directory) / "target"
            target_root.mkdir()
            with mock.patch.dict(
                os.environ,
                {
                    "CODEX_HOME": str(parent_home),
                    "CODEX_API_KEY": "",
                    "CODEX_ACCESS_TOKEN": "",
                },
                clear=False,
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "isolated_auth_unavailable"
                ):
                    RUNNER.prepare_isolated_codex_home(target_root)

    def test_run_reviewer_uses_temporary_codex_home(self):
        packet = {
            "request_id": "request-3",
            "hook_manifest": {
                "evidence_mode": "activity_window",
                "events": [{"outcome": "unknown"}],
            },
        }
        review = {
            "schema_version": 1,
            "request_id": "request-3",
            "classification": "novel_exploration",
            "confidence": 0.9,
            "same_failure_family": False,
            "prior_lesson_verified": False,
            "evidence_adequate": True,
            "should_interrupt": False,
            "reason": "Evidence-producing probe",
            "recommended_action": "continue",
        }
        stdout = "\n".join([
            json.dumps({"type": "thread.started", "thread_id": "child-3"}),
            json.dumps({
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": json.dumps(review),
                },
            }),
        ])
        captured = {}

        def fake_run(command, prompt, timeout, env):
            captured["command"] = command
            captured["codex_home"] = env["CODEX_HOME"]
            self.assertTrue(
                (Path(captured["codex_home"]) / "auth.json").is_file()
            )
            return subprocess.CompletedProcess(command, 0, stdout, "")

        with tempfile.TemporaryDirectory() as directory:
            parent_home = Path(directory) / "parent"
            parent_home.mkdir()
            (parent_home / "auth.json").write_text(
                '{"auth_mode":"chatgpt"}', encoding="utf-8"
            )
            with mock.patch.dict(
                os.environ,
                {
                    "CODEX_HOME": str(parent_home),
                    "CODEX_API_KEY": "",
                    "CODEX_ACCESS_TOKEN": "",
                },
                clear=False,
            ), mock.patch.object(
                RUNNER, "find_codex_cli", return_value="codex"
            ), mock.patch.object(
                RUNNER, "run_bounded_process", side_effect=fake_run
            ):
                result = RUNNER.run_reviewer(packet, {})

        self.assertEqual(result["reviewer_agent_id"], "child-3")
        self.assertEqual(result["reviewer_isolation"], "enforced_no_tools")
        self.assertEqual(
            result["reviewer_context_isolation"],
            "temporary_codex_home",
        )
        self.assertFalse(Path(captured["codex_home"]).exists())
        self.assertTrue(
            str(captured["codex_home"]).startswith(
                str(parent_home / "tmp" / "learning-retrospective-reviewer")
            )
        )
        self.assertIn("--strict-config", captured["command"])
        self.assertIn('web_search="disabled"', captured["command"])
        self.assertIn("agents.enabled=false", captured["command"])
        for feature in RUNNER.CHILD_DISABLED_FEATURES:
            self.assertIn(feature, captured["command"])

    def test_bounded_process_stops_on_timeout(self):
        started = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            RUNNER.run_bounded_process(
                [sys.executable, "-c", "import time; time.sleep(10)"],
                "",
                0.1,
                dict(os.environ),
            )
        self.assertLess(time.monotonic() - started, 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)

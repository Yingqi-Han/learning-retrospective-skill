"""Tests for the retry-loop detector hook scripts.

Stdlib-only. Run from anywhere:

    python learning-retrospective/tests/test_retry_loop_detector.py

Each test uses a fresh random session id, so repeated runs do not pollute
each other through the per-session state files in the temp directory.
"""
import json
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
HOOKS_DIR = TESTS_DIR.parent / "hooks"
FIXTURES_DIR = TESTS_DIR / "fixtures"

CLAUDE = HOOKS_DIR / "retry-loop-detector-claude.py"
CODEX = HOOKS_DIR / "retry-loop-detector-codex.py"

BOM = b"\xef\xbb\xbf"


def load_fixture(name):
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def run_hook(script, payload, bom=False):
    raw = json.dumps(payload).encode("utf-8")
    if bom:
        raw = BOM + raw
    proc = subprocess.run(
        [sys.executable, "-S", str(script)],
        input=raw,
        capture_output=True,
        timeout=30,
    )
    return proc.returncode, proc.stdout.decode("utf-8").strip()


def fresh_session(payload):
    payload = dict(payload)
    payload["session_id"] = "t" + uuid.uuid4().hex[:12]
    return payload


def assert_reminder(testcase, out):
    testcase.assertTrue(out, "expected a reminder on the second failure")
    parsed = json.loads(out)
    ctx = parsed["hookSpecificOutput"]["additionalContext"]
    testcase.assertIn("failed 2 times", ctx)
    testcase.assertIn("lesson", ctx)


class ClaudeDetectorTest(unittest.TestCase):
    def test_second_identical_failure_emits_reminder_then_success_resets(self):
        fail = fresh_session(load_fixture("claude-post-tool-failure.json"))
        ok = dict(load_fixture("claude-post-tool-success.json"))
        ok["session_id"] = fail["session_id"]

        code, out = run_hook(CLAUDE, fail)
        self.assertEqual(code, 0)
        self.assertEqual(out, "", "first failure must not emit a reminder")

        code, out = run_hook(CLAUDE, fail)
        self.assertEqual(code, 0)
        assert_reminder(self, out)

        code, out = run_hook(CLAUDE, ok)
        self.assertEqual(code, 0)
        self.assertEqual(out, "", "success must reset silently")

        code, out = run_hook(CLAUDE, fail)
        self.assertEqual(code, 0)
        self.assertEqual(out, "", "first failure after reset must not emit")

    def test_bom_prefixed_input_still_counts(self):
        fail = fresh_session(load_fixture("claude-post-tool-failure.json"))
        run_hook(CLAUDE, fail, bom=True)
        code, out = run_hook(CLAUDE, fail, bom=True)
        self.assertEqual(code, 0)
        assert_reminder(self, out)

    def test_non_bash_tool_is_ignored(self):
        fail = fresh_session(load_fixture("claude-post-tool-failure.json"))
        fail["tool_name"] = "Edit"
        for _ in range(3):
            code, out = run_hook(CLAUDE, fail)
            self.assertEqual(code, 0)
            self.assertEqual(out, "")

    def test_different_commands_do_not_accumulate(self):
        fail_a = fresh_session(load_fixture("claude-post-tool-failure.json"))
        fail_b = dict(fail_a)
        fail_b["tool_input"] = {"command": "an entirely different command"}
        run_hook(CLAUDE, fail_a)
        code, out = run_hook(CLAUDE, fail_b)
        self.assertEqual(code, 0)
        self.assertEqual(out, "", "two different failing commands must not trigger")

    def test_same_command_in_different_cwd_does_not_accumulate(self):
        fail_a = fresh_session(load_fixture("claude-post-tool-failure.json"))
        fail_a["cwd"] = "/project/a"
        fail_b = dict(fail_a)
        fail_b["cwd"] = "/project/b"
        run_hook(CLAUDE, fail_a)
        code, out = run_hook(CLAUDE, fail_b)
        self.assertEqual(code, 0)
        self.assertEqual(out, "", "same command in different cwd is a different action")

    def test_unsafe_session_id_still_works(self):
        fail = load_fixture("claude-post-tool-failure.json")
        fail = dict(fail)
        fail["session_id"] = "../weird:session/../" + uuid.uuid4().hex[:8]
        code, out = run_hook(CLAUDE, fail)
        self.assertEqual(code, 0)
        self.assertEqual(out, "")
        code, out = run_hook(CLAUDE, fail)
        self.assertEqual(code, 0)
        assert_reminder(self, out)

    def test_garbage_input_exits_quietly(self):
        proc = subprocess.run(
            [sys.executable, "-S", str(CLAUDE)],
            input=b"not json at all",
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.decode().strip(), "")


class CodexDetectorTest(unittest.TestCase):
    def test_second_identical_failure_emits_reminder_then_success_resets(self):
        fail = fresh_session(load_fixture("codex-post-tool-use-fail.json"))
        ok = dict(load_fixture("codex-post-tool-use-success.json"))
        ok["session_id"] = fail["session_id"]

        code, out = run_hook(CODEX, fail)
        self.assertEqual(code, 0)
        self.assertEqual(out, "", "first failure must not emit a reminder")

        code, out = run_hook(CODEX, fail)
        self.assertEqual(code, 0)
        assert_reminder(self, out)

        code, out = run_hook(CODEX, ok)
        self.assertEqual(code, 0)
        self.assertEqual(out, "", "success must reset silently")

    def test_missing_exit_code_fails_safe_as_success(self):
        fail = fresh_session(load_fixture("codex-post-tool-use-fail.json"))
        missing = dict(load_fixture("codex-post-tool-use-missing-exit-code.json"))
        missing["session_id"] = fail["session_id"]

        run_hook(CODEX, fail)
        # A missing exit code must reset the counter, not increment it.
        code, out = run_hook(CODEX, missing)
        self.assertEqual(code, 0)
        self.assertEqual(out, "", "missing exit_code must be treated as success")

        code, out = run_hook(CODEX, fail)
        self.assertEqual(code, 0)
        self.assertEqual(out, "", "counter must have been reset by the missing-field payload")

    def test_unsafe_session_id_still_works(self):
        fail = load_fixture("codex-post-tool-use-fail.json")
        fail = dict(fail)
        fail["session_id"] = "../weird:session/../" + uuid.uuid4().hex[:8]
        code, out = run_hook(CODEX, fail)
        self.assertEqual(code, 0)
        self.assertEqual(out, "")
        code, out = run_hook(CODEX, fail)
        self.assertEqual(code, 0)
        assert_reminder(self, out)


if __name__ == "__main__":
    unittest.main(verbosity=2)

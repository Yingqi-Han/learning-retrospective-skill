"""Tests for the retry-loop detector hook scripts.

Stdlib-only. Run from anywhere:

    python learning-retrospective/tests/test_retry_loop_detector.py

Each test uses a fresh random session id and removes its state file afterward,
so repeated runs do not pollute the temp directory.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
HOOKS_DIR = TESTS_DIR.parent / "hooks"
FIXTURES_DIR = TESTS_DIR / "fixtures"

CLAUDE = HOOKS_DIR / "retry-loop-detector-claude.py"
CODEX = HOOKS_DIR / "retry-loop-detector-codex.py"

BOM = b"\xef\xbb\xbf"
CREATED_STATE_PATHS = set()


def load_fixture(name):
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def run_hook(script, payload, bom=False):
    session_id = payload.get("session_id")
    if session_id:
        prefix = "codex" if script == CODEX else "claude"
        session_key = hashlib.sha1(
            str(session_id).encode("utf-8", "replace")
        ).hexdigest()[:12]
        CREATED_STATE_PATHS.add(
            Path(tempfile.gettempdir()) / f"{prefix}-retry-loop-{session_key}.json"
        )
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


def assert_reminder(testcase, out, count=2):
    testcase.assertTrue(out, f"expected a reminder on failure {count}")
    parsed = json.loads(out)
    ctx = parsed["hookSpecificOutput"]["additionalContext"]
    testcase.assertIn(f"failed {count} times", ctx)
    testcase.assertIn("lesson", ctx)


def tearDownModule():
    for path in CREATED_STATE_PATHS:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


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

    def test_reminder_uses_exponential_backoff(self):
        fail = fresh_session(load_fixture("claude-post-tool-failure.json"))
        run_hook(CLAUDE, fail)
        _, second = run_hook(CLAUDE, fail)
        _, third = run_hook(CLAUDE, fail)
        _, fourth = run_hook(CLAUDE, fail)
        assert_reminder(self, second, 2)
        self.assertEqual(third, "", "third failure must not repeat the reminder")
        assert_reminder(self, fourth, 4)

    def test_missing_session_id_fails_safe(self):
        fail = load_fixture("claude-post-tool-failure.json")
        fail.pop("session_id", None)
        for _ in range(2):
            code, out = run_hook(CLAUDE, fail)
            self.assertEqual(code, 0)
            self.assertEqual(out, "")


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

    def test_reminder_uses_exponential_backoff(self):
        fail = fresh_session(load_fixture("codex-post-tool-use-fail.json"))
        run_hook(CODEX, fail)
        _, second = run_hook(CODEX, fail)
        _, third = run_hook(CODEX, fail)
        _, fourth = run_hook(CODEX, fail)
        assert_reminder(self, second, 2)
        self.assertEqual(third, "", "third failure must not repeat the reminder")
        assert_reminder(self, fourth, 4)

    def test_missing_session_id_fails_safe(self):
        fail = load_fixture("codex-post-tool-use-fail.json")
        fail.pop("session_id", None)
        for _ in range(2):
            code, out = run_hook(CODEX, fail)
            self.assertEqual(code, 0)
            self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)

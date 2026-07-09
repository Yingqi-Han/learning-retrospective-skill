"""Tests for scripts/lesson_lint.py. Stdlib-only; run directly with python."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINT = ROOT / "scripts" / "lesson_lint.py"
FILLED = ROOT / "examples" / "filled-lesson-libreoffice.md"

GOOD_LESSON = """# Lesson: sample

## Trigger
- Conversion fails with a specific error.

## Verified Facts
- The converter binary is at /usr/bin/soffice, confirmed with which.

## Preferred Procedure
1. Run the documented command.

## Last Verified
- 2026-07-09

## Scope
- This machine only.
"""

BAD_LESSON = """# Lesson: bad

## Trigger
- Something failed.

## Verified Facts
- It probably fails because of the proxy, I think.
- api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"
"""


def run_lint(args=None, stdin=None):
    cmd = [sys.executable, "-S", str(LINT)] + (args or [])
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run(cmd, input=stdin, capture_output=True, text=True,
                            encoding="utf-8", timeout=30, env=env)
    return result.returncode, result.stdout


class LessonLintTests(unittest.TestCase):
    def test_good_lesson_is_clean(self):
        code, out = run_lint(["-"], stdin=GOOD_LESSON)
        self.assertEqual(code, 0, out)
        self.assertIn("clean", out)

    def test_bad_lesson_fails_with_specific_findings(self):
        code, out = run_lint(["-"], stdin=BAD_LESSON)
        self.assertEqual(code, 1, out)
        self.assertIn("possible secret", out)
        self.assertIn("hedged language", out)
        self.assertIn("missing section 'Preferred Procedure'", out)
        self.assertIn("missing section 'Last Verified'", out)

    def test_long_code_block_is_flagged(self):
        log_block = "```\n" + "\n".join(f"log line {i}" for i in range(60)) + "\n```\n"
        code, out = run_lint(["-"], stdin=GOOD_LESSON + "\n" + log_block)
        self.assertEqual(code, 1, out)
        self.assertIn("raw log dump", out)

    def test_shipped_filled_example_passes(self):
        # The example file wraps the lesson in a ```markdown display fence;
        # lint the lesson body itself, as it would be stored. Normalize CRLF:
        # Windows CI runners check out with autocrlf=true.
        text = FILLED.read_text(encoding="utf-8").replace("\r\n", "\n")
        body = text.split("```markdown\n", 1)[1].split("\n```", 1)[0]
        code, out = run_lint(["-"], stdin=body)
        self.assertEqual(code, 0, out)

    def test_no_args_is_usage_error(self):
        code, _ = run_lint([])
        self.assertEqual(code, 2)

    def test_help_flag_prints_usage_and_exits_zero(self):
        code, out = run_lint(["--help"])
        self.assertEqual(code, 0, out)
        self.assertIn("usage", out.lower())
        self.assertIn("LESSON", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)

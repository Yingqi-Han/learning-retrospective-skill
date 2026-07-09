#!/usr/bin/env python3
"""Lint a captured lesson before it is written to persistent memory.

Usage:
    python lesson_lint.py <lesson.md> [more.md ...]
    ... | python lesson_lint.py -          (read from stdin)

Checks (see SECURITY_NOTES.md for the rationale):
    - secrets: token/key/password/cookie patterns, PEM blocks, common
      credential formats (AWS, GitHub, OpenAI-style, JWT)
    - raw-log dumps: fenced code blocks longer than MAX_BLOCK_LINES
    - missing durability sections: Trigger, Verified Facts,
      Preferred Procedure, Scope, Last Verified
    - unverified language inside Verified Facts (probably / might /
      I think / seems / 大概 / 可能 / 应该是)

Exit code 0 = clean, 1 = findings, 2 = usage error. Stdlib-only.
"""
import re
import sys

MAX_BLOCK_LINES = 40

SECRET_PATTERNS = [
    (re.compile(r"(?i)\b(api[_-]?key|secret|token|passwd|password|cookie|authorization|bearer)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-./+]{8,}"), "credential assignment"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "GitHub token"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"), "API secret key"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\."), "JWT"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "PEM private key"),
]

REQUIRED_SECTIONS = ["Trigger", "Verified Facts", "Preferred Procedure", "Scope", "Last Verified"]

HEDGE_WORDS = re.compile(r"(?i)\b(probably|might|maybe|i think|seems|presumably|guess)\b|大概|可能|应该是|好像")


def lint_text(text, name="<stdin>"):
    findings = []
    lines = text.splitlines()

    for i, line in enumerate(lines, 1):
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(f"{name}:{i}: possible secret ({label}); scrub before saving")

    in_block = False
    block_start = 0
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("```"):
            if not in_block:
                in_block, block_start = True, i
            else:
                in_block = False
                if i - block_start - 1 > MAX_BLOCK_LINES:
                    findings.append(
                        f"{name}:{block_start}: code block with {i - block_start - 1} lines "
                        f"looks like a raw log dump; keep only the first actionable error")

    section_pat = re.compile(r"^#{1,6}\s+(.*)$")
    sections = {m.group(1).strip() for l in lines if (m := section_pat.match(l))}
    for required in REQUIRED_SECTIONS:
        if not any(required.lower() in s.lower() for s in sections):
            findings.append(f"{name}: missing section '{required}' (see the Lesson Template)")

    current = ""
    for i, line in enumerate(lines, 1):
        m = section_pat.match(line)
        if m:
            current = m.group(1).strip().lower()
            continue
        if "verified facts" in current and HEDGE_WORDS.search(line):
            findings.append(f"{name}:{i}: hedged language inside Verified Facts; "
                            "verify it or move it out of this section")

    return findings


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    findings = []
    for arg in argv[1:]:
        if arg == "-":
            findings += lint_text(sys.stdin.read())
        else:
            try:
                with open(arg, encoding="utf-8-sig") as f:
                    findings += lint_text(f.read(), arg)
            except OSError as e:
                print(f"ERROR: cannot read {arg}: {e}")
                return 2
    if findings:
        for f in findings:
            print(f)
        print(f"{len(findings)} finding(s). Fix them before writing this lesson to memory.")
        return 1
    print("Lesson lint: clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

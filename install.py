#!/usr/bin/env python3
"""One-command installer for the learning-retrospective skill.

Usage:
    python install.py --agent codex
    python install.py --agent claude
    python install.py --agent project [--target ./.agent-skills]
    python install.py --agent codex --dry-run

What it does:
    1. Sanity-checks the repository (SKILL.md, VERSION present).
    2. Runs the hook detector test suite.
    3. Copies the nested learning-retrospective/ folder into the target
       skills directory.
    4. Verifies the installed copy.

What it deliberately does NOT do:
    - It never registers hooks or edits settings.json / hooks.json / any
      persistent agent configuration. Hooks are executable local code; with
      --with-hooks it only copies the scripts to the harness hooks directory
      and prints the registration instructions for you to apply manually
      (see SECURITY_NOTES.md).

Stdlib-only; works on Windows, macOS, and Linux with Python 3.8+.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SKILL_SRC = REPO_ROOT / "learning-retrospective"
TESTS = SKILL_SRC / "tests" / "test_retry_loop_detector.py"

TARGETS = {
    "codex": Path.home() / ".codex" / "skills",
    "claude": Path.home() / ".claude" / "skills",
}

HOOK_DIRS = {
    "codex": Path.home() / ".codex" / "hooks",
    "claude": Path.home() / ".claude" / "hooks",
}

HOOK_SCRIPTS = {
    "codex": "retry-loop-detector-codex.py",
    "claude": "retry-loop-detector-claude.py",
}


def fail(msg):
    print(f"ERROR: {msg}")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--agent", required=True, choices=["codex", "claude", "project"])
    parser.add_argument("--target", default=None,
                        help="skills directory for --agent project (default ./.agent-skills)")
    parser.add_argument("--with-hooks", action="store_true",
                        help="also copy (never register) the hook detector script")
    parser.add_argument("--force", action="store_true",
                        help="overwrite an existing installed copy")
    parser.add_argument("--skip-tests", action="store_true",
                        help="skip the test suite (not recommended)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print target paths and planned writes without copying files")
    args = parser.parse_args()

    # 1. Sanity checks
    if not (SKILL_SRC / "SKILL.md").is_file():
        fail("learning-retrospective/SKILL.md not found; run from the repository root.")
    if not (SKILL_SRC / "VERSION").is_file():
        fail("learning-retrospective/VERSION not found.")
    version = (SKILL_SRC / "VERSION").read_text(encoding="utf-8").strip()
    print(f"Installing learning-retrospective {version}")

    # 2. Tests
    if args.skip_tests:
        print("WARNING: skipping tests; install may succeed even if hook scripts are broken.")
    else:
        print("Running hook detector tests...")
        result = subprocess.run([sys.executable, str(TESTS)], capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr)
            fail("test suite failed; not installing. Use --skip-tests to override.")
        print("Tests passed.")

    # 3. Copy the nested skill folder
    if args.agent == "project":
        skills_dir = Path(args.target) if args.target else Path("./.agent-skills")
    else:
        skills_dir = TARGETS[args.agent]
    dest = skills_dir / "learning-retrospective"

    print(f"Target skills directory: {skills_dir}")
    print(f"Target skill path: {dest}")
    if dest.exists():
        print(f"Existing install: yes ({'would overwrite' if args.force else 'would refuse without --force'})")
    else:
        print("Existing install: no")
    if args.with_hooks and args.agent != "project":
        script = HOOK_SCRIPTS[args.agent]
        print(f"Hook script copy target: {HOOK_DIRS[args.agent] / script} (registration remains manual)")
    elif args.with_hooks:
        print("Hook script copy target: none (hooks are per-user, not per-project)")
    else:
        print("Hook script copy target: none (--with-hooks not set)")

    if args.dry_run:
        print("DRY RUN: no files were copied, removed, or created.")
        print("Done.")
        return

    if dest.exists():
        if not args.force:
            fail(f"{dest} already exists. Re-run with --force to overwrite. "
                 "Note: overwriting discards local edits such as localized "
                 "trigger phrases (references/localization.md).")
        shutil.rmtree(dest)
    skills_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        SKILL_SRC,
        dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    print(f"Copied skill to {dest}")

    # 4. Verify
    for rel in ("SKILL.md", "VERSION", "SECURITY_NOTES.md"):
        if not (dest / rel).is_file():
            fail(f"verification failed: {dest / rel} missing after copy.")
    installed_version = (dest / "VERSION").read_text(encoding="utf-8").strip()
    if installed_version != version:
        fail(f"verification failed: installed VERSION {installed_version} != {version}.")
    print(f"Verified: SKILL.md, VERSION ({installed_version}), SECURITY_NOTES.md present.")

    # 5. Hooks: copy only, never register
    if args.with_hooks:
        if args.agent == "project":
            print("Hooks are per-user, not per-project; re-run with --agent codex|claude for hooks.")
        else:
            hook_dir = HOOK_DIRS[args.agent]
            hook_dir.mkdir(parents=True, exist_ok=True)
            script = HOOK_SCRIPTS[args.agent]
            shutil.copy2(SKILL_SRC / "hooks" / script, hook_dir / script)
            print(f"Copied hook script to {hook_dir / script} (NOT registered).")
            print("Next steps (manual, after reading SECURITY_NOTES.md):")
            print(f"  - Registration snippet: {dest / 'references' / 'hook-activation.md'}")
            if args.agent == "codex":
                print("  - Codex additionally requires trusting the hook via /hooks in the app.")
    else:
        print("Hooks not installed (default). Use --with-hooks to copy the script; "
              "registration is always manual - read SECURITY_NOTES.md first.")

    print("Done.")


if __name__ == "__main__":
    main()

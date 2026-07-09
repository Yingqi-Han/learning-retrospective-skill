#!/usr/bin/env python3
"""One-command installer for the learning-retrospective skill.

Usage:
    python install.py --agent codex
    python install.py --agent claude
    python install.py --agent project [--target ./.agent-skills]
    python install.py --agent codex --dry-run
    python install.py --agent claude --locale zh-CN
    python install.py --agent claude --uninstall
    python install.py --agent codex --print-hook-config

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
import datetime
import json
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

# Keep in sync with references/localization.md.
LOCALE_ADDENDA = {
    "zh-CN": (" — including Chinese requests such as 复盘, 总结经验, 总结教训, "
              "吸取教训, 记住这个坑, 避免重复踩坑, 别再重复试错"),
}
LOCALE_MARKERS = {"zh-CN": "复盘"}
DESC_ANCHOR = "retry loops. Do not use"


def fail(msg):
    print(f"ERROR: {msg}")
    sys.exit(1)


def print_hook_config(agent):
    """Print the registration snippet with resolved local paths. Never writes."""
    if agent == "project":
        fail("--print-hook-config needs --agent codex or --agent claude.")
    interpreter = sys.executable.replace("\\", "/")
    script = (HOOK_DIRS[agent] / HOOK_SCRIPTS[agent]).as_posix()
    if agent == "claude":
        entry = {"type": "command", "command": sys.executable,
                 "args": ["-S", str(HOOK_DIRS[agent] / HOOK_SCRIPTS[agent])],
                 "timeout": 5}
        snippet = {"hooks": {
            "PostToolUse": [{"matcher": "Bash", "hooks": [entry]}],
            "PostToolUseFailure": [{"matcher": "Bash", "hooks": [entry]}],
        }}
        target = "~/.claude/settings.json (merge under existing keys)"
    else:
        snippet = {"hooks": {"PostToolUse": [{"matcher": "^Bash$", "hooks": [{
            "type": "command",
            "command": f'"{interpreter}" -S "{script}"',
            "timeout": 5}]}]}}
        target = "~/.codex/hooks.json (then trust it via /hooks inside Codex)"
    print(f"Proposed hook registration for {agent} - review, then merge manually into {target}:")
    print(json.dumps(snippet, indent=2))
    print("Nothing was written. See SECURITY_NOTES.md before registering.")


def apply_locale(dest, locale):
    """Append native-language trigger phrases to the installed description line."""
    addendum = LOCALE_ADDENDA[locale]
    skill_md = dest / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("description:"):
            if LOCALE_MARKERS[locale] in line:
                print(f"Locale {locale}: trigger phrases already present, skipping.")
                return
            if DESC_ANCHOR in line:
                lines[i] = line.replace("retry loops. Do not use",
                                        f"retry loops{addendum}. Do not use", 1)
            else:
                lines[i] = line.rstrip() + addendum
            skill_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(f"Locale {locale}: appended trigger phrases to installed description.")
            return
    fail("could not find the description line in the installed SKILL.md.")


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
    parser.add_argument("--uninstall", action="store_true",
                        help="remove the installed skill folder (hook scripts and hook registrations are never touched)")
    parser.add_argument("--locale", choices=sorted(LOCALE_ADDENDA),
                        help="append native-language trigger phrases to the installed description (e.g. zh-CN)")
    parser.add_argument("--print-hook-config", action="store_true",
                        help="print the hook registration snippet with resolved paths and exit; writes nothing")
    args = parser.parse_args()

    if args.print_hook_config:
        print_hook_config(args.agent)
        return

    # 1. Sanity checks
    if not (SKILL_SRC / "SKILL.md").is_file():
        fail("learning-retrospective/SKILL.md not found; run from the repository root.")
    if not (SKILL_SRC / "VERSION").is_file():
        fail("learning-retrospective/VERSION not found.")
    version = (SKILL_SRC / "VERSION").read_text(encoding="utf-8").strip()
    print(f"Installing learning-retrospective {version}")

    # Uninstall path: remove only the skill folder, never hook files/config.
    if args.uninstall:
        if args.agent == "project":
            skills_dir = Path(args.target) if args.target else Path("./.agent-skills")
        else:
            skills_dir = TARGETS[args.agent]
        dest = skills_dir / "learning-retrospective"
        if not dest.exists():
            print(f"Nothing to uninstall: {dest} does not exist.")
            return
        if not (dest / "SKILL.md").is_file():
            fail(f"{dest} does not look like an installed copy (no SKILL.md); refusing to delete.")
        if args.dry_run:
            print(f"DRY RUN: would remove {dest}. Hook scripts and registrations would be untouched.")
            return
        shutil.rmtree(dest)
        print(f"Removed {dest}.")
        print("Not touched: hook scripts in the harness hooks directory and any hook "
              "registration in settings.json / hooks.json - remove those manually if desired.")
        return

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
            fail(f"{dest} already exists. Re-run with --force to update (the old copy "
                 "is kept as a timestamped .bak folder). Local edits such as localized "
                 "trigger phrases can be re-applied with --locale.")
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = dest.with_name(f"learning-retrospective.bak-{stamp}")
        dest.rename(backup)
        print(f"Existing install backed up to {backup}")
        old_skill = backup / "SKILL.md"
        if old_skill.is_file() and args.locale is None:
            old_desc = next((l for l in old_skill.read_text(encoding="utf-8").splitlines()
                             if l.startswith("description:")), "")
            if any(m in old_desc for m in LOCALE_MARKERS.values()):
                print("NOTE: the previous copy had localized trigger phrases in its "
                      "description. Re-apply them with --locale (e.g. --locale zh-CN) "
                      "or copy the line from the backup.")
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

    # 4b. Optional trigger-phrase localization
    if args.locale:
        apply_locale(dest, args.locale)

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

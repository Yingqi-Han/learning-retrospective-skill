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
    2. Runs the complete stdlib-only test suite.
    3. Copies the nested learning-retrospective/ folder into the target
       skills directory through a verified staging directory.
    4. Verifies the complete installed file manifest and version.

What it deliberately does NOT do:
    - It never registers hooks or edits settings.json / hooks.json / any
      persistent agent configuration. Hooks are executable local code; with
      --with-hooks it only copies the scripts to the harness hooks directory
      and prints the registration instructions for you to apply manually
      (see SECURITY_NOTES.md).

Stdlib-only; works on Windows, macOS, and Linux. CI-tested on Python
3.10-3.14; kept 3.8-compatible by inspection.
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SKILL_SRC = REPO_ROOT / "learning-retrospective"
TESTS_DIR = SKILL_SRC / "tests"

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
HOOK_SUPPORT_FILES = {
    "codex": ["retry-reviewer-codex-cli.py"],
    "claude": [],
}
REVIEW_CONFIG_EXAMPLE = "reviewer-config.example.json"
INSTALLED_REVIEW_CONFIG_EXAMPLE = "learning-retrospective-reviewer.example.json"
ACTIVE_REVIEW_CONFIG = "learning-retrospective-reviewer.json"

# Keep in sync with references/localization.md.
LOCALE_ADDENDA = {
    "zh-CN": (" — including Chinese requests such as 复盘, 总结经验, 总结教训, "
              "吸取教训, 记住这个坑, 避免重复踩坑, 别再重复试错"),
}
LOCALE_MARKERS = {"zh-CN": "复盘"}
DESC_ANCHOR = "retry loops. Do not use"
REQUIRED_INSTALL_FILES = {
    "SKILL.md",
    "VERSION",
    "SECURITY_NOTES.md",
    "agents/openai.yaml",
    "hooks/retry-loop-detector-codex.py",
    "hooks/retry-loop-detector-claude.py",
    "hooks/retry-reviewer-codex-cli.py",
    "hooks/reviewer-config.example.json",
    "references/semantic-review.md",
    "scripts/lesson_lint.py",
    "tests/test_retry_loop_detector.py",
    "tests/test_codex_reviewer_runner.py",
    "tests/test_installer.py",
    "tests/test_lesson_lint.py",
}


def fail(msg):
    print(f"ERROR: {msg}")
    sys.exit(1)


def parse_description_line(line):
    """Decode either a plain YAML scalar or our JSON-compatible quoted scalar."""
    raw_description = line.split(":", 1)[1].strip()
    if raw_description.startswith('"'):
        try:
            return json.loads(raw_description)
        except (ValueError, TypeError) as exc:
            raise RuntimeError(
                "installed description is not valid JSON/YAML quoted text"
            ) from exc
    return raw_description


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
        windows_command = f'& "{interpreter}" -S "{script}"'
        snippet = {"hooks": {"PostToolUse": [{"matcher": "^Bash$", "hooks": [{
            "type": "command",
            "command": f'"{interpreter}" -S "{script}"',
            "commandWindows": windows_command,
            "timeout": 60}]}]}}
        target = (
            "~/.codex/hooks.json (then review and trust the current hook hash "
            "in the Codex surface; /hooks is CLI/TUI-specific)"
        )
    print(f"Proposed hook registration for {agent} - review, then merge manually into {target}:")
    print(json.dumps(snippet, indent=2))
    if not (HOOK_DIRS[agent] / HOOK_SCRIPTS[agent]).is_file():
        print("NOTE: the hook script is not present at that path yet; "
              "run install.py with --with-hooks first, or copy it manually.")
    print("Nothing was written. See SECURITY_NOTES.md before registering.")


def apply_locale(dest, locale):
    """Append localized triggers while keeping SKILL.md ASCII on disk."""
    addendum = LOCALE_ADDENDA[locale]
    skill_md = dest / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("description:"):
            description = parse_description_line(line)
            if LOCALE_MARKERS[locale] in description:
                print(f"Locale {locale}: trigger phrases already present, skipping.")
                return
            if DESC_ANCHOR in description:
                description = description.replace(
                    "retry loops. Do not use",
                    f"retry loops{addendum}. Do not use",
                    1,
                )
            else:
                description = description.rstrip() + addendum
            # JSON double-quoted strings are valid YAML double-quoted scalars.
            # ensure_ascii keeps Windows locale-default validators from failing.
            lines[i] = "description: " + json.dumps(description, ensure_ascii=True)
            skill_md.write_text("\n".join(lines) + "\n", encoding="ascii")
            print(f"Locale {locale}: appended trigger phrases as ASCII YAML escapes.")
            return
    raise RuntimeError("could not find the description line in the installed SKILL.md")


def install_files(root):
    """Return copied file paths relative to root, excluding Python caches."""
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    }


def verify_install(dest, version):
    """Verify the complete manifest, core files, version, and UTF-8 frontmatter."""
    actual_files = install_files(dest)
    expected_files = install_files(SKILL_SRC)
    if actual_files != expected_files:
        missing = sorted(expected_files - actual_files)
        extra = sorted(actual_files - expected_files)
        raise RuntimeError(f"file manifest mismatch; missing={missing}, extra={extra}")
    missing_required = sorted(REQUIRED_INSTALL_FILES - actual_files)
    if missing_required:
        raise RuntimeError(f"required files missing: {missing_required}")
    installed_version = (dest / "VERSION").read_text(encoding="utf-8").strip()
    if installed_version != version:
        raise RuntimeError(
            f"installed VERSION {installed_version} does not match source {version}"
        )
    skill_text = (dest / "SKILL.md").read_text(encoding="utf-8")
    if not skill_text.startswith("---\n") or "\nname: learning-retrospective\n" not in skill_text:
        raise RuntimeError("SKILL.md frontmatter is missing or malformed")
    description_line = next(
        (line for line in skill_text.splitlines() if line.startswith("description:")),
        "",
    )
    if not description_line.split(":", 1)[1].strip():
        raise RuntimeError("SKILL.md description is empty")
    print(
        f"Verified: complete {len(actual_files)}-file manifest, VERSION "
        f"({installed_version}), and UTF-8 frontmatter."
    )


def backup_root_for(agent, skills_dir):
    """Keep backups outside the active skills discovery directory."""
    if agent in TARGETS:
        return Path.home() / f".{agent}" / "skill-backups"
    name = skills_dir.name or "agent-skills"
    return skills_dir.parent / f".{name}-backups"


def hook_backup_root_for(agent):
    """Keep hook rollback copies outside the active hooks directory."""
    return Path.home() / f".{agent}" / "hook-backups"


def install_hook_files(agent, hook_dir, backup_root, stamp):
    """Stage, verify, and transactionally replace one harness's hook files."""
    hook_dir = Path(hook_dir)
    backup_root = Path(backup_root)
    staging = backup_root / f".learning-retrospective-hooks.staging-{stamp}-{os.getpid()}"
    backup = backup_root / f"learning-retrospective-hooks.bak-{stamp}"
    active_config = hook_dir / ACTIVE_REVIEW_CONFIG
    active_config_preserved = active_config.exists()

    pairs = []
    for source_name in HOOK_SUPPORT_FILES[agent]:
        pairs.append((SKILL_SRC / "hooks" / source_name, hook_dir / source_name))
    pairs.append((
        SKILL_SRC / "hooks" / REVIEW_CONFIG_EXAMPLE,
        hook_dir / INSTALLED_REVIEW_CONFIG_EXAMPLE,
    ))
    if not active_config_preserved:
        pairs.append((
            SKILL_SRC / "hooks" / REVIEW_CONFIG_EXAMPLE,
            active_config,
        ))
    # Switch the detector last so an old detector never calls a half-updated
    # support bundle.
    script = HOOK_SCRIPTS[agent]
    pairs.append((SKILL_SRC / "hooks" / script, hook_dir / script))

    hook_dir.mkdir(parents=True, exist_ok=True)
    backup_root.mkdir(parents=True, exist_ok=True)
    staging.mkdir()
    replaced = []
    backed_up = set()
    try:
        for source, target in pairs:
            staged = staging / target.name
            shutil.copy2(source, staged)
            if staged.read_bytes() != source.read_bytes():
                raise RuntimeError(f"staged hook verification failed: {target.name}")

        existing = [target for _, target in pairs if target.exists()]
        if existing:
            backup.mkdir()
            for target in existing:
                shutil.copy2(target, backup / target.name)
                backed_up.add(target.name)

        for source, target in pairs:
            staged = staging / target.name
            os.replace(str(staged), str(target))
            replaced.append(target)
            if target.read_bytes() != source.read_bytes():
                raise RuntimeError(f"activated hook verification failed: {target.name}")
    except Exception:
        for target in reversed(replaced):
            rollback = backup / target.name
            if target.name in backed_up and rollback.is_file():
                shutil.copy2(rollback, target)
            elif target.exists():
                target.unlink()
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    return {
        "targets": [target for _, target in pairs],
        "active_config": active_config,
        "active_config_preserved": active_config_preserved,
        "backup": backup if backup.exists() else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--agent", required=True, choices=["codex", "claude", "project"])
    parser.add_argument("--target", default=None,
                        help="skills directory for --agent project (default ./.agent-skills)")
    parser.add_argument("--with-hooks", action="store_true",
                        help="also copy (never register) the hook detector and reviewer config example")
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
        print("Running complete test suite...")
        result = subprocess.run(
            [sys.executable, "-S", "-m", "unittest", "discover", "-s", str(TESTS_DIR), "-v"],
            capture_output=True,
            text=True,
        )
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
    backup_root = backup_root_for(args.agent, skills_dir)

    print(f"Target skills directory: {skills_dir}")
    print(f"Target skill path: {dest}")
    if dest.exists():
        print(f"Existing install: yes ({'would overwrite' if args.force else 'would refuse without --force'})")
        if args.force:
            print(f"Backup directory: {backup_root} (outside active skills discovery)")
    else:
        print("Existing install: no")
    if args.with_hooks and args.agent != "project":
        script = HOOK_SCRIPTS[args.agent]
        print(f"Hook script copy target: {HOOK_DIRS[args.agent] / script} (registration remains manual)")
        print("Reviewer config example target: "
              f"{HOOK_DIRS[args.agent] / INSTALLED_REVIEW_CONFIG_EXAMPLE}")
        active_config = HOOK_DIRS[args.agent] / ACTIVE_REVIEW_CONFIG
        print(f"Active reviewer config target: {active_config} "
              f"({'would preserve' if active_config.exists() else 'would create with defaults'})")
    elif args.with_hooks:
        print("Hook script copy target: none (hooks are per-user, not per-project)")
    else:
        print("Hook script copy target: none (--with-hooks not set)")

    if args.dry_run:
        print("DRY RUN: no files were copied, removed, or created.")
        print("Done.")
        return

    if dest.exists() and not args.force:
        fail(f"{dest} already exists. Re-run with --force to update (the old copy "
             "is kept outside the active skills directory). Local edits such as localized "
             "trigger phrases can be re-applied with --locale.")

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = backup_root / f"learning-retrospective.bak-{stamp}"
    staging = backup_root / f".learning-retrospective.staging-{stamp}-{os.getpid()}"
    moved_old = False
    activated = False
    backup_root.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(
            SKILL_SRC,
            staging,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
        if args.locale:
            apply_locale(staging, args.locale)
        verify_install(staging, version)

        skills_dir.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            old_skill = dest / "SKILL.md"
            if old_skill.is_file() and args.locale is None:
                old_desc = next(
                    (line for line in old_skill.read_text(encoding="utf-8").splitlines()
                     if line.startswith("description:")),
                    "",
                )
                old_description = parse_description_line(old_desc) if old_desc else ""
                if any(marker in old_description for marker in LOCALE_MARKERS.values()):
                    print("NOTE: the previous copy had localized trigger phrases. "
                          "Re-apply them with --locale (e.g. --locale zh-CN).")
            dest.rename(backup)
            moved_old = True
            print(f"Existing install backed up outside active skills to {backup}")
        staging.rename(dest)
        activated = True
        print(f"Activated verified skill at {dest}")
        verify_install(dest, version)
    except Exception as exc:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        if moved_old and backup.exists():
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            backup.rename(dest)
            print(f"Restored previous install after update failure: {dest}")
        elif activated and dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        fail(f"transactional install failed: {exc}")

    # 5. Hooks: copy only, never register
    if args.with_hooks:
        if args.agent == "project":
            print("Hooks are per-user, not per-project; re-run with --agent codex|claude for hooks.")
        else:
            hook_dir = HOOK_DIRS[args.agent]
            result = install_hook_files(
                args.agent,
                hook_dir,
                hook_backup_root_for(args.agent),
                stamp,
            )
            script = HOOK_SCRIPTS[args.agent]
            print(
                f"Transactionally installed hook script to "
                f"{hook_dir / script} (NOT registered)."
            )
            for support_file in HOOK_SUPPORT_FILES[args.agent]:
                print(f"Copied hook support file to {hook_dir / support_file}.")
            print("Copied optional reviewer config example to "
                  f"{hook_dir / INSTALLED_REVIEW_CONFIG_EXAMPLE}.")
            active_config = result["active_config"]
            if active_config.exists():
                print(f"Active reviewer config available at {active_config}; "
                      "existing preferences were preserved.")
            if result["backup"]:
                print(f"Previous hook files backed up to {result['backup']}.")
            print("Next steps (manual, after reading SECURITY_NOTES.md):")
            print(f"  - Registration snippet: {dest / 'references' / 'hook-activation.md'}")
            if args.agent == "codex":
                print(
                    "  - Codex additionally requires trusting the current hook hash. "
                    "The Desktop Hooks panel and CLI/TUI /hooks flow differ; an "
                    "enabled switch alone does not prove trust."
                )
    else:
        print("Hooks not installed (default). Use --with-hooks to copy the script; "
              "registration is always manual - read SECURITY_NOTES.md first.")

    print("Done.")


if __name__ == "__main__":
    main()

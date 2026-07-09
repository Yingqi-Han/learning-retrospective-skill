# Changelog

## 0.6.0 - 2026-07-09

- Add GitHub Actions CI: hook detector tests, lesson lint tests, and an installer end-to-end run (install, dry-run, force-update with locale, uninstall) across Linux/Windows/macOS and Python 3.8-3.14. Test badges added to both READMEs.
- Tag releases starting with v0.6.0 so users can install a fixed version (`git checkout v0.6.0`) instead of tracking `main`.
- Installer: add `--uninstall` (removes only the skill folder, never hook files or registrations), `--locale zh-CN` (idempotently appends Chinese trigger phrases to the installed description), and `--print-hook-config` (prints the registration snippet with resolved local interpreter/script paths, writes nothing). `--force` now backs up the existing install to a timestamped `.bak` folder instead of deleting it, and warns when the backup contained localized trigger phrases.
- Add `scripts/lesson_lint.py`: lint a lesson before it is written to persistent memory - flags credential patterns (AWS/GitHub/OpenAI-style keys, JWTs, PEM blocks, credential assignments), raw-log code blocks over 40 lines, missing durability sections (Trigger, Verified Facts, Preferred Procedure, Scope, Last Verified), and hedged language inside Verified Facts. Covered by `tests/test_lesson_lint.py` (5 tests, includes the shipped filled example as a clean fixture).
- Add `hooks/payload-probe.py` plus a "Verifying the Current Hook Schema" section in `hook-activation.md`: a temporary hook that records payload key names and value types (never values) so users can re-verify empirical field shapes such as Codex `tool_response.exit_code` after harness upgrades.

## 0.5.2 - 2026-07-09

- Add `install.py --dry-run` to print target paths, overwrite status, and optional hook-copy targets without creating, deleting, or copying files.
- Strengthen the `--skip-tests` warning so agents do not treat skipped tests as an ordinary successful validation path.
- Exclude Python cache artifacts (`__pycache__`, `*.pyc`, `*.pyo`) when copying the nested skill folder during install.
- Add the symmetric Codex unsafe-`session_id` test for the hardened hook detector. The hook detector suite is now 10/10 passing on Windows 11.
- Make the AI-assisted install prompt visible directly in both READMEs, while still pointing agents to `INSTALL_FOR_AGENTS.md`.

## 0.5.1 - 2026-07-09

- Add `install.py`: one-command install (`python install.py --agent codex|claude|project`) that runs the test suite, copies the nested skill folder, and verifies the result. Hooks are never registered automatically; `--with-hooks` only copies the script and prints manual registration steps. Tested end-to-end including the refuse-overwrite and `--force` paths.
- Add `INSTALL_FOR_AGENTS.md`: mechanical install instructions for AI agents, with explicit boundaries (no hooks by default, no persistent-config writes, copy only the nested folder, report what was and was not installed).
- Ship `SECURITY_NOTES.md` inside the nested skill folder so a folder-only install keeps its security guidance; the repository root copy is canonical. Fix the stale "sample hook scripts in references" wording and the dangling reference in `hook-activation.md`.
- Harden the hook detectors: hash `session_id` before using it in the state filename (path-safe against separator characters), and include `cwd` in the retry key so the same command in two directories is not conflated.
- Add three edge-case tests: different commands do not accumulate, same command in different cwd does not accumulate, and an unsafe `session_id` (path separators, colons) still counts correctly. 9/9 passing on Windows 11.
- Add Quick Start sections with the installer commands to both READMEs.

## 0.5.0 - 2026-07-09

- Extract the hook detector scripts from Markdown into runnable files (`hooks/retry-loop-detector-claude.py`, `hooks/retry-loop-detector-codex.py`) and add an automated stdlib-only test suite (`tests/test_retry_loop_detector.py` with JSON fixtures) covering fail/fail/reset sequences, BOM input, non-Bash tools, garbage input, and the Codex missing-exit-code fail-safe. 6/6 passing on Windows 11.
- Add a Simplified Chinese README (`README.zh-CN.md`) with a language switcher in both READMEs.
- Add `references/localization.md` with a copy-paste Chinese trigger addendum and guidance for other languages.
- Add `examples/bad-lessons.md`: six anti-example captures that poison memory (one-off rules, unverified guesses, log dumps with secrets, unscoped "always" rules, untrusted-content adoption, obvious restatements).
- Link `SECURITY_NOTES.md` from the README Safety Defaults and the hooks install section.
- Pin the Codex compatibility claim to the exact tested build (26.623.141536) and add a verified-date note to the Claude Code paths in `references/memory-surfaces.md`.
- Harden the Zotero example: never edit the SQLite database directly unless Zotero is closed, backed up, and the user explicitly approves.
- Add a `VERSION` file (kept out of `SKILL.md` frontmatter for validator compatibility).

## 0.4.4 - 2026-07-09

- Update `agents/openai.yaml` wording to match the 0.4.0 reframe (never solve the same problem twice; lesson capture and recall), replacing the older retry-loop-only positioning.
- Re-verify the Claude Code deployment live after syncing it to the 0.4.3 hook design (`-S`, 5s timeout, `utf-8-sig` stdin): reminder injected on the second identical failure.

## 0.4.3 - 2026-07-09

- Optimize hook examples for stdlib-only retry detectors: run Python with `-S` to skip site-package startup and reduce the timeout from 10 seconds to 5 seconds.
- Read hook JSON from `stdin.buffer` with `utf-8-sig` decoding, so Windows/BOM input does not silently disable the detector.
- Replace Unicode punctuation in `references/hook-activation.md` with ASCII punctuation for more portable validation and display.

## 0.4.2 - 2026-07-09

- Extend `SECURITY_NOTES.md` for the hook era: hooks are executable local code (never auto-installed without explicit approval, full interpreter paths, re-review after edits), and lessons are privileged writes — never capture a lesson sourced solely from untrusted content (memory-poisoning defense), scrub secrets from commands and error text before capture.
- Downgrade the Codex `tool_response.exit_code` claim from schema fact to empirically observed shape: the generated hook schema leaves `tool_response` unconstrained, so the detector must be re-tested after Codex upgrades (it fails safe if the field disappears).
- Add `Validation Evidence`, `Drift Risk`, and `Last Verified` fields to the Lesson Template so stale lessons are not treated as hard rules.
- Add a filled, completed lesson example (`examples/filled-lesson-libreoffice.md`) alongside the pattern examples.
- Pin compatibility claims to environment and date (Windows 11, Codex desktop 26.6xx, 2026-07-09).
- Document trigger-phrase localization: the repo `SKILL.md` stays ASCII for validator portability; users should append native-language trigger words to their installed copy when their harness handles UTF-8.

## 0.4.1 - 2026-07-09

- Keep `learning-retrospective/SKILL.md` ASCII-only so the existing Windows `quick_validate.py` path works even when Python defaults to a non-UTF-8 locale.
- Install the skill into `~/.codex/skills/learning-retrospective` and run Codex subagent forward tests for one trigger case and one non-trigger case.

## 0.4.0 - 2026-07-09

- Reframe the skill around its real target: solving the same problem twice. Failure on a novel problem is legitimate exploration and is no longer treated as a signal to interrupt; the only discipline imposed on novel problems is no verbatim retries and one explicit hypothesis per attempt.
- Add Post-Resolution Capture as the primary automatic mode: after a success that took two or more failed attempts or a non-obvious workaround, capture the lesson while the evidence is still in context.
- Add a known-vs-novel classification step to the workflow: search memory for the failure signature first; a covered failure is a known problem (follow the lesson), an uncovered one is novel (explore, then capture).
- Reword the hook reminder accordingly: "check memory for a prior lesson; if none, keep exploring with a changed hypothesis and capture the lesson after solving" instead of "stop retrying".
- Update the trigger description to include post-success capture and 总结经验.

## 0.3.2 - 2026-07-09

- Add a Codex hook-activation section: Codex now supports lifecycle hooks (`~/.codex/hooks.json` or inline `[hooks]` in `config.toml`), so the previous "instruction-level fallback only" advice for Codex was outdated. Key differences documented: no failure-specific event (branch on `tool_response.exit_code` in one `PostToolUse` script), handler `command` is a string with optional `commandWindows`, and non-managed hooks require one-time user trust via `/hooks` before they run.
- Remove the "Suggested GitHub Metadata" section from the README — authoring-time scaffolding, not reader-facing.

## 0.3.1 - 2026-07-09

- Replace the untested Claude Code hook sketch with a design deployed and verified live on Windows. The 0.3.0 sketch had a fatal flaw: it listened on `PostToolUse`, which fires only on successful tool calls, so it could never see a failure. The tested design registers one script on both `PostToolUse` (success resets the counter) and `PostToolUseFailure` (failure increments it).
- Use exec form with a full interpreter path in the hook registration: on Windows, hook commands may run through Git Bash, whose PATH can lack `python` even when PowerShell finds it.
- Document the two-step verification procedure (synthetic-JSON pipe test, then a live forced failure) so the hook is never trusted untested — the same failure gate this skill prescribes for everything else.

## 0.3.0 - 2026-07-09

- Rewrite the trigger description in second person and add Chinese trigger phrases (复盘, 总结教训, 记住这个坑, …) for bilingual recall.
- Add `references/hook-activation.md`: automatic activation via harness hooks, with a Claude Code `PostToolUse` repeated-failure detector example.
- Correct Claude Code memory-surface facts (per-project memory directory, frontmatter format, `MEMORY.md` index) in `references/memory-surfaces.md`.
- Add a generic dependency-install loop example.
- Mark Claude Code as tested in the compatibility table (deployed and discovered live, 2026-07-09).

## 0.2.0 - 2026-07-09

- Tighten trigger language and add explicit non-triggers.
- Add a write permission gate for persistent memory, project docs, and skill edits.
- Add concrete examples for PDF rendering, GitHub Actions, DOCX conversion, and Zotero linked attachments.
- Clarify installation instructions and compatibility notes.
- Document MIT licensing and suggested GitHub metadata.

## 0.1.0 - 2026-07-09

- Initial public version of the learning retrospective skill.

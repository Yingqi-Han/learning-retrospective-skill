# Changelog

## 0.8.1 - 2026-07-24

- Keep the two-call exact-repeat path fast, but stop treating every six unknown
  Codex shell results as a semantic-review candidate.
- Require broad activity-only review to span 12 calls, at least three command
  signatures, and at least 120 seconds. Back it off for at least 24 additional
  calls and 15 minutes after each broad review.
- Add bounded local tuning fields for the activity window and record
  `candidate_reason` in the privacy-safe evidence manifest and diagnostics.
- Add regression tests proving that a rapid 12-command inspection burst makes
  no model call while sustained activity still reviews at the configured
  boundary.

## 0.8.0 - 2026-07-24

- Bind every semantic review request to a privacy-safe
  `HOOK_EVIDENCE_MANIFEST` generated from actual hook payloads. The manifest
  carries a request id, ordered event indexes, command signatures, and
  structured/unknown outcomes without storing raw commands or output.
- Require the main agent to build `REVIEW_PACKET_V1` by copying relevant raw
  tool-event fields instead of replacing them with an unverifiable free-form
  summary.
- Split semantic triage from lesson verification: the isolated child reports
  failure-family similarity, while `known_loop` now requires a source-labelled
  prior lesson and `prior_lesson_verified=true`. The direct Codex backend has no
  memory access and therefore cannot interrupt a task on its own.
- Stop conflating no-write and no-tool guarantees. Distinguish
  `enforced_no_tools`, `enforced_read_only`, and `prompt_only`, and use
  non-inherited task context when available.
- Extend the reviewer schema with `schema_version`, `request_id`,
  `evidence_adequate`, and `reviewer_isolation`. Retry malformed output once
  with the same reviewer, then apply a request-bound fail-closed result.
- Require a non-empty `reviewer_agent_id` from the actual spawn call and a wait
  on exactly that id. Empty-target waits and missing spawn traces now degrade to
  `reviewer_unavailable` instead of being reported as reviewer conclusions.
- Add manifest provenance, ordering, outcome, privacy, and reviewer-protocol
  assertions to the hook test suite.
- Add an explicit opt-in Codex CLI reviewer backend. It reconstructs a bounded
  evidence packet from the actual parent rollout, redacts common credential
  shapes, launches the configured model in a temporary user-context-isolated
  Codex home with tool-bearing features disabled, a read-only sandbox, and a
  strict output schema. It rejects unexpected tool traces, captures the runtime
  thread id, and injects the validated result without relying on main-agent
  compliance.
- Harden the backend after adversarial review: cover API keys, AWS keys,
  authenticated URLs, cookies, npm tokens, JWTs, and private keys; normalize
  command/cwd signatures across hook and rollout sources; derive exit status
  only from anchored Codex shell envelopes; require two failed tool events for
  an activity-mode `known_loop`; cap model time at 45 seconds; and terminate
  the reviewer process group on timeout.
- Make `--with-hooks` transactional with staging, verification, detector-last
  activation, rollback tests, and backups outside the active hooks directory.
  Correct the documentation examples to use 5 seconds for Claude's lightweight
  detector and 60 seconds for the opt-in Codex model path.
- Keep `main_agent` as the portable public default. The installer copies the
  new backend, preserves local activation settings, and prints a 60-second
  Codex hook timeout suitable for the opt-in model call.

## 0.7.1 - 2026-07-24

- Fix Codex hooks on Windows: add a `commandWindows` override with PowerShell's `&` call operator. A quoted executable path without `&` exited before Python started, producing the misleading `hook exited with code 1` UI state.
- Add a Codex compatibility fallback for builds such as `0.145.0` that expose `tool_response` as output text without a structured exit code. The detector never parses command output to guess success; it requests semantic review after an exact command repeats or after a bounded six-call activity window.
- Preserve deterministic failure counting on harness versions that do provide structured exit codes, while keeping the public reviewer contract vendor-neutral.
- Add privacy-safe malformed-stdin diagnostics and Codex activity-fallback tests. The complete stdlib-only suite now has 32 tests.
- Require an actual fresh read-only subagent when the harness exposes multi-agent tools, name Codex's SpawnAgent/collaboration surface explicitly, provide an exact fail-closed replacement for invalid or internally inconsistent reviewer JSON, and exclude user-requested probes from loop classification.
- Reject boolean pseudo-exit-codes instead of accepting them as integers in Python payloads.
- Correct Codex trust guidance: Desktop Hooks settings and CLI/TUI `/hooks` are different surfaces, enablement is not trust, and `hooks/list` is the authoritative diagnostic for `currentHash` and `trustStatus`.

## 0.7.0 - 2026-07-24

- Add two-tier retry detection: exact repeated failures still trigger deterministic reminders at counts 2, 4, 8..., while three failures across at least two command signatures in the latest six Bash calls request a bounded semantic review.
- Add a vendor-neutral, read-only secondary-agent classification contract that distinguishes `known_loop`, `novel_exploration`, `routine_failure`, and `uncertain`; interrupt only high-confidence known loops.
- Add optional local reviewer preferences (`preferred_model`, reasoning effort, confidence threshold) without making any model or vendor a public dependency. Hooks never launch model processes directly.
- Add semantic-review tests for both Claude Code and Codex, including configured-model routing, cooldown behavior, and a privacy check that raw commands are not injected by the hook.
- Add privacy-safe Codex hook diagnostics and fail-open handling for malformed payloads or internal detector errors.

## 0.6.6 - 2026-07-10

- Fix the cross-platform CI assertion for ASCII-safe localized descriptions. The original one-line YAML/Bash/Python command lost one backslash layer under Bash and compared decoded Chinese text against escaped on-disk text, even though all 20 tests and installer operations had passed. Use an ASCII-only Python here-document and construct the decoded trigger from Unicode code points, avoiding both multi-layer escaping and shell-specific source encoding.

## 0.6.5 - 2026-07-10

- Make installation genuinely transactional: copy, localize, and verify in an external staging directory before activation; keep timestamped backups outside active skill discovery; restore the previous install automatically if activation or final verification fails.
- Run the complete unittest suite from `install.py`, including lesson-lint tests, instead of reporting success after hook tests alone. Verify the complete copied file manifest and required runtime files.
- Keep localized `SKILL.md` files ASCII-safe: `--locale zh-CN` now emits Chinese trigger phrases as JSON-compatible YAML Unicode escapes, preserving Chinese semantics without breaking Windows GBK-default validators.
- Harden both retry detectors: ignore payloads without session ids, tolerate malformed state types, write state atomically, remove state older than seven days, and emit reminders at 2, 4, 8... repeated failures instead of every retry. Tests now clean up their own state files.
- Shorten `agents/openai.yaml` UI metadata to the recommended range. Upgrade GitHub Actions to Node 24-based `checkout@v6` and `setup-python@v6`, add read-only contents permission, and consolidate CI on full unittest discovery.

## 0.6.4 - 2026-07-09

- Fix `lesson_lint.py --help`: the flag was treated as a file path and errored. The CLI now uses argparse with proper usage/help output; exit-code contract unchanged (0 clean, 1 findings, 2 usage error). Added a help-flag test (lint suite now 6 tests).
- Add a Release Verification section to `SECURITY_NOTES.md`: tags are annotated but not GPG-signed; strict environments should pin and review a commit SHA rather than trusting a tag name.


## 0.6.3 - 2026-07-09

- Make the hook intervention visible to the user, not just the model: both detectors now emit `systemMessage` (short, shown in the harness UI) alongside `hookSpecificOutput.additionalContext` (full reminder, injected into the model's context). Found while trying to screenshot the reminder in the Claude Code desktop app: the injection worked but left no user-visible trace, and an invisible intervention cannot be trusted or debugged.

## 0.6.2 - 2026-07-09

- Strip the UTF-8 BOM that a PowerShell 5.1 `Set-Content -Encoding UTF8` edit had introduced into both READMEs.
- Update the manual-install tree to include `SECURITY_NOTES.md` and `scripts/`, matching the actual package contents.
- `--print-hook-config` now notes when the hook script is not yet present at the printed path (run `--with-hooks` first).
- State the Python support boundary precisely in both READMEs and the installer docstring: CI-tested on 3.10-3.14, kept 3.8-compatible by inspection.

## 0.6.1 - 2026-07-09

- Fix the lesson-lint test on CRLF checkouts: Windows GitHub runners check out with `autocrlf=true`, so a `\n`-literal fence split never matched. Normalize newlines and pin subprocess IO encoding to UTF-8.
- Drop the retired `ubuntu-22.04` / Python 3.8 CI job (the image cancels without running); CI-tested floor is 3.10, code floor remains 3.8 by inspection.
- CI is green on this release: 9 jobs across Linux/Windows/macOS x Python 3.10/3.12/3.14. Prefer the `v0.6.1` tag over `v0.6.0`, which predates the Windows test fix.

## 0.6.0 - 2026-07-09

- Add GitHub Actions CI: hook detector tests, lesson lint tests, and an installer end-to-end run (install, dry-run, force-update with locale, uninstall) across Linux/Windows/macOS on Python 3.10-3.14 (3.8 remains the code floor by inspection; EOL interpreters are not CI-tested). Test badges added to both READMEs.
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

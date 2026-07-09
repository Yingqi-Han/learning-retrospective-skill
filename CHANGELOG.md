# Changelog

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

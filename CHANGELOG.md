# Changelog

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

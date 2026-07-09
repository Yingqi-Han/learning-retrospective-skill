# Learning Retrospective Skill

**English** | [简体中文](README.zh-CN.md)

`learning-retrospective` is a small, agent-agnostic skill for stopping repeated trial-and-error and preserving verified lessons.

It is designed to work with Codex, Claude Code, Cursor, Cline, OpenCode, or any agent harness that can load `SKILL.md`-style instructions or plain Markdown guidance.

## Philosophy

Failure is not error — repeated attempts on a novel problem are legitimate exploration. The waste this skill targets is solving the **same** problem twice: struggling through a failure loop that a past session already resolved, because the lesson was never captured or never recalled. So it distinguishes two modes: on a **known problem** (a stored lesson covers the failure signature), recall and follow the lesson before the next attempt; on a **novel problem**, explore freely — just never retry verbatim — and capture the lesson automatically after solving it.

## What It Does

- Capture lessons automatically after a hard-won success (two or more failed attempts, non-obvious workaround, machine-specific fact) — the primary mode.
- Check memory for a prior lesson before re-deriving a fix, and classify the problem as known or novel.
- Detect verbatim retry loops and force an evidence checkpoint before more tool switching.
- Add explicit failure gates before broad discovery.
- Capture only verified, reusable lessons.
- Route lessons to user memory, project memory, or skill updates.
- Optionally ask any available secondary reviewer or agent for a bounded audit.
- Optionally activate automatically via harness hooks that detect repeated failures (see `learning-retrospective/references/hook-activation.md`; the Claude Code detector there is deployed and verified live, 2026-07-09).

## Quick Start

```bash
git clone https://github.com/Yingqi-Han/learning-retrospective-skill.git
cd learning-retrospective-skill
python install.py --agent codex     # or: --agent claude
python install.py --agent project --target ./.agent-skills   # project-level
```

The installer runs the test suite, copies the nested skill folder, and verifies the result. Hooks are optional and are **not** installed by default; use `--with-hooks` only after reading [`SECURITY_NOTES.md`](SECURITY_NOTES.md), and registration always stays manual. To have an AI agent perform the install, point it at [`INSTALL_FOR_AGENTS.md`](INSTALL_FOR_AGENTS.md).

## Manual Install

Copy the nested skill folder into a supported skills directory. Do not copy the repository root unless your agent explicitly supports repository-level skill discovery.

```text
learning-retrospective/
  SKILL.md
  VERSION
  agents/openai.yaml
  references/
  examples/
  hooks/      # runnable retry-loop detector scripts (optional)
  tests/      # automated tests for the hook scripts
```

Examples:

```bash
# Correct: copy the nested skill folder, not the repository root
cp -r ./learning-retrospective ~/.codex/skills/

# Claude Code-style local skills
cp -r ./learning-retrospective ~/.claude/skills/

# Project-level shared skill
mkdir -p ./.agent-skills
cp -r ./learning-retrospective ./.agent-skills/
```

If your agent does not support skill folders, paste `SKILL.md` into its custom instructions and load the reference files when needed.

### Localization of trigger phrases

The repository copy of `SKILL.md` is ASCII-only because at least one skill validator (Codex `quick_validate.py` on Windows) reads files with the locale default encoding and crashes on non-ASCII bytes under a GBK locale. If you interact with your agent in another language and your harness handles UTF-8 (Claude Code does), append native-language trigger phrases to the `description:` line of your **installed** copy — description-based recall improves markedly when the trigger words match the language you actually type. See `learning-retrospective/references/localization.md` for a copy-paste Chinese addendum and guidance for other languages.

### Hooks (optional, read the security notes first)

Runnable retry-loop detector scripts for Claude Code and Codex live in `learning-retrospective/hooks/`, with an automated test suite in `learning-retrospective/tests/` (stdlib-only):

```bash
python learning-retrospective/tests/test_retry_loop_detector.py
```

Hooks are executable local code that runs on every future tool call — read `SECURITY_NOTES.md` before installing, review the scripts, and verify with one forced live failure after registration. Registration steps per harness are in `learning-retrospective/references/hook-activation.md`.

## Compatibility

| Agent | Tested | Install surface | Notes |
|---|---:|---|---|
| Codex | yes, structure validated and subagent-tested (Windows 11, Codex desktop app 26.623.141536, 2026-07-09) | `~/.codex/skills/` | Uses `SKILL.md` frontmatter and optional `agents/openai.yaml`; keep `SKILL.md` ASCII-only for Windows validator compatibility. Hook config pipe-tested; hook field shapes are empirical, re-test after upgrades. |
| Claude Code | yes, deployed and discovered (Windows 11, 2026-07-09) | `~/.claude/skills/` | Copy the folder; the skill is discovered live from `SKILL.md` frontmatter, no restart needed. `agents/openai.yaml` is ignored. Hook-based auto-activation verified live same date — see `references/hook-activation.md`. |
| Cursor | not yet | rules or custom instructions | Paste `SKILL.md`; load references manually as needed. |
| Cline | not yet | `.clinerules` or memory bank | Use as plain Markdown workflow guidance if skill folders are unavailable. |
| OpenCode | not yet | custom skill or instruction folder | Use the same `SKILL.md` plus references pattern if supported. |

## Safety Defaults

- Do not write to user memory, repository rules, project docs, or other skills unless the user explicitly asked to save/update the lesson.
- Present the proposed lesson and target surface first when permission is unclear.
- Do not store secrets, tokens, cookies, credentials, private data, long raw logs, or unverified guesses.
- Complete the user's task before spending time on retrospective writing.
- Before installing hook scripts, read [`SECURITY_NOTES.md`](SECURITY_NOTES.md): hooks are executable local code, and lessons are persistent privileged writes (memory-poisoning surface).

## Examples

The `examples/` directory contains concrete loop patterns:

- PDF rendering/conversion loop
- GitHub Actions retry loop
- DOCX conversion loop
- Zotero linked attachment loop
- Dependency install loop
- A filled, completed lesson (LibreOffice conversion) showing what capture output should look like
- Anti-examples (`bad-lessons.md`): captures that poison memory and must be rejected

## Positioning

This is not a memory database, MCP server, hook framework, or autonomous skill generator. It is the small control loop that decides:

1. Are we repeating failed attempts?
2. What verified fact did we miss?
3. What is the next evidence-backed action?
4. What lesson should future agents remember?

It can be used alongside larger systems such as Claudeception, 10x/agent-loom, claude-memory-skill, or agentmemory.

## License

MIT. See `LICENSE`.

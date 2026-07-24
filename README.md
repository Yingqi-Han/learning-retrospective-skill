# Learning Retrospective Skill

[![tests](https://github.com/Yingqi-Han/learning-retrospective-skill/actions/workflows/test.yml/badge.svg)](https://github.com/Yingqi-Han/learning-retrospective-skill/actions/workflows/test.yml)

**English** | [简体中文](README.zh-CN.md)

`learning-retrospective` is a small, agent-agnostic skill for stopping repeated trial-and-error and preserving verified lessons.

It is designed to work with Codex, Claude Code, Cursor, Cline, OpenCode, or any agent harness that can load `SKILL.md`-style instructions or plain Markdown guidance.

## Philosophy

Failure is not error — repeated attempts on a novel problem are legitimate exploration. The waste this skill targets is solving the **same** problem twice: struggling through a failure loop that a past session already resolved, because the lesson was never captured or never recalled. So it distinguishes two modes: on a **known problem** (a stored lesson covers the failure signature), recall and follow the lesson before the next attempt; on a **novel problem**, explore freely — just never retry verbatim — and capture the lesson automatically after solving it.

## What It Does

- Capture lessons automatically after a hard-won success (two or more failed attempts, non-obvious workaround, machine-specific fact) — the primary mode.
- Check memory for a prior lesson before re-deriving a fix, and classify the problem as known or novel.
- Detect exact retry candidates and escalate short multi-command activity or failure windows to a bounded semantic reviewer.
- Add explicit failure gates before broad discovery.
- Capture only verified, reusable lessons.
- Route lessons to user memory, project memory, or skill updates.
- Optionally ask any available fast secondary reviewer to distinguish a known loop from evidence-producing novel exploration.
- Optionally activate automatically via harness hooks that detect repeated failures (see `learning-retrospective/references/hook-activation.md`; the Claude Code detector there is deployed and verified live, 2026-07-09).

## Quick Start

```bash
git clone https://github.com/Yingqi-Han/learning-retrospective-skill.git
cd learning-retrospective-skill
python install.py --agent codex     # or: --agent claude
python install.py --agent project --target ./.agent-skills   # project-level
```

The installer runs the test suite, copies the nested skill folder, and verifies the result. Hooks are optional and are **not** installed by default; use `--with-hooks` only after reading [`SECURITY_NOTES.md`](SECURITY_NOTES.md), and registration always stays manual. To have an AI agent perform the install, point it at [`INSTALL_FOR_AGENTS.md`](INSTALL_FOR_AGENTS.md).

Useful flags:

- `--locale zh-CN` — append Chinese trigger phrases as ASCII YAML escapes (better recall without breaking locale-default Windows validators; see `references/localization.md`).
- `--force` — transactionally update an existing install; the old copy is kept in a timestamped backup directory outside active skill discovery.
- `--uninstall` — remove the installed skill folder (hook scripts/registrations are never touched).
- `--print-hook-config` — print the hook registration snippet with resolved local paths; writes nothing.
- `--dry-run` — preview every path the installer would touch.

To install a fixed version instead of latest `main`, check out the latest release tag first (`git tag --list`, then e.g. `git checkout v0.6.6`).

Python: CI-tested on 3.10-3.14 (Linux/Windows/macOS); the code is kept 3.8-compatible by inspection, but EOL interpreters are not CI-tested.

AI-assisted install prompt:

```text
Clone https://github.com/Yingqi-Han/learning-retrospective-skill and install it
for Codex or Claude Code following INSTALL_FOR_AGENTS.md. Do not install hooks
unless I explicitly confirm.
```

Preview writes without changing files:

```bash
python install.py --agent codex --dry-run
```

## Manual Install

Copy the nested skill folder into a supported skills directory. Do not copy the repository root unless your agent explicitly supports repository-level skill discovery.

```text
learning-retrospective/
  SKILL.md
  VERSION
  SECURITY_NOTES.md
  agents/openai.yaml
  references/
  examples/
  hooks/      # runnable retry-loop detector scripts + payload probe (optional)
  scripts/    # lesson_lint.py - lint a lesson before writing it to memory
  tests/      # automated tests for the hook scripts and the lint
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

The repository copy of `SKILL.md` is ASCII-only because at least one skill validator (Codex `quick_validate.py` on Windows) reads files with the locale default encoding and crashes on non-ASCII bytes under a GBK locale. Prefer `--locale zh-CN`: the installer writes Chinese triggers as YAML `\uXXXX` escapes, so YAML-aware agents recover the Chinese text while the file stays ASCII-compatible. See `learning-retrospective/references/localization.md` for manual and other-language guidance.

### Hooks (optional, read the security notes first)

Runnable retry-loop detector scripts for Claude Code and Codex live in `learning-retrospective/hooks/`, with an automated test suite in `learning-retrospective/tests/` (stdlib-only):

```bash
python -S -m unittest discover -s learning-retrospective/tests -v
```

Hooks are executable local code that runs on every future tool call — read `SECURITY_NOTES.md` before installing, review the scripts, and verify with one live candidate after registration. Registration steps per harness are in `learning-retrospective/references/hook-activation.md`.

The detectors use two tiers. Harnesses that expose structured failure status retain deterministic repeated-failure reminders. On Codex builds that expose only output text, the detector never guesses failure from error keywords. An exact repeat still requests review on the second call. Broad activity-only review is deliberately slower: by default it requires 12 calls across at least three command signatures over at least 120 seconds, then waits at least 24 more calls and 15 minutes before another broad review. These bounds are locally configurable. The hook supplies a privacy-safe manifest of events it actually observed. The protocol distinguishes enforced tool denial, filesystem read-only mode, and a prompt-only contract instead of treating them as equivalent.

The public default is `review_backend: "main_agent"` and never starts a model process. Codex users may explicitly opt into `review_backend: "codex_cli"` in their local reviewer config. That backend reads a bounded parent-rollout tail, redacts common credential forms, runs one real Codex child in a temporary `CODEX_HOME`, disables shell/web/browser/MCP-style tool surfaces before the model call, enforces `--sandbox read-only`, validates a strict output schema, captures the runtime `thread_id`, and injects the result directly. The temporary home copies file-based Codex authentication for the duration of the call, but does not inherit user skills, hooks, rules, or memory; Codex built-in system context still exists. Therefore the child performs semantic triage (`same_failure_family`) rather than pretending to know stored lessons. The main agent performs one bounded lesson lookup and may promote the result to `known_loop` only after citing a still-applicable source-labelled lesson. Increase the Codex hook timeout to 60 seconds before enabling it. `install.py --with-hooks` transactionally copies the backend while preserving the user's active configuration. See `learning-retrospective/references/semantic-review.md`.

## Compatibility

| Agent | Tested | Install surface | Notes |
|---|---:|---|---|
| Codex | yes, structure validated and subagent-tested (Windows 11; semantic classifier re-tested with an optional fast reviewer, 2026-07-24) | `~/.codex/skills/` | Uses `SKILL.md` frontmatter and optional `agents/openai.yaml`; keep `SKILL.md` ASCII-only for Windows validator compatibility. Hook field shapes are empirical; re-test and re-trust after upgrades or edits. |
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

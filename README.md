# Learning Retrospective Skill

`learning-retrospective` is a small, agent-agnostic skill for stopping repeated trial-and-error and preserving verified lessons.

It is designed to work with Codex, Claude Code, Cursor, Cline, OpenCode, or any agent harness that can load `SKILL.md`-style instructions or plain Markdown guidance.

## What It Does

- Detect retry loops and repeated fallback behavior.
- Force an evidence checkpoint before more tool switching.
- Add explicit failure gates before broad discovery.
- Capture only verified, reusable lessons.
- Route lessons to user memory, project memory, or skill updates.
- Optionally ask any available secondary reviewer or agent for a bounded audit.

## Install

Copy the nested skill folder into a supported skills directory. Do not copy the repository root unless your agent explicitly supports repository-level skill discovery.

```text
learning-retrospective/
  SKILL.md
  agents/openai.yaml
  references/
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

## Compatibility

| Agent | Tested | Install surface | Notes |
|---|---:|---|---|
| Codex | yes, structure validated | `~/.codex/skills/` | Uses `SKILL.md` frontmatter and optional `agents/openai.yaml`. |
| Claude Code | not yet | `~/.claude/skills/` or project guidance | May need manual confirmation of local skill discovery behavior. |
| Cursor | not yet | rules or custom instructions | Paste `SKILL.md`; load references manually as needed. |
| Cline | not yet | `.clinerules` or memory bank | Use as plain Markdown workflow guidance if skill folders are unavailable. |
| OpenCode | not yet | custom skill or instruction folder | Use the same `SKILL.md` plus references pattern if supported. |

## Safety Defaults

- Do not write to user memory, repository rules, project docs, or other skills unless the user explicitly asked to save/update the lesson.
- Present the proposed lesson and target surface first when permission is unclear.
- Do not store secrets, tokens, cookies, credentials, private data, long raw logs, or unverified guesses.
- Complete the user's task before spending time on retrospective writing.

## Examples

The `examples/` directory contains concrete loop patterns:

- PDF rendering/conversion loop
- GitHub Actions retry loop
- DOCX conversion loop
- Zotero linked attachment loop

## Positioning

This is not a memory database, MCP server, hook framework, or autonomous skill generator. It is the small control loop that decides:

1. Are we repeating failed attempts?
2. What verified fact did we miss?
3. What is the next evidence-backed action?
4. What lesson should future agents remember?

It can be used alongside larger systems such as Claudeception, 10x/agent-loom, claude-memory-skill, or agentmemory.

## Suggested GitHub Metadata

Suggested repository description:

```text
Agent-agnostic skill for breaking retry loops and capturing verified workflow lessons.
```

Suggested topics:

```text
agent-skill, codex, claude-code, cursor, cline, opencode, ai-agents, memory, retrospective, workflow
```

## License

MIT. See `LICENSE`.

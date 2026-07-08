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

Copy this folder into a supported skills directory:

```text
learning-retrospective/
  SKILL.md
  agents/openai.yaml
  references/
```

Examples:

```bash
# Codex-style local skills
cp -r learning-retrospective ~/.codex/skills/

# Claude Code-style local skills
cp -r learning-retrospective ~/.claude/skills/

# Project-level shared skill
mkdir -p ./.agent-skills
cp -r learning-retrospective ./.agent-skills/
```

If your agent does not support skill folders, paste `SKILL.md` into its custom instructions and load the reference files when needed.

## Positioning

This is not a memory database, MCP server, hook framework, or autonomous skill generator. It is the small control loop that decides:

1. Are we repeating failed attempts?
2. What verified fact did we miss?
3. What is the next evidence-backed action?
4. What lesson should future agents remember?

It can be used alongside larger systems such as Claudeception, 10x/agent-loom, claude-memory-skill, or agentmemory.

## License

Choose a license before publishing. MIT is a reasonable default for this kind of prompt/skill artifact, but the repository owner should decide.

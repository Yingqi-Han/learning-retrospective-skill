# Memory Surfaces

Store lessons where future agents are likely to find them. Prefer plain text, small entries, and grep-friendly keywords.

## User-Level Memory

Use for facts that apply across projects on one machine or to one user's preferences:

- installed tool paths
- proxy/network setup
- preferred package managers
- recurring account or browser workflows
- user's preferred level of verification

Examples:

- Codex: user memory folder, local skills, or persistent instructions if available.
- Claude Code: per-project memory at `~/.claude/projects/<project-slug>/memory/` — one fact per file with YAML frontmatter (`name`, `description`, `metadata.type`), indexed by a one-line entry in that directory's `MEMORY.md`; `~/.claude/CLAUDE.md` for user-global instructions; `~/.claude/skills/` for user-level skills.
- Cursor/Cline/OpenCode: memory bank, rules files, notes, or custom instruction files supported by the tool.
- Generic: `~/agent-memory/`, `~/.config/<agent>/memory/`, or a user-maintained markdown knowledge base.

Note for Claude Code: when writing a lesson as a memory file, use the harness's native frontmatter format rather than the raw Lesson Template — put the trigger into `description:` (that field drives recall) and the template body below the frontmatter.

Platform paths above are drift-prone facts. The Claude Code details were verified on Windows 11, 2026-07-09; re-check them after harness upgrades before relying on them.

## Project-Level Memory

Use for repository-specific facts:

- architecture choices
- test commands
- service startup order
- migration rules
- deployment constraints
- known flaky tests and accepted workarounds

Good surfaces:

- `AGENTS.md`
- `CLAUDE.md`
- `.cursor/rules/`
- `.clinerules`
- `docs/agent-notes.md`
- `.ai/knowledge/`
- repo-local skills

## Skill Updates

Update or create a skill when the lesson is procedural and likely to recur:

- multi-step repair workflows
- document conversion pipelines
- release or PR routines
- data validation checklists
- environment setup recipes

Keep skills concise. Move longer examples or platform variants into `references/`.

## What Not To Store

- API keys, tokens, cookies, or passwords
- private user data that is not needed for future execution
- huge logs or whole stack traces
- one-off mistakes with no reusable lesson
- guesses that were not verified

## Write Shape

Each memory entry should answer:

- When should this be recalled?
- What exact fact was verified?
- What should future agents do first?
- What should they avoid retrying?
- What validation proves success?

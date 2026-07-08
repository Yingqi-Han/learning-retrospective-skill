---
name: learning-retrospective
description: Agent-agnostic loop breaker and lesson-capture workflow. Use when an AI coding agent is repeating failed attempts, rediscovering known local facts, switching tools without new evidence, hitting the same error multiple times, or when the user asks the agent to learn from mistakes, create a retrospective, update memory, avoid future retry loops, or make the workflow portable across Codex, Claude Code, Cursor, Cline, OpenCode, or other agent harnesses.
---

# Learning Retrospective

Use this skill to stop repeated trial-and-error and turn verified lessons into durable context for future agents. Keep the main task moving; the retrospective should be a short control loop, not a new project.

## Loop Signals

Trigger a retrospective when one or more signals appear:

- The same command, test, conversion, install, API call, or UI action fails twice.
- The agent starts broad discovery after a verified local fact should have been checked.
- The agent switches tools repeatedly without a new hypothesis.
- The user says the agent is looping, forgot prior work, or should remember the lesson.
- A fix depends on machine-specific paths, environment variables, installed tools, credentials flow, account state, or project conventions.
- A failure was resolved by a non-obvious command, local workaround, or order of operations.

Do not run this workflow for every small error. Use it when the lesson is reusable or the current behavior is starting to waste time.

## Workflow

1. Pause the loop.
   - Stop broad search, repeated fallback attempts, and speculative edits.
   - State the immediate goal, the last failing action, and the exact error or symptom.
   - Preserve any running process or user data before changing course.

2. Rebuild the evidence.
   - List what is already verified, including paths, versions, commands, outputs, and files.
   - Search existing memory or project guidance before asking the user to repeat context.
   - Prefer cheap verification of drift-prone facts over assumptions.

3. Choose one next hypothesis.
   - Pick the smallest command or edit that directly tests the leading hypothesis.
   - Add a failure gate: define what result means success, what result means stop, and what fallback is allowed.
   - Avoid falling through into unrelated fallback discovery when the gate fails.

4. Complete the user task first.
   - Fix, convert, install, test, or configure the actual target.
   - Verify with observed evidence, not confidence.
   - Keep backups temporary and remove them after the user confirms they are no longer needed.

5. Capture the lesson.
   - Record only lessons that are verified, reusable, and non-obvious.
   - Include exact commands, paths, versions, failure text, and the better order of operations.
   - Exclude secrets, private data, long logs, and unverified guesses.
   - Prefer one small memory update over a large narrative.

6. Store it in the right surface.
   - Use user-level memory for cross-project machine or preference facts.
   - Use repo/project docs for project-specific conventions.
   - Update an existing skill only when the lesson changes a reusable procedure.
   - Create a new skill only when the procedure is recurring, portable, and worth triggering automatically.
   - See `references/memory-surfaces.md` for platform-neutral placement guidance.

7. Optionally ask an independent reviewer.
   - Use any available secondary agent, model, reviewer prompt, or fresh session; do not require a specific vendor or model.
   - Give it only the artifact paths, the failed loop summary, and the concrete validation questions.
   - Ask for the smallest safety or clarity improvement.
   - If no subagent exists, run the same checklist yourself.
   - See `references/reviewer-prompt.md`.

## Lesson Template

```markdown
# Lesson: <short name>

## Trigger
- What pattern should make a future agent recall this?

## Verified Facts
- Exact paths, versions, commands, files, or account state.

## Failed Attempts To Avoid
- Attempts that were tried and why they were wrong or wasteful.

## Preferred Procedure
1. First command/check.
2. Validation gate.
3. Fallback only if the gate fails.

## Scope
- Applies to: <machine/project/tool/context>
- Does not apply to: <known boundaries>
```

## Final Response

Tell the user:

- What loop was detected.
- What task result was achieved.
- What lesson was captured and where it was written.
- What limitation remains, especially if future agents must explicitly load memory or invoke the skill.

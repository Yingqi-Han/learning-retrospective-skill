---
name: learning-retrospective
description: Use when a task just succeeded after multiple failed attempts or a non-obvious workaround (capture the lesson), when you are re-encountering a problem that a stored lesson already covers, when you have repeated the same failed action verbatim, or when the user asks for a retrospective or lesson to prevent future retry loops. Do not use for ordinary first-pass debugging of a novel problem, general memory notes, pure explanation, summarization, translation, or writing tasks.
---

# Learning Retrospective

Use this skill to turn verified lessons into durable context for future agents, so a problem solved once is never re-solved by trial-and-error. Keep the main task moving; the retrospective should be a short control loop, not a new project.

Failure is not error. Repeated attempts on a **novel** problem are legitimate exploration and must not be suppressed - the only discipline a novel problem needs is no verbatim retries and one explicit hypothesis per attempt. The behavior this skill exists to eliminate is different: struggling through the **same** problem a second time because the first solution was never captured, or was captured but not recalled. So the skill has two modes with different strengths:

- **Known problem** (a stored lesson or memory covers this failure signature): intervene early - recall the lesson before the next attempt and follow it.
- **Novel problem** (no prior lesson): do not interrupt exploration. Vary the approach instead of retrying verbatim, solve it, then capture the lesson afterward.

## Post-Resolution Capture

This is the primary automatic mode. After a task succeeds, check one question before ending the turn: did getting here involve two or more failed attempts, a non-obvious workaround, a machine-specific fact, or an order of operations that a future agent would have to rediscover? If yes, run steps 5-6 of the Workflow (capture the lesson, store it in the right surface, subject to the Write Permission Gate). If no, end normally - do not manufacture lessons out of routine work.

The capture must happen while the evidence is still in context: exact commands, exact error text, what was tried and why it failed. A lesson written from memory of the struggle is worth less than one written from the transcript of it.

## Loop Signals

Trigger a retrospective when one or more signals appear:

- The same command, test, conversion, install, API call, or UI action fails twice.
- Several different commands fail within one short window while pursuing the
  same goal or switching tools without a new hypothesis.
- The agent starts broad discovery after a verified local fact should have been checked.
- The agent switches tools repeatedly without a new hypothesis.
- The user says the agent is looping, forgot prior work, or should remember the lesson.
- A fix depends on machine-specific paths, environment variables, installed tools, credentials flow, account state, or project conventions.
- A failure was resolved by a non-obvious command, local workaround, or order of operations.

Do not run this workflow for every small error. Use it when the lesson is reusable or the current behavior is starting to waste time.

## Non-Triggers

Do not invoke this skill for:

- A first-time ordinary error with an obvious next fix.
- Normal debugging where each attempt produces new evidence.
- Pure explanation, summarization, translation, or writing tasks.
- Broad project review unless a repeated failure pattern has already appeared.
- Memory updates requested by the user that do not involve a workflow lesson.

## Write Permission Gate

Before writing to user memory, repository docs, project rules, or another skill:

- If the user explicitly asked to save, update, or write the lesson, proceed.
- Otherwise, present the proposed lesson and target surface first.
- Never modify project instructions, skills, or persistent memory silently.
- Never store secrets, tokens, credentials, cookies, private data, or long raw logs.

## Workflow

1. Pause the loop.
   - Stop verbatim retries, broad unfocused search, and speculative edits.
   - State the immediate goal, the last failing action, and the exact error or symptom.
   - Preserve any running process or user data before changing course.

2. Rebuild the evidence and classify the problem.
   - Search existing memory and project guidance for this failure signature first. If a prior lesson covers it, this is a known problem: follow the lesson instead of re-deriving it.
   - If nothing covers it, this is a novel problem: continue exploring with varied hypotheses, and plan to capture the lesson after resolution.
   - List what is already verified, including paths, versions, commands, outputs, and files.
   - Prefer cheap verification of drift-prone facts over assumptions.
   - If a hook reported a semantic retry candidate, treat it as a request for
     review, not proof of a loop. Use the bounded classifier in
     `references/semantic-review.md` before interrupting novel exploration.

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
   - Pass the Write Permission Gate before making persistent edits.
   - Use user-level memory for cross-project machine or preference facts.
   - Use repo/project docs for project-specific conventions.
   - Update an existing skill only when the lesson changes a reusable procedure.
   - Create a new skill only when the procedure is recurring, portable, and worth triggering automatically.
   - See `references/memory-surfaces.md` for platform-neutral placement guidance.

7. Optionally ask an independent reviewer.
   - Use any available secondary agent, model, reviewer prompt, or fresh session; do not require a specific vendor or model.
   - Give it the smallest task-specific packet: artifact paths, the failed loop summary, and concrete validation questions. Do not claim that this removes built-in system context.
   - Ask for the smallest safety or clarity improvement.
   - For a semantic retry candidate, prefer enforced tool denial. A read-only
     filesystem alone still permits reads and commands, so report it separately.
     Otherwise use a fresh, non-inherited, prompt-only non-tool reviewer and
     report that weaker isolation honestly.
     Require the evidence-bound contract in `references/semantic-review.md`.
     Let the reviewer identify a shared failure family, but require a bounded
     main-agent lookup of source-labelled prior lessons before promoting it to
     `known_loop`. Interrupt only a high-confidence known loop with a verified,
     still-applicable lesson; let evidence-producing `novel_exploration`
     continue.
   - If no subagent exists, run the same checklist yourself.
   - See `references/reviewer-prompt.md`.

## Automatic Activation

This skill is normally recalled through its description, which is weakest exactly when an agent is mid-loop. If your harness supports hooks or tool-event callbacks, wire a retry-candidate detector that injects a reminder to invoke this skill. Use structured failure status when the harness provides it. When it does not, never guess failure from error keywords; use exact repetition or a bounded activity window only to request a bounded secondary-agent review. A backend may treat a harness-generated, anchored shell exit envelope as structured packet evidence, but must not parse arbitrary command text for failure words. By default the hook must not launch a model process itself; it only asks the main agent or harness to perform the review. The shipped hooks attach a privacy-safe manifest generated from actual hook payloads; the main agent must copy the relevant raw tool-event fields into the review packet rather than replace them with a free-form summary. The reviewer detects failure-family similarity; a `known_loop` additionally requires a source-labelled prior lesson verified by the main agent. Codex users may explicitly opt into the user-context-isolated `codex_cli` backend described in `references/semantic-review.md`; it is never enabled by the public default. Runnable detector scripts live in `hooks/` (Claude Code and Codex variants) with an automated test suite in `tests/`; see `references/hook-activation.md` for registration, trust requirements, and the general pattern for other harnesses. Treat any hook config you write as an artifact under this skill's own rules: run the test suite, then trigger one real candidate to prove it fires, before trusting it.

## Examples

Use examples as anchors for trigger and execution behavior:

- `examples/pdf-rendering-loop.md`
- `examples/github-actions-loop.md`
- `examples/docx-conversion-loop.md`
- `examples/zotero-linked-attachment-loop.md`
- `examples/dependency-install-loop.md`
- `examples/filled-lesson-libreoffice.md` (a completed lesson, not a pattern)
- `examples/bad-lessons.md` (anti-examples: captures that poison memory)

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

## Validation Evidence
- The exact command and observed output that proved the preferred procedure works.

## Drift Risk
- What may invalidate this lesson: version, path, API shape, account state, OS, permissions.

## Last Verified
- YYYY-MM-DD

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

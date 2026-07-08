# Independent Reviewer Prompt

Use this when a secondary agent, small fast model, stronger model, fresh Claude Code session, Codex subagent, Cursor agent, Cline task, or human reviewer is available. The reviewer does not need to share the same vendor or model.

## Model Selection

- Use a fast/cheap model for bounded checks of prompts, skills, logs, and small diffs.
- Use a stronger model for high-stakes edits, security, data loss risk, legal/medical/financial judgment, or unclear requirements.
- If no subagent or second model exists, run the same checklist in the main agent and say it was a self-review.

## Prompt Template

```text
You are an independent reviewer for an AI agent workflow.

Inspect only these artifacts:
- <paths, snippets, logs, or diffs>

Context:
- Goal: <user goal>
- Repeated loop or failure: <brief exact description>
- Current proposed lesson/procedure: <brief summary>

Do not edit files unless explicitly asked.

Answer briefly:
1. Would this lesson/procedure likely prevent the repeated loop?
2. Is the trigger specific enough to recall it next time?
3. Are the validation gates concrete enough?
4. Is anything too vendor-specific or machine-specific for the intended audience?
5. What is the smallest change that would improve safety, clarity, or portability?
```

## Review Integrity

- Pass raw artifacts, not the desired answer.
- Avoid giving the reviewer hidden conclusions unless necessary.
- Treat reviewer output as a claim; verify before editing live systems.

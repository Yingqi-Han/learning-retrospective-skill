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

## Semantic Loop Classifier

When a hook reports a structured failure window or an activity-only candidate
with unknown exit status, use the evidence-bound classifier in
`semantic-review.md`. Give it `REVIEW_PACKET_V1` plus the unchanged
`HOOK_EVIDENCE_MANIFEST`. Require one JSON object with:

- `schema_version`: `1`;
- the exact hook `request_id`;
- `classification`: `known_loop`, `novel_exploration`, `routine_failure`, or
  `uncertain`;
- `confidence`: `0.0` to `1.0`;
- `same_failure_family`, `prior_lesson_verified`, `evidence_adequate`, and
  `should_interrupt`: booleans;
- `reviewer_agent_id`: the exact non-empty id returned by the spawn call;
- `reviewer_isolation`: `enforced_no_tools`, `enforced_read_only`, or
  `prompt_only`;
- a short evidence-based `reason`;
- `recommended_action`: `recall_lesson`, `change_hypothesis`, `continue`, or
  `ask_user`.

If the first response is invalid, ask the same reviewer to correct it once.
Never spawn a second reviewer just to repair formatting. Apply the fail-closed
result if the correction is still invalid.

Do not report a reviewer result unless the trace contains a successful spawn
with a non-empty id and a wait on exactly that id. Calling wait with an empty
target list is not a review.

The reviewer may recommend interruption, but the main agent must verify that
the cited lesson or local fact is still applicable. Reviewer output alone is
never sufficient evidence for a persistent memory write.

Before spawning a manual reviewer, the main agent performs one bounded
read-only lookup and supplies only source-labelled `prior_lesson_candidates`.
An isolated direct reviewer receives an empty candidate list by design. With
an empty list it must set `prior_lesson_verified=false`, must not return
`known_loop`, and must not request interruption; it can still report
`same_failure_family=true` so the main agent knows a lesson lookup is warranted.

Do not treat user-requested repetition, benchmark probes, or evidence-producing
variations as loops merely because commands repeat. With activity-only evidence
and no structured exit status, `known_loop` additionally requires concrete
failed outcomes in the supplied transcript and an applicable prior lesson or
verified local fact.

## Review Integrity

- Pass raw artifacts, not the desired answer.
- Avoid giving the reviewer hidden conclusions unless necessary.
- Treat reviewer output as a claim; verify before editing live systems.

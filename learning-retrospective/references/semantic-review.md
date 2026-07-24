# Semantic Retry Review

Use a secondary agent only after a lightweight detector reports a candidate
episode. The signal may come from structured failures or, on harnesses that do
not expose exit status, from exact repetition or a bounded activity window.
The reviewer decides whether the attempts belong to the same failure family
and whether the evidence is converging. It may classify an episode as a
`known_loop` only when the packet includes a source-labelled, still-applicable
prior lesson. The main agent owns that bounded lesson lookup and the final
decision.

## Safety Boundary

- The public default must not launch a model process directly. A local user may
  explicitly opt into a documented backend with a bounded privacy and timeout
  contract.
- Prefer enforced tool denial. A read-only filesystem still permits reads and
  commands, so report it separately and do not treat it as tool denial.
  Otherwise use a prompt-only non-tool contract and report the weaker isolation
  honestly as `prompt_only`.
- The reviewer must not call tools, edit files, write memory, or retry the
  failed action under either isolation mode.
- When a multi-agent surface exists, the main agent must actually spawn one
  fresh reviewer; it must not self-classify and present that as subagent output.
- Record the non-empty agent id returned by spawn, include it in the packet,
  and wait on exactly that id. An empty wait target, missing spawn trace, or
  mismatched id means no reviewer ran.
- On Codex, check specifically for `SpawnAgent`/collaboration or a `multi_agent`
  tool before reporting that no reviewer is available.
- Use non-inherited context such as `fork_context:false` when supported.
- Send the smallest task-specific packet: the current goal, unchanged hook
  manifest, and last 6-12 relevant tool events. Do not claim that this removes
  the model's built-in system context.
- Redact credentials, private output, and unrelated transcript content.
- A candidate signal is not proof. The main agent owns the final decision.

## Model Selection

Use any available fast, low-cost secondary agent. A local installation may set
`preferred_model` in `hooks/learning-retrospective-reviewer.json`; this is a
preference, not a dependency. If that model is unavailable, inherit the parent
model or run the same classification checklist in the main agent.

Do not hard-code a vendor or model in the public skill. Keep the model override
in local configuration so Codex, Claude Code, Cursor, Cline, OpenCode, and
future harnesses can use their own reviewer surface.

## Optional Codex CLI Backend

The public default is:

```json
{
  "review_backend": "main_agent"
}
```

This mode injects the evidence protocol and relies on an available multi-agent
surface. It cannot mechanically force the main agent to spawn.

Codex users may explicitly opt into a real isolated child:

```json
{
  "preferred_model": "your-fast-reviewer-model",
  "reasoning_effort": "medium",
  "confidence_threshold": 0.8,
  "review_backend": "codex_cli",
  "codex_cli_path": "",
  "review_timeout_seconds": 45,
  "activity_review_calls": 12,
  "activity_review_min_span_seconds": 120,
  "activity_review_cooldown_calls": 24,
  "activity_review_cooldown_seconds": 900
}
```

`retry-reviewer-codex-cli.py` then:

1. Locates the persisted parent rollout by session id and reads at most the
   latest 4 MiB.
2. Copies at most 12 recent shell events, redacts common credential shapes, and
   compares their signatures with the hook manifest.
3. Creates a temporary `CODEX_HOME`, copies file-based authentication only for
   the duration of the call, and excludes user skills, hooks, rules, and memory.
   Codex built-in system instructions and system skills still exist.
4. Starts one Codex CLI child with `--sandbox read-only`,
   `--ignore-user-config`, `--ignore-rules`, strict config/schema validation,
   disabled shell/web/browser/MCP-style tool features, and an empty temporary
   cwd. A CLI version that does not recognize the required controls fails
   closed.
5. Rejects any unexpected child tool trace, validates the JSON result, captures
   the actual runtime `thread_id`, and injects the result directly into the
   parent.

Because this isolated child deliberately cannot read persistent memory, the
direct packet contains `prior_lesson_candidates: []`. Its useful role is
semantic triage: it can establish `same_failure_family`, distinguish a probe
from an unproductive pattern, and tell the main agent when to perform one
bounded lesson lookup. It cannot independently return a valid `known_loop` or
interrupt the task. The main agent may promote the episode only after finding
and citing an applicable stored lesson or verified local fact.

The detector sets `LEARNING_RETROSPECTIVE_DISABLE=1` in the child environment
to prevent recursive review hooks. Raw event content is passed through pipes
and is not written by the runner. The temporary child lives under
`CODEX_HOME/tmp/learning-retrospective-reviewer/`, keeping the short-lived
authentication copy inside the existing Codex trust boundary; normal exit and
timeout remove the per-call directory. A machine crash or forced process kill
can still leave a stale per-call directory, which may be deleted after Codex is
closed. The reviewer timeout is capped at 45 seconds and its process group is
terminated on timeout, leaving a 15-second cushion inside the required
60-second hook timeout. The redacted packet is still sent to the configured
Codex model, so this backend requires explicit user approval. If the backend
fails, the hook reports a privacy-safe reason and falls back to the manual
protocol without claiming a completed review.

The runner derives `succeeded` or `failed` only from an anchored Codex shell
envelope such as `Exit code: 1`; it never searches arbitrary command output for
error words. In `activity_window` mode, a positive `known_loop` requires at
least two such failed tool events when the hook manifest itself has only
`unknown` outcomes.

## Input Packet

The hook injects `HOOK_EVIDENCE_MANIFEST`, generated from events it actually
observed. The manifest contains:

- `schema_version`;
- a request-specific `request_id`;
- `evidence_source=hook_observed_payloads`;
- structured-failure or activity-window mode; and
- a `candidate_reason` distinguishing structured failures, exact unknown
  repetition, and sustained unknown activity; and
- ordered event indexes, command signatures, and outcomes
  (`failed`/`succeeded`/`unknown`).

The manifest intentionally omits raw commands and output, and the rolling state
does not store them. It binds the review request to the detector's observations
but is not enough for semantic classification by itself.

Build `REVIEW_PACKET_V1` by copying, not freely summarizing:

- the user's immediate goal;
- the non-empty `SPAWNED_REVIEWER_ID` returned by the actual spawn call;
- the unchanged hook manifest;
- the last 6-12 relevant tool-event fields visible in the parent context:
  ordinal, command or action, relevant cwd, structured exit status, concise
  error or outcome, and stated hypothesis;
- the current hypothesis, if one was stated;
- zero or more `prior_lesson_candidates`, each with a stable `source_id`, a
  short trigger/lesson summary, and current applicability evidence; never send
  the full memory store;
- whether the detector saw structured failures, exact repetition, or an
  activity-only window with unknown result status.

If the raw events are unavailable, do not invent them. If their order or
outcomes conflict with the hook manifest, mark the evidence inadequate and do
not interrupt.

## Required Output

The reviewer must return one JSON object and no prose:

```json
{
  "schema_version": 1,
  "request_id": "0123456789abcdef",
  "classification": "known_loop",
  "confidence": 0.91,
  "same_failure_family": true,
  "prior_lesson_verified": true,
  "evidence_adequate": true,
  "should_interrupt": true,
  "reviewer_agent_id": "actual-spawned-agent-id",
  "reviewer_isolation": "prompt_only",
  "reason": "Short evidence-based reason",
  "recommended_action": "recall_lesson"
}
```

Allowed classifications:

- `known_loop`: a verified lesson or local fact already covers the episode.
- `novel_exploration`: attempts are producing new evidence and converging.
- `routine_failure`: an ordinary isolated failure with an obvious next check.
- `uncertain`: the packet is insufficient or conflicting.

Allowed actions:

- `recall_lesson`
- `change_hypothesis`
- `continue`
- `ask_user`

Allowed isolation values:

- `enforced_no_tools`: the harness technically removed tool access;
- `enforced_read_only`: writes were denied, but reads or commands may remain;
- `prompt_only`: the reviewer was instructed not to use tools, but the runtime
  did not enforce that restriction.

The opt-in Codex CLI backend adds
`reviewer_context_isolation=temporary_codex_home` after schema validation.
This reports exclusion of user customization, not literal packet-only model
context.

Reject outputs with a wrong `schema_version`, mismatched `request_id`, a
missing or mismatched `reviewer_agent_id`, wrong field types, confidence
outside `0.0` to `1.0`, or values outside these enums.
Do not silently coerce strings into booleans or invent actions.
`same_failure_family`, `prior_lesson_verified`, `evidence_adequate`, and
`should_interrupt` must be literal JSON booleans, not descriptions such as
`"same command"` or `"none"`.

If the first response is invalid, send one correction request containing only
the validation errors to the same reviewer and wait once more. Do not spawn a
second reviewer. If the correction is still invalid, discard it and use the
fail-closed replacement.

Discard an invalid object instead of quoting or summarizing it. Use this exact
fail-closed replacement:

```json
{
  "schema_version": 1,
  "request_id": "<copy the hook request_id>",
  "classification": "uncertain",
  "confidence": 0.0,
  "same_failure_family": false,
  "prior_lesson_verified": false,
  "evidence_adequate": false,
  "should_interrupt": false,
  "reviewer_agent_id": null,
  "reviewer_isolation": "prompt_only",
  "reason": "invalid reviewer schema",
  "recommended_action": "ask_user"
}
```

This fallback is a main-agent safety result, not proof that a reviewer ran.
When spawn is unavailable or fails to return a non-empty id, report
`reviewer_unavailable` and do not claim a reviewer classification.

`known_loop` is also invalid unless at least one source-labelled
`prior_lesson_candidates` entry exists and `same_failure_family`,
`prior_lesson_verified`, `evidence_adequate`, and `should_interrupt` are all
`true`. A reviewer cannot set `prior_lesson_verified=true` when the candidate
list is empty. Any result with `evidence_adequate=false` and
`should_interrupt=true`, or with `should_interrupt=true` outside `known_loop`,
is invalid. These consistency rules prevent a harmless probe, incomplete
packet, or model guess from stopping the main task.

A user-requested repetition, benchmark, hook probe, or evidence-producing
variation is not a retry loop by itself. When the detector has only an
activity-window signal and no structured exit status, do not classify the
episode as `known_loop` merely because a command repeated. Require concrete
failed outcomes in the supplied transcript and an applicable prior lesson or
verified local fact. Otherwise set `should_interrupt` to `false` and choose
`uncertain`, `routine_failure`, or `novel_exploration`.

## Decision Gate

Interrupt the main agent only when:

- `classification` is `known_loop`;
- `confidence` meets the configured threshold (default `0.80`);
- `prior_lesson_verified` is true and cites a supplied candidate;
- `evidence_adequate` is true;
- `should_interrupt` is true; and
- the cited prior lesson or verified fact is still applicable.

For `novel_exploration`, continue the task. For `routine_failure`, use the
obvious next check. For `uncertain`, avoid automatic persistence and ask the
main agent to rebuild the evidence.

After the task succeeds, use the normal Write Permission Gate before storing
any lesson. Reviewer output is a claim, not validation evidence.

## Platform Limit

The hook can prove that it emitted a reminder and can attach metadata derived
from actual tool-event payloads. In `main_agent` mode it cannot force the main
agent to delegate, grant a subagent permissions the harness does not support,
or let the reviewer independently query the complete parent transcript. On
current Codex multi-agent surfaces, `fork_context:false` plus a copied evidence
packet avoids inherited conversation history, but built-in context may remain
and the no-tool rule is prompt-only unless the harness enforces it.

The opt-in `codex_cli` backend closes that orchestration gap for Codex by
starting and validating a real child outside the main agent's discretion. It
also disables the current Codex tool-bearing features before the call and uses
a temporary user-context-isolated home. Because that child cannot read
persistent memory, it performs semantic triage and leaves the known-lesson
promotion to the main agent. It does not make the public skill
universally autonomous: other harnesses still need their own enforceable
backend adapters.

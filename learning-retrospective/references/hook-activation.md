# Automatic Activation via Hooks

The core weakness of any retrospective skill is the trigger paradox: it relies on the agent noticing that it is looping, and a mid-loop agent is exactly the agent least likely to notice. Description-based recall is passive. A hook turns activation into an external, enforced signal.

The pattern is harness-agnostic, but event placement is harness-specific:

1. Prefer a failure-specific event when the harness provides one.
2. If post-tool hooks omit failures, observe attempts in `PreToolUse`; never
   pretend a success-only event is a complete execution log.
3. Keep a small rolling state of command hashes and timestamps; expire stale
   state and never store raw commands or output.
4. A repeated attempt or bounded activity window may request semantic review,
   but may not declare a loop. Recover outcomes from real parent tool events.
5. A bounded secondary agent decides whether the candidate is a known loop or legitimate novel exploration. Report `enforced_no_tools` only when the harness technically removes tool access; a read-only filesystem alone still permits reads and commands.

Calibrate the reminder to the skill's two modes: it must not suppress legitimate exploration of a novel problem. Verbatim-identical retries are the one behavior that is almost never productive, which is why they are the trigger; but the injected message should say "check memory for a prior lesson; if none, keep exploring with a changed hypothesis and capture the lesson after solving," not "stop working on this."

## Semantic Review Escalation

Claude Code uses structured failure events. Codex records attempts before
execution because its current `PostToolUse` path is success-only. The Codex
detector requests review when a signature appears twice in the latest 12
attempts, including non-consecutive repetition. A broad attempt review requires
12 calls containing at least three command hashes over at least 120 seconds. It
then waits at least 24 additional calls and 15 minutes before another broad
review; exact repetitions retain the shorter eight-call candidate cooldown. With
the opt-in `codex_cli` backend, an attempt-window candidate spends at most one
automated model call per `activity_review_cooldown_seconds` (default 900);
later candidates inside that window fall back to the manual protocol with the
reason `automated_review_cooldown`. Commands and outputs are not stored in
rolling state; only event indexes, command hashes, and timestamps are retained.
When review is requested, the hook injects a `HOOK_EVIDENCE_MANIFEST` generated
from actual `PreToolUse` observations. The reviewer obtains prior outcomes from
the bounded parent rollout; the current event remains `pending`.

This signal is deliberately a candidate, not a verdict. The main agent or
harness should:

1. Spawn exactly one fresh reviewer with non-inherited context. Prefer enforced
   tool denial. If only writes are denied, report `enforced_read_only`; if the
   restriction is instructional only, report `prompt_only`.
2. Record the non-empty agent id returned by spawn, include it as
   `reviewer_agent_id`, and wait on exactly that id. Empty wait targets or a
   missing spawn trace mean no review occurred.
3. Copy, rather than freely summarize, the current goal and the last 6-12
   relevant raw tool-event fields into `REVIEW_PACKET_V1`.
4. Include the hook manifest unchanged and redact secrets and unrelated private
   output.
5. Require the JSON contract in `semantic-review.md`. If it is invalid, request
   one correction from the same reviewer before applying the fail-closed result.
6. Interrupt only a `known_loop` at or above the configured confidence
   threshold (default `0.80`).
7. Continue `novel_exploration` when each attempt is producing new evidence.

The public `main_agent` backend does not start a model process itself. That
avoids recursive sessions, hidden credential use, and unpredictable latency.
The explicit `codex_cli` opt-in below is the exception and adds recursion,
privacy, tool-denial, and timeout controls. If no secondary-agent surface
exists, the main agent runs the same classification checklist.

Model selection is local and optional. `install.py --with-hooks` creates
`learning-retrospective-reviewer.json` with empty defaults on first install
and never overwrites it later. For a manual install, copy
`../hooks/reviewer-config.example.json` beside the hook with that name, then
set a locally available model:

```json
{
  "preferred_model": "your-fast-reviewer-model",
  "reasoning_effort": "medium",
  "confidence_threshold": 0.8,
  "review_backend": "main_agent",
  "codex_cli_path": "",
  "review_timeout_seconds": 45
}
```

Do not commit a machine-specific model choice to a shared repository. An empty
`preferred_model` means "use any available fast, low-cost secondary agent."
`main_agent` is the safe public default and never starts a model process.

Codex users may explicitly set `review_backend` to `codex_cli`. The installer
copies `retry-reviewer-codex-cli.py` beside the detector. This backend reads a
bounded parent-rollout tail, redacts common credential shapes, runs one real
Codex child in a temporary user-context-isolated home, disables tool-bearing
features before the model call, enforces a read-only sandbox, rejects any
unexpected tool trace, and captures the real child thread id. It sends the
redacted packet to the configured model and may add several seconds of latency,
so review `SECURITY_NOTES.md`, set the hook timeout to 60 seconds, and test one
harmless candidate before relying on it.

## Claude Code Example (tested 2026-07-09, re-verified 2026-07-26)

This design was deployed and verified end-to-end on a real machine: on the second identical Bash failure, the reminder was injected into the model's context as a system reminder.

This detector receives structured failure status from `PostToolUseFailure`, so it has no activity window and no direct model backend. Only `preferred_model`, `reasoning_effort`, and `confidence_threshold` are read from the local reviewer config; `review_backend`, `codex_cli_path`, and the `activity_review_*` keys belong to the Codex detector and are ignored here. Setting one of them records a `reviewer_config_keys_unsupported` diagnostic rather than silently doing nothing, and `install.py --agent claude --with-hooks` writes only the supported keys.

Two verified facts shaped the design:

- `PostToolUse` fires only on **successful** tool calls; failures fire `PostToolUseFailure`. A single-event heuristic that parses `tool_response` for error strings never sees real failures. Register the same script on **both** events: failure increments the counter, success resets it - no fragile output parsing needed.
- On Windows, hook commands may run through Git Bash, whose PATH can lack `python` even when PowerShell finds it. Use the exec form (`command` + `args`, no shell) with the interpreter's full path. Prefer `python -S` for this stdlib-only detector to avoid site-package startup overhead.

The runnable script is `../hooks/retry-loop-detector-claude.py` (stdlib-only, covered by the complete unittest suite). Copy it to `~/.claude/hooks/` and review it before registering — see `../SECURITY_NOTES.md`.

Register it in `~/.claude/settings.json` (exec form; substitute your interpreter path):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "C:\\path\\to\\python.exe",
            "args": ["-S", "C:\\Users\\<user>\\.claude\\hooks\\retry-loop-detector-claude.py"],
            "timeout": 5
          }
        ]
      }
    ],
    "PostToolUseFailure": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "C:\\path\\to\\python.exe",
            "args": ["-S", "C:\\Users\\<user>\\.claude\\hooks\\retry-loop-detector-claude.py"],
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

Verification procedure (do this once before trusting it):

1. Run the automated suite: `python -S -m unittest discover -s learning-retrospective/tests -v` (covers fail/fail/reset sequences, backoff, missing session ids, BOM input, non-Bash tools, and garbage input).
2. Run one harmless failing command twice in a live Claude Code session and
   confirm the reminder appears. For Codex, repeat one harmless failing command
   twice and confirm `PreToolUse` requests review before the second execution.

Notes:

- Exact retries are handled deterministically; multi-command failure windows
  request semantic review instead of being treated as confirmed loops.
- Keep the injected reminder short. Its only job is to break the loop and hand control to the skill.
- The state file is scoped per session id, so parallel sessions do not interfere.
- State files older than seven days are removed by a best-effort daily cleanup; missing session ids fail safe without counting.

## Codex Example (config validated 2026-07-26)

Codex supports lifecycle hooks in `~/.codex/hooks.json` (or inline `[hooks]`
tables in `config.toml`). Three differences from Claude Code, verified against
the [official hooks documentation](https://developers.openai.com/codex/hooks)
and the Codex source:

- There is no failure-specific event
  ([openai/codex#24907](https://github.com/openai/codex/issues/24907) requests
  one), and current Codex dispatch invokes `PostToolUse` only for successful
  tools. The detector therefore registers on `PreToolUse`, which observes both
  eventual successes and failures. It records attempts, not outcomes; the
  reviewer reads prior outcomes from the parent rollout.
- The handler `command` is a single string (no exec-form `args` array). On Windows, a quoted executable path at the start of a PowerShell command needs the `&` call operator; without it the hook exits with code 1 before Python starts. Use `commandWindows` for that override and full interpreter paths for the same PATH reasons as on Claude Code.
- Non-managed hooks do not run until the user reviews and trusts the current definition hash. Installing the files is not enough. CLI/TUI releases may expose `/hooks`; Codex Desktop uses a Hooks settings panel, and some releases show only an enable/disable switch. Enablement and trust are separate, so the switch alone does not prove that the hook is runnable.

`~/.codex/hooks.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "^Bash$",
        "hooks": [
          {
            "type": "command",
            "command": "\"C:/path/to/python.exe\" -S \"C:/Users/<user>/.codex/hooks/retry-loop-detector-codex.py\"",
            "commandWindows": "& \"C:/path/to/python.exe\" -S \"C:/Users/<user>/.codex/hooks/retry-loop-detector-codex.py\"",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

The runnable detector is `../hooks/retry-loop-detector-codex.py`; the optional
isolated backend is `../hooks/retry-reviewer-codex-cli.py`. The detector
requires a session id, expires state older than seven days, and never stores raw
commands or output. A repeated attempt requests review before execution; broad
activity uses the slower 12-call/120-second gate and 24-call/15-minute cooldown
without claiming a failure. The review packet aligns manifest attempts to
rollout attempts as an ordered subsequence, reports skipped rollout events, and
requires the current pending event to match. Verify with three gates:
run the complete suite (`python -S -m unittest discover -s
learning-retrospective/tests -v`), repeat one harmless failing command twice,
then run 12 rapid harmless distinct commands and confirm that no broad review appears.
Use a test-only zero-span configuration to verify the sustained-activity
boundary without waiting two minutes.

For troubleshooting, Codex app-server's read-only `hooks/list` method reports
`enabled`, `currentHash`, and `trustStatus`. A hook can therefore be
`enabled: true` but still have `trustStatus: "modified"` and remain inert.
Treat `trustStatus: "trusted"` plus a normal, non-bypassed live invocation as
the verification gate. Codex currently has no dedicated public installer API
for granting trust; never copy a stale hash or auto-approve an unreviewed hook.

## Verifying the Current Hook Schema

After a harness upgrade, run the lifecycle shape probe:

1. Temporarily register `../hooks/payload-probe.py` on `PreToolUse` with the
   same interpreter and matcher as the detector.
2. Trigger one successful and one failing Bash command.
3. Read `<temp dir>/hook-payload-shape.jsonl`: each line records key names and
   value types only - never values - so nothing sensitive lands on disk.
4. Confirm both attempts produced records with `hook_event_name=PreToolUse`,
   `tool_use_id`, and `tool_input.command`. Unregister the probe and delete its
   output afterward.

This live gate catches the exact lifecycle regression that unit tests cannot:
a harness may parse a synthetic failure payload correctly while never emitting
that event for a real failed tool.

## Other Harnesses

- **Cursor / Cline / OpenCode**: if no tool-event hook exists, the fallback is instruction-level - add one line to the harness's persistent instructions: "If the same command fails twice, stop and run the learning-retrospective workflow before any further attempt."
- **Any harness with shell wrappers**: wrap the shell entry point to count repeated failing commands and emit the reminder on stderr, which most agents read.

A hook does not replace the skill; it only guarantees the skill gets a chance to run.

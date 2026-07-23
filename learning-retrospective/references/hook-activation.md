# Automatic Activation via Hooks

The core weakness of any retrospective skill is the trigger paradox: it relies on the agent noticing that it is looping, and a mid-loop agent is exactly the agent least likely to notice. Description-based recall is passive. A hook turns activation into an external, enforced signal.

The pattern is harness-agnostic and has two tiers:

1. Observe tool executions and use structured success/failure status when the harness provides it.
2. Keep a small rolling state of command hashes and result-state booleans; expire stale state.
3. With structured status, when the same action fails twice **verbatim**, inject a deterministic reminder. If the retry continues, remind again only at exponentially spaced counts (4, 8, 16...).
4. Without structured status, do not parse output strings to guess failure. Exact repetition or a bounded activity window may request semantic review, but may not declare a loop.
5. A bounded secondary agent decides whether the candidate is a known loop or legitimate novel exploration. Report `enforced_no_tools` only when the harness technically removes tool access; a read-only filesystem alone still permits reads and commands.

Calibrate the reminder to the skill's two modes: it must not suppress legitimate exploration of a novel problem. Verbatim-identical retries are the one behavior that is almost never productive, which is why they are the trigger; but the injected message should say "check memory for a prior lesson; if none, keep exploring with a changed hypothesis and capture the lesson after solving," not "stop working on this."

## Semantic Review Escalation

With structured status, the shipped detectors request semantic review when the
current failed call makes at least three failures among the last six Bash calls,
across at least two command hashes. Without structured status, the Codex
detector requests review after an exact repeat or a six-call window containing
at least two command hashes. It then waits at least eight Bash calls before
another semantic review. Commands and outputs are not stored in rolling state;
only event indexes, command hashes, and booleans/null result markers are
retained. When review is requested, the hook injects a
`HOOK_EVIDENCE_MANIFEST` generated from those actual payload observations.

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

## Claude Code Example (tested 2026-07-09)

This design was deployed and verified end-to-end on a real machine: on the second identical Bash failure, the reminder was injected into the model's context as a system reminder.

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
2. Run one harmless failing command twice in a live Claude Code session and confirm the reminder appears. For Codex, repeat one harmless command twice and confirm a semantic-review candidate; current Codex builds may not expose structured exit status to hooks.

Notes:

- Exact retries are handled deterministically; multi-command failure windows
  request semantic review instead of being treated as confirmed loops.
- Keep the injected reminder short. Its only job is to break the loop and hand control to the skill.
- The state file is scoped per session id, so parallel sessions do not interfere.
- State files older than seven days are removed by a best-effort daily cleanup; missing session ids fail safe without counting.

## Codex Example (config validated 2026-07-09)

Codex supports lifecycle hooks in `~/.codex/hooks.json` (or inline `[hooks]` tables in `config.toml`). Three differences from Claude Code, verified against the official docs and the codex repo:

- There is no failure-specific event ([openai/codex#24907](https://github.com/openai/codex/issues/24907) requests one). Some older/adjacent harness payloads include a structured exit code, but Codex `0.145.0` passes `tool_response` as output text only. The detector preserves deterministic failure counting when structured status exists. Otherwise it never parses output text to guess success; exact repetition or a bounded six-call activity window only requests semantic review.
- The handler `command` is a single string (no exec-form `args` array). On Windows, a quoted executable path at the start of a PowerShell command needs the `&` call operator; without it the hook exits with code 1 before Python starts. Use `commandWindows` for that override and full interpreter paths for the same PATH reasons as on Claude Code.
- Non-managed hooks do not run until the user reviews and trusts the current definition hash. Installing the files is not enough. CLI/TUI releases may expose `/hooks`; Codex Desktop uses a Hooks settings panel, and some releases show only an enable/disable switch. Enablement and trust are separate, so the switch alone does not prove that the hook is runnable.

`~/.codex/hooks.json`:

```json
{
  "hooks": {
    "PostToolUse": [
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
commands or output. With structured status it backs exact failure reminders off
at 2, 4, 8... and requests semantic review for a bounded multi-command failure
window. Without structured status, an exact repeat or six-call activity window
requests semantic review without claiming a failure. Verify with three gates:
run the complete suite (`python -S -m unittest discover -s
learning-retrospective/tests -v`), repeat one harmless command twice, then run
six harmless distinct commands and confirm the semantic-review request or
validated automated result appears after trusting the hook.

For troubleshooting, Codex app-server's read-only `hooks/list` method reports
`enabled`, `currentHash`, and `trustStatus`. A hook can therefore be
`enabled: true` but still have `trustStatus: "modified"` and remain inert.
Treat `trustStatus: "trusted"` plus a normal, non-bypassed live invocation as
the verification gate. Codex currently has no dedicated public installer API
for granting trust; never copy a stale hash or auto-approve an unreviewed hook.

## Verifying the Current Hook Schema

Payload shapes are empirical, not guaranteed - especially on Codex, whose generated schema leaves `tool_response` unconstrained. After a harness upgrade, or before relying on a field the docs do not promise, run the shape probe:

1. Temporarily register `../hooks/payload-probe.py` the same way as the detector (same interpreter, same event).
2. Trigger one successful and one failing command.
3. Read `<temp dir>/hook-payload-shape.jsonl`: each line records key names and value types only - never values - so nothing sensitive lands on disk.
4. Confirm `tool_input.command` exists and note whether `tool_response.exit_code` is available. The detector supports both structured-status and activity-only modes; unregister the probe and delete its file afterward.

If `exit_code` is absent, the Codex detector switches to activity-only semantic review and does not infer failure from output text.

## Other Harnesses

- **Cursor / Cline / OpenCode**: if no tool-event hook exists, the fallback is instruction-level - add one line to the harness's persistent instructions: "If the same command fails twice, stop and run the learning-retrospective workflow before any further attempt."
- **Any harness with shell wrappers**: wrap the shell entry point to count repeated failing commands and emit the reminder on stderr, which most agents read.

A hook does not replace the skill; it only guarantees the skill gets a chance to run.

# Automatic Activation via Hooks

The core weakness of any retrospective skill is the trigger paradox: it relies on the agent noticing that it is looping, and a mid-loop agent is exactly the agent least likely to notice. Description-based recall is passive. A hook turns activation into an external, enforced signal.

The pattern is harness-agnostic:

1. Observe tool executions (command, success/failure).
2. Keep a small rolling state of recent failures.
3. When the same action fails twice **verbatim**, inject a reminder into the agent's context.

Calibrate the reminder to the skill's two modes: it must not suppress legitimate exploration of a novel problem. Verbatim-identical retries are the one behavior that is almost never productive, which is why they are the trigger; but the injected message should say "check memory for a prior lesson; if none, keep exploring with a changed hypothesis and capture the lesson after solving," not "stop working on this."

## Claude Code Example (tested 2026-07-09)

This design was deployed and verified end-to-end on a real machine: on the second identical Bash failure, the reminder was injected into the model's context as a system reminder.

Two verified facts shaped the design:

- `PostToolUse` fires only on **successful** tool calls; failures fire `PostToolUseFailure`. A single-event heuristic that parses `tool_response` for error strings never sees real failures. Register the same script on **both** events: failure increments the counter, success resets it - no fragile output parsing needed.
- On Windows, hook commands may run through Git Bash, whose PATH can lack `python` even when PowerShell finds it. Use the exec form (`command` + `args`, no shell) with the interpreter's full path. Prefer `python -S` for this stdlib-only detector to avoid site-package startup overhead.

The runnable script is `../hooks/retry-loop-detector-claude.py` (stdlib-only, tested by `../tests/test_retry_loop_detector.py`). Copy it to `~/.claude/hooks/` and review it before registering — see `../SECURITY_NOTES.md`.

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

1. Run the automated suite: `python learning-retrospective/tests/test_retry_loop_detector.py` (covers fail/fail/reset sequences, BOM input, non-Bash tools, garbage input).
2. Run one harmless failing command twice in a live session and confirm the reminder appears.

Notes:

- Detection is exact-command-match only; paraphrased retries of the same broken approach are not caught - that remains the skill's job once activated.
- Keep the injected reminder short. Its only job is to break the loop and hand control to the skill.
- The state file is scoped per session id, so parallel sessions do not interfere.

## Codex Example (config validated 2026-07-09)

Codex supports lifecycle hooks in `~/.codex/hooks.json` (or inline `[hooks]` tables in `config.toml`). Three differences from Claude Code, verified against the official docs and the codex repo:

- There is no failure-specific event ([openai/codex#24907](https://github.com/openai/codex/issues/24907) requests one). `PostToolUse` fires for both success and non-zero exits, so branch on the exit code inside one script instead of registering two events. Note the epistemic status: in currently observed Codex builds `tool_response` for Bash includes `output` and `exit_code`, but the generated hook schema leaves `tool_response` unconstrained - this field shape is empirical, not guaranteed. Re-run the pipe test and one live forced failure after Codex upgrades; the script below already fails safe (missing exit code is treated as success, so a renamed field silently disables detection rather than spamming false reminders).
- The handler `command` is a single string (no exec-form `args` array); use `commandWindows` for a Windows-specific override, and full interpreter paths for the same PATH reasons as on Claude Code.
- Non-managed hooks do not run until the user reviews and trusts them via `/hooks` inside Codex. Installing the files is not enough - tell the user about this step, and re-approve after any edit to the hook definition.

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
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

The runnable script is `../hooks/retry-loop-detector-codex.py`. It treats a missing `exit_code` as success rather than failure - a false reminder on every tool call is worse than a missed one, so a renamed field silently disables detection instead of spamming. Verify with the same two-step gate: run `../tests/test_retry_loop_detector.py` (its Codex cases cover fail/fail/reset and the missing-exit-code fail-safe), then force one real failure in a live session after trusting the hook.

## Other Harnesses

- **Cursor / Cline / OpenCode**: if no tool-event hook exists, the fallback is instruction-level - add one line to the harness's persistent instructions: "If the same command fails twice, stop and run the learning-retrospective workflow before any further attempt."
- **Any harness with shell wrappers**: wrap the shell entry point to count repeated failing commands and emit the reminder on stderr, which most agents read.

A hook does not replace the skill; it only guarantees the skill gets a chance to run.

# Automatic Activation via Hooks

The core weakness of any retrospective skill is the trigger paradox: it relies on the agent noticing that it is looping, and a mid-loop agent is exactly the agent least likely to notice. Description-based recall is passive. A hook turns activation into an external, enforced signal.

The pattern is harness-agnostic:

1. Observe tool executions (command, success/failure).
2. Keep a small rolling state of recent failures.
3. When the same action fails twice, inject a reminder into the agent's context to stop and invoke this skill.

## Claude Code Example (tested 2026-07-09)

This design was deployed and verified end-to-end on a real machine: on the second identical Bash failure, the reminder was injected into the model's context as a system reminder.

Two verified facts shaped the design:

- `PostToolUse` fires only on **successful** tool calls; failures fire `PostToolUseFailure`. A single-event heuristic that parses `tool_response` for error strings never sees real failures. Register the same script on **both** events: failure increments the counter, success resets it — no fragile output parsing needed.
- On Windows, hook commands may run through Git Bash, whose PATH can lack `python` even when PowerShell finds it. Use the exec form (`command` + `args`, no shell) with the interpreter's full path.

`~/.claude/hooks/retry-loop-detector.py`:

```python
import hashlib, json, os, sys, tempfile

THRESHOLD = 2

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

if data.get("tool_name") != "Bash":
    sys.exit(0)

event = data.get("hook_event_name", "")
command = ((data.get("tool_input") or {}).get("command") or "").strip()
if not command:
    sys.exit(0)

session = (data.get("session_id") or "global")[:16]
key = hashlib.sha1(command.encode("utf-8", "replace")).hexdigest()[:12]
state_path = os.path.join(tempfile.gettempdir(), f"claude-retry-loop-{session}.json")

try:
    with open(state_path, encoding="utf-8") as f:
        state = json.load(f)
except Exception:
    state = {}

if event == "PostToolUseFailure":
    state[key] = state.get(key, 0) + 1
else:
    state.pop(key, None)

try:
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f)
except Exception:
    pass

if state.get(key, 0) >= THRESHOLD:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": (
                f"Retry-loop detector: this exact command has now failed "
                f"{state[key]} times in this session. Stop retrying it "
                "verbatim. Invoke the learning-retrospective skill: state the "
                "verified facts, form one hypothesis with an explicit failure "
                "gate, and capture the lesson if it is reusable."
            ),
        }
    }))
```

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
            "args": ["C:\\Users\\<user>\\.claude\\hooks\\retry-loop-detector.py"],
            "timeout": 10
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
            "args": ["C:\\Users\\<user>\\.claude\\hooks\\retry-loop-detector.py"],
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

Verification procedure (do this once before trusting it):

1. Pipe-test the script with synthetic JSON for fail #1 (no output), fail #2 (reminder emitted), success (reset).
2. Run one harmless failing command twice in a live session and confirm the reminder appears.

Notes:

- Detection is exact-command-match only; paraphrased retries of the same broken approach are not caught — that remains the skill's job once activated.
- Keep the injected reminder short. Its only job is to break the loop and hand control to the skill.
- The state file is scoped per session id, so parallel sessions do not interfere.

## Other Harnesses

- **Codex / OpenCode / Cursor / Cline**: if no tool-event hook exists, the fallback is instruction-level — add one line to the harness's persistent instructions: "If the same command fails twice, stop and run the learning-retrospective workflow before any further attempt."
- **Any harness with shell wrappers**: wrap the shell entry point to count repeated failing commands and emit the reminder on stderr, which most agents read.

A hook does not replace the skill; it only guarantees the skill gets a chance to run.

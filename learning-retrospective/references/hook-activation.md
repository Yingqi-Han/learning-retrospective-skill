# Automatic Activation via Hooks

The core weakness of any retrospective skill is the trigger paradox: it relies on the agent noticing that it is looping, and a mid-loop agent is exactly the agent least likely to notice. Description-based recall is passive. A hook turns activation into an external, enforced signal.

The pattern is harness-agnostic:

1. Observe tool executions (command, success/failure).
2. Keep a small rolling state of recent failures.
3. When the same action fails twice, inject a reminder into the agent's context to stop and invoke this skill.

## Claude Code Example

Claude Code supports `PostToolUse` hooks that receive tool call details as JSON on stdin and can inject `additionalContext` back into the conversation.

`~/.claude/hooks/retry-loop-detector.py` (sketch — adapt field names to your Claude Code version):

```python
import json, sys, hashlib, os, tempfile

data = json.load(sys.stdin)
if data.get("tool_name") != "Bash":
    sys.exit(0)

command = data.get("tool_input", {}).get("command", "")
response = json.dumps(data.get("tool_response", ""))
failed = any(k in response for k in ("Exit code 1", "\"is_error\": true", "command not found", "No such file"))

state_path = os.path.join(tempfile.gettempdir(), "claude-retry-loop-state.json")
try:
    state = json.load(open(state_path))
except Exception:
    state = {}

key = hashlib.sha1(command.encode()).hexdigest()[:12]
state[key] = state.get(key, 0) + 1 if failed else 0
json.dump(state, open(state_path, "w"))

if failed and state[key] >= 2:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                "The same command has now failed "
                f"{state[key]} times. Stop retrying. Invoke the "
                "learning-retrospective skill: state the verified facts, "
                "pick one hypothesis with a failure gate, and capture the lesson."
            ),
        }
    }))
```

Register it in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "python ~/.claude/hooks/retry-loop-detector.py" }
        ]
      }
    ]
  }
}
```

Notes:

- The failure heuristic above is deliberately crude; tune it to the tool-response shape your version emits, and verify with one forced failure before trusting it.
- Keep the injected reminder short. Its only job is to break the loop and hand control to the skill.
- Scope the state file per session if parallel sessions are common.

## Other Harnesses

- **Codex / OpenCode / Cursor / Cline**: if no tool-event hook exists, the fallback is instruction-level — add one line to the harness's persistent instructions: "If the same command fails twice, stop and run the learning-retrospective workflow before any further attempt."
- **Any harness with shell wrappers**: wrap the shell entry point to count repeated failing commands and emit the reminder on stderr, which most agents read.

A hook does not replace the skill; it only guarantees the skill gets a chance to run.

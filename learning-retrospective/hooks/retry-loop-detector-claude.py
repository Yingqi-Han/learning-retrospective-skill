"""Retry-loop detector for Claude Code.

Register on BOTH PostToolUse (success -> reset counter) and PostToolUseFailure
(failure -> increment counter) with matcher "Bash"; see
references/hook-activation.md for the settings.json snippet and the
verification procedure. When the same command fails twice in one session,
injects a reminder to check stored lessons before the next attempt.

Stdlib-only; safe to run with `python -S`.
"""
import hashlib
import json
import os
import sys
import tempfile

THRESHOLD = 2

try:
    raw = sys.stdin.buffer.read()
    data = json.loads(raw.decode("utf-8-sig"))
except Exception:
    sys.exit(0)

if data.get("tool_name") != "Bash":
    sys.exit(0)

event = data.get("hook_event_name", "")
command = ((data.get("tool_input") or {}).get("command") or "").strip()
if not command:
    sys.exit(0)

# Hash externally supplied values before using them in paths or keys:
# session_id could contain path separators; the same command in two
# different working directories is not the same action.
session_raw = str(data.get("session_id") or "global")
session_key = hashlib.sha1(session_raw.encode("utf-8", "replace")).hexdigest()[:12]
cwd = str(data.get("cwd") or "")
key = hashlib.sha1((cwd + "\n" + command).encode("utf-8", "replace")).hexdigest()[:12]
state_path = os.path.join(tempfile.gettempdir(), f"claude-retry-loop-{session_key}.json")

try:
    with open(state_path, encoding="utf-8") as f:
        state = json.load(f)
except Exception:
    state = {}

if event == "PostToolUseFailure":
    state[key] = state.get(key, 0) + 1
else:
    state.pop(key, None)

if len(state) > 200:  # cap state file growth
    state = {key: state.get(key, 0)} if key in state else {}

try:
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f)
except Exception:
    pass

if state.get(key, 0) >= THRESHOLD:
    print(json.dumps({
        # systemMessage is shown to the USER in the UI; additionalContext is
        # injected into the MODEL's context. Both matter: an invisible
        # intervention cannot be trusted or debugged.
        "systemMessage": (
            f"Retry-loop detector: same command failed {state[key]}x - "
            "told the agent to check stored lessons before retrying."
        ),
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": (
                f"Retry-loop detector: this exact command has now failed "
                f"{state[key]} times in this session. Do not run it again "
                "unchanged. First check stored lessons/memory for this "
                "failure signature: if a prior lesson covers it, follow that "
                "lesson. If none exists, this is a novel problem - keep "
                "exploring, but with a changed hypothesis, and capture the "
                "lesson via the learning-retrospective skill after you solve "
                "it."
            ),
        }
    }))
sys.exit(0)

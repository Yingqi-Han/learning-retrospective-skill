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
import time

THRESHOLD = 2
STATE_PREFIX = "claude-retry-loop-"
STATE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
CLEANUP_INTERVAL_SECONDS = 24 * 60 * 60


def cleanup_stale_state(temp_dir):
    """Remove old detector state at most once per day; never block the hook."""
    marker = os.path.join(temp_dir, f"{STATE_PREFIX}cleanup")
    now = time.time()
    try:
        if os.path.exists(marker) and now - os.path.getmtime(marker) < CLEANUP_INTERVAL_SECONDS:
            return
        with open(marker, "a", encoding="utf-8"):
            pass
        os.utime(marker, None)
        for name in os.listdir(temp_dir):
            if not (name.startswith(STATE_PREFIX) and name.endswith(".json")):
                continue
            path = os.path.join(temp_dir, name)
            if now - os.path.getmtime(path) > STATE_MAX_AGE_SECONDS:
                os.remove(path)
    except Exception:
        pass


def should_remind(count):
    """Remind at 2, 4, 8... failures instead of spamming every retry."""
    return count >= THRESHOLD and count & (count - 1) == 0

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
if not data.get("session_id"):
    sys.exit(0)
session_raw = str(data["session_id"])
session_key = hashlib.sha1(session_raw.encode("utf-8", "replace")).hexdigest()[:12]
cwd = str(data.get("cwd") or "")
key = hashlib.sha1((cwd + "\n" + command).encode("utf-8", "replace")).hexdigest()[:12]
temp_dir = tempfile.gettempdir()
cleanup_stale_state(temp_dir)
state_path = os.path.join(temp_dir, f"{STATE_PREFIX}{session_key}.json")

try:
    with open(state_path, encoding="utf-8") as f:
        state = json.load(f)
except Exception:
    state = {}
if not isinstance(state, dict):
    state = {}

if event == "PostToolUseFailure":
    previous = state.get(key, 0)
    if not isinstance(previous, int) or isinstance(previous, bool):
        previous = 0
    state[key] = previous + 1
else:
    state.pop(key, None)

if len(state) > 200:  # cap state file growth
    state = {key: state.get(key, 0)} if key in state else {}

try:
    pending_path = f"{state_path}.{os.getpid()}.tmp"
    with open(pending_path, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(pending_path, state_path)
except Exception:
    try:
        os.remove(pending_path)
    except Exception:
        pass

if should_remind(state.get(key, 0)):
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

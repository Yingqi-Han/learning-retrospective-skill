"""Retry-loop detector for Codex.

Register on PostToolUse (matcher ^Bash$) in ~/.codex/hooks.json; see
references/hook-activation.md for the config snippet, the /hooks trust
requirement, and the verification procedure. Codex has no failure-specific
hook event; PostToolUse fires for both success and non-zero exits, and in
currently observed builds tool_response carries the exit code (empirical, not
schema-guaranteed - a missing field is treated as success so the detector
fails safe). Failure increments a per-session counter, success resets it.

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

command = ((data.get("tool_input") or {}).get("command") or "").strip()
if not command:
    sys.exit(0)

resp = data.get("tool_response")
exit_code = None
if isinstance(resp, dict):
    for k in ("exit_code", "exitCode"):
        if isinstance(resp.get(k), int):
            exit_code = resp[k]
            break
failed = exit_code is not None and exit_code != 0

# Hash externally supplied values before using them in paths or keys:
# session_id could contain path separators; the same command in two
# different working directories is not the same action.
session_raw = str(data.get("session_id") or "global")
session_key = hashlib.sha1(session_raw.encode("utf-8", "replace")).hexdigest()[:12]
cwd = str(data.get("cwd") or "")
key = hashlib.sha1((cwd + "\n" + command).encode("utf-8", "replace")).hexdigest()[:12]
state_path = os.path.join(tempfile.gettempdir(), f"codex-retry-loop-{session_key}.json")

try:
    with open(state_path, encoding="utf-8") as f:
        state = json.load(f)
except Exception:
    state = {}

if failed:
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
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                f"Retry-loop detector: this exact command has now failed "
                f"{state[key]} times in this session. Do not run it again "
                "unchanged. First check stored lessons/memory for this "
                "failure signature: if a prior lesson covers it, follow that "
                "lesson. If none exists, this is a novel problem - keep "
                "exploring, but with a changed hypothesis, and capture the "
                "lesson via the learning-retrospective workflow after you "
                "solve it."
            ),
        }
    }))
sys.exit(0)

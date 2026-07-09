"""Hook payload SHAPE probe - verify what your harness actually sends.

The Codex hook schema leaves tool_response unconstrained, and any harness can
change its payload between versions. Register this probe TEMPORARILY in place
of (or alongside) the retry-loop detector, trigger one successful and one
failing command, then read the shape file it writes:

    <temp dir>/hook-payload-shape.jsonl

Each line records the event name plus the STRUCTURE of the payload - key
names and value types only. Values are never written, so commands, outputs,
paths, and anything sensitive stay out of the file. Unregister the probe when
done and delete the shape file.

Stdlib-only; safe to run with `python -S`.
"""
import json
import os
import sys
import tempfile


def shape(value, depth=0):
    """Map a payload to key names and type names, never values."""
    if depth > 4:
        return "..."
    if isinstance(value, dict):
        return {k: shape(v, depth + 1) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [shape(value[0], depth + 1)] if value else []
    return type(value).__name__


try:
    raw = sys.stdin.buffer.read()
    data = json.loads(raw.decode("utf-8-sig"))
except Exception:
    sys.exit(0)

record = {
    "hook_event_name": data.get("hook_event_name"),
    "tool_name": data.get("tool_name"),
    "payload_shape": shape(data),
}

out_path = os.path.join(tempfile.gettempdir(), "hook-payload-shape.jsonl")
try:
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
except Exception:
    pass
sys.exit(0)

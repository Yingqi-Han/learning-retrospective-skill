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
import traceback

THRESHOLD = 2
SEMANTIC_WINDOW_SIZE = 6
SEMANTIC_FAILURE_THRESHOLD = 3
SEMANTIC_DISTINCT_COMMANDS = 2
SEMANTIC_COOLDOWN_CALLS = 8
STATE_PREFIX = "claude-retry-loop-"
STATE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
CLEANUP_INTERVAL_SECONDS = 24 * 60 * 60
REVIEW_CONFIG_FILE = "learning-retrospective-reviewer.json"
REVIEW_CONFIG_PATH_ENV = "LEARNING_RETROSPECTIVE_REVIEW_CONFIG"
DIAGNOSTIC_FILE = "claude-retry-loop-diagnostics.jsonl"
DIAGNOSTIC_PATH_ENV = "LEARNING_RETROSPECTIVE_DIAGNOSTIC_PATH"
_diagnostic_phase = "startup"


def append_diagnostic(kind, **fields):
    """Append privacy-preserving hook diagnostics; never block the hook."""
    record = {
        "timestamp": int(time.time()),
        "kind": kind,
        **fields,
    }
    try:
        path = os.environ.get(DIAGNOSTIC_PATH_ENV) or os.path.join(
            tempfile.gettempdir(), DIAGNOSTIC_FILE
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")
    except Exception:
        pass


def fail_safe_excepthook(exc_type, _exc, tb):
    """Turn unexpected detector bugs into a visible, non-blocking warning."""
    line = None
    try:
        frames = traceback.extract_tb(tb)
        if frames:
            line = frames[-1].lineno
    except Exception:
        pass
    append_diagnostic(
        "internal_error",
        exception_type=getattr(exc_type, "__name__", "UnknownError"),
        line=line,
        phase=_diagnostic_phase,
    )
    try:
        warning = {
            "systemMessage": (
                "Retry-loop detector recovered from an internal error; "
                "privacy-safe diagnostics were recorded."
            ),
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    "The retry-loop detector encountered an internal error "
                    "and failed open. Do not treat this event as evidence that "
                    "no retry loop exists."
                ),
            },
        }
        sys.stdout.write(json.dumps(warning) + "\n")
        sys.stdout.flush()
    except Exception:
        pass
    os._exit(0)


sys.excepthook = fail_safe_excepthook


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


def update_semantic_window(state, key, failed):
    """Return a bounded semantic-review candidate without storing raw commands."""
    event_index = state.get("__event_index__", 0)
    if not isinstance(event_index, int) or isinstance(event_index, bool):
        event_index = 0
    event_index += 1

    recent = state.get("__recent__", [])
    if not isinstance(recent, list):
        recent = []
    recent = [
        item for item in recent
        if isinstance(item, dict)
        and isinstance(item.get("failed"), bool)
        and isinstance(item.get("key"), str)
    ]
    recent.append({"event_index": event_index, "failed": failed, "key": key})
    recent = recent[-SEMANTIC_WINDOW_SIZE:]
    first_index = max(1, event_index - len(recent) + 1)
    for offset, item in enumerate(recent):
        stored_index = item.get("event_index")
        if not isinstance(stored_index, int) or isinstance(stored_index, bool):
            item["event_index"] = first_index + offset

    last_review = state.get("__semantic_review_at__", -SEMANTIC_COOLDOWN_CALLS)
    if not isinstance(last_review, int) or isinstance(last_review, bool):
        last_review = -SEMANTIC_COOLDOWN_CALLS
    failed_items = [item for item in recent if item["failed"]]
    distinct = {item["key"] for item in failed_items}
    candidate = (
        failed
        and len(failed_items) >= SEMANTIC_FAILURE_THRESHOLD
        and len(distinct) >= SEMANTIC_DISTINCT_COMMANDS
        and event_index - last_review >= SEMANTIC_COOLDOWN_CALLS
    )

    state["__event_index__"] = event_index
    state["__recent__"] = recent
    if candidate:
        state["__semantic_review_at__"] = event_index
    return {
        "candidate": candidate,
        "event_index": event_index,
        "evidence_mode": "structured_failures",
        "failure_count": len(failed_items),
        "distinct_commands": len(distinct),
        "window_size": len(recent),
        "events": [
            {
                "event_index": item["event_index"],
                "command_signature": item["key"],
                "outcome": "failed" if item["failed"] else "succeeded",
            }
            for item in recent
        ],
    }


def load_reviewer_preferences():
    """Load optional local reviewer preferences; never require a model vendor."""
    path = os.environ.get(REVIEW_CONFIG_PATH_ENV) or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), REVIEW_CONFIG_FILE
    )
    try:
        with open(path, encoding="utf-8") as f:
            config = json.load(f)
    except Exception:
        config = {}
    if not isinstance(config, dict):
        config = {}

    model = config.get("preferred_model", "")
    if not isinstance(model, str) or not all(
        char.isalnum() or char in "._-" for char in model
    ) or len(model) > 100:
        model = ""
    effort = config.get("reasoning_effort", "medium")
    if effort not in {"low", "medium", "high", "xhigh"}:
        effort = "medium"
    threshold = config.get("confidence_threshold", 0.8)
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
        threshold = 0.8
    threshold = min(1.0, max(0.5, float(threshold)))
    return model, effort, threshold


def build_evidence_manifest(signal, session_key):
    """Build a privacy-safe manifest from events observed by the hook itself."""
    core = {
        "schema_version": 1,
        "evidence_source": "hook_observed_payloads",
        "evidence_mode": signal["evidence_mode"],
        "events": signal["events"],
    }
    request_material = session_key + "\n" + json.dumps(
        core, sort_keys=True, separators=(",", ":")
    )
    return {
        **core,
        "request_id": hashlib.sha256(
            request_material.encode("utf-8", "replace")
        ).hexdigest()[:16],
    }


def semantic_review_context(signal, manifest):
    """Build a vendor-neutral, evidence-bound subagent review request."""
    model, effort, threshold = load_reviewer_preferences()
    reviewer = (
        f"Prefer reviewer model {model} at {effort} reasoning. "
        if model
        else "Use any available fast, low-cost secondary agent. "
    )
    fallback = {
        "schema_version": 1,
        "request_id": manifest["request_id"],
        "classification": "uncertain",
        "confidence": 0.0,
        "same_failure_family": False,
        "prior_lesson_verified": False,
        "evidence_adequate": False,
        "should_interrupt": False,
        "reviewer_agent_id": None,
        "reviewer_isolation": "prompt_only",
        "reason": "invalid reviewer schema",
        "recommended_action": "ask_user",
    }
    manifest_json = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    fallback_json = json.dumps(fallback, sort_keys=True, separators=(",", ":"))
    return (
        "Semantic retry candidate, not a confirmed loop: "
        f"{signal['failure_count']} failed Bash calls among the last "
        f"{signal['window_size']}, across {signal['distinct_commands']} "
        "different command signatures. The following manifest was generated "
        "from actual hook payloads. It proves event order, command signatures, "
        "and structured outcomes while omitting raw commands and output.\n"
        "HOOK_EVIDENCE_MANIFEST_BEGIN\n"
        + manifest_json
        + "\nHOOK_EVIDENCE_MANIFEST_END\n"
        "Before another broad fallback, invoke the learning-retrospective "
        "workflow and spawn exactly one fresh secondary reviewer when the "
        "harness supports it. Do not self-classify or fabricate reviewer output. "
        "Use non-inherited context when supported. Do not call the reviewer "
        "read-only unless the spawn interface enforces tool denial or read-only "
        "permissions. Record the non-empty agent id returned by the spawn call "
        "as SPAWNED_REVIEWER_ID, include it in REVIEW_PACKET_V1, and require the "
        "reviewer to echo it as reviewer_agent_id. Wait on exactly that id. A "
        "missing spawn id, empty wait target, or mismatched id means no review "
        "occurred and must be reported as reviewer_unavailable. When permissions "
        "are not enforced, report reviewer_isolation=prompt_only. Before "
        "spawning, perform one bounded read-only lookup for lessons matching the "
        "failure signature. Include only source-labelled candidate summaries "
        "that are still applicable as prior_lesson_candidates; use an empty "
        "array when none is verified. Build REVIEW_PACKET_V1 by copying, not "
        "summarizing, the current goal and the "
        "last 6-12 relevant raw tool-event fields: ordinal, command or action, "
        "cwd when relevant, structured outcome, concise error, and hypothesis. "
        "Include the hook manifest unchanged and redact secrets. If raw events "
        "are unavailable or conflict with the manifest, set "
        "evidence_adequate=false and should_interrupt=false. "
        + reviewer
        + "The reviewer must not call tools, edit files, write memory, or retry "
        "the action. Require exactly one JSON object and no prose with "
        "schema_version=1, the exact request_id, classification (known_loop, "
        "novel_exploration, routine_failure, or uncertain), confidence, "
        "same_failure_family, prior_lesson_verified, evidence_adequate, "
        "should_interrupt, "
        "reviewer_agent_id, reviewer_isolation, reason, and recommended_action "
        "(recall_lesson, change_hypothesis, continue, or ask_user). The echoed "
        "reviewer_agent_id must exactly match the non-empty spawn id. Confidence "
        "must be numeric from 0 to 1 and all four boolean fields must be literal "
        "true/false. If invalid, send one correction request to the same reviewer "
        "and wait once; do not spawn another reviewer. If still invalid, discard "
        "it and use exactly: "
        + fallback_json
        + ". This fallback is a main-agent safety result, not a successful "
        "reviewer result. known_loop is invalid unless a source-labelled prior "
        "lesson candidate exists and same_failure_family, "
        "prior_lesson_verified, evidence_adequate, and should_interrupt are all "
        "true. Interrupt only "
        f"for valid known_loop with confidence >= {threshold:.2f}; continue "
        "evidence-producing novel exploration."
    )

_diagnostic_phase = "decode_input"
try:
    raw = sys.stdin.buffer.read()
    data = json.loads(raw.decode("utf-8-sig"))
except Exception:
    sys.exit(0)

_diagnostic_phase = "validate_input"
if data.get("tool_name") != "Bash":
    sys.exit(0)

event = data.get("hook_event_name", "")
tool_input = data.get("tool_input")
if not isinstance(tool_input, dict):
    sys.exit(0)
command_value = tool_input.get("command")
if not isinstance(command_value, str):
    sys.exit(0)
command = command_value.strip()
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

_diagnostic_phase = "update_state"
if event == "PostToolUseFailure":
    previous = state.get(key, 0)
    if not isinstance(previous, int) or isinstance(previous, bool):
        previous = 0
    state[key] = previous + 1
else:
    state.pop(key, None)

failed = event == "PostToolUseFailure"
semantic_signal = update_semantic_window(state, key, failed)

if len(state) > 205:  # cap command counters while preserving control metadata
    preserved = {
        name: state[name]
        for name in ("__event_index__", "__recent__", "__semantic_review_at__")
        if name in state
    }
    if key in state:
        preserved[key] = state[key]
    state = preserved

_diagnostic_phase = "write_state"
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

_diagnostic_phase = "emit_reminder"
count = state.get(key, 0)
if not isinstance(count, int) or isinstance(count, bool):
    count = 0
exact_reminder = should_remind(count)
semantic_candidate = semantic_signal["candidate"]
semantic_manifest = (
    build_evidence_manifest(semantic_signal, session_key)
    if semantic_candidate
    else None
)
if exact_reminder or semantic_candidate:
    contexts = []
    system_messages = []
    if exact_reminder:
        system_messages.append(f"same command failed {count}x")
        contexts.append(
            f"Retry-loop detector: this exact command has now failed "
            f"{count} times in this session. Do not run it again unchanged. "
            "First check stored lessons/memory for this failure signature. "
            "If none exists, continue only with a changed hypothesis and "
            "capture the verified lesson after solving it."
        )
    if semantic_candidate:
        system_messages.append("semantic review requested")
        contexts.append(semantic_review_context(semantic_signal, semantic_manifest))
    print(json.dumps({
        # systemMessage is shown to the USER in the UI; additionalContext is
        # injected into the MODEL's context. Both matter: an invisible
        # intervention cannot be trusted or debugged.
        "systemMessage": (
            "Retry-loop detector: " + "; ".join(system_messages) + "."
        ),
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": "\n\n".join(contexts),
        }
    }))
_diagnostic_phase = "complete"
sys.exit(0)

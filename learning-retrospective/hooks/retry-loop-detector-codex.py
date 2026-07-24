"""Retry-loop detector for Codex.

Register on PostToolUse (matcher ^Bash$) in ~/.codex/hooks.json; see
references/hook-activation.md for the config snippet, the surface-specific
trust requirement, and the verification procedure. Codex payloads are not stable:
some builds expose a structured exit code while others expose output text only.
Structured payloads retain deterministic failure counting. When the exit status
is unavailable, the hook requests bounded semantic review based on command
repetition and shell-activity cadence; it never guesses failure from output text.

Stdlib-only; safe to run with `python -S`.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import traceback

THRESHOLD = 2
SEMANTIC_WINDOW_SIZE = 12
SEMANTIC_FAILURE_THRESHOLD = 3
SEMANTIC_DISTINCT_COMMANDS = 2
SEMANTIC_COOLDOWN_CALLS = 8
ACTIVITY_REVIEW_CALLS = 12
ACTIVITY_REVIEW_DISTINCT_COMMANDS = 3
ACTIVITY_REVIEW_MIN_SPAN_SECONDS = 120
ACTIVITY_REVIEW_COOLDOWN_CALLS = 24
ACTIVITY_REVIEW_COOLDOWN_SECONDS = 15 * 60
UNKNOWN_REPEAT_THRESHOLD = 2
STATE_PREFIX = "codex-retry-loop-"
STATE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
CLEANUP_INTERVAL_SECONDS = 24 * 60 * 60
DIAGNOSTIC_FILE = "codex-retry-loop-diagnostics.jsonl"
DIAGNOSTIC_PATH_ENV = "LEARNING_RETROSPECTIVE_DIAGNOSTIC_PATH"
REVIEW_CONFIG_FILE = "learning-retrospective-reviewer.json"
REVIEW_CONFIG_PATH_ENV = "LEARNING_RETROSPECTIVE_REVIEW_CONFIG"
REVIEW_RUNNER_FILE = "retry-reviewer-codex-cli.py"
MAX_REVIEW_TIMEOUT_SECONDS = 45
_diagnostic_phase = "startup"

if os.environ.get("LEARNING_RETROSPECTIVE_DISABLE") == "1":
    sys.exit(0)


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


def normalize_cwd(cwd):
    value = str(cwd or "").strip()
    return os.path.normcase(os.path.normpath(value)) if value else ""


def command_signature(cwd, command):
    material = normalize_cwd(cwd) + "\n" + str(command or "").strip()
    return hashlib.sha1(material.encode("utf-8", "replace")).hexdigest()[:12]


def update_semantic_window(state, key, failed, config=None):
    """Return a bounded semantic-review candidate without storing raw commands."""
    config = config if isinstance(config, dict) else {}
    activity_review_calls = config.get(
        "activity_review_calls", ACTIVITY_REVIEW_CALLS
    )
    activity_min_span = config.get(
        "activity_review_min_span_seconds",
        ACTIVITY_REVIEW_MIN_SPAN_SECONDS,
    )
    activity_cooldown_calls = config.get(
        "activity_review_cooldown_calls",
        ACTIVITY_REVIEW_COOLDOWN_CALLS,
    )
    activity_cooldown_seconds = config.get(
        "activity_review_cooldown_seconds",
        ACTIVITY_REVIEW_COOLDOWN_SECONDS,
    )
    now = int(time.time())
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
        and (
            isinstance(item.get("failed"), bool)
            or item.get("failed") is None
        )
        and isinstance(item.get("key"), str)
    ]
    recent.append({"event_index": event_index, "failed": failed, "key": key})
    recent = recent[-SEMANTIC_WINDOW_SIZE:]
    first_index = max(1, event_index - len(recent) + 1)
    for offset, item in enumerate(recent):
        stored_index = item.get("event_index")
        if not isinstance(stored_index, int) or isinstance(stored_index, bool):
            item["event_index"] = first_index + offset

    last_key = state.get("__last_key__")
    repeat_count = state.get("__repeat_count__", 0)
    if not isinstance(repeat_count, int) or isinstance(repeat_count, bool):
        repeat_count = 0
    repeat_count = repeat_count + 1 if last_key == key else 1

    last_review = state.get(
        "__semantic_review_at__", -ACTIVITY_REVIEW_COOLDOWN_CALLS
    )
    if not isinstance(last_review, int) or isinstance(last_review, bool):
        last_review = -ACTIVITY_REVIEW_COOLDOWN_CALLS
    activity_started = state.get("__activity_started_at__")
    if (
        failed is None
        and (
            not isinstance(activity_started, int)
            or isinstance(activity_started, bool)
            or activity_started > now
        )
    ):
        activity_started = now
    elif failed is not None:
        activity_started = None
    last_activity_review = state.get("__activity_review_time__", 0)
    if (
        not isinstance(last_activity_review, int)
        or isinstance(last_activity_review, bool)
        or last_activity_review > now
    ):
        last_activity_review = 0
    failed_items = [item for item in recent if item["failed"]]
    distinct = {item["key"] for item in failed_items}
    structured_candidate = (
        failed
        and len(failed_items) >= SEMANTIC_FAILURE_THRESHOLD
        and len(distinct) >= SEMANTIC_DISTINCT_COMMANDS
        and event_index - last_review >= SEMANTIC_COOLDOWN_CALLS
    )
    activity_distinct = {item["key"] for item in recent}
    unknown_repeat_candidate = (
        failed is None
        and repeat_count >= UNKNOWN_REPEAT_THRESHOLD
        and event_index - last_review >= SEMANTIC_COOLDOWN_CALLS
    )
    broad_activity_candidate = (
        failed is None
        and repeat_count < UNKNOWN_REPEAT_THRESHOLD
        and len(recent) >= activity_review_calls
        and len(activity_distinct) >= ACTIVITY_REVIEW_DISTINCT_COMMANDS
        and activity_started is not None
        and now - activity_started >= activity_min_span
        and event_index - last_review >= activity_cooldown_calls
        and now - last_activity_review >= activity_cooldown_seconds
    )
    activity_candidate = unknown_repeat_candidate or broad_activity_candidate
    candidate = structured_candidate or activity_candidate
    candidate_reason = (
        "structured_failures"
        if structured_candidate
        else "unknown_exact_repeat"
        if unknown_repeat_candidate
        else "sustained_unknown_activity"
        if broad_activity_candidate
        else "none"
    )

    state["__event_index__"] = event_index
    state["__recent__"] = recent
    state["__last_key__"] = key
    state["__repeat_count__"] = repeat_count
    if activity_started is None:
        state.pop("__activity_started_at__", None)
    else:
        state["__activity_started_at__"] = activity_started
    if candidate:
        state["__semantic_review_at__"] = event_index
    if broad_activity_candidate:
        state["__activity_review_time__"] = now
    return {
        "candidate": candidate,
        "candidate_reason": candidate_reason,
        "event_index": event_index,
        "evidence_mode": (
            "structured_failures" if structured_candidate else "activity_window"
        ),
        "failure_count": len(failed_items),
        "distinct_commands": (
            len(distinct) if structured_candidate else len(activity_distinct)
        ),
        "repeat_count": repeat_count,
        "window_size": len(recent),
        "events": [
            {
                "event_index": item["event_index"],
                "command_signature": item["key"],
                "outcome": (
                    "failed"
                    if item["failed"] is True
                    else "succeeded"
                    if item["failed"] is False
                    else "unknown"
                ),
            }
            for item in recent
        ],
    }


def load_reviewer_config():
    """Load and validate optional local reviewer settings."""
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
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", model):
        model = ""
    effort = config.get("reasoning_effort", "medium")
    if effort not in {"low", "medium", "high", "xhigh"}:
        effort = "medium"
    threshold = config.get("confidence_threshold", 0.8)
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
        threshold = 0.8
    threshold = min(1.0, max(0.5, float(threshold)))
    backend = config.get("review_backend", "main_agent")
    if backend not in {"main_agent", "codex_cli"}:
        backend = "main_agent"
    codex_cli_path = config.get("codex_cli_path", "")
    if (
        not isinstance(codex_cli_path, str)
        or "\n" in codex_cli_path
        or len(codex_cli_path) > 1024
    ):
        codex_cli_path = ""
    timeout = config.get("review_timeout_seconds", 45)
    if not isinstance(timeout, int) or isinstance(timeout, bool):
        timeout = 45
    timeout = min(MAX_REVIEW_TIMEOUT_SECONDS, max(10, timeout))
    activity_review_calls = config.get(
        "activity_review_calls", ACTIVITY_REVIEW_CALLS
    )
    if not isinstance(activity_review_calls, int) or isinstance(
        activity_review_calls, bool
    ):
        activity_review_calls = ACTIVITY_REVIEW_CALLS
    activity_review_calls = min(
        SEMANTIC_WINDOW_SIZE, max(8, activity_review_calls)
    )
    activity_review_min_span_seconds = config.get(
        "activity_review_min_span_seconds",
        ACTIVITY_REVIEW_MIN_SPAN_SECONDS,
    )
    if not isinstance(activity_review_min_span_seconds, int) or isinstance(
        activity_review_min_span_seconds, bool
    ):
        activity_review_min_span_seconds = ACTIVITY_REVIEW_MIN_SPAN_SECONDS
    activity_review_min_span_seconds = min(
        3600, max(0, activity_review_min_span_seconds)
    )
    activity_review_cooldown_calls = config.get(
        "activity_review_cooldown_calls",
        ACTIVITY_REVIEW_COOLDOWN_CALLS,
    )
    if not isinstance(activity_review_cooldown_calls, int) or isinstance(
        activity_review_cooldown_calls, bool
    ):
        activity_review_cooldown_calls = ACTIVITY_REVIEW_COOLDOWN_CALLS
    activity_review_cooldown_calls = min(
        200, max(SEMANTIC_COOLDOWN_CALLS, activity_review_cooldown_calls)
    )
    activity_review_cooldown_seconds = config.get(
        "activity_review_cooldown_seconds",
        ACTIVITY_REVIEW_COOLDOWN_SECONDS,
    )
    if not isinstance(activity_review_cooldown_seconds, int) or isinstance(
        activity_review_cooldown_seconds, bool
    ):
        activity_review_cooldown_seconds = ACTIVITY_REVIEW_COOLDOWN_SECONDS
    activity_review_cooldown_seconds = min(
        24 * 60 * 60, max(0, activity_review_cooldown_seconds)
    )
    return {
        "preferred_model": model,
        "reasoning_effort": effort,
        "confidence_threshold": threshold,
        "review_backend": backend,
        "codex_cli_path": codex_cli_path,
        "review_timeout_seconds": timeout,
        "activity_review_calls": activity_review_calls,
        "activity_review_min_span_seconds": activity_review_min_span_seconds,
        "activity_review_cooldown_calls": activity_review_cooldown_calls,
        "activity_review_cooldown_seconds": activity_review_cooldown_seconds,
    }


def load_reviewer_preferences():
    """Return the vendor-neutral preferences used in injected context."""
    config = load_reviewer_config()
    return (
        config["preferred_model"],
        config["reasoning_effort"],
        config["confidence_threshold"],
    )


def run_automated_review(manifest, hook_payload):
    """Run the explicitly configured Codex CLI backend, if enabled."""
    config = load_reviewer_config()
    if config["review_backend"] != "codex_cli":
        return None, ""
    runner = os.path.join(os.path.dirname(os.path.abspath(__file__)), REVIEW_RUNNER_FILE)
    if not os.path.isfile(runner):
        return None, "review_runner_missing"
    request = {
        "manifest": manifest,
        "hook_payload": {
            "session_id": hook_payload.get("session_id"),
            "cwd": hook_payload.get("cwd"),
            "tool_input": hook_payload.get("tool_input"),
            "tool_response": hook_payload.get("tool_response"),
        },
    }
    env = dict(os.environ)
    if config["codex_cli_path"]:
        env["LEARNING_RETROSPECTIVE_CODEX_CLI"] = config["codex_cli_path"]
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        completed = subprocess.run(
            [sys.executable, "-S", runner],
            input=json.dumps(request),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=config["review_timeout_seconds"] + 5,
            env=env,
            **kwargs,
        )
        result = json.loads(completed.stdout)
    except subprocess.TimeoutExpired:
        return None, "review_runner_timeout"
    except Exception:
        return None, "review_runner_invalid_output"
    if completed.returncode != 0 or not isinstance(result, dict):
        return None, "review_runner_failed"
    if result.get("ok") is not True:
        reason = result.get("error")
        if not isinstance(reason, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,100}", reason
        ):
            reason = "review_runner_failed"
        return None, reason
    review = result.get("review")
    if not isinstance(review, dict):
        return None, "review_result_missing"
    if review.get("request_id") != manifest["request_id"]:
        return None, "review_request_id_mismatch"
    reviewer_id = review.get("reviewer_agent_id")
    if not isinstance(reviewer_id, str) or not reviewer_id:
        return None, "reviewer_agent_id_missing"
    return review, ""


def automated_review_context(review):
    """Inject a completed, runtime-identified reviewer result."""
    return (
        "Automated semantic review completed through the explicitly configured "
        "Codex CLI backend. The reviewer ran in a separate read-only sandbox and "
        "a temporary Codex home that excluded the user's skills, hooks, rules, "
        "and memory. Codex built-in system instructions and system skills may "
        "still be present. The runtime thread id was captured by the launcher. "
        "Do not spawn another reviewer for this candidate. This isolated "
        "reviewer intentionally had no persistent-memory access, so its result "
        "is semantic triage rather than proof of a known lesson. When "
        "same_failure_family=true and prior_lesson_verified=false, perform one "
        "bounded lookup of stored lessons or memory using the failure signature. "
        "Only the main agent may promote the episode to known_loop after citing "
        "a still-applicable lesson or verified local fact. Otherwise change the "
        "hypothesis or continue evidence-producing exploration; do not interrupt "
        "the task.\n"
        "AUTOMATED_SEMANTIC_REVIEW_RESULT_BEGIN\n"
        + json.dumps(review, sort_keys=True, separators=(",", ":"))
        + "\nAUTOMATED_SEMANTIC_REVIEW_RESULT_END"
    )


def build_evidence_manifest(signal, session_key):
    """Build a privacy-safe manifest from events observed by the hook itself."""
    core = {
        "schema_version": 1,
        "evidence_source": "hook_observed_payloads",
        "evidence_mode": signal["evidence_mode"],
        "candidate_reason": signal["candidate_reason"],
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
    if signal["evidence_mode"] == "structured_failures":
        evidence = (
            f"{signal['failure_count']} failed Bash calls among the last "
            f"{signal['window_size']}, across {signal['distinct_commands']} "
            "different command signatures"
        )
    else:
        evidence = (
            "this Codex build did not expose a structured shell exit status; "
            f"the activity window contains {signal['window_size']} calls across "
            f"{signal['distinct_commands']} command signatures, with a current "
            f"exact-repeat count of {signal['repeat_count']}"
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
        + evidence
        + ". The following manifest was generated from actual hook payloads. "
        "It proves event order, command signatures, and any structured outcome, "
        "while intentionally omitting raw commands and output.\n"
        "HOOK_EVIDENCE_MANIFEST_BEGIN\n"
        + manifest_json
        + "\nHOOK_EVIDENCE_MANIFEST_END\n"
        "Before another broad fallback, invoke the learning-retrospective "
        "workflow. If this harness exposes a multi-agent tool, you MUST actually "
        "spawn exactly one fresh secondary reviewer; do not self-classify or "
        "fabricate reviewer output. On Codex, check specifically for spawn_agent "
        "or an equivalent multi-agent tool before declaring the reviewer "
        "unavailable. Use fork_context:false when supported so the reviewer "
        "does not inherit the current conversation; built-in system context may "
        "still remain. "
        "Immediately record the non-empty agent id returned by spawn_agent as "
        "SPAWNED_REVIEWER_ID. If spawn does not return a non-empty id, report "
        "reviewer_unavailable; do not call wait and do not claim a reviewer "
        "classification. Put SPAWNED_REVIEWER_ID in REVIEW_PACKET_V1 and require "
        "the reviewer to echo it exactly as reviewer_agent_id. Call wait_agent "
        "with exactly that same id. A wait with an empty target list, a missing "
        "spawn trace, or a mismatched id means no review occurred. "
        "Report reviewer_isolation=enforced_no_tools only when the spawn "
        "interface technically removes tool access. Report enforced_read_only "
        "when writes are denied but reads or commands may remain; that mode is "
        "not safe for hostile packet text. Otherwise use a prompt-only non-tool "
        "contract and report reviewer_isolation=prompt_only. "
        "Build REVIEW_PACKET_V1 by copying, not summarizing, the current goal and "
        "the last 6-12 relevant raw tool-event fields visible in the parent "
        "context: ordinal, command or action, cwd when relevant, structured exit "
        "status, concise error or outcome, and stated hypothesis. Include the "
        "hook manifest unchanged. Before spawning, perform one bounded read-only "
        "lookup for lessons matching the failure signature. Include only "
        "source-labelled candidate summaries that are still applicable as "
        "prior_lesson_candidates; use an empty array when none is verified. "
        "Redact secrets and unrelated private output. "
        "If the raw events are unavailable or conflict with the manifest, the "
        "reviewer must set evidence_adequate=false and should_interrupt=false. "
        + reviewer
        + "The reviewer must not call tools, edit files, write memory, or retry "
        "the failed action. Require exactly one JSON object and no prose with "
        "schema_version=1, the exact request_id, classification (known_loop, "
        "novel_exploration, routine_failure, or uncertain), confidence, "
        "same_failure_family, prior_lesson_verified, evidence_adequate, "
        "should_interrupt, "
        "reviewer_agent_id, reviewer_isolation, reason, and recommended_action "
        "(recall_lesson, change_hypothesis, continue, or ask_user). Validate that "
        "reviewer_agent_id exactly matches the non-empty SPAWNED_REVIEWER_ID, "
        "confidence is numeric from 0 to 1, and all four boolean fields are "
        "literal true/false. "
        "If the response is invalid, send one correction request to the same "
        "reviewer with the validation errors and wait once more; do not spawn a "
        "second reviewer. If the corrected response is still invalid, discard it "
        "and use exactly: "
        + fallback_json
        + ". This fallback is a main-agent safety result, not a successful "
        "reviewer result. Do not quote or summarize an invalid object as if it "
        "passed. Treat "
        "known_loop as internally invalid unless a source-labelled prior lesson "
        "candidate exists and same_failure_family, prior_lesson_verified, "
        "evidence_adequate, and should_interrupt are all true. Treat any result "
        "with evidence_adequate=false and should_interrupt=true as invalid. "
        "A user-requested repetition, test probe, "
        "or evidence-producing variation is not a retry loop by itself. In "
        "activity-window mode, never return known_loop solely from repetition: "
        "require concrete failed outcomes in the supplied transcript plus an "
        "applicable prior lesson or verified fact. Otherwise set should_interrupt "
        "to false and use uncertain, routine_failure, or novel_exploration. If no "
        "multi-agent tool exists, explicitly report reviewer_unavailable before "
        "running the checklist in the main agent. Interrupt only for known_loop "
        "with confidence "
        f">= {threshold:.2f}; continue evidence-producing novel exploration."
    )


_diagnostic_phase = "decode_input"
try:
    raw = sys.stdin.buffer.read()
    data = json.loads(raw.decode("utf-8-sig"))
except Exception as exc:
    append_diagnostic(
        "unsupported_input",
        reason="json_decode_failed",
        exception_type=type(exc).__name__,
        raw_bytes=len(raw) if "raw" in locals() else 0,
        phase=_diagnostic_phase,
    )
    sys.exit(0)
if not isinstance(data, dict):
    append_diagnostic(
        "unsupported_input",
        reason="payload_not_object",
        payload_type=type(data).__name__,
        phase=_diagnostic_phase,
    )
    sys.exit(0)

_diagnostic_phase = "validate_input"
if data.get("tool_name") != "Bash":
    append_diagnostic(
        "unsupported_input",
        reason="tool_name_mismatch",
        tool_name_type=type(data.get("tool_name")).__name__,
        phase=_diagnostic_phase,
    )
    sys.exit(0)

tool_input = data.get("tool_input")
if not isinstance(tool_input, dict):
    sys.exit(0)
command_value = tool_input.get("command")
if command_value is None:
    sys.exit(0)
if not isinstance(command_value, str):
    append_diagnostic(
        "unsupported_input",
        command_type=type(command_value).__name__,
        phase=_diagnostic_phase,
    )
    sys.exit(0)
command = command_value.strip()
if not command:
    sys.exit(0)

_diagnostic_phase = "classify_result"
resp = data.get("tool_response")
exit_code = None
if isinstance(resp, dict):
    for k in ("exit_code", "exitCode"):
        if isinstance(resp.get(k), int) and not isinstance(resp.get(k), bool):
            exit_code = resp[k]
            break
failed = None if exit_code is None else exit_code != 0

# Hash externally supplied values before using them in paths or keys:
# session_id could contain path separators; the same command in two
# different working directories is not the same action.
if not data.get("session_id"):
    sys.exit(0)
_diagnostic_phase = "load_state"
session_raw = str(data["session_id"])
session_key = hashlib.sha1(session_raw.encode("utf-8", "replace")).hexdigest()[:12]
cwd = str(tool_input.get("workdir") or data.get("cwd") or "")
key = command_signature(cwd, command)
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
if failed is True:
    previous = state.get(key, 0)
    if not isinstance(previous, int) or isinstance(previous, bool):
        previous = 0
    state[key] = previous + 1
elif failed is False:
    state.pop(key, None)

review_config = load_reviewer_config()
semantic_signal = update_semantic_window(state, key, failed, review_config)

if len(state) > 205:  # cap command counters while preserving control metadata
    preserved = {
        name: state[name]
        for name in (
            "__event_index__",
            "__recent__",
            "__semantic_review_at__",
            "__last_key__",
            "__repeat_count__",
            "__activity_started_at__",
            "__activity_review_time__",
        )
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
exact_reminder = failed is True and should_remind(count)
semantic_candidate = semantic_signal["candidate"]
semantic_manifest = (
    build_evidence_manifest(semantic_signal, session_key)
    if semantic_candidate
    else None
)
automated_review = None
automated_review_error = ""
if semantic_candidate:
    automated_review, automated_review_error = run_automated_review(
        semantic_manifest, data
    )
if exact_reminder:
    append_diagnostic("reminder_emitted", failure_count=count)
if semantic_candidate:
    append_diagnostic(
        "semantic_review_requested",
        evidence_mode=semantic_signal["evidence_mode"],
        candidate_reason=semantic_signal["candidate_reason"],
        failure_count=semantic_signal["failure_count"],
        distinct_commands=semantic_signal["distinct_commands"],
        repeat_count=semantic_signal["repeat_count"],
        window_size=semantic_signal["window_size"],
        request_id=semantic_manifest["request_id"],
    )
    if automated_review:
        append_diagnostic(
            "automated_review_completed",
            request_id=semantic_manifest["request_id"],
            reviewer_agent_id=automated_review["reviewer_agent_id"],
            classification=automated_review.get("classification"),
            should_interrupt=automated_review.get("should_interrupt"),
        )
    elif automated_review_error:
        append_diagnostic(
            "automated_review_unavailable",
            request_id=semantic_manifest["request_id"],
            reason=automated_review_error,
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
        if automated_review:
            system_messages.append("automated semantic review completed")
            contexts.append(automated_review_context(automated_review))
        else:
            system_messages.append("semantic review requested")
            manual_context = semantic_review_context(
                semantic_signal, semantic_manifest
            )
            if automated_review_error:
                manual_context = (
                    "The explicitly configured automated reviewer was unavailable "
                    f"({automated_review_error}). Do not fabricate a reviewer "
                    "result.\n" + manual_context
                )
            contexts.append(manual_context)
    print(json.dumps({
        # systemMessage is shown to the USER in the UI; additionalContext is
        # injected into the MODEL's context. Both matter: an invisible
        # intervention cannot be trusted or debugged.
        "systemMessage": (
            "Retry-loop detector: " + "; ".join(system_messages) + "."
        ),
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "\n\n".join(contexts),
        }
    }))
_diagnostic_phase = "complete"
sys.exit(0)

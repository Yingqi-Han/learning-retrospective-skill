"""Run one evidence-bound retry review through an isolated Codex CLI child.

This helper is opt-in and is invoked by retry-loop-detector-codex.py only when
the local reviewer config selects the ``codex_cli`` backend. It reads a bounded
tail of the parent rollout, redacts likely secrets, runs Codex with a read-only
sandbox and a temporary user-context-isolated Codex home, validates the
structured result, and returns one JSON object. Raw commands and output are
never written by this script.
"""
import glob
import hashlib
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_TRANSCRIPT_BYTES = 4 * 1024 * 1024
MAX_EVENTS = 12
MAX_TEXT = 600
MAX_REVIEW_TIMEOUT_SECONDS = 45
CONFIG_FILE = "learning-retrospective-reviewer.json"
CONFIG_PATH_ENV = "LEARNING_RETROSPECTIVE_REVIEW_CONFIG"
CODEX_CLI_ENV = "LEARNING_RETROSPECTIVE_CODEX_CLI"
DEBUG_ENV = "LEARNING_RETROSPECTIVE_REVIEW_DEBUG"
CHILD_DISABLED_FEATURES = (
    "plugins",
    "apps",
    "memories",
    "skill_search",
    "multi_agent",
    "hooks",
    "shell_tool",
    "unified_exec",
    "browser_use",
    "browser_use_external",
    "browser_use_full_cdp_access",
    "in_app_browser",
    "computer_use",
    "image_generation",
    "workspace_dependencies",
    "code_mode",
    "code_mode_host",
    "skill_mcp_dependency_install",
    "tool_suggest",
)

CLASSIFICATIONS = {
    "known_loop",
    "novel_exploration",
    "routine_failure",
    "uncertain",
}
ACTIONS = {"recall_lesson", "change_hypothesis", "continue", "ask_user"}

SECRET_SUBSTITUTIONS = (
    (
        re.compile(
            r"(?is)-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?"
            r"-----END [A-Z0-9 ]*PRIVATE KEY-----"
        ),
        "<redacted-private-key>",
    ),
    (
        re.compile(
            r"(?i)\b([a-z][a-z0-9+.-]*://)"
            r"[^/\s:@]+:[^@\s/]+@"
        ),
        r"\1<redacted>@",
    ),
    (
        re.compile(
            r"(?im)^(\s*(?:authorization|proxy-authorization|cookie|"
            r"set-cookie|x-api-key)\s*:\s*).*$"
        ),
        r"\1<redacted>",
    ),
    (
        re.compile(
            r"(?i)(--[A-Za-z0-9_-]*(?:api[-_]?key|token|password|"
            r"passwd|secret|cookie)[A-Za-z0-9_-]*(?:=|\s+))"
            r"[^\s,;]+"
        ),
        r"\1<redacted>",
    ),
    (
        re.compile(
            r"(?i)([\"']?[A-Za-z0-9_.:/-]*(?:api[_-]?key|auth[_-]?token|"
            r"access[_-]?token|refresh[_-]?token|id[_-]?token|token|password|"
            r"passwd|secret|authorization|cookie)[A-Za-z0-9_.:/-]*[\"']?"
            r"\s*[:=]\s*)[^\s,;]+"
        ),
        r"\1<redacted>",
    ),
    (
        re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]+"),
        r"\1 <redacted>",
    ),
    (
        re.compile(
            r"\b(?:sk-[A-Za-z0-9_-]{12,}|ghp_[A-Za-z0-9_-]{12,}|"
            r"github_pat_[A-Za-z0-9_-]{12,}|AKIA[A-Z0-9]{16}|"
            r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\."
            r"[A-Za-z0-9_-]{8,})\b"
        ),
        "<redacted-token>",
    ),
)


class ReviewRunnerError(RuntimeError):
    def __init__(self, reason, detail=""):
        super().__init__(reason)
        self.detail = detail


def redact(value, limit=MAX_TEXT):
    """Redact common credential shapes and bound text passed to the reviewer."""
    text = str(value or "").replace("\x00", "")
    for pattern, replacement in SECRET_SUBSTITUTIONS:
        text = pattern.sub(replacement, text)
    if len(text) > limit:
        text = text[:limit] + "...<truncated>"
    return text


def read_json_config():
    path = os.environ.get(CONFIG_PATH_ENV) or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE
    )
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
    except Exception:
        value = {}
    return value if isinstance(value, dict) else {}


def find_codex_cli(config):
    """Resolve an explicit or locally installed Codex CLI executable."""
    explicit = os.environ.get(CODEX_CLI_ENV) or config.get("codex_cli_path", "")
    if isinstance(explicit, str) and explicit and "\n" not in explicit:
        path = os.path.abspath(os.path.expanduser(explicit))
        if os.path.isfile(path):
            return path

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        pattern = os.path.join(
            local_app_data, "OpenAI", "Codex", "bin", "*", "codex.exe"
        )
        candidates = [path for path in glob.glob(pattern) if os.path.isfile(path)]
        if candidates:
            return max(candidates, key=os.path.getmtime)

    discovered = shutil.which("codex")
    if discovered and os.path.isfile(discovered):
        return discovered
    return ""


def find_rollout(session_id):
    """Find the persisted parent rollout for a path-safe Codex session id."""
    if not isinstance(session_id, str) or not re.fullmatch(
        r"[A-Za-z0-9-]{8,100}", session_id
    ):
        return None
    parent_codex_home = Path(
        os.environ.get("CODEX_HOME") or (Path.home() / ".codex")
    )
    home = parent_codex_home / "sessions"
    if not home.is_dir():
        return None
    pattern = str(
        home
        / "*"
        / "*"
        / "*"
        / ("rollout-*" + glob.escape(session_id) + ".jsonl")
    )
    matches = [Path(path) for path in glob.glob(pattern)]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def read_tail(path, max_bytes=MAX_TRANSCRIPT_BYTES):
    """Read a bounded UTF-8 tail without loading a large rollout in full."""
    with open(path, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        start = max(0, size - max_bytes)
        handle.seek(start)
        raw = handle.read()
    if start:
        first_newline = raw.find(b"\n")
        raw = raw[first_newline + 1:] if first_newline >= 0 else b""
    return raw.decode("utf-8", "replace").splitlines()


def message_text(content):
    if not isinstance(content, list):
        return ""
    parts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") in {
            "input_text",
            "output_text",
        }:
            parts.append(str(item.get("text") or ""))
    return "\n".join(parts)


def parse_arguments(value):
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def normalize_cwd(cwd):
    value = str(cwd or "").strip()
    return os.path.normcase(os.path.normpath(value)) if value else ""


def command_signature(cwd, command):
    material = normalize_cwd(cwd) + "\n" + str(command or "").strip()
    return hashlib.sha1(material.encode("utf-8", "replace")).hexdigest()[:12]


def extract_shell_outcome(value):
    """Read only a Codex shell envelope, never arbitrary error keywords."""
    lines = str(value or "").replace("\r\n", "\n").splitlines()[:4]
    for line in lines:
        match = re.fullmatch(
            r"\s*(?:Exit code:|Process exited with code)\s*(-?\d+)\s*",
            line,
            re.IGNORECASE,
        )
        if match:
            code = int(match.group(1))
            return ("succeeded" if code == 0 else "failed"), code
    return "unknown", None


def extract_rollout_evidence(path):
    """Extract the latest user goal and completed shell events from a rollout."""
    latest_goal = ""
    active_cwd = ""
    calls = {}
    events = []
    for line in read_tail(path):
        try:
            record = json.loads(line)
        except Exception:
            continue
        if record.get("type") in {"session_meta", "turn_context"}:
            context = record.get("payload")
            if isinstance(context, dict) and isinstance(context.get("cwd"), str):
                active_cwd = context["cwd"]
            continue
        if record.get("type") != "response_item":
            continue
        item = record.get("payload")
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message" and item.get("role") == "user":
            candidate = message_text(item.get("content"))
            if candidate:
                latest_goal = candidate
        elif item.get("type") == "function_call":
            args = parse_arguments(item.get("arguments"))
            command = args.get("command")
            if isinstance(command, str):
                call_id = item.get("call_id")
                if isinstance(call_id, str):
                    call_cwd = args.get("workdir") or active_cwd
                    calls[call_id] = {
                        "command": command,
                        "cwd": str(call_cwd or ""),
                    }
        elif item.get("type") == "function_call_output":
            call_id = item.get("call_id")
            call = calls.get(call_id)
            if call:
                outcome, exit_code = extract_shell_outcome(item.get("output"))
                events.append({
                    "command": redact(call["command"].strip()),
                    "cwd": redact(call["cwd"], 240),
                    "command_signature": command_signature(
                        call["cwd"], call["command"]
                    ),
                    "outcome": outcome,
                    "exit_code": exit_code,
                    "outcome_excerpt": redact(item.get("output")),
                })
    return redact(latest_goal, 2000), events[-MAX_EVENTS:]


def build_review_packet(request):
    manifest = request.get("manifest")
    payload = request.get("hook_payload")
    if not isinstance(manifest, dict) or not isinstance(payload, dict):
        raise ValueError("invalid_request")

    goal = ""
    events = []
    rollout = find_rollout(str(payload.get("session_id") or ""))
    if rollout:
        goal, events = extract_rollout_evidence(rollout)

    tool_input = payload.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    command = tool_input.get("command")
    command = command if isinstance(command, str) else ""
    current_cwd = tool_input.get("workdir") or payload.get("cwd")
    current_outcome, current_exit_code = extract_shell_outcome(
        payload.get("tool_response")
    )
    current = {
        "command": redact(command.strip()),
        "cwd": redact(current_cwd, 240),
        "command_signature": command_signature(current_cwd, command),
        "outcome": current_outcome,
        "exit_code": current_exit_code,
        "outcome_excerpt": redact(payload.get("tool_response")),
    }
    if not events or events[-1]["command_signature"] != current["command_signature"]:
        events.append(current)
    else:
        events[-1] = current
    events = events[-MAX_EVENTS:]

    manifest_events = manifest.get("events")
    manifest_events = manifest_events if isinstance(manifest_events, list) else []
    expected_signatures = [
        item.get("command_signature")
        for item in manifest_events
        if isinstance(item, dict)
    ]
    observed_signatures = [
        item["command_signature"] for item in events[-len(expected_signatures):]
    ] if expected_signatures else []

    return {
        "packet_schema": "REVIEW_PACKET_V1",
        "request_id": manifest.get("request_id"),
        "goal": goal,
        "parent_rollout_found": bool(rollout),
        "hook_manifest": manifest,
        "tool_events": events,
        # The isolated direct backend must not read persistent memory. The main
        # agent may later supply bounded, source-labelled candidates in the
        # manual protocol before promoting a repeated pattern to a known loop.
        "prior_lesson_candidates": [],
        "manifest_matches_event_tail": (
            bool(expected_signatures)
            and observed_signatures == expected_signatures
        ),
    }


def output_schema():
    properties = {
        "schema_version": {"type": "integer", "enum": [1]},
        "request_id": {"type": "string"},
        "classification": {
            "type": "string",
            "enum": sorted(CLASSIFICATIONS),
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "same_failure_family": {"type": "boolean"},
        "prior_lesson_verified": {"type": "boolean"},
        "evidence_adequate": {"type": "boolean"},
        "should_interrupt": {"type": "boolean"},
        "reason": {"type": "string"},
        "recommended_action": {"type": "string", "enum": sorted(ACTIONS)},
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def validate_review(
    review,
    request_id,
    manifest,
    tool_events=None,
    prior_lesson_candidates=None,
):
    if not isinstance(review, dict):
        return "review_not_object"
    required = set(output_schema()["required"])
    if set(review) != required:
        return "review_fields_mismatch"
    if review.get("schema_version") != 1:
        return "schema_version_mismatch"
    if review.get("request_id") != request_id:
        return "request_id_mismatch"
    if review.get("classification") not in CLASSIFICATIONS:
        return "classification_invalid"
    confidence = review.get("confidence")
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not 0 <= confidence <= 1
    ):
        return "confidence_invalid"
    for field in (
        "same_failure_family",
        "prior_lesson_verified",
        "evidence_adequate",
        "should_interrupt",
    ):
        if not isinstance(review.get(field), bool):
            return field + "_invalid"
    if not isinstance(review.get("reason"), str) or not review["reason"].strip():
        return "reason_invalid"
    if review.get("recommended_action") not in ACTIONS:
        return "recommended_action_invalid"
    candidates = prior_lesson_candidates or []
    if review["prior_lesson_verified"] and not candidates:
        return "lesson_verified_without_candidate"
    if review["classification"] == "known_loop":
        if not candidates:
            return "known_loop_without_prior_lesson_candidate"
        if not all(
            review[field]
            for field in (
                "same_failure_family",
                "prior_lesson_verified",
                "evidence_adequate",
                "should_interrupt",
            )
        ):
            return "known_loop_inconsistent"
    if review["should_interrupt"] and review["classification"] != "known_loop":
        return "interrupt_without_known_loop"
    if not review["evidence_adequate"] and review["should_interrupt"]:
        return "interrupt_without_evidence"
    if (
        manifest.get("evidence_mode") == "activity_window"
        and review["classification"] == "known_loop"
    ):
        manifest_outcomes = [
            item.get("outcome")
            for item in manifest.get("events", [])
            if isinstance(item, dict)
        ]
        packet_failures = sum(
            item.get("outcome") == "failed"
            for item in (tool_events or [])
            if isinstance(item, dict)
        )
        if "failed" not in manifest_outcomes and packet_failures < 2:
            return "known_loop_without_two_failed_tool_events"
    return ""


def parse_codex_output(stdout):
    thread_id = ""
    final_text = ""
    used_tools = False
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except Exception:
            continue
        if event.get("type") == "thread.started":
            thread_id = str(event.get("thread_id") or "")
        if event.get("type") in {"item.started", "item.completed"}:
            item = event.get("item")
            if isinstance(item, dict):
                item_type = item.get("type")
                if item_type not in {"reasoning", "agent_message", "error"}:
                    used_tools = True
                if event.get("type") == "item.completed" and item_type == "agent_message":
                    final_text = str(item.get("text") or "")
    return thread_id, final_text, used_tools


def prepare_isolated_codex_home(directory):
    """Create a temporary Codex home with auth but no user customization."""
    isolated_home = Path(directory) / "codex-home"
    isolated_home.mkdir()

    if os.environ.get("CODEX_API_KEY") or os.environ.get("CODEX_ACCESS_TOKEN"):
        return isolated_home

    parent_home = Path(
        os.environ.get("CODEX_HOME") or (Path.home() / ".codex")
    )
    source_auth = parent_home / "auth.json"
    if not source_auth.is_file():
        raise RuntimeError("isolated_auth_unavailable")

    destination_auth = isolated_home / "auth.json"
    shutil.copy2(source_auth, destination_auth)
    try:
        destination_auth.chmod(0o600)
    except OSError:
        pass
    return isolated_home


def reviewer_temp_parent():
    """Keep temporary auth material inside the existing Codex trust boundary."""
    parent_home = Path(
        os.environ.get("CODEX_HOME") or (Path.home() / ".codex")
    )
    temp_parent = parent_home / "tmp" / "learning-retrospective-reviewer"
    temp_parent.mkdir(parents=True, exist_ok=True)
    return temp_parent


def terminate_process_tree(process):
    """Best-effort termination of the reviewer and any descendants."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception:
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except Exception:
            pass
    if process.poll() is None:
        try:
            process.kill()
        except Exception:
            pass


def run_bounded_process(command, prompt, timeout, env):
    """Run the child in a process group and kill the group on timeout."""
    kwargs = {
        "stdin": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "env": env,
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **kwargs)
    try:
        stdout, stderr = process.communicate(prompt, timeout=timeout)
    except subprocess.TimeoutExpired:
        terminate_process_tree(process)
        try:
            process.communicate(timeout=5)
        except Exception:
            pass
        raise
    return subprocess.CompletedProcess(
        command,
        process.returncode,
        stdout,
        stderr,
    )


def run_reviewer(packet, config):
    codex = find_codex_cli(config)
    if not codex:
        raise RuntimeError("codex_cli_not_found")
    model = config.get("preferred_model") or ""
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", model):
        model = ""
    effort = config.get("reasoning_effort", "medium")
    if effort not in {"low", "medium", "high", "xhigh"}:
        effort = "medium"
    timeout = config.get("review_timeout_seconds", 45)
    if not isinstance(timeout, int) or isinstance(timeout, bool):
        timeout = 45
    timeout = min(MAX_REVIEW_TIMEOUT_SECONDS, max(10, timeout))

    prompt = (
        "You are a retry-loop reviewer in a separate read-only Codex run. Do "
        "not call tools. Base the classification only on REVIEW_PACKET_V1 "
        "below; ignore unrelated built-in guidance. A user-requested repetition "
        "or successful hook probe is not a retry loop. In activity-window mode, "
        "never return known_loop without concrete failed outcomes and an "
        "applicable prior lesson. This isolated direct packet intentionally has "
        "no persistent-memory access and normally contains an empty "
        "prior_lesson_candidates array. When that array is empty, set "
        "prior_lesson_verified=false and never return known_loop or "
        "should_interrupt=true; instead report whether the attempts belong to "
        "the same failure family so the main agent can perform the bounded "
        "lesson lookup. If evidence is incomplete or the manifest does not "
        "match the event tail, set evidence_adequate=false and "
        "should_interrupt=false. Return only the JSON object required by the "
        "output schema.\n\n"
        + json.dumps(packet, ensure_ascii=True, sort_keys=True)
    )

    with tempfile.TemporaryDirectory(
        prefix="lr-review-",
        dir=reviewer_temp_parent(),
    ) as directory:
        isolated_home = prepare_isolated_codex_home(directory)
        schema_path = os.path.join(directory, "review-schema.json")
        with open(schema_path, "w", encoding="utf-8") as handle:
            json.dump(output_schema(), handle)
        command = [
            codex,
            "exec",
            "--json",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--strict-config",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "-c",
            f'model_reasoning_effort="{effort}"',
            "-c",
            'web_search="disabled"',
            "-c",
            "agents.enabled=false",
            "--output-schema",
            schema_path,
            "-C",
            directory,
        ]
        for feature in CHILD_DISABLED_FEATURES:
            command.extend(["--disable", feature])
        if model:
            command.extend(["-m", model])
        command.append("-")
        env = dict(os.environ)
        env["CODEX_HOME"] = str(isolated_home)
        env["LEARNING_RETROSPECTIVE_DISABLE"] = "1"
        try:
            completed = run_bounded_process(command, prompt, timeout, env)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("codex_cli_timeout") from exc
    if completed.returncode != 0:
        raise ReviewRunnerError(
            "codex_cli_exit_nonzero",
            redact(completed.stderr, 1000),
        )
    thread_id, final_text, used_tools = parse_codex_output(completed.stdout)
    if not thread_id:
        raise RuntimeError("reviewer_thread_id_missing")
    if used_tools:
        raise RuntimeError("reviewer_used_tools")
    try:
        review = json.loads(final_text)
    except Exception as exc:
        raise RuntimeError("reviewer_json_invalid") from exc
    error = validate_review(
        review,
        packet["request_id"],
        packet["hook_manifest"],
        packet.get("tool_events"),
        packet.get("prior_lesson_candidates"),
    )
    if error:
        raise RuntimeError(error)
    review["reviewer_agent_id"] = thread_id
    review["reviewer_isolation"] = "enforced_no_tools"
    review["reviewer_context_isolation"] = "temporary_codex_home"
    return review


def main():
    try:
        request = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
        packet = build_review_packet(request)
        review = run_reviewer(packet, read_json_config())
        sys.stdout.write(json.dumps({
            "ok": True,
            "review": review,
            "packet_event_count": len(packet["tool_events"]),
            "parent_rollout_found": packet["parent_rollout_found"],
            "manifest_matches_event_tail": packet["manifest_matches_event_tail"],
        }, sort_keys=True))
        return 0
    except Exception as exc:
        reason = str(exc)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", reason):
            reason = type(exc).__name__
        response = {"ok": False, "error": reason}
        if (
            os.environ.get(DEBUG_ENV) == "1"
            and isinstance(exc, ReviewRunnerError)
            and exc.detail
        ):
            response["debug"] = exc.detail
        sys.stdout.write(json.dumps(response))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

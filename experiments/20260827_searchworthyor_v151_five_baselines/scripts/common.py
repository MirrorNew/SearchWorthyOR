from __future__ import annotations

import http.client
import ipaddress
import json
import os
import re
import secrets
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parent
EXPERIMENT_ROOT = SCRIPT_ROOT.parent
WORKFLOW_ROOT = EXPERIMENT_ROOT.parents[1]
CONFIG_PATH = EXPERIMENT_ROOT / "EXPERIMENT_CONFIG.json"
_BOOTSTRAP_CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _resolve_config_path(raw: Any) -> Path:
    path = Path(str(raw)).expanduser()
    return path.resolve() if path.is_absolute() else (EXPERIMENT_ROOT / path).resolve()


DATASET_ROOT = _resolve_config_path(_BOOTSTRAP_CONFIG["dataset_root"])
PUBLIC_INPUT_PATH = _resolve_config_path(_BOOTSTRAP_CONFIG["public_input_file"])
SMOKE_SUMMARY_PATH = EXPERIMENT_ROOT / "runs" / "smoke" / "validation_summary.json"
PREFLIGHT_SUMMARY_PATH = EXPERIMENT_ROOT / "preflight" / "summary.json"
GLOBAL_STOP_PATH = EXPERIMENT_ROOT / "runs" / "GLOBAL_STOP.json"
DEFAULT_ENV_FILE = _resolve_config_path(_BOOTSTRAP_CONFIG["credential_file"])


def _bootstrap_base_url(path: Path) -> str:
    if path.is_file():
        for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "OPENOR_BASE_URL":
                value = value.strip()
                if value[:1] == value[-1:] and value[:1] in {"'", '"'}:
                    value = value[1:-1]
                return value.rstrip("/")
        raise RuntimeError("OPENOR_BASE_URL is absent from the experiment-local .env.local")
    provider = _BOOTSTRAP_CONFIG.get("provider")
    configured = provider.get("base_url") if isinstance(provider, dict) else None
    if configured == "https://api.shubiaobiao.cn/v1":
        return configured
    raise RuntimeError("missing .env.local and no locked Shubiaobiao base URL in config")


BASE_URL = _bootstrap_base_url(DEFAULT_ENV_FILE)
_MODEL_CONFIG = _BOOTSTRAP_CONFIG.get("model")
if not isinstance(_MODEL_CONFIG, dict):
    raise RuntimeError("EXPERIMENT_CONFIG.json model must be an object")
MODEL = str(_MODEL_CONFIG.get("name"))
REASONING_EFFORT = str(_MODEL_CONFIG.get("reasoning_effort"))
TEMPERATURE = _MODEL_CONFIG.get("temperature")
if (MODEL, REASONING_EFFORT, TEMPERATURE) != ("gpt-5.6-luna", "xhigh", 1):
    raise RuntimeError("EXPERIMENT_CONFIG.json does not contain the locked Luna/xhigh/T1 tuple")
_PROVIDER_CONFIG = _BOOTSTRAP_CONFIG.get("provider")
if not isinstance(_PROVIDER_CONFIG, dict):
    raise RuntimeError("EXPERIMENT_CONFIG.json provider must be an object")
if str(_PROVIDER_CONFIG.get("base_url", "")).rstrip("/") != BASE_URL:
    raise RuntimeError("provider base_url does not match experiment-local .env.local")
CHAT_ENDPOINT = str(_PROVIDER_CONFIG.get("chat_endpoint"))
RESPONSES_ENDPOINT = str(_PROVIDER_CONFIG.get("responses_endpoint"))
if (CHAT_ENDPOINT, RESPONSES_ENDPOINT) != ("/chat/completions", "/responses"):
    raise RuntimeError("provider endpoints changed")
COMPAT_TOP_P = 0.8
RETRYABLE_HTTP_CODES = {408, 429, 500, 502, 503, 504}
MAX_RETRY_WAIT_SECONDS = 30.0
ALLOWED_PAYLOAD_FIELDS = {"model", "messages", "reasoning_effort", "temperature", "top_p"}
TERMINAL_STATUSES = {
    "OK",
    "OUTPUT_CONTRACT_FAILURE",
    "PARSE_FAILURE",
    "RETRIEVAL_FAILURE",
    "PROVIDER_FAILURE",
    "RUNNER_FAILURE",
    "CONFIGURATION_VIOLATION",
}

_LOG_LOCK = threading.Lock()
_API_ORIGIN = urllib.parse.urlsplit(BASE_URL)


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


_NO_REDIRECT_OPENER = urllib.request.build_opener(_NoRedirectHandler())


class StrictAPIRequestError(RuntimeError):
    def __init__(
        self,
        message: str,
        upstream_attempts: int,
        status: int | None = None,
        failure_type: str | None = None,
    ):
        super().__init__(message)
        self.upstream_attempts = upstream_attempts
        self.status = status
        self.failure_type = failure_type


class ConfigurationViolation(RuntimeError):
    pass


class GlobalStopError(RuntimeError):
    pass


def _retry_after_seconds(value: str | None) -> float:
    if not value:
        return 5.0
    try:
        return max(0.0, float(value.strip()))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return max(0.0, (parsed - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return 5.0


def classify_responses_search_error(exc: BaseException, status: int | None = None) -> str:
    if status == 403:
        return "SEARCH_HTTP_403"
    if status == 429:
        return "SEARCH_HTTP_429"
    if isinstance(status, int) and status >= 500:
        return "SEARCH_HTTP_5XX"
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    chain = " ".join(
        str(item)
        for item in (exc, reason, getattr(exc, "__cause__", None), getattr(reason, "__cause__", None))
        if item is not None
    ).lower()
    if isinstance(reason, ssl.SSLError) or "ssl" in chain or "tls" in chain:
        return "SEARCH_TLS_FAILURE"
    if isinstance(reason, socket.gaierror) or "gaierror" in chain or "getaddrinfo failed" in chain:
        return "SEARCH_DNS_FAILURE"
    if isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in chain:
        return "SEARCH_TIMEOUT"
    if isinstance(reason, (http.client.RemoteDisconnected, ConnectionResetError, ConnectionAbortedError)):
        return "SEARCH_REMOTE_DISCONNECT"
    if isinstance(exc, (json.JSONDecodeError, ValueError)):
        return "SEARCH_PARSE_FAILURE"
    return "SEARCH_BACKEND_FAILURE" if isinstance(exc, RuntimeError) else "SEARCH_REMOTE_DISCONNECT"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_no}: expected an object")
        rows.append(row)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    os.replace(temporary, path)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
    os.replace(temporary, path)


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOG_LOCK:
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")


def index_unique(rows: list[dict[str, Any]], key: str = "id") -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        identifier = str(row.get(key) or "")
        if not identifier or identifier in result:
            raise ValueError(f"missing or duplicate {key}: {identifier!r}")
        result[identifier] = row
    return result


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.is_file():
        raise FileNotFoundError(CONFIG_PATH)
    config = read_json(CONFIG_PATH)
    if config.get("schema_version") != "searchworthyor.v151.five_baselines.v1":
        raise RuntimeError("experiment schema_version changed")
    if _resolve_config_path(config.get("experiment_root")) != EXPERIMENT_ROOT.resolve():
        raise RuntimeError("experiment_root changed")
    if _resolve_config_path(config.get("dataset_root")) != DATASET_ROOT.resolve():
        raise RuntimeError("dataset_root changed")
    if _resolve_config_path(config.get("credential_file")) != DEFAULT_ENV_FILE.resolve():
        raise RuntimeError("credential_file changed")
    if _resolve_config_path(config.get("public_input_file")) != PUBLIC_INPUT_PATH.resolve():
        raise RuntimeError("public_input_file changed")
    if config.get("model") != {"name": MODEL, "reasoning_effort": REASONING_EFFORT, "temperature": TEMPERATURE}:
        raise RuntimeError("locked model tuple changed")
    inputs = config.get("inputs")
    if (
        not isinstance(inputs, dict)
        or inputs.get("case_suffixes") != ["C1", "C2"]
        or inputs.get("case_count") != 240
        or inputs.get("source_task_count") != 120
    ):
        raise RuntimeError("fixed V1.5.1 paired input contract changed")
    if inputs.get("model_fields") != ["id", "case_id", "prompt_zh"] or inputs.get("private_gold_visible_to_runner") is not False:
        raise RuntimeError("runner input or Gold visibility contract changed")
    methods = config.get("methods")
    expected_methods = {
        "Direct-v2 Base-Solve Gated Search",
        "CoE",
        "OptiMUS",
        "optiminer-training-free",
        "Search-First Gated Raw-NL",
    }
    if not isinstance(methods, dict) or set(methods) != expected_methods:
        raise RuntimeError("the fixed five-method contract changed")
    phases = config.get("phases")
    if (
        not isinstance(phases, dict)
        or phases.get("smoke", {}).get("instances") != 10
        or phases.get("formal", {}).get("instances") != 1200
    ):
        raise RuntimeError("Smoke/Formal instance contract changed")
    shared_search_config(config)
    return config


def shared_search_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    value = config if config is not None else read_json(CONFIG_PATH)
    profiles = value.get("search_profiles")
    profile = profiles.get("shubiaobiao_hosted_search_shared") if isinstance(profiles, dict) else None
    expected = {
        "endpoint": RESPONSES_ENDPOINT,
        "tool": "web_search",
        "search_context_size": "low",
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "temperature": TEMPERATURE,
        "max_query_chars": 320,
        "max_queries_per_case": 3,
        "tool_calls_per_planned_query": 1,
        "max_exposed_results_per_query": 6,
        "max_opened_pages_per_query": 3,
        "max_page_attempts_per_query": 6,
        "max_successful_pages_per_case": 9,
        "max_page_attempts_per_case": 18,
        "require_relevance": True,
        "require_operator_compliance": True,
        "save_planned_query": True,
        "save_executed_query": True,
        "save_query_rewrite": True,
        "save_raw_results": True,
        "save_opened_pages": True,
        "save_evidence_text": True,
        "backend_fallback": False,
    }
    if profile != expected:
        raise RuntimeError("shubiaobiao_hosted_search_shared changed")
    methods = value.get("methods")
    if (
        not isinstance(methods, dict)
        or methods.get("Direct-v2 Base-Solve Gated Search", {}).get("search_profile")
        != "shubiaobiao_hosted_search_shared"
        or methods.get("Search-First Gated Raw-NL", {}).get("search_profile")
        != "shubiaobiao_hosted_search_shared"
    ):
        raise RuntimeError("Direct/Chain2 no longer share one search profile")
    return profile


def validate_formal_gate() -> dict[str, Any]:
    load_config()
    if not PREFLIGHT_SUMMARY_PATH.is_file() or read_json(PREFLIGHT_SUMMARY_PATH).get("status") != "PASS":
        raise RuntimeError("formal experiment requires a passing concurrent preflight")
    if not SMOKE_SUMMARY_PATH.is_file():
        raise RuntimeError("formal experiment requires runs/smoke/validation_summary.json")
    gate = read_json(SMOKE_SUMMARY_PATH)
    if gate.get("status") != "PASS" or gate.get("terminal_instances") != 10:
        raise RuntimeError("smoke gate has not passed")
    for key in (
        "configuration_violations",
        "gold_leakage",
        "api_key_leakage",
        "identity_mismatch",
        "duplicate_terminal_outputs",
        "harness_runner_failures",
        "raw_nl_binding_failures",
        "direct_base_stage_missing",
        "direct_base_failure_unaccounted",
    ):
        if gate.get(key) != 0:
            raise RuntimeError(f"smoke gate failed: {key}={gate.get(key)!r}")
    if not isinstance(gate.get("direct_base_solve_completed"), int) or gate["direct_base_solve_completed"] < 1:
        raise RuntimeError("smoke gate did not observe a completed Direct Base solve")
    if not isinstance(gate.get("raw_nl_nonempty_instances"), int) or gate["raw_nl_nonempty_instances"] < 1:
        raise RuntimeError("smoke gate did not observe Raw-NL evidence binding")
    return gate


def validate_direct_formal_gate() -> dict[str, Any]:
    return validate_formal_gate()


def public_cases() -> dict[str, dict[str, Any]]:
    rows = read_jsonl(PUBLIC_INPUT_PATH)
    indexed = index_unique(rows, "case_id")
    expected_ids = {
        f"SWOR-R{index:03d}-C{case}"
        for index in range(1, 121)
        for case in (1, 2)
    }
    if set(indexed) != expected_ids:
        raise ValueError("selected public cases must contain all 240 paired V1.5.1 case IDs exactly once")
    for identifier, row in indexed.items():
        if set(row) != {"id", "case_id", "prompt_zh"}:
            raise ValueError(f"{identifier}: unexpected public input fields")
    return indexed


def output_schema_for(public: dict[str, Any]) -> dict[str, Any]:
    if set(public) != {"id", "case_id", "prompt_zh"}:
        raise ValueError("runner input must contain exactly id/case_id/prompt_zh")
    marker = "公开 output_schema："
    prompt = str(public["prompt_zh"])
    if prompt.count(marker) != 1:
        raise ValueError("prompt_zh must contain exactly one public output_schema marker")
    raw_schema = prompt.split(marker, 1)[1].strip()
    try:
        schema = json.loads(raw_schema)
    except json.JSONDecodeError as exc:
        raise ValueError("prompt_zh public output_schema is invalid JSON") from exc
    if not isinstance(schema, dict):
        raise ValueError("public output schema is absent")
    if not isinstance(schema.get("actions"), list) or not isinstance(schema.get("objective"), dict):
        raise ValueError("public output schema has an invalid contract")
    return schema


def smoke_ids() -> list[str]:
    values = load_config().get("phases", {}).get("smoke", {}).get("case_ids")
    if not isinstance(values, list) or len(values) != 2 or len(set(values)) != 2:
        raise ValueError("configuration must contain one paired C1/C2 Smoke task")
    expected = ["SWOR-R001-C1", "SWOR-R001-C2"]
    if values != expected:
        raise ValueError("paired Smoke case IDs changed")
    return values


def selected_ids(phase: str, explicit: str = "") -> list[str]:
    if explicit:
        values = [item.strip() for item in explicit.split(",") if item.strip()]
    elif phase == "smoke":
        values = smoke_ids()
    else:
        values = [f"SWOR-R{index:03d}-C{case}" for index in range(1, 121) for case in (1, 2)]
    if len(values) != len(set(values)) or any(not re.fullmatch(r"SWOR-R\d{3}-C[12]", value) for value in values):
        raise ValueError("case IDs must be unique SWOR-Rnnn-C1/C2 values")
    return values


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if value[:1] == value[-1:] and value[:1] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def load_api_key(env_file: Path = DEFAULT_ENV_FILE) -> str:
    if env_file.resolve() != DEFAULT_ENV_FILE.resolve():
        raise GlobalStopError("only the experiment-local .env.local is allowed")
    values = _read_env_file(env_file)
    if set(values) != {"OPENOR_BASE_URL", "OPENOR_API_KEY"}:
        raise GlobalStopError("experiment-local .env.local must contain only Base URL and API key")
    if values.get("OPENOR_BASE_URL", "").rstrip("/") != BASE_URL:
        raise GlobalStopError("OPENOR_BASE_URL is not the required Shubiaobiao /v1 endpoint")
    value = values.get("OPENOR_API_KEY")
    if not value:
        raise GlobalStopError("OPENOR_API_KEY is absent from the fixed .env.local")
    return value


def count_api_key_leaks(root: Path) -> int:
    secret = load_api_key().encode("utf-8")
    if not secret or not root.exists():
        return 0
    leaks = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        found = False
        tail = b""
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                data = tail + chunk
                if secret in data:
                    found = True
                    break
                overlap = len(secret) - 1
                tail = data[-overlap:] if overlap else b""
        leaks += int(found)
    return leaks


def record_global_stop(reason: str, detail: str) -> None:
    if not GLOBAL_STOP_PATH.exists():
        write_json(GLOBAL_STOP_PATH, {"status": "STOPPED", "reason": reason, "detail": detail[:1200]})


def check_global_stop() -> None:
    if GLOBAL_STOP_PATH.is_file():
        payload = read_json(GLOBAL_STOP_PATH)
        raise GlobalStopError(f"global stop is active: {payload.get('reason')}")


def _validate_actual_configuration(parsed: dict[str, Any]) -> str:
    actual_model = parsed.get("model")
    if actual_model != MODEL:
        detail = f"actual model mismatch: expected {MODEL}, got {actual_model!r}"
        record_global_stop("CONFIGURATION_VIOLATION", detail)
        raise ConfigurationViolation(detail)
    actual_reasoning = parsed.get("reasoning")
    actual_effort = actual_reasoning.get("effort") if isinstance(actual_reasoning, dict) else None
    if actual_effort is not None and actual_effort != REASONING_EFFORT:
        detail = f"actual reasoning_effort mismatch: expected {REASONING_EFFORT}, got {actual_effort!r}"
        record_global_stop("CONFIGURATION_VIOLATION", detail)
        raise ConfigurationViolation(detail)
    actual_temperature = parsed.get("temperature")
    if actual_temperature is not None and actual_temperature != TEMPERATURE:
        detail = f"actual temperature mismatch: expected {TEMPERATURE}, got {actual_temperature!r}"
        record_global_stop("CONFIGURATION_VIOLATION", detail)
        raise ConfigurationViolation(detail)
    return str(actual_model)


def _fatal_provider_error(status: int | None, detail: str) -> bool:
    lowered = detail.lower()
    return status in {401, 402, 403} or any(marker in lowered for marker in ("insufficient balance", "insufficient credit", "余额不足", "authentication"))


def safe_usage(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    names = ("prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens", "reasoning_tokens")
    return {name: item for name in names if isinstance((item := value.get(name)), int) and not isinstance(item, bool) and item >= 0}


def validate_payload(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("request payload must be an object")
    extras = set(payload) - ALLOWED_PAYLOAD_FIELDS
    if extras:
        raise ValueError(f"request fields are not allowed: {sorted(extras)}")
    required = {"model": MODEL, "reasoning_effort": REASONING_EFFORT, "temperature": TEMPERATURE}
    for key, expected in required.items():
        if payload.get(key) != expected:
            raise ValueError(f"request {key} must be {expected!r}")
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty list")
    for message in messages:
        if not isinstance(message, dict) or set(message) != {"role", "content"}:
            raise ValueError("each message must contain exactly role and content")
        if message["role"] not in {"system", "user", "assistant"} or not isinstance(message["content"], str):
            raise ValueError("message role/content are invalid")
    if "top_p" in payload and payload["top_p"] != COMPAT_TOP_P:
        raise ValueError(f"top_p must be {COMPAT_TOP_P}")


def adapt_native_proxy_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Omit a provider-unsupported native option while preserving the frozen trio."""
    validate_payload(payload)
    if "top_p" not in payload:
        return dict(payload), None
    adapted = dict(payload)
    original = adapted.pop("top_p")
    validate_payload(adapted)
    return adapted, {
        "field": "top_p",
        "native_value": original,
        "provider_action": "omitted",
        "reason": "gpt-5.6-luna rejects the top_p field",
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "temperature": TEMPERATURE,
    }


@dataclass
class StrictAPIClient:
    api_key: str = field(repr=False)
    artifact_dir: Path
    method: str
    task_id: str
    timeout_seconds: int = 650
    call_counter: int = 0

    @classmethod
    def from_environment(
        cls,
        artifact_dir: Path,
        method: str,
        task_id: str,
        env_file: Path = DEFAULT_ENV_FILE,
        timeout_seconds: int = 650,
    ) -> "StrictAPIClient":
        return cls(load_api_key(env_file), artifact_dir, method, task_id, timeout_seconds)

    @property
    def log_path(self) -> Path:
        return self.artifact_dir / "api_calls.jsonl"

    def complete(self, messages: list[dict[str, str]], purpose: str) -> dict[str, Any]:
        return self.complete_payload(
            {
                "model": MODEL,
                "messages": messages,
                "reasoning_effort": REASONING_EFFORT,
                "temperature": TEMPERATURE,
            },
            purpose,
        )

    def complete_payload(self, payload: dict[str, Any], purpose: str = "native_agent") -> dict[str, Any]:
        check_global_stop()
        validate_payload(payload)
        self.call_counter += 1
        call_id = self.call_counter
        safe_purpose = re.sub(r"[^A-Za-z0-9_.-]+", "_", purpose)[:80] or "call"
        call_dir = self.artifact_dir / "llm_calls"
        request_path = call_dir / f"{call_id:04d}_{safe_purpose}_request.json"
        response_path = call_dir / f"{call_id:04d}_{safe_purpose}_response.json"
        write_json(request_path, payload)
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        started = time.perf_counter()
        last_error: Exception | None = None
        last_status: int | None = None
        retry_events: list[dict[str, Any]] = []
        for attempt in (1, 2):
            retry_wait_seconds = 5.0
            try:
                request = urllib.request.Request(
                    f"{BASE_URL}{CHAT_ENDPOINT}",
                    data=data,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json; charset=utf-8"},
                    method="POST",
                )
                with _NO_REDIRECT_OPENER.open(request, timeout=self.timeout_seconds) as response:
                    last_status = response.status
                    final = urllib.parse.urlsplit(response.geturl())
                    if (final.scheme, final.hostname, final.port or 443) != (_API_ORIGIN.scheme, _API_ORIGIN.hostname, _API_ORIGIN.port or 443):
                        raise RuntimeError("API response origin mismatch")
                    parsed = json.loads(response.read().decode("utf-8"))
                if not isinstance(parsed, dict):
                    raise ValueError("API response must be an object")
                actual_model = _validate_actual_configuration(parsed)
                choices = parsed.get("choices") or []
                message = choices[0].get("message") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
                content = message.get("content") if isinstance(message, dict) else None
                if not isinstance(content, str) or not content.strip():
                    raise RuntimeError("response contains no assistant content")
                write_json(response_path, parsed)
                result = {
                    "content": content,
                    "raw": parsed,
                    "actual_model": actual_model,
                    "usage": safe_usage(parsed.get("usage")),
                    "logical_call": call_id,
                    "upstream_attempts": attempt,
                    "wall_seconds": time.perf_counter() - started,
                    "request_path": str(request_path),
                    "response_path": str(response_path),
                    "retry_events": retry_events,
                }
                append_jsonl(
                    self.log_path,
                    {
                        "method": self.method,
                        "task_id": self.task_id,
                        "purpose": purpose,
                        "logical_call": call_id,
                        "requested_model": MODEL,
                        "actual_model": actual_model,
                        "reasoning_effort": REASONING_EFFORT,
                        "temperature": TEMPERATURE,
                        "status": last_status,
                        "upstream_attempts": attempt,
                        "usage": result["usage"],
                        "wall_seconds": result["wall_seconds"],
                        "request_path": str(request_path),
                        "response_path": str(response_path),
                        "retry_events": retry_events,
                    },
                )
                return result
            except urllib.error.HTTPError as exc:
                last_error = exc
                last_status = exc.code
                body = exc.read().decode("utf-8", "replace")[:1200]
                retryable = exc.code in RETRYABLE_HTTP_CODES
                error_detail = body
                if _fatal_provider_error(exc.code, body):
                    record_global_stop("PROVIDER_FATAL", f"HTTP {exc.code}: {body}")
                    raise GlobalStopError(f"fatal provider error: HTTP {exc.code}") from exc
                retry_wait_seconds = _retry_after_seconds(exc.headers.get("Retry-After")) if exc.code == 429 else 5.0
                if exc.code == 429 and retry_wait_seconds > MAX_RETRY_WAIT_SECONDS:
                    retryable = False
            except (urllib.error.URLError, TimeoutError, http.client.RemoteDisconnected) as exc:
                last_error = exc
                last_status = None
                retryable = True
                error_detail = type(exc).__name__
            except (ConfigurationViolation, GlobalStopError):
                raise
            except (json.JSONDecodeError, RuntimeError, ValueError) as exc:
                last_error = exc
                retryable = False
                error_detail = str(exc)[:1200]
            if retryable and attempt == 1:
                retry_events.append(
                    {
                        "attempt": attempt,
                        "status": last_status,
                        "error_type": type(last_error).__name__ if last_error else "UnknownError",
                        "wait_seconds": retry_wait_seconds,
                    }
                )
                time.sleep(retry_wait_seconds)
                continue
            elapsed = time.perf_counter() - started
            append_jsonl(
                self.log_path,
                {
                    "method": self.method,
                    "task_id": self.task_id,
                    "purpose": purpose,
                    "logical_call": call_id,
                    "requested_model": MODEL,
                    "actual_model": None,
                    "reasoning_effort": REASONING_EFFORT,
                    "temperature": TEMPERATURE,
                    "status": last_status if last_status is not None else "transport_error",
                    "upstream_attempts": attempt,
                    "usage": {},
                    "wall_seconds": elapsed,
                    "error_type": type(last_error).__name__ if last_error else "UnknownError",
                    "error_detail": error_detail,
                    "request_path": str(request_path),
                    "response_path": None,
                    "retry_events": retry_events,
                },
            )
            raise StrictAPIRequestError(
                f"strict API request failed after {attempt} upstream attempt(s): {type(last_error).__name__ if last_error else 'UnknownError'}",
                attempt,
                last_status,
            ) from last_error
        raise AssertionError("unreachable")

    def web_search(self, query: str, purpose: str = "web_search") -> dict[str, Any]:
        check_global_stop()
        if not isinstance(query, str) or not query.strip():
            raise ValueError("web search query must be a non-empty string")
        self.call_counter += 1
        call_id = self.call_counter
        safe_purpose = re.sub(r"[^A-Za-z0-9_.-]+", "_", purpose)[:80] or "web_search"
        call_dir = self.artifact_dir / "llm_calls"
        request_path = call_dir / f"{call_id:04d}_{safe_purpose}_request.json"
        response_path = call_dir / f"{call_id:04d}_{safe_purpose}_response.json"
        payload = {
            "model": MODEL,
            "reasoning": {"effort": REASONING_EFFORT},
            "temperature": TEMPERATURE,
            "tools": [{"type": "web_search", "search_context_size": shared_search_config()["search_context_size"]}],
            "tool_choice": "required",
            "include": ["web_search_call.results"],
            "input": (
                "Execute exactly one public web search for the planned query below. "
                "Do not answer from memory and do not perform a second search. "
                "Return a concise response grounded in the search results.\n"
                f"PLANNED_QUERY_JSON={json.dumps(query.strip(), ensure_ascii=False)}"
            ),
        }
        write_json(request_path, payload)
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        started = time.perf_counter()
        last_error: Exception | None = None
        last_status: int | None = None
        retry_events: list[dict[str, Any]] = []
        for attempt in (1, 2):
            retry_wait_seconds = 5.0
            try:
                request = urllib.request.Request(
                    f"{BASE_URL}{RESPONSES_ENDPOINT}",
                    data=data,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json; charset=utf-8"},
                    method="POST",
                )
                with _NO_REDIRECT_OPENER.open(request, timeout=self.timeout_seconds) as response:
                    last_status = response.status
                    final = urllib.parse.urlsplit(response.geturl())
                    if (final.scheme, final.hostname, final.port or 443) != (_API_ORIGIN.scheme, _API_ORIGIN.hostname, _API_ORIGIN.port or 443):
                        raise RuntimeError("API response origin mismatch")
                    parsed = json.loads(response.read().decode("utf-8"))
                if not isinstance(parsed, dict):
                    raise ValueError("Responses API response must be an object")
                actual_model = _validate_actual_configuration(parsed)
                if parsed.get("status") != "completed":
                    raise RuntimeError(f"Responses API status is not completed: {parsed.get('status')!r}")
                calls = [
                    item
                    for item in parsed.get("output", [])
                    if isinstance(item, dict) and item.get("type") == "web_search_call"
                ]
                if len(calls) != 1:
                    raise RuntimeError(f"expected exactly one web_search_call, got {len(calls)}")
                action = calls[0].get("action")
                executed_queries = action.get("queries") if isinstance(action, dict) else None
                executed_query = action.get("query") if isinstance(action, dict) else None
                if (
                    not isinstance(executed_query, str)
                    or not executed_query.strip()
                    or not isinstance(executed_queries, list)
                    or executed_queries != [executed_query]
                ):
                    raise RuntimeError("web_search_call must expose exactly one executed query")
                raw_results = calls[0].get("results")
                if not isinstance(raw_results, list):
                    raise RuntimeError("web_search_call results are absent")
                write_json(response_path, parsed)
                usage = safe_usage(parsed.get("usage"))
                elapsed = time.perf_counter() - started
                result = {
                    "raw": parsed,
                    "actual_model": actual_model,
                    "usage": usage,
                    "logical_call": call_id,
                    "upstream_attempts": attempt,
                    "retry_events": retry_events,
                    "wall_seconds": elapsed,
                    "request_path": str(request_path),
                    "response_path": str(response_path),
                    "planned_query": query.strip(),
                    "executed_query": executed_query.strip(),
                    "raw_results": raw_results,
                    "tool_call_count": 1,
                }
                append_jsonl(
                    self.log_path,
                    {
                        "method": self.method,
                        "task_id": self.task_id,
                        "purpose": purpose,
                        "api": "responses",
                        "logical_call": call_id,
                        "requested_model": MODEL,
                        "actual_model": actual_model,
                        "reasoning_effort": REASONING_EFFORT,
                        "temperature": TEMPERATURE,
                        "status": last_status,
                        "upstream_attempts": attempt,
                        "usage": usage,
                        "wall_seconds": elapsed,
                        "planned_query": query.strip(),
                        "executed_query": executed_query.strip(),
                        "query_rewritten": executed_query.strip() != query.strip(),
                        "web_search_call_count": 1,
                        "backend_raw_result_count": len(raw_results),
                        "request_path": str(request_path),
                        "response_path": str(response_path),
                    },
                )
                return result
            except urllib.error.HTTPError as exc:
                last_error = exc
                last_status = exc.code
                error_detail = exc.read().decode("utf-8", "replace")[:1200]
                retryable = exc.code in RETRYABLE_HTTP_CODES
                if _fatal_provider_error(exc.code, error_detail):
                    record_global_stop("PROVIDER_FATAL", f"HTTP {exc.code}: {error_detail}")
                    raise GlobalStopError(f"fatal provider error: HTTP {exc.code}") from exc
                retry_wait_seconds = _retry_after_seconds(exc.headers.get("Retry-After")) if exc.code == 429 else 5.0
                if exc.code == 429 and retry_wait_seconds > MAX_RETRY_WAIT_SECONDS:
                    retryable = False
            except (
                urllib.error.URLError,
                TimeoutError,
                http.client.RemoteDisconnected,
                socket.gaierror,
                ssl.SSLError,
                ConnectionResetError,
                ConnectionAbortedError,
            ) as exc:
                last_error = exc
                last_status = None
                error_detail = type(exc).__name__
                retryable = True
            except (ConfigurationViolation, GlobalStopError):
                raise
            except (json.JSONDecodeError, RuntimeError, ValueError) as exc:
                last_error = exc
                error_detail = str(exc)[:1200]
                retryable = False
            if retryable and attempt == 1:
                retry_events.append(
                    {
                        "attempt": attempt,
                        "status": last_status,
                        "error_type": type(last_error).__name__ if last_error else "UnknownError",
                        "wait_seconds": retry_wait_seconds,
                    }
                )
                time.sleep(retry_wait_seconds)
                continue
            elapsed = time.perf_counter() - started
            failure_type = classify_responses_search_error(last_error or RuntimeError(error_detail), last_status)
            append_jsonl(
                self.log_path,
                {
                    "method": self.method,
                    "task_id": self.task_id,
                    "purpose": purpose,
                    "api": "responses",
                    "logical_call": call_id,
                    "requested_model": MODEL,
                    "actual_model": None,
                    "reasoning_effort": REASONING_EFFORT,
                    "temperature": TEMPERATURE,
                    "status": last_status if last_status is not None else "transport_error",
                    "upstream_attempts": attempt,
                    "usage": {},
                    "wall_seconds": elapsed,
                    "planned_query": query.strip(),
                    "error_type": type(last_error).__name__ if last_error else "UnknownError",
                    "failure_type": failure_type,
                    "error_detail": error_detail,
                    "retry_events": retry_events,
                    "request_path": str(request_path),
                    "response_path": None,
                },
            )
            raise StrictAPIRequestError(
                f"strict Responses web search failed after {attempt} upstream attempt(s): "
                f"{type(last_error).__name__ if last_error else 'UnknownError'}: {error_detail}",
                attempt,
                last_status,
                failure_type,
            ) from last_error
        raise AssertionError("unreachable")


class StrictProxyHandler(BaseHTTPRequestHandler):
    server: "StrictProxyServer"

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self.send_error(404)
            return
        if not self._authorized():
            self._json_error(401, "invalid private-proxy capability")
            return
        self._json(200, {"status": "ok", "model": MODEL, "reasoning_effort": REASONING_EFFORT, "temperature": TEMPERATURE})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        if not self._authorized():
            self._json_error(401, "invalid private-proxy capability")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 10_000_000:
                raise ValueError("request body length is invalid")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            adapted, adaptation = adapt_native_proxy_payload(payload)
            if adaptation is not None:
                append_jsonl(self.server.client.artifact_dir / "proxy_adaptations.jsonl", adaptation)
            result = self.server.client.complete_payload(adapted, "native_agent")
            self._json(200, result["raw"])
        except ValueError as exc:
            self._json_error(400, str(exc))
        except Exception as exc:
            self._json_error(502, f"strict upstream failure: {type(exc).__name__}")

    def _authorized(self) -> bool:
        supplied = self.headers.get("Authorization", "")
        return secrets.compare_digest(supplied, f"Bearer {self.server.capability}")

    def _json(self, status: int, value: Any) -> None:
        body = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json_error(self, status: int, message: str) -> None:
        self._json(status, {"error": {"message": message, "type": "strict_proxy_error"}})

    def log_message(self, format: str, *args: Any) -> None:
        return


class StrictProxyServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], client: StrictAPIClient, capability: str):
        if not ipaddress.ip_address(address[0]).is_loopback:
            raise ValueError("proxy must bind to a literal loopback address")
        if ":" in address[0]:
            self.address_family = socket.AF_INET6
        super().__init__(address, StrictProxyHandler)
        self.client = client
        self.capability = capability


def summarize_calls(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path) if path.is_file() else []
    prompt = completion = total = 0
    usage_available = bool(rows)
    for row in rows:
        usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
        prompt_value = usage.get("prompt_tokens", usage.get("input_tokens"))
        completion_value = usage.get("completion_tokens", usage.get("output_tokens"))
        total_value = usage.get("total_tokens")
        if not isinstance(prompt_value, int) or not isinstance(completion_value, int):
            usage_available = False
            continue
        prompt += prompt_value
        completion += completion_value
        total += total_value if isinstance(total_value, int) else prompt_value + completion_value
    return {
        "calls": len(rows),
        "upstream_attempts": sum(int(row.get("upstream_attempts") or 0) for row in rows),
        "prompt_tokens": prompt if usage_available else None,
        "completion_tokens": completion if usage_available else None,
        "total_tokens": total if usage_available else None,
        "wall_seconds": sum(float(row.get("wall_seconds") or 0.0) for row in rows),
        "actual_models": sorted({str(row["actual_model"]) for row in rows if row.get("actual_model")}),
    }


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    candidates = [stripped]
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidates.insert(0, fenced.group(1))
    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
        for index, character in enumerate(candidate):
            if character != "{":
                continue
            try:
                value, _ = decoder.raw_decode(candidate[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
    raise ValueError("response contains no JSON object")


def failure_status(flags: dict[str, bool]) -> str:
    # Retrieval quality is reported independently.  A partial/failed search
    # must not erase a successfully produced final model-and-solve answer.
    priority = (
        ("configuration_violation", "CONFIGURATION_VIOLATION"),
        ("provider_failure", "PROVIDER_FAILURE"),
        ("runner_failure", "RUNNER_FAILURE"),
        ("parse_failure", "PARSE_FAILURE"),
        ("output_contract_failure", "OUTPUT_CONTRACT_FAILURE"),
    )
    return next((status for key, status in priority if flags.get(key)), "OK")


def unified_output(
    *,
    method: str,
    phase: str,
    public: dict[str, Any],
    search: dict[str, Any] | None = None,
    decision_state: str | None = None,
    applicability: bool | dict[str, Any] | None = None,
    patch: list[Any] | None = None,
    patch_elements: list[Any] | None = None,
    actions: list[dict[str, Any]] | None = None,
    objective: dict[str, Any] | None = None,
    flags: dict[str, bool] | None = None,
    failure_detail: str | None = None,
    native_artifacts: dict[str, str] | None = None,
    accounting: dict[str, Any] | None = None,
    solver_status: str | None = None,
    attempt: int = 1,
) -> dict[str, Any]:
    normalized_flags = {
        "configuration_violation": False,
        "provider_failure": False,
        "runner_failure": False,
        "retrieval_failure": False,
        "parse_failure": False,
        "output_contract_failure": False,
        **(flags or {}),
    }
    schema = output_schema_for(public)
    expected_ids = [str(item["id"]) for item in schema["actions"]]
    actual_ids = [str(item.get("id")) for item in actions] if isinstance(actions, list) and all(isinstance(item, dict) for item in actions) else []
    if actual_ids != expected_ids or any(not isinstance(item.get("value"), int) or isinstance(item.get("value"), bool) for item in actions or []):
        normalized_flags["output_contract_failure"] = True
    accepted_units = schema["objective"].get("accepted_units")
    normalized_objective = dict(objective) if isinstance(objective, dict) else objective
    if isinstance(normalized_objective, dict) and "sense" not in normalized_objective and normalized_objective.get("direction") in {"min", "max"}:
        normalized_objective["sense"] = normalized_objective.pop("direction")
    objective_complete = (
        isinstance(normalized_objective, dict)
        and isinstance(normalized_objective.get("value"), (int, float))
        and not isinstance(normalized_objective.get("value"), bool)
        and normalized_objective.get("sense") in {"min", "max"}
        and isinstance(accepted_units, dict)
        and normalized_objective.get("unit") in accepted_units
    )
    if not objective_complete:
        normalized_flags["output_contract_failure"] = True
    normalized_applicability = applicability.get("applies") if isinstance(applicability, dict) else applicability
    if normalized_applicability is not None and not isinstance(normalized_applicability, bool):
        normalized_flags["output_contract_failure"] = True
    normalized_patch = patch if patch is not None else patch_elements
    if normalized_patch is not None and not isinstance(normalized_patch, list):
        normalized_flags["output_contract_failure"] = True
    if decision_state is not None and decision_state not in {"RETAIN", "PATCH_CHANGES"}:
        normalized_flags["output_contract_failure"] = True
    actual_models = (accounting or {}).get("actual_models") or []
    return {
        "schema_version": "searchworthyor.v151.unified_baseline_output.v1",
        "task_id": public["id"],
        "case_id": public["case_id"],
        "method": method,
        "phase": phase,
        "attempt": attempt,
        "requested_configuration": {"model": MODEL, "reasoning_effort": REASONING_EFFORT, "temperature": TEMPERATURE},
        "actual_models": actual_models,
        "status": failure_status(normalized_flags),
        "search": search or {"queries": [], "pages": [], "search_count": 0, "pages_opened": 0},
        "decision_state": decision_state,
        "applicability": normalized_applicability,
        "patch": normalized_patch,
        "patch_elements": normalized_patch,
        "actions": actions,
        "objective": normalized_objective,
        "solver_status": solver_status,
        "observed_fields": {
            "decision_state": decision_state is not None,
            "applicability": normalized_applicability is not None,
            "patch": normalized_patch is not None,
            "actions": actions is not None,
            "objective_value": isinstance(normalized_objective, dict) and normalized_objective.get("value") is not None,
            "objective_sense": isinstance(normalized_objective, dict) and normalized_objective.get("sense") is not None,
            "objective_unit": isinstance(normalized_objective, dict) and normalized_objective.get("unit") is not None,
        },
        "failure_flags": normalized_flags,
        "failure_detail": failure_detail,
        "native_artifacts": native_artifacts or {},
        "accounting": accounting or {},
    }

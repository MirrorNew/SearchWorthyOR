"""Shared contracts for the three public SearchWorthyOR runners.

This module owns only configuration, public-input projection, the strict live
API client, resumable outputs, and token/time accounting.  Baseline-specific
bridges, private scoring data, replay recovery, and native HTTP proxies are not
part of this public runtime.
"""

from __future__ import annotations

import hashlib
import http.client
import concurrent.futures
import json
import os
import re
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
from functools import lru_cache
from pathlib import Path
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parent
EXPERIMENT_ROOT = SCRIPT_ROOT.parent
CONFIG_PATH = EXPERIMENT_ROOT / "EXPERIMENT_CONFIG.json"
_BOOTSTRAP_CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _resolve_config_path(raw: Any) -> Path:
    path = Path(str(raw)).expanduser()
    return path.resolve() if path.is_absolute() else (EXPERIMENT_ROOT / path).resolve()


PUBLIC_INPUT_PATH = _resolve_config_path(_BOOTSTRAP_CONFIG["public_input_file"])
SNAPSHOT_STATUS_PATH = EXPERIMENT_ROOT / "datasets" / "SearchWorthyOR-v1.6.1-candidate" / "dataset_status.json"
SMOKE_SUMMARY_PATH = EXPERIMENT_ROOT / "runs" / "smoke" / "validation_summary.json"
PREFLIGHT_SUMMARY_PATH = EXPERIMENT_ROOT / "preflight" / "summary.json"
GLOBAL_STOP_PATH = EXPERIMENT_ROOT / "runs" / "GLOBAL_STOP.json"
DEFAULT_ENV_FILE = EXPERIMENT_ROOT / ".env.local"


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
        raise RuntimeError("OPENOR_BASE_URL is absent from the repository-local .env.local")
    provider = _BOOTSTRAP_CONFIG.get("provider")
    configured = provider.get("base_url") if isinstance(provider, dict) else None
    if configured == "https://api.shubiaobiao.cn/v1":
        return configured
    raise RuntimeError("missing repository-local .env.local and no locked Shubiaobiao base URL in config")


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
    raise RuntimeError("provider base_url does not match the repository-local .env.local")
CHAT_ENDPOINT = str(_PROVIDER_CONFIG.get("chat_endpoint"))
RESPONSES_ENDPOINT = str(_PROVIDER_CONFIG.get("responses_endpoint"))
if (CHAT_ENDPOINT, RESPONSES_ENDPOINT) != ("/chat/completions", "/responses"):
    raise RuntimeError("provider endpoints changed")
_RETRY_CONFIG = _BOOTSTRAP_CONFIG.get("retry")
if not isinstance(_RETRY_CONFIG, dict):
    raise RuntimeError("EXPERIMENT_CONFIG.json retry must be an object")
INFRASTRUCTURE_RETRIES = _RETRY_CONFIG.get("infrastructure_retries")
if type(INFRASTRUCTURE_RETRIES) is not int or INFRASTRUCTURE_RETRIES < 0:
    raise RuntimeError("infrastructure_retries must be a non-negative integer")
RETRYABLE_HTTP_CODES = set(_RETRY_CONFIG.get("retry_status_codes") or [])
MAX_RETRY_WAIT_SECONDS = 30.0
ALLOWED_PAYLOAD_FIELDS = {"model", "messages", "reasoning_effort", "temperature", "max_tokens"}
TERMINAL_STATUSES = {
    "OK",
    "ABSTAIN",
    "OUTPUT_CONTRACT_FAILURE",
    "PARSE_FAILURE",
    "RETRIEVAL_FAILURE",
    "PROVIDER_FAILURE",
    "RUNNER_FAILURE",
    "CONFIGURATION_VIOLATION",
}
INFRASTRUCTURE_STATUSES = frozenset({"CONFIGURATION_VIOLATION", "PROVIDER_FAILURE", "RUNNER_FAILURE"})

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


def classify_chat_error(exc: BaseException, status: int | None = None) -> str:
    return classify_responses_search_error(exc, status).replace("SEARCH_", "CHAT_", 1)


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


def bounded_futures(
    submit: Any,
    items: list[str],
    max_in_flight: int,
) -> Any:
    """Yield completed futures while keeping at most max_in_flight tasks submitted."""
    iterator = iter(items)
    pending: dict[concurrent.futures.Future[Any], str] = {}
    for _ in range(min(max_in_flight, len(items))):
        item = next(iterator)
        pending[submit(item)] = item
    try:
        while pending:
            done, _ = concurrent.futures.wait(pending, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                item = pending.pop(future)
                yield item, future
                try:
                    next_item = next(iterator)
                except StopIteration:
                    continue
                pending[submit(next_item)] = next_item
    finally:
        for future in pending:
            future.cancel()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@lru_cache(maxsize=1)
def input_digest() -> str:
    digest = hashlib.sha256()
    digest.update(b"public_cases\0")
    digest.update(bytes.fromhex(_sha256(PUBLIC_INPUT_PATH)))
    return digest.hexdigest()


@lru_cache(maxsize=1)
def configuration_digest() -> str:
    return _sha256(CONFIG_PATH)


def dataset_snapshot_status() -> dict[str, Any]:
    value = read_json(SNAPSHOT_STATUS_PATH)
    counts = value.get("counts")
    validation = value.get("validation")
    if (
        value.get("schema_version") != "searchworthyor.dataset_status.v1"
        or value.get("release_name") != "SearchWorthyOR-v1.6.1-candidate"
        or counts != {"source_tasks": 120, "public_cases": 360, "C1": 120, "C2": 120, "C3": 120}
        or not isinstance(validation, dict)
        or validation.get("status") not in {"PASS", "FAIL"}
        or not isinstance(validation.get("error_count"), int)
        or not isinstance(value.get("exploratory_only"), bool)
    ):
        raise RuntimeError("dataset snapshot status contract is invalid")
    return value


def load_resumable_output(path: Path, *, eval_id: str, method: str, phase: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = read_json(path)
    expected = {
        "eval_id": eval_id,
        "method": method,
        "phase": phase,
        "input_digest": input_digest(),
        "configuration_digest": configuration_digest(),
    }
    mismatches = {name: value.get(name) for name, wanted in expected.items() if value.get(name) != wanted}
    if mismatches:
        raise ConfigurationViolation(f"existing output does not match current input/configuration: {mismatches}")
    return value


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
    if config.get("schema_version") != "searchworthyor.v161.three_methods.v1":
        raise RuntimeError("experiment schema_version changed")
    if config.get("implementation_revision") != "public-v1":
        raise RuntimeError("implementation_revision changed")
    if _resolve_config_path(config.get("experiment_root")) != EXPERIMENT_ROOT.resolve():
        raise RuntimeError("experiment_root changed")
    if _resolve_config_path(config.get("public_input_file")) != PUBLIC_INPUT_PATH.resolve():
        raise RuntimeError("public_input_file changed")
    if any(name in config for name in ("dataset_root", "credential_file", "task_matrix_file", "private_gold_file")):
        raise RuntimeError("runner config contains a dataset, credential, or private path")
    if config.get("model") != {"name": MODEL, "reasoning_effort": REASONING_EFFORT, "temperature": TEMPERATURE}:
        raise RuntimeError("locked model tuple changed")
    if config.get("provider") != _PROVIDER_CONFIG:
        raise RuntimeError("locked Shubiaobiao provider contract changed")
    if config.get("retry") != {
        "infrastructure_retries": 2,
        "retry_status_codes": [408, 429, 500, 502, 503, 504],
        "retry_answer_errors": False,
        "retry_parse_failures": False,
        "retry_retrieval_failures": False,
        "retry_output_contract_failures": False,
    }:
        raise RuntimeError("locked retry contract changed")
    if config.get("allow_exploratory_snapshot") is not True:
        raise RuntimeError("current snapshot requires explicit allow_exploratory_snapshot=true")
    inputs = config.get("inputs")
    if (
        not isinstance(inputs, dict)
        or inputs.get("case_suffixes") != ["C1", "C2", "C3"]
        or inputs.get("case_count") != 360
        or inputs.get("source_task_count") != 120
    ):
        raise RuntimeError("fixed V1.6.1 triplet input contract changed")
    if inputs.get("model_fields") != ["eval_id", "prompt_zh"] or inputs.get("private_gold_visible_to_runner") is not False:
        raise RuntimeError("runner input or Gold visibility contract changed")
    methods = config.get("methods")
    expected_methods = {
        "Direct-v2 Base-Solve Gated Search",
        "Search-First Gated Raw-NL",
        "SearchWorthy",
    }
    if not isinstance(methods, dict) or set(methods) != expected_methods:
        raise RuntimeError("the fixed three-method contract changed")
    phases = config.get("phases")
    if (
        not isinstance(phases, dict)
        or phases.get("smoke", {}).get("instances") != 8
        or phases.get("formal", {}).get("instances") != 1080
    ):
        raise RuntimeError("Smoke/Formal instance contract changed")
    parallelism = config.get("parallelism")
    if (
        not isinstance(parallelism, dict)
        or parallelism.get("smoke_total_workers") != 5
        or parallelism.get("formal_total_workers") != 9
    ):
        raise RuntimeError("parallel worker contract changed")
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
        "search_budget_unit": "hosted_web_search_call",
        "provider_query_expansion_policy": "accept_and_log",
        "max_exposed_results_per_query": 10,
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
    if profile != expected or type(profile.get("tool_calls_per_planned_query")) is not int:
        raise RuntimeError("shubiaobiao_hosted_search_shared changed")
    methods = value.get("methods")
    if (
        not isinstance(methods, dict)
        or methods.get("Direct-v2 Base-Solve Gated Search", {}).get("search_profile")
        != "shubiaobiao_hosted_search_shared"
        or methods.get("Search-First Gated Raw-NL", {}).get("search_profile")
        != "shubiaobiao_hosted_search_shared"
        or methods.get("SearchWorthy", {}).get("search_profile")
        != "shubiaobiao_hosted_search_shared"
    ):
        raise RuntimeError("Direct/Chain2 no longer share one search profile")
    return profile


def hosted_search_request_payload(query: str) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("web search query must be a non-empty string")
    planned_query = query.strip()
    profile = shared_search_config()
    return {
        "model": MODEL,
        "reasoning": {"effort": REASONING_EFFORT},
        "temperature": TEMPERATURE,
        "max_tool_calls": profile["tool_calls_per_planned_query"],
        "tools": [{"type": "web_search", "search_context_size": profile["search_context_size"]}],
        "tool_choice": "required",
        "include": ["web_search_call.results"],
        "input": (
            "Execute exactly one public web search for the planned query below. "
            "Do not answer from memory and do not perform a second search. "
            "Return a concise response grounded in the search results.\n"
            f"PLANNED_QUERY_JSON={json.dumps(planned_query, ensure_ascii=False)}"
        ),
    }


def uncapped_chat_request_payload(messages: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "model": MODEL,
        "messages": messages,
        "reasoning_effort": REASONING_EFFORT,
        "temperature": TEMPERATURE,
    }


def validate_formal_gate() -> dict[str, Any]:
    config = load_config()
    snapshot = dataset_snapshot_status()
    current_input_digest = input_digest()
    current_configuration_digest = configuration_digest()
    snapshot_allowed = snapshot["validation"]["status"] == "PASS" or (
        snapshot["exploratory_only"] is True and config.get("allow_exploratory_snapshot") is True
    )
    if not snapshot_allowed:
        raise RuntimeError(f"dataset snapshot is not allowed for this run: {snapshot}")
    if not PREFLIGHT_SUMMARY_PATH.is_file():
        raise RuntimeError("formal experiment requires a passing concurrent preflight")
    preflight = read_json(PREFLIGHT_SUMMARY_PATH)
    if (
        preflight.get("status") != "PASS"
        or preflight.get("input_digest") != current_input_digest
        or preflight.get("configuration_digest") != current_configuration_digest
    ):
        raise RuntimeError("formal experiment requires a current input/configuration-bound preflight")
    if not SMOKE_SUMMARY_PATH.is_file():
        raise RuntimeError("formal experiment requires runs/smoke/validation_summary.json")
    gate = read_json(SMOKE_SUMMARY_PATH)
    if (
        gate.get("schema_version") != "searchworthyor.v161.three_methods.output_validation.v1"
        or gate.get("phase") != "smoke"
        or gate.get("status") != "PASS"
        or gate.get("expected_instances") != 8
        or gate.get("terminal_instances") != 8
        or gate.get("input_digest") != current_input_digest
        or gate.get("configuration_digest") != current_configuration_digest
    ):
        raise RuntimeError("smoke gate has not passed")
    for key in (
        "missing_outputs",
        "identity_failures",
        "digest_failures",
        "terminal_status_failures",
        "infrastructure_failures",
        "accounting_failures",
    ):
        if gate.get(key) != 0:
            raise RuntimeError(f"smoke gate failed: {key}={gate.get(key)!r}")
    provider_success = gate.get("provider_success_by_method")
    if (
        not isinstance(provider_success, dict)
        or set(provider_success) != {"direct", "search_first", "searchworthy"}
        or any(not isinstance(value, int) or isinstance(value, bool) or value < 1 for value in provider_success.values())
    ):
        raise RuntimeError("smoke gate did not observe provider success for every method")
    return {**gate, "dataset_snapshot_status": snapshot}


def validate_smoke_launch_gate() -> dict[str, Any]:
    config = load_config()
    snapshot = dataset_snapshot_status()
    snapshot_allowed = snapshot["validation"]["status"] == "PASS" or (
        snapshot["exploratory_only"] is True and config.get("allow_exploratory_snapshot") is True
    )
    if not snapshot_allowed:
        raise RuntimeError(f"dataset snapshot is not allowed for this run: {snapshot}")
    if not PREFLIGHT_SUMMARY_PATH.is_file():
        raise RuntimeError("smoke experiment requires a passing concurrent preflight")
    preflight = read_json(PREFLIGHT_SUMMARY_PATH)
    if (
        preflight.get("status") != "PASS"
        or preflight.get("input_digest") != input_digest()
        or preflight.get("configuration_digest") != configuration_digest()
    ):
        raise RuntimeError("smoke experiment requires a current input/configuration-bound preflight")
    return {"preflight": preflight, "dataset_snapshot_status": snapshot}


def validate_direct_formal_gate() -> dict[str, Any]:
    return validate_formal_gate()


def public_cases() -> dict[str, dict[str, Any]]:
    rows = read_jsonl(PUBLIC_INPUT_PATH)
    indexed = index_unique(rows, "eval_id")
    if len(indexed) != 360:
        raise ValueError("public cases must contain all 360 V1.6.1 eval IDs exactly once")
    for identifier, row in indexed.items():
        if not re.fullmatch(r"SWOR-E-[0-9A-F]{20}", identifier):
            raise ValueError(f"invalid opaque eval_id: {identifier!r}")
        if set(row) != {"eval_id", "prompt_zh"}:
            raise ValueError(f"{identifier}: unexpected public input fields")
    return indexed


def output_schema_for(public: dict[str, Any]) -> dict[str, Any]:
    if set(public) != {"eval_id", "prompt_zh"}:
        raise ValueError("runner input must contain exactly eval_id/prompt_zh")
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
    if not isinstance(values, list) or len(values) != 1:
        raise ValueError("configuration must contain one shared Smoke eval_id")
    if values[0] not in public_cases():
        raise ValueError("shared Smoke eval_id is absent from public input")
    return values


def searchworthy_smoke_ids() -> list[str]:
    values = load_config().get("phases", {}).get("smoke", {}).get("searchworthy_case_ids")
    if not isinstance(values, list) or len(values) != 6 or len(set(values)) != 6:
        raise ValueError("configuration must contain six unique SearchWorthy Smoke eval_ids")
    if smoke_ids()[0] not in values or any(value not in public_cases() for value in values):
        raise ValueError("SearchWorthy Smoke IDs must include the shared case and exist in public input")
    return values


def selected_ids(phase: str, explicit: str = "") -> list[str]:
    if explicit:
        values = [item.strip() for item in explicit.split(",") if item.strip()]
    elif phase == "smoke":
        values = smoke_ids()
    else:
        values = list(public_cases())
    if len(values) != len(set(values)) or any(not re.fullmatch(r"SWOR-E-[0-9A-F]{20}", value) for value in values):
        raise ValueError("case IDs must be unique opaque V1.6.1 eval IDs")
    if any(value not in public_cases() for value in values):
        raise ValueError("selected eval ID is absent from public input")
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
        raise GlobalStopError("only the repository-local .env.local is allowed")
    values = _read_env_file(env_file)
    if set(values) != {"OPENOR_BASE_URL", "OPENOR_API_KEY"}:
        raise GlobalStopError("repository-local .env.local must contain only Base URL and API key")
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
    payload: dict[str, Any] = {"status": "STOPPED", "reason": reason, "detail": detail[:1200]}
    if not GLOBAL_STOP_PATH.exists():
        write_json(GLOBAL_STOP_PATH, payload)


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
    if "max_tokens" in payload and (
        not isinstance(payload["max_tokens"], int)
        or isinstance(payload["max_tokens"], bool)
        or payload["max_tokens"] <= 0
    ):
        raise ValueError("max_tokens must be a positive integer")


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
        artifact_dir = Path(artifact_dir)
        return cls(load_api_key(env_file), artifact_dir, method, task_id, timeout_seconds)

    @property
    def log_path(self) -> Path:
        return self.artifact_dir / "api_calls.jsonl"

    def complete(
        self,
        messages: list[dict[str, str]],
        purpose: str,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        if max_tokens is not None and (
            not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens <= 0
        ):
            raise ValueError("max_tokens must be a positive integer")
        payload = uncapped_chat_request_payload(messages)
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        return self.complete_payload(payload, purpose)

    def complete_payload(
        self,
        payload: dict[str, Any],
        purpose: str = "native_agent",
    ) -> dict[str, Any]:
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
        attempt_wall_seconds: list[float] = []
        attempt_started_at_utc: list[str] = []
        attempt_phases: list[dict[str, Any]] = []
        max_attempts = INFRASTRUCTURE_RETRIES + 1
        for attempt in range(1, max_attempts + 1):
            retry_wait_seconds = min(5.0 * attempt, MAX_RETRY_WAIT_SECONDS)
            observed_actual_model: str | None = None
            observed_usage: dict[str, int] = {}
            observed_finish_reason: Any = None
            observed_content_present = False
            observed_content_length = 0
            response_saved = False
            attempt_started_at_utc.append(datetime.now(timezone.utc).isoformat())
            attempt_started = time.perf_counter()
            phase = {
                "attempt": attempt,
                "phase_reached": "awaiting_response_headers",
                "request_bytes": len(data),
                "response_header_seconds": None,
                "body_read_seconds": None,
                "json_parse_seconds": None,
                "response_bytes": None,
            }
            try:
                request = urllib.request.Request(
                    f"{BASE_URL}{CHAT_ENDPOINT}",
                    data=data,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json; charset=utf-8"},
                    method="POST",
                )
                with _NO_REDIRECT_OPENER.open(request, timeout=self.timeout_seconds) as response:
                    phase["response_header_seconds"] = time.perf_counter() - attempt_started
                    phase["phase_reached"] = "reading_response_body"
                    last_status = response.status
                    final = urllib.parse.urlsplit(response.geturl())
                    if (final.scheme, final.hostname, final.port or 443) != (_API_ORIGIN.scheme, _API_ORIGIN.hostname, _API_ORIGIN.port or 443):
                        raise RuntimeError("API response origin mismatch")
                    body_started = time.perf_counter()
                    response_body = response.read()
                    phase["body_read_seconds"] = time.perf_counter() - body_started
                    phase["response_bytes"] = len(response_body)
                    phase["phase_reached"] = "parsing_json"
                    parse_started = time.perf_counter()
                    parsed = json.loads(response_body.decode("utf-8"))
                    phase["json_parse_seconds"] = time.perf_counter() - parse_started
                    phase["phase_reached"] = "complete"
                if not isinstance(parsed, dict):
                    raise ValueError("API response must be an object")
                write_json(response_path, parsed)
                response_saved = True
                observed_usage = safe_usage(parsed.get("usage"))
                choices = parsed.get("choices")
                choice = choices[0] if isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict) else None
                observed_finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None
                message = choice.get("message") if isinstance(choice, dict) else None
                content = message.get("content") if isinstance(message, dict) else None
                observed_content_present = isinstance(content, str) and bool(content.strip())
                observed_content_length = len(content) if isinstance(content, str) else 0
                actual_model = _validate_actual_configuration(parsed)
                observed_actual_model = actual_model
                if not isinstance(content, str) or not content.strip():
                    raise RuntimeError("response contains no assistant content")
                attempt_wall_seconds.append(time.perf_counter() - attempt_started)
                attempt_phases.append(phase)
                result = {
                    "content": content,
                    "raw": parsed,
                    "actual_model": actual_model,
                    "usage": observed_usage,
                    "finish_reason": observed_finish_reason,
                    "content_present": observed_content_present,
                    "content_length": observed_content_length,
                    "logical_call": call_id,
                    "upstream_attempts": attempt,
                    "wall_seconds": time.perf_counter() - started,
                    "request_path": str(request_path),
                    "response_path": str(response_path),
                    "retry_events": retry_events,
                    "attempt_wall_seconds": attempt_wall_seconds,
                    "attempt_started_at_utc": attempt_started_at_utc,
                    "attempt_phases": attempt_phases,
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
                        "finish_reason": observed_finish_reason,
                        "content_present": observed_content_present,
                        "content_length": observed_content_length,
                        "wall_seconds": result["wall_seconds"],
                        "request_path": str(request_path),
                        "response_path": str(response_path),
                        "retry_events": retry_events,
                        "attempt_wall_seconds": attempt_wall_seconds,
                        "attempt_started_at_utc": attempt_started_at_utc,
                        "attempt_phases": attempt_phases,
                    },
                )
                return result
            except urllib.error.HTTPError as exc:
                last_error = exc
                last_status = exc.code
                phase["response_header_seconds"] = time.perf_counter() - attempt_started
                phase["phase_reached"] = "http_error_response"
                body = exc.read().decode("utf-8", "replace")[:1200]
                retryable = exc.code in RETRYABLE_HTTP_CODES
                error_detail = body
                if _fatal_provider_error(exc.code, body):
                    record_global_stop("PROVIDER_FATAL", f"HTTP {exc.code}: {body}")
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
                retryable = True
                error_detail = type(exc).__name__
            except (ConfigurationViolation, GlobalStopError):
                raise
            except (json.JSONDecodeError, RuntimeError, ValueError) as exc:
                last_error = exc
                retryable = False
                error_detail = str(exc)[:1200]
            attempt_wall_seconds.append(time.perf_counter() - attempt_started)
            attempt_phases.append(phase)
            if retryable and attempt < max_attempts:
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
            failure_type = classify_chat_error(last_error or RuntimeError(error_detail), last_status)
            append_jsonl(
                self.log_path,
                {
                    "method": self.method,
                    "task_id": self.task_id,
                    "purpose": purpose,
                    "logical_call": call_id,
                    "requested_model": MODEL,
                    "actual_model": observed_actual_model,
                    "reasoning_effort": REASONING_EFFORT,
                    "temperature": TEMPERATURE,
                    "status": last_status if last_status is not None else "transport_error",
                    "upstream_attempts": attempt,
                    "usage": observed_usage,
                    "finish_reason": observed_finish_reason,
                    "content_present": observed_content_present,
                    "content_length": observed_content_length,
                    "wall_seconds": elapsed,
                    "error_type": type(last_error).__name__ if last_error else "UnknownError",
                    "failure_type": failure_type,
                    "error_detail": error_detail,
                    "request_path": str(request_path),
                    "response_path": str(response_path) if response_saved else None,
                    "retry_events": retry_events,
                    "attempt_wall_seconds": attempt_wall_seconds,
                    "attempt_started_at_utc": attempt_started_at_utc,
                    "attempt_phases": attempt_phases,
                },
            )
            raise StrictAPIRequestError(
                f"strict API request failed after {attempt} upstream attempt(s): {type(last_error).__name__ if last_error else 'UnknownError'}",
                attempt,
                last_status,
                failure_type,
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
        payload = hosted_search_request_payload(query)
        write_json(request_path, payload)
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        started = time.perf_counter()
        last_error: Exception | None = None
        last_status: int | None = None
        retry_events: list[dict[str, Any]] = []
        attempt_wall_seconds: list[float] = []
        attempt_started_at_utc: list[str] = []
        attempt_phases: list[dict[str, Any]] = []
        observed_actual_model: str | None = None
        observed_usage: dict[str, int] = {}
        observed_tool_call_count: int | None = None
        response_saved = False
        max_attempts = INFRASTRUCTURE_RETRIES + 1
        for attempt in range(1, max_attempts + 1):
            retry_wait_seconds = min(5.0 * attempt, MAX_RETRY_WAIT_SECONDS)
            attempt_started_at_utc.append(datetime.now(timezone.utc).isoformat())
            attempt_started = time.perf_counter()
            phase = {
                "attempt": attempt,
                "phase_reached": "awaiting_response_headers",
                "request_bytes": len(data),
                "response_header_seconds": None,
                "body_read_seconds": None,
                "json_parse_seconds": None,
                "response_bytes": None,
            }
            try:
                request = urllib.request.Request(
                    f"{BASE_URL}{RESPONSES_ENDPOINT}",
                    data=data,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json; charset=utf-8"},
                    method="POST",
                )
                with _NO_REDIRECT_OPENER.open(request, timeout=self.timeout_seconds) as response:
                    phase["response_header_seconds"] = time.perf_counter() - attempt_started
                    phase["phase_reached"] = "reading_response_body"
                    last_status = response.status
                    final = urllib.parse.urlsplit(response.geturl())
                    if (final.scheme, final.hostname, final.port or 443) != (_API_ORIGIN.scheme, _API_ORIGIN.hostname, _API_ORIGIN.port or 443):
                        raise RuntimeError("API response origin mismatch")
                    body_started = time.perf_counter()
                    response_body = response.read()
                    phase["body_read_seconds"] = time.perf_counter() - body_started
                    phase["response_bytes"] = len(response_body)
                    phase["phase_reached"] = "parsing_json"
                    parse_started = time.perf_counter()
                    parsed = json.loads(response_body.decode("utf-8"))
                    phase["json_parse_seconds"] = time.perf_counter() - parse_started
                    phase["phase_reached"] = "complete"
                if not isinstance(parsed, dict):
                    raise ValueError("Responses API response must be an object")
                # Preserve every parsed HTTP 200 response before enforcing the
                # hosted-search contract so a provider-side violation remains
                # auditable instead of becoming a response_path=None failure.
                write_json(response_path, parsed)
                response_saved = True
                raw_actual_model = parsed.get("model")
                observed_actual_model = raw_actual_model if isinstance(raw_actual_model, str) else None
                observed_usage = safe_usage(parsed.get("usage"))
                raw_output = parsed.get("output")
                provider_calls = [
                    item
                    for item in raw_output
                    if isinstance(item, dict) and item.get("type") == "web_search_call"
                ] if isinstance(raw_output, list) else []
                observed_calls = [
                    item
                    for item in provider_calls
                    if isinstance(item.get("action"), dict)
                    and item["action"].get("type") in {None, "search"}
                    and ("query" in item["action"] or "queries" in item["action"])
                ]
                provider_open_page_count = sum(
                    1
                    for item in provider_calls
                    if isinstance(item.get("action"), dict) and item["action"].get("type") == "open_page"
                )
                observed_tool_call_count = len(observed_calls) if isinstance(raw_output, list) else None
                actual_model = _validate_actual_configuration(parsed)
                observed_actual_model = actual_model
                if parsed.get("status") != "completed":
                    raise RuntimeError(f"Responses API status is not completed: {parsed.get('status')!r}")
                if not isinstance(raw_output, list):
                    raise ValueError("Responses API output must be a list")
                calls = observed_calls
                if len(calls) != 1:
                    raise RuntimeError(f"expected exactly one search action, got {len(calls)}")
                action = calls[0].get("action")
                executed_queries = action.get("queries") if isinstance(action, dict) else None
                executed_query = action.get("query") if isinstance(action, dict) else None
                if (
                    not isinstance(executed_query, str)
                    or not executed_query.strip()
                    or not isinstance(executed_queries, list)
                    or not executed_queries
                    or any(not isinstance(item, str) or not item.strip() for item in executed_queries)
                    or executed_queries[0] != executed_query
                ):
                    raise RuntimeError("web_search_call must expose a valid executed query list")
                raw_results = calls[0].get("results")
                if not isinstance(raw_results, list):
                    raise RuntimeError("web_search_call results are absent")
                usage = observed_usage
                attempt_wall_seconds.append(time.perf_counter() - attempt_started)
                attempt_phases.append(phase)
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
                    "executed_queries": list(executed_queries),
                    "executed_query_count": len(executed_queries),
                    "query_budget_units": 1,
                    "provider_query_expanded": len(executed_queries) > 1,
                    "raw_results": raw_results,
                    "tool_call_count": 1,
                    "provider_web_search_output_count": len(provider_calls),
                    "provider_open_page_count": provider_open_page_count,
                    "attempt_wall_seconds": attempt_wall_seconds,
                    "attempt_started_at_utc": attempt_started_at_utc,
                    "attempt_phases": attempt_phases,
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
                        "executed_queries": list(executed_queries),
                        "executed_query_count": len(executed_queries),
                        "query_budget_units": 1,
                        "provider_query_expanded": len(executed_queries) > 1,
                        "query_rewritten": executed_query.strip() != query.strip(),
                        "web_search_call_count": 1,
                        "provider_web_search_output_count": len(provider_calls),
                        "provider_open_page_count": provider_open_page_count,
                        "backend_raw_result_count": len(raw_results),
                        "raw_result_count": len(raw_results),
                        "results_discarded": False,
                        "retrieval_contract_status": "ACCEPTED_PROVIDER_EXPANSION" if len(executed_queries) > 1 else "ACCEPTED_SINGLE_QUERY",
                        "request_path": str(request_path),
                        "response_path": str(response_path),
                        "attempt_wall_seconds": attempt_wall_seconds,
                        "attempt_started_at_utc": attempt_started_at_utc,
                        "attempt_phases": attempt_phases,
                    },
                )
                return result
            except urllib.error.HTTPError as exc:
                last_error = exc
                last_status = exc.code
                phase["response_header_seconds"] = time.perf_counter() - attempt_started
                phase["phase_reached"] = "http_error_response"
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
            except GlobalStopError:
                raise
            except ConfigurationViolation as exc:
                last_error = exc
                error_detail = str(exc)[:1200]
                retryable = False
            except (json.JSONDecodeError, RuntimeError, ValueError) as exc:
                last_error = exc
                error_detail = str(exc)[:1200]
                retryable = False
            attempt_wall_seconds.append(time.perf_counter() - attempt_started)
            attempt_phases.append(phase)
            if retryable and attempt < max_attempts:
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
            failure_type = (
                "CONFIGURATION_VIOLATION"
                if isinstance(last_error, ConfigurationViolation)
                else classify_responses_search_error(last_error or RuntimeError(error_detail), last_status)
            )
            append_jsonl(
                self.log_path,
                {
                    "method": self.method,
                    "task_id": self.task_id,
                    "purpose": purpose,
                    "api": "responses",
                    "logical_call": call_id,
                    "requested_model": MODEL,
                    "actual_model": observed_actual_model,
                    "reasoning_effort": REASONING_EFFORT,
                    "temperature": TEMPERATURE,
                    "status": last_status if last_status is not None else "transport_error",
                    "upstream_attempts": attempt,
                    "usage": observed_usage,
                    "wall_seconds": elapsed,
                    "planned_query": query.strip(),
                    "web_search_call_count": observed_tool_call_count,
                    "error_type": type(last_error).__name__ if last_error else "UnknownError",
                    "failure_type": failure_type,
                    "error_detail": error_detail,
                    "retry_events": retry_events,
                    "request_path": str(request_path),
                    "response_path": str(response_path) if response_saved else None,
                    "attempt_wall_seconds": attempt_wall_seconds,
                    "attempt_started_at_utc": attempt_started_at_utc,
                    "attempt_phases": attempt_phases,
                },
            )
            if isinstance(last_error, ConfigurationViolation):
                raise last_error
            raise StrictAPIRequestError(
                f"strict Responses web search failed after {attempt} upstream attempt(s): "
                f"{type(last_error).__name__ if last_error else 'UnknownError'}: {error_detail}",
                attempt,
                last_status,
                failure_type,
            ) from last_error
        raise AssertionError("unreachable")


def summarize_calls(path: Path, *more_paths: Path) -> dict[str, Any]:
    rows = [row for current in (path, *more_paths) if current.is_file() for row in read_jsonl(current)]
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
    wall_seconds = sum(float(row.get("wall_seconds") or 0.0) for row in rows)
    calls = len(rows)
    return {
        "calls": calls,
        "upstream_attempts": sum(int(row.get("upstream_attempts") or 0) for row in rows),
        "prompt_tokens": prompt if usage_available else None,
        "completion_tokens": completion if usage_available else None,
        "total_tokens": total if usage_available else None,
        "usage_complete": usage_available,
        "wall_seconds": wall_seconds,
        "mean_call_latency_seconds": wall_seconds / calls if calls else None,
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
        ("solver_failure", "OUTPUT_CONTRACT_FAILURE"),
        ("output_contract_failure", "OUTPUT_CONTRACT_FAILURE"),
    )
    return next((status for key, status in priority if flags.get(key)), "OK")


def unified_output(
    *,
    method: str,
    phase: str,
    public: dict[str, Any],
    status: str | None = None,
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
    if status not in {None, "ABSTAIN", "RETRIEVAL_FAILURE"}:
        raise ValueError("explicit unified status must be ABSTAIN, RETRIEVAL_FAILURE, or None")
    non_decision_terminal = status in {"ABSTAIN", "RETRIEVAL_FAILURE"}
    if non_decision_terminal and any(value is not None for value in (decision_state, actions, objective)):
        raise ValueError(f"{status} must not claim a decision state, actions, or objective")
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
    if not non_decision_terminal and (actual_ids != expected_ids or any(not isinstance(item.get("value"), int) or isinstance(item.get("value"), bool) for item in actions or [])):
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
    if not non_decision_terminal and not objective_complete:
        normalized_flags["output_contract_failure"] = True
    normalized_applicability = applicability.get("applies") if isinstance(applicability, dict) else applicability
    if normalized_applicability is not None and not isinstance(normalized_applicability, bool):
        normalized_flags["output_contract_failure"] = True
    normalized_patch = patch if patch is not None else patch_elements
    if normalized_patch is not None and not isinstance(normalized_patch, list):
        normalized_flags["output_contract_failure"] = True
    if decision_state is not None and decision_state not in {"NO_SEARCH", "RETAIN", "PATCH_CHANGES"}:
        normalized_flags["output_contract_failure"] = True
    actual_models = (accounting or {}).get("actual_models") or []
    normalized_accounting = dict(accounting or {})
    calls = normalized_accounting.get("calls")
    if not isinstance(calls, int) or isinstance(calls, bool) or calls < 0:
        calls = 0
        normalized_accounting["calls"] = calls
    for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
        normalized_accounting.setdefault(name, None)
    call_wall = normalized_accounting.get("wall_seconds")
    if not isinstance(call_wall, (int, float)) or isinstance(call_wall, bool) or call_wall < 0:
        call_wall = 0.0
        normalized_accounting["wall_seconds"] = call_wall
    wall_total = normalized_accounting.get("wall_total_seconds")
    if not isinstance(wall_total, (int, float)) or isinstance(wall_total, bool) or wall_total < 0:
        wall_total = float(call_wall) if isinstance(call_wall, (int, float)) and not isinstance(call_wall, bool) else 0.0
        normalized_accounting["wall_total_seconds"] = wall_total
    if "mean_call_latency_seconds" not in normalized_accounting:
        normalized_accounting["mean_call_latency_seconds"] = (
            float(call_wall) / calls
            if calls > 0
            else None
        )
    total_tokens = normalized_accounting.get("total_tokens")
    normalized_accounting["tokens_per_second"] = (
        float(total_tokens) / float(wall_total)
        if isinstance(total_tokens, int) and not isinstance(total_tokens, bool) and wall_total > 0
        else None
    )
    return {
        "schema_version": "searchworthyor.v161.unified_output.v1",
        "eval_id": public["eval_id"],
        "input_digest": input_digest(),
        "configuration_digest": configuration_digest(),
        "method": method,
        "phase": phase,
        "attempt": attempt,
        "requested_configuration": {"model": MODEL, "reasoning_effort": REASONING_EFFORT, "temperature": TEMPERATURE},
        "actual_models": actual_models,
        "status": status or failure_status(normalized_flags),
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
        "accounting": normalized_accounting,
    }

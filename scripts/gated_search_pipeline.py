from __future__ import annotations

import json
import math
import re
import time
import traceback
from pathlib import Path
from typing import Any, Literal

from candidate_adapter import execute_candidate, normalize_actions_exact
from common import (
    EXPERIMENT_ROOT,
    ConfigurationViolation,
    GlobalStopError,
    StrictAPIClient,
    StrictAPIRequestError,
    extract_json_object,
    load_resumable_output,
    output_schema_for,
    public_cases,
    record_global_stop,
    shared_search_config,
    summarize_calls,
    unified_output,
    write_json,
)
from web_retrieval import PublicWebRetriever, RetrievalFailure, canonicalize_url, collapse_whitespace, verify_quote


Mode = Literal["direct", "search_first"]
RETRIEVAL_COMPLETE = "RETRIEVAL_COMPLETE"


def _strict_api_error_in_chain(exc: BaseException) -> StrictAPIRequestError | None:
    pending: list[BaseException] = [exc]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, StrictAPIRequestError):
            return current
        pending.extend(
            linked
            for linked in (current.__cause__, current.__context__)
            if isinstance(linked, BaseException)
        )
    return None


BASE_SYSTEM = """Build and solve the Base operations-research model from only the supplied public prompt_zh. Do not use web knowledge and do not anticipate a later Patch. Return exactly one JSON object without Markdown:
{
  "mathematical_model": {
    "variables": [{"id":"exact public action_id","domain":"binary/integer/continuous","meaning":"..."}],
    "objective": {"sense":"min or max","expression":"explicit mathematical expression","unit":"one accepted public unit"},
    "constraints": [{"name":"...","expression":"explicit mathematical relation","meaning":"..."}],
    "assumptions": ["only assumptions stated by the public task"]
  },
  "native_model_or_code": "self-contained Python using gurobipy",
  "actions": [{"id":"every public action_id in exact order","value":0}],
  "objective": {"sense":"min or max","value":0.0,"unit":"one accepted public unit"},
  "reasoning": "concise base-model explanation"
}
The Python must name decision variables exactly as the public action_ids and call optimize() exactly once. It must not read files, use the network, spawn subprocesses, or use hidden data."""

DIRECT_GATE_SYSTEM = """Decide whether this already-built and attempted Base OR model needs public-web search before the final decision. Use this simple boundary only:
NeedSearch = missing external real-world knowledge AND that knowledge could affect applicability, feasibility, a constraint, a parameter, the objective, or action mapping.
Return exactly one JSON object without Markdown:
{"search_needed":true,"trigger_reason":"...","external_unknowns":["specific unknown"],"first_query":"one concise authoritative-web query"}
Both branches must return exactly all four keys. If the predicate is false, return search_needed=false, a short non-empty trigger_reason, external_unknowns=[], and first_query=null. This is a simple one-shot baseline gate: do not use value-of-information, sensitivity analysis, Gold, private data, or benchmark IDs."""

SEARCH_FIRST_GATE_SYSTEM = """Using only the supplied public prompt_zh, decide whether public-web search is needed before any OR model is built. Do not formulate, summarize, assume, or solve a mathematical model in this step. Use this simple boundary only:
NeedSearch = missing external real-world knowledge AND that knowledge could affect applicability, feasibility, a constraint, a parameter, the objective, or action mapping.
Return exactly one JSON object without Markdown:
{"search_needed":true,"trigger_reason":"...","external_unknowns":["specific unknown"],"first_query":"one concise authoritative-web query"}
Both branches must return exactly all four keys. If the predicate is false, return search_needed=false, a short non-empty trigger_reason, external_unknowns=[], and first_query=null. This is a simple one-shot baseline gate: do not use value-of-information, sensitivity analysis, Gold, private data, benchmark IDs, or any prebuilt model."""

CONTINUATION_SYSTEM = """Generate one revised authoritative public-web query for an unresolved external-rule question. Return exactly {"query":"..."} without Markdown. The query must address the supplied failure or missing evidence, differ from every prior query, and stay concise. Use at most one site: operator. Never mention SearchWorthyOR, benchmark/task IDs, local paths, Gold, private data, output_schema, or oracle evidence. For Search-First, do not formulate or use a mathematical model."""

EVIDENCE_SYSTEM = """Select direct original text from the supplied newly opened public pages and judge the current evidence set with one weak global boolean. Return exactly one JSON object without Markdown:
{"pages":[{"url":"exact supplied final_url","quotes":["verbatim text from that page"]}],"evidence_sufficient":false,"missing_rule_reason":"...","next_query":"revised query or null"}
Each quote must occur verbatim under whitespace-only normalization in the supplied page text. Titles and search snippets are not evidence. Set evidence_sufficient=true only when the current verified evidence is enough to judge applicability and all model changes implicated by the external unknowns. If multiple rule questions remain, identify them in missing_rule_reason and make next_query target one unresolved question. Do not give the final optimization answer."""

DIRECT_FINAL_SYSTEM = """Complete the final Direct-v2 operations-research decision. You are given the public prompt, the formal Base model and Base solve attempt, retrieval diagnostics, and any verified verbatim web evidence. Patch only model elements justified by the evidence; if evidence is absent or incomplete, still build and solve the best defensible final model and explicitly reflect that limitation in reasoning. Return exactly one JSON object without Markdown:
{
  "decision_state":"NO_SEARCH or RETAIN or PATCH_CHANGES",
  "applicability":false,
  "patch":[],
  "mathematical_model":{"variables":[],"objective":{},"constraints":[],"assumptions":[]},
  "native_model_or_code":"self-contained Python using gurobipy",
  "declared_solver_status":"MODELLED",
  "actions":[{"id":"every public action_id in exact order","value":0}],
  "objective":{"sense":"min or max","value":0.0,"unit":"one accepted public unit"},
  "reasoning":"..."
}
NO_SEARCH is required when the Search Gate did not trigger and requires patch=[]. RETAIN requires a triggered search, applicability=false, and patch=[]. PATCH_CHANGES requires a triggered search, applicability=true, and a non-empty structural patch. The Python must name variables exactly as public action_ids, call optimize() exactly once, and use no files, network, subprocesses, or hidden data. Never fabricate evidence or Gold."""

SEARCH_FIRST_FINAL_SYSTEM = """Complete one Search-First Raw-NL operations-research modeling and solving request. No mathematical model was built before this call. Use the public prompt_zh plus retrieved_evidence_raw_nl, build the final model once, and solve it. If evidence is absent or incomplete, still build and solve the best defensible model and explicitly reflect that limitation in reasoning. Return exactly one JSON object without Markdown:
{
  "decision_state":"NO_SEARCH or RETAIN or PATCH_CHANGES",
  "applicability":false,
  "patch":[],
  "mathematical_model":{"variables":[],"objective":{},"constraints":[],"assumptions":[]},
  "native_model_or_code":"self-contained Python using gurobipy",
  "declared_solver_status":"MODELLED",
  "actions":[{"id":"every public action_id in exact order","value":0}],
  "objective":{"sense":"min or max","value":0.0,"unit":"one accepted public unit"},
  "reasoning":"..."
}
NO_SEARCH is required when the Search Gate did not trigger and requires patch=[]. RETAIN requires a triggered search, applicability=false, and patch=[]. PATCH_CHANGES requires a triggered search, applicability=true, and a non-empty structural patch. The Python must name variables exactly as public action_ids, call optimize() exactly once, and use no files, network, subprocesses, or hidden data. Never fabricate evidence or Gold."""


def validate_search_budget(search_count: int, readable_pages: int = 0, page_attempts: int = 0) -> None:
    config = shared_search_config()
    if not 0 <= search_count <= int(config["max_queries_per_case"]):
        raise ValueError("search count is outside the fixed zero-to-three budget")
    if not 0 <= readable_pages <= int(config["max_successful_pages_per_case"]):
        raise ValueError("readable-page count exceeds the fixed nine-page budget")
    if not 0 <= page_attempts <= int(config["max_page_attempts_per_case"]):
        raise ValueError("page-attempt count exceeds the fixed eighteen-attempt budget")


def validate_query(query: Any, public: dict[str, Any], previous: list[str] | None = None) -> str:
    if not isinstance(query, str):
        raise ValueError("query must be a string")
    value = collapse_whitespace(query)
    if not value:
        raise ValueError("query is empty")
    if "\ufffd" in value or value.encode("utf-8").decode("utf-8") != value:
        raise ValueError("query is not valid UTF-8")
    if len(value) > int(shared_search_config()["max_query_chars"]):
        raise ValueError("query exceeds the fixed character limit")
    lowered = value.lower()
    forbidden = ("searchworthyor", "swor-r", "gold", "oracle", "private", "prompt_zh", "output_schema", "problem_zh")
    if any(marker in lowered for marker in forbidden):
        raise ValueError("query contains a benchmark, private, Gold, or prompt marker")
    if public["eval_id"].lower() in lowered or re.search(r"(?i)\b[A-Z]:\\|\\\\|/private/|\.jsonl?\b", value):
        raise ValueError("query contains a task ID, local path, or data-file marker")
    if any(character in value for character in "{}[]"):
        raise ValueError("query contains JSON leakage")
    if len(re.findall(r"(?i)(?<!\w)site:", value)) > 1:
        raise ValueError("query contains more than one site: operator")
    if any(collapse_whitespace(item).casefold() == value.casefold() for item in previous or []):
        raise ValueError("query duplicates a prior query")
    return value


PROGRAMMATIC_NO_SEARCH_REASON = "PROGRAM: search_needed=false with no external unknown or query"


def parse_gate(value: dict[str, Any], public: dict[str, Any]) -> dict[str, Any]:
    needed = value.get("search_needed")
    reason = value.get("trigger_reason")
    unknowns = value.get("external_unknowns")
    first_query = value.get("first_query")
    if not isinstance(needed, bool) or not isinstance(unknowns, list):
        raise ValueError("Search Gate response has an invalid contract")
    if any(not isinstance(item, str) or not item.strip() for item in unknowns) or len(unknowns) > 10:
        raise ValueError("Search Gate external_unknowns are invalid")
    if needed:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Search Gate trigger_reason is required when search is triggered")
        if not unknowns:
            raise ValueError("Search Gate triggered without an external unknown")
        query = validate_query(first_query, public)
    else:
        if unknowns or first_query is not None:
            raise ValueError("Search Gate non-trigger must use external_unknowns=[] and first_query=null")
        if reason is None:
            reason = PROGRAMMATIC_NO_SEARCH_REASON
        elif not isinstance(reason, str) or not reason.strip():
            raise ValueError("Search Gate trigger_reason must be non-empty when supplied")
        query = None
    return {
        "status": "TRIGGERED" if needed else "NOT_TRIGGERED",
        "search_needed": needed,
        "trigger_reason": reason.strip(),
        "external_unknowns": [item.strip() for item in unknowns],
        "first_query": query,
    }


def validate_math_model(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["mathematical_model must be an object"]
    errors: list[str] = []
    if not isinstance(value.get("variables"), list) or not value["variables"]:
        errors.append("mathematical_model.variables must be non-empty")
    if not isinstance(value.get("constraints"), list):
        errors.append("mathematical_model.constraints must be a list")
    objective = value.get("objective")
    if not isinstance(objective, dict) or objective.get("sense") not in {"min", "max"} or not isinstance(objective.get("expression"), str):
        errors.append("mathematical_model.objective is invalid")
    if not isinstance(value.get("assumptions"), list):
        errors.append("mathematical_model.assumptions must be a list")
    return errors


def validate_actions(value: Any, output_schema: dict[str, Any]) -> list[dict[str, Any]] | None:
    if not isinstance(value, list) or len(value) != len(output_schema["actions"]):
        return None
    expected = [str(item["id"]) for item in output_schema["actions"]]
    actual = [str(item.get("id")) for item in value if isinstance(item, dict)]
    if actual != expected or len(actual) != len(value):
        return None
    normalized: list[dict[str, Any]] = []
    for spec, row in zip(output_schema["actions"], value):
        number = row.get("value")
        if not isinstance(number, int) or isinstance(number, bool):
            return None
        if str(spec.get("type", "")).upper() == "BINARY" and number not in {0, 1}:
            return None
        normalized.append({"id": str(spec["id"]), "value": number})
    return normalized


def validate_objective(value: Any, output_schema: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    number = value.get("value")
    if (
        not isinstance(number, (int, float))
        or isinstance(number, bool)
        or not math.isfinite(float(number))
        or value.get("sense") not in {"min", "max"}
        or value.get("unit") not in output_schema["objective"]["accepted_units"]
    ):
        return None
    return {"sense": value["sense"], "value": float(number), "unit": value["unit"]}


def parse_base(value: dict[str, Any], output_schema: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    errors = validate_math_model(value.get("mathematical_model"))
    code = value.get("native_model_or_code")
    if not isinstance(code, str) or not code.strip():
        errors.append("Base native_model_or_code is missing")
        code = None
    actions = validate_actions(value.get("actions"), output_schema)
    if actions is None:
        errors.append("Base actions are invalid")
    objective = validate_objective(value.get("objective"), output_schema)
    if objective is None:
        errors.append("Base objective is invalid")
    reasoning = value.get("reasoning")
    if not isinstance(reasoning, str) or not reasoning.strip():
        errors.append("Base reasoning is missing")
        reasoning = None
    return {
        "mathematical_model": value.get("mathematical_model") if isinstance(value.get("mathematical_model"), dict) else None,
        "native_model_or_code": code,
        "actions": actions,
        "objective": objective,
        "reasoning": reasoning,
    }, errors


def parse_final(value: dict[str, Any], output_schema: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    errors = validate_math_model(value.get("mathematical_model"))
    state = value.get("decision_state")
    applicability = value.get("applicability")
    patch = value.get("patch")
    if state not in {"NO_SEARCH", "RETAIN", "PATCH_CHANGES"}:
        errors.append("decision_state is invalid")
    if not isinstance(applicability, bool):
        errors.append("applicability must be boolean")
    if not isinstance(patch, list):
        errors.append("patch must be a list")
        patch = None
    if state == "NO_SEARCH" and patch != []:
        errors.append("NO_SEARCH requires patch=[]")
    if state == "RETAIN" and (applicability is not False or patch != []):
        errors.append("RETAIN requires applicability=false and patch=[]")
    if state == "PATCH_CHANGES" and (applicability is not True or not patch):
        errors.append("PATCH_CHANGES requires applicability=true and a non-empty patch")
    code = value.get("native_model_or_code")
    if not isinstance(code, str) or not code.strip():
        errors.append("final native_model_or_code is missing")
        code = None
    declared = value.get("declared_solver_status")
    if not isinstance(declared, str) or not declared.strip():
        errors.append("declared_solver_status is missing")
        declared = None
    actions = validate_actions(value.get("actions"), output_schema)
    if actions is None:
        errors.append("final actions are invalid")
    objective = validate_objective(value.get("objective"), output_schema)
    if objective is None:
        errors.append("final objective is invalid")
    reasoning = value.get("reasoning")
    if not isinstance(reasoning, str) or not reasoning.strip():
        errors.append("final reasoning is missing")
        reasoning = None
    return {
        "decision_state": state if state in {"NO_SEARCH", "RETAIN", "PATCH_CHANGES"} else None,
        "applicability": applicability if isinstance(applicability, bool) else None,
        "patch": patch,
        "mathematical_model": value.get("mathematical_model") if isinstance(value.get("mathematical_model"), dict) else None,
        "native_model_or_code": code,
        "declared_solver_status": declared,
        "actions": actions,
        "objective": objective,
        "reasoning": reasoning,
    }, errors


def execute_generated(code: str | None, output_schema: dict[str, Any], execution_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "attempted": False,
        "status": "MISSING_CODE",
        "solver_actions": None,
        "solver_objective": None,
    }
    if not isinstance(code, str) or not code.strip():
        return result
    execution_dir.mkdir(parents=True, exist_ok=False)
    result["attempted"] = True
    try:
        execution = execute_candidate(code, execution_dir)
    except (SyntaxError, ValueError) as exc:
        result.update({"status": "CODE_VALIDATION_FAILURE", "detail": f"{type(exc).__name__}: {exc}"})
        return result
    capture = execution.get("capture") if isinstance(execution, dict) else None
    solver_actions, mapping = normalize_actions_exact(output_schema["actions"], capture)
    objective_value = capture.get("objective") if isinstance(capture, dict) else None
    model_sense = capture.get("model_sense") if isinstance(capture, dict) else None
    solver_objective = None
    if isinstance(objective_value, (int, float)) and not isinstance(objective_value, bool) and math.isfinite(float(objective_value)):
        solver_objective = {
            "sense": "min" if model_sense == 1 else "max" if model_sense == -1 else None,
            "value": float(objective_value),
            "unit": None,
        }
    status = "EXECUTION_FAILURE"
    if execution.get("status") == "timeout":
        status = "TIMEOUT"
    elif execution.get("status") == "success" and isinstance(capture, dict):
        if capture.get("status") == 2 and solver_actions is not None:
            status = "OPTIMAL_EXACT_ACTION_MAPPING"
        elif capture.get("status") == 2:
            status = "OPTIMAL_ACTION_MAPPING_FAILED"
        else:
            status = f"SOLVER_STATUS_{capture.get('status')}"
    result.update(
        {
            "status": status,
            "returncode": execution.get("returncode"),
            "capture_status": capture.get("status") if isinstance(capture, dict) else None,
            "action_mapping": mapping,
            "solver_actions": solver_actions,
            "solver_objective": solver_objective,
            "stdout": execution.get("stdout"),
            "stderr": execution.get("stderr"),
        }
    )
    return result


def solver_authoritative_answer(
    final_fields: dict[str, Any], final_solve: dict[str, Any]
) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if final_solve.get("status") != "OPTIMAL_EXACT_ACTION_MAPPING":
        return None, None, ["final solver did not produce an optimal exact action mapping"]
    solver_actions = final_solve.get("solver_actions")
    solver_objective = final_solve.get("solver_objective")
    claimed_actions = final_fields.get("actions")
    claimed_objective = final_fields.get("objective")
    if not isinstance(solver_actions, list) or solver_actions != claimed_actions:
        errors.append("solver actions do not match claimed final actions")
    if not isinstance(solver_objective, dict) or not isinstance(claimed_objective, dict):
        errors.append("solver or claimed objective is missing")
        authoritative_objective = None
    else:
        solver_value = solver_objective.get("value")
        claimed_value = claimed_objective.get("value")
        objective_matches = (
            solver_objective.get("sense") == claimed_objective.get("sense")
            and isinstance(solver_value, (int, float))
            and isinstance(claimed_value, (int, float))
            and math.isclose(float(solver_value), float(claimed_value), rel_tol=1e-9, abs_tol=1e-8)
        )
        if not objective_matches:
            errors.append("solver objective does not match claimed final objective")
        authoritative_objective = (
            {
                "sense": solver_objective.get("sense"),
                "value": float(solver_value),
                "unit": claimed_objective.get("unit"),
            }
            if isinstance(solver_value, (int, float)) and solver_objective.get("sense") in {"min", "max"}
            else None
        )
    return solver_actions if isinstance(solver_actions, list) else None, authoritative_objective, errors


def extract_verified_evidence(
    value: dict[str, Any], pages: list[dict[str, Any]], round_index: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool, str, str | None]:
    rows = value.get("pages")
    sufficient = value.get("evidence_sufficient")
    missing_reason = value.get("missing_rule_reason")
    next_query = value.get("next_query")
    if not isinstance(rows, list) or not isinstance(sufficient, bool) or not isinstance(missing_reason, str):
        raise ValueError("evidence selection response has an invalid contract")
    if next_query is not None and not isinstance(next_query, str):
        raise ValueError("next_query must be a string or null")
    by_url = {canonicalize_url(str(page["final_url"])): page for page in pages}
    verified: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("url"), str) or not isinstance(row.get("quotes"), list):
            failures.append({"retrieval_round": round_index, "failure_type": "QUOTE_VERIFICATION_FAILURE", "detail": "invalid quote row"})
            continue
        source = by_url.get(canonicalize_url(row["url"]))
        if source is None:
            failures.append({"retrieval_round": round_index, "url": row["url"], "failure_type": "QUOTE_VERIFICATION_FAILURE", "detail": "URL was not opened in this round"})
            continue
        for quote in row["quotes"]:
            if isinstance(quote, str) and verify_quote(str(source["visible_text"]), quote):
                verified.append(
                    {
                        "requested_url": source["requested_url"],
                        "final_url": source["final_url"],
                        "publisher": source["publisher"],
                        "page_title": source["title"],
                        "quote": collapse_whitespace(quote),
                        "quote_verified": True,
                        "retrieval_round": round_index,
                    }
                )
            else:
                failures.append({"retrieval_round": round_index, "url": source["final_url"], "failure_type": "QUOTE_VERIFICATION_FAILURE", "detail": "quote is absent under whitespace-only normalization"})
    unique = list({(canonicalize_url(row["final_url"]), row["quote"]): row for row in verified}.values())
    if sufficient and not unique:
        sufficient = False
        failures.append({"retrieval_round": round_index, "failure_type": "QUOTE_VERIFICATION_FAILURE", "detail": "evidence_sufficient=true but no new quote verified"})
    normalized_next = collapse_whitespace(next_query) if isinstance(next_query, str) and next_query.strip() else None
    return unique, failures, sufficient, missing_reason.strip(), normalized_next


def continuation_query(
    client: StrictAPIClient,
    mode: Mode,
    public: dict[str, Any],
    external_unknowns: list[str],
    prior_queries: list[str],
    failure_reason: str,
    round_index: int,
) -> str:
    payload = {
        "pipeline": "Search-First prompt-only" if mode == "search_first" else "Direct-v2 model-aware",
        "public_prompt_zh": public["prompt_zh"],
        "external_unknowns": external_unknowns,
        "prior_queries": prior_queries,
        "failure_or_missing_evidence": failure_reason,
    }
    response = client.complete(
        [
            {"role": "system", "content": CONTINUATION_SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))},
        ],
        f"continuation_query_round_{round_index + 1}",
    )
    return validate_query(extract_json_object(response["content"]).get("query"), public, prior_queries)


def retrieval_status(gate: dict[str, Any], rounds: list[dict[str, Any]], pages: list[dict[str, Any]], evidence: list[dict[str, Any]], sufficient: bool) -> str:
    if gate.get("status") == "NOT_TRIGGERED":
        return "NOT_TRIGGERED"
    if gate.get("status") == "GATE_FAILURE":
        return "GATE_FAILURE"
    if sufficient and evidence:
        return RETRIEVAL_COMPLETE
    if evidence:
        return "RETRIEVAL_PARTIAL"
    if pages:
        return "EVIDENCE_INCOMPLETE"
    failure_types = [str(row.get("failure_type") or "") for row in rounds]
    attempts = [attempt for row in rounds for attempt in row.get("page_open_attempts", [])]
    if attempts:
        return "PAGE_OPEN_FAILURE"
    if any(value in {"SEARCH_EMPTY_RESULTS", "SEARCH_OPERATOR_VIOLATION"} for value in failure_types):
        return "NO_RELEVANT_RESULTS"
    if any(value.startswith("SEARCH_") for value in failure_types):
        return "SEARCH_BACKEND_FAILURE"
    return "EVIDENCE_INCOMPLETE"


def evidence_raw_nl(evidence: list[dict[str, Any]], status: str) -> str:
    if not evidence:
        return f"RETRIEVAL_STATUS: {status}\nNO_VERIFIED_WEB_EVIDENCE"
    blocks = []
    for index, row in enumerate(evidence, start=1):
        blocks.append(
            "\n".join(
                [
                    f"EVIDENCE_{index}",
                    f"SOURCE_URL: {row['final_url']}",
                    f"PUBLISHER: {row['publisher']}",
                    f"VERBATIM_EVIDENCE: {row['quote']}",
                ]
            )
        )
    return f"RETRIEVAL_STATUS: {status}\n\n" + "\n\n".join(blocks)


def decision_comparison(base: dict[str, Any], final: dict[str, Any]) -> dict[str, Any]:
    base_actions = base.get("actions")
    final_actions = final.get("actions")
    base_objective = base.get("objective")
    final_objective = final.get("objective")
    action_changed = isinstance(base_actions, list) and isinstance(final_actions, list) and base_actions != final_actions
    objective_changed = (
        isinstance(base_objective, dict)
        and isinstance(final_objective, dict)
        and (
            base_objective.get("sense") != final_objective.get("sense")
            or base_objective.get("unit") != final_objective.get("unit")
            or not math.isclose(float(base_objective.get("value")), float(final_objective.get("value")), rel_tol=1e-9, abs_tol=1e-8)
        )
    )
    observed = isinstance(base_actions, list) and isinstance(final_actions, list) and isinstance(base_objective, dict) and isinstance(final_objective, dict)
    return {
        "observed": observed,
        "action_changed": action_changed if observed else None,
        "objective_changed": objective_changed if observed else None,
        "decision_changed": (action_changed or objective_changed) if observed else None,
    }


def run_case(mode: Mode, phase: str, case_id: str, method: str, method_slug: str) -> dict[str, Any]:
    public = public_cases()[case_id]
    output_schema = output_schema_for(public)
    case_dir = EXPERIMENT_ROOT / "runs" / phase / method_slug / case_id
    output_path = case_dir / "unified_output.json"
    existing = load_resumable_output(output_path, eval_id=case_id, method=method, phase=phase)
    if existing is not None:
        return existing
    case_dir.mkdir(parents=True, exist_ok=True)
    interrupted = sorted(path for path in case_dir.glob("attempt_*") if path.is_dir())
    if interrupted:
        accounting = summarize_calls(interrupted[-1] / "api_calls.jsonl")
        output = unified_output(
            method=method,
            phase=phase,
            public=public,
            flags={"runner_failure": True},
            failure_detail="interrupted attempt exists without a terminal output; refusing another API call",
            native_artifacts={"attempt_dir": str(interrupted[-1])},
            accounting=accounting,
        )
        write_json(output_path, output)
        return output
    attempt_dir = case_dir / "attempt_1"
    attempt_dir.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    client = StrictAPIClient.from_environment(attempt_dir, method=method, task_id=case_id)
    search_config = shared_search_config()
    retriever = PublicWebRetriever(
        max_results=int(search_config["max_exposed_results_per_query"]),
        max_open=int(search_config["max_opened_pages_per_query"]),
        search_client=client,
    )

    stage_failures: list[dict[str, Any]] = []
    base: dict[str, Any] = {
        "mathematical_model": None,
        "native_model_or_code": None,
        "actions": None,
        "objective": None,
        "reasoning": None,
    }
    base_contract_errors: list[str] = []
    base_authoritative: dict[str, Any] = {"actions": None, "objective": None}
    base_solve = {"attempted": False, "status": "NOT_APPLICABLE" if mode == "search_first" else "NOT_STARTED"}
    base_stage_attempted = mode == "direct"
    base_stage_status = "NOT_APPLICABLE" if mode == "search_first" else "NOT_STARTED"
    base_stage_provider_failure = False
    base_stage_parse_failure = False
    base_stage_runner_failure = False
    gate: dict[str, Any] = {
        "status": "NOT_STARTED",
        "search_needed": False,
        "trigger_reason": None,
        "external_unknowns": [],
        "first_query": None,
    }
    gate_provider_failure = False
    gate_parse_failure = False
    gate_runner_failure = False

    if mode == "direct":
        try:
            base_response = client.complete(
                [
                    {"role": "system", "content": BASE_SYSTEM},
                    {"role": "user", "content": public["prompt_zh"]},
                ],
                "base_formulate_and_solve",
            )
            base_value = extract_json_object(base_response["content"])
            write_json(attempt_dir / "base_model_content.json", base_value)
            base, base_contract_errors = parse_base(base_value, output_schema)
            base_solve = execute_generated(base["native_model_or_code"], output_schema, attempt_dir / "base_model_execution")
            base_actions, base_objective, base_solver_errors = solver_authoritative_answer(base, base_solve)
            base_authoritative = {"actions": base_actions, "objective": base_objective}
            base_contract_errors.extend(base_solver_errors)
            base_stage_status = "COMPLETE" if not base_contract_errors else "OUTPUT_CONTRACT_FAILURE"
            if base_contract_errors:
                stage_failures.append(
                    {
                        "stage": "BASE_MODEL_SOLVE",
                        "type": "OUTPUT_CONTRACT_FAILURE",
                        "detail": "; ".join(base_contract_errors)[:1000],
                    }
                )
        except (ConfigurationViolation, GlobalStopError):
            raise
        except StrictAPIRequestError as exc:
            base_stage_provider_failure = True
            base_stage_status = "PROVIDER_FAILURE"
            stage_failures.append({"stage": "BASE_MODEL_SOLVE", "type": type(exc).__name__, "detail": str(exc)[:1000]})
            base_solve = {"attempted": False, "status": "BASE_PROVIDER_FAILURE", "detail": str(exc)[:1000]}
        except ValueError as exc:
            base_stage_parse_failure = True
            base_stage_status = "PARSE_FAILURE"
            stage_failures.append({"stage": "BASE_MODEL_SOLVE", "type": type(exc).__name__, "detail": str(exc)[:1000]})
            base_solve = {"attempted": False, "status": "BASE_PARSE_FAILURE", "detail": str(exc)[:1000]}
        except Exception as exc:
            base_stage_runner_failure = True
            base_stage_status = "RUNNER_FAILURE"
            stage_failures.append({"stage": "BASE_MODEL_SOLVE", "type": type(exc).__name__, "detail": str(exc)[:1000]})
            base_solve = {"attempted": False, "status": "BASE_STAGE_FAILURE", "detail": str(exc)[:1000]}

    base_stage_failed = mode == "direct" and base_stage_status != "COMPLETE"
    try:
        if not base_stage_failed:
            if mode == "direct":
                gate_payload = {
                    "public_prompt_zh": public["prompt_zh"],
                    "base_mathematical_model": base["mathematical_model"],
                    "base_model_actions": base["actions"],
                    "base_model_objective": base["objective"],
                    "base_solver_attempt": base_solve,
                    "base_contract_errors": base_contract_errors,
                }
                gate_system = DIRECT_GATE_SYSTEM
            else:
                gate_payload = {"public_prompt_zh": public["prompt_zh"]}
                gate_system = SEARCH_FIRST_GATE_SYSTEM
            gate_response = client.complete(
                [
                    {"role": "system", "content": gate_system},
                    {"role": "user", "content": json.dumps(gate_payload, ensure_ascii=False, separators=(",", ":"))},
                ],
                "search_gate",
            )
            gate = parse_gate(extract_json_object(gate_response["content"]), public)
    except (ConfigurationViolation, GlobalStopError):
        raise
    except StrictAPIRequestError as exc:
        gate_provider_failure = True
        gate = {
            "status": "GATE_FAILURE",
            "search_needed": False,
            "trigger_reason": f"{type(exc).__name__}: {str(exc)[:800]}",
            "external_unknowns": [],
            "first_query": None,
        }
        stage_failures.append({"stage": "SEARCH_GATE", "type": type(exc).__name__, "detail": str(exc)[:1000]})
    except ValueError as exc:
        gate_parse_failure = True
        gate = {
            "status": "GATE_FAILURE",
            "search_needed": False,
            "trigger_reason": f"{type(exc).__name__}: {str(exc)[:800]}",
            "external_unknowns": [],
            "first_query": None,
        }
        stage_failures.append({"stage": "SEARCH_GATE", "type": type(exc).__name__, "detail": str(exc)[:1000]})
    except Exception as exc:
        gate_runner_failure = True
        gate = {
            "status": "GATE_FAILURE",
            "search_needed": False,
            "trigger_reason": f"{type(exc).__name__}: {str(exc)[:800]}",
            "external_unknowns": [],
            "first_query": None,
        }
        stage_failures.append({"stage": "SEARCH_GATE", "type": type(exc).__name__, "detail": str(exc)[:1000]})

    gate_stage_failed = gate_provider_failure or gate_parse_failure or gate_runner_failure
    terminal_dependency_failure = base_stage_failed or gate_stage_failed
    search_provider_failure = False
    search_budget_units = 0
    queries: list[str] = []
    rounds: list[dict[str, Any]] = []
    all_results: list[dict[str, Any]] = []
    opened_pages: list[dict[str, Any]] = []
    page_attempts: list[dict[str, Any]] = []
    verified_evidence: list[dict[str, Any]] = []
    quote_failures: list[dict[str, Any]] = []
    evidence_sufficient = False
    missing_rule_reason = ""
    stop_reason = "SEARCH_GATE_NOT_TRIGGERED" if gate["status"] == "NOT_TRIGGERED" else gate["status"]
    query = gate.get("first_query")
    if gate.get("search_needed") is True and isinstance(query, str):
        for round_index in range(1, int(search_config["max_queries_per_case"]) + 1):
            round_started = time.perf_counter()
            queries.append(query)
            search_budget_units += 1
            round_row: dict[str, Any] = {
                "retrieval_round": round_index,
                "planned_query": query,
                "executed_query": None,
                "executed_queries": [],
                "query_budget_consumed": 1,
                "results_discarded": False,
                "query_rewritten": None,
                "search_backend": "shubiaobiao_responses_web_search",
                "backend_status": "NOT_STARTED",
                "search_results": [],
                "page_open_attempts": [],
                "readable_pages": [],
                "verified_quote_count": 0,
                "evidence_sufficient": False,
                "failure_type": None,
                "failure_detail": None,
                "stop_reason": None,
            }
            try:
                search = retriever.search(query)
                round_row.update(
                    {
                        "backend_status": "SUCCESS",
                        "executed_query": search["executed_query"],
                        "executed_queries": list(search["executed_queries"]),
                        "query_budget_consumed": 1,
                        "results_discarded": False,
                        "query_rewritten": search["query_rewritten"],
                        "search_actual_model": search["actual_model"],
                        "backend_raw_result_count": search["backend_raw_result_count"],
                        "normalized_raw_result_count": search["normalized_raw_result_count"],
                        "web_search_call_count": search["web_search_call_count"],
                    }
                )
                seen_results = {canonicalize_url(str(row["url"])) for row in all_results}
                new_results = []
                for result in search["results"]:
                    normalized = {**result, "retrieval_round": round_index}
                    if canonicalize_url(str(result["url"])) not in seen_results:
                        seen_results.add(canonicalize_url(str(result["url"])))
                        new_results.append(normalized)
                        all_results.append(normalized)
                round_row["search_results"] = new_results
                pages, attempts = retriever.open_top(new_results)
                for item in pages:
                    item["retrieval_round"] = round_index
                for item in attempts:
                    item["retrieval_round"] = round_index
                opened_pages.extend(pages)
                page_attempts.extend(attempts)
                round_row["page_open_attempts"] = attempts
                round_row["readable_pages"] = [
                    {key: page.get(key) for key in ("requested_url", "final_url", "title", "publisher", "content_type", "backend", "retrieval_round")}
                    for page in pages
                ]
                if not pages:
                    round_row["failure_type"] = "PAGE_OPEN_FAILURE"
                    round_row["failure_detail"] = "accepted search results produced no readable page"
                    missing_rule_reason = round_row["failure_detail"]
                else:
                    extraction_payload = {
                        "public_prompt_zh": public["prompt_zh"],
                        "external_unknowns": gate["external_unknowns"],
                        "planned_query": query,
                        "verified_evidence_so_far": verified_evidence,
                        "newly_opened_pages": [
                            {
                                "requested_url": page["requested_url"],
                                "final_url": page["final_url"],
                                "title": page["title"],
                                "publisher": page["publisher"],
                                "page_text": page["visible_text"][:16000],
                            }
                            for page in pages
                        ],
                    }
                    extraction_response = client.complete(
                        [
                            {"role": "system", "content": EVIDENCE_SYSTEM},
                            {"role": "user", "content": json.dumps(extraction_payload, ensure_ascii=False, separators=(",", ":"))},
                        ],
                        f"evidence_check_round_{round_index}",
                    )
                    selected, invalid, sufficient, missing_reason, proposed_query = extract_verified_evidence(
                        extract_json_object(extraction_response["content"]), pages, round_index
                    )
                    seen_evidence = {(canonicalize_url(row["final_url"]), row["quote"]) for row in verified_evidence}
                    newly_verified = 0
                    for row in selected:
                        key = (canonicalize_url(row["final_url"]), row["quote"])
                        if key not in seen_evidence:
                            seen_evidence.add(key)
                            verified_evidence.append(row)
                            newly_verified += 1
                    quote_failures.extend(invalid)
                    evidence_sufficient = sufficient
                    missing_rule_reason = missing_reason
                    round_row["verified_quote_count"] = newly_verified
                    round_row["evidence_sufficient"] = sufficient
                    round_row["missing_rule_reason"] = missing_reason
                    if sufficient:
                        stop_reason = "EVIDENCE_SUFFICIENT"
                        round_row["stop_reason"] = stop_reason
                        rounds.append({**round_row, "wall_seconds": time.perf_counter() - round_started})
                        break
                    if round_index < int(search_config["max_queries_per_case"]) and proposed_query:
                        query = validate_query(proposed_query, public, queries)
                        round_row["stop_reason"] = "NEXT_QUERY_FROM_EVIDENCE_CHECK"
                        rounds.append({**round_row, "wall_seconds": time.perf_counter() - round_started})
                        continue
            except StrictAPIRequestError as exc:
                search_provider_failure = True
                failure_stage = "EVIDENCE_CHECK" if round_row["backend_status"] == "SUCCESS" else "SEARCH_RETRIEVAL"
                round_row.update(
                    {
                        "failure_type": "SEARCH_PROVIDER_FAILURE",
                        "failure_detail": str(exc)[:1000],
                        "stop_reason": "SEARCH_PROVIDER_FAILURE",
                    }
                )
                stage_failures.append(
                    {"stage": failure_stage, "type": type(exc).__name__, "detail": str(exc)[:1000]}
                )
                stop_reason = "SEARCH_PROVIDER_FAILURE"
                rounds.append({**round_row, "wall_seconds": time.perf_counter() - round_started})
                break
            except RetrievalFailure as exc:
                provider_error = _strict_api_error_in_chain(exc)
                if provider_error is not None:
                    search_provider_failure = True
                    round_row.update(
                        {
                            "backend_status": "FAILURE",
                            "failure_type": "SEARCH_PROVIDER_FAILURE",
                            "failure_detail": str(provider_error)[:1000],
                            "stop_reason": "SEARCH_PROVIDER_FAILURE",
                        }
                    )
                    stage_failures.append(
                        {
                            "stage": "SEARCH_RETRIEVAL",
                            "type": type(provider_error).__name__,
                            "detail": str(provider_error)[:1000],
                        }
                    )
                    stop_reason = "SEARCH_PROVIDER_FAILURE"
                    rounds.append({**round_row, "wall_seconds": time.perf_counter() - round_started})
                    break
                round_row.update(
                    {
                        "backend_status": "FAILURE",
                        "failure_type": exc.failure_type,
                        "failure_detail": exc.detail,
                    }
                )
                if isinstance(exc.context, dict):
                    round_row["executed_query"] = exc.context.get("executed_query")
                    round_row["executed_queries"] = exc.context.get("executed_queries", [])
                    round_row["backend_raw_result_count"] = exc.context.get("backend_raw_result_count", 0)
                    round_row["normalized_raw_result_count"] = exc.context.get("normalized_raw_result_count", 0)
                    round_row["web_search_call_count"] = exc.context.get("web_search_call_count", 0)
                    round_row["search_actual_model"] = exc.context.get("actual_model")
                    round_row["results_discarded"] = exc.context.get("results_discarded", False)
                executed_query = round_row.get("executed_query")
                if isinstance(executed_query, str) and not round_row.get("executed_queries"):
                    round_row["executed_queries"] = [executed_query]
                round_row["query_budget_consumed"] = 1
                round_row["results_discarded"] = False
                missing_rule_reason = f"{exc.failure_type}: {exc.detail}"
            except (ConfigurationViolation, GlobalStopError):
                raise
            except Exception as exc:
                round_row.update(
                    {
                        "failure_type": "EVIDENCE_CHECK_FAILURE",
                        "failure_detail": f"{type(exc).__name__}: {str(exc)[:900]}",
                    }
                )
                missing_rule_reason = round_row["failure_detail"]

            if round_index < int(search_config["max_queries_per_case"]):
                try:
                    query = continuation_query(
                        client,
                        mode,
                        public,
                        gate["external_unknowns"],
                        queries,
                        missing_rule_reason or "evidence remains incomplete",
                        round_index,
                    )
                    round_row["stop_reason"] = "CONTINUATION_QUERY_TRIGGERED"
                    rounds.append({**round_row, "wall_seconds": time.perf_counter() - round_started})
                    continue
                except (ConfigurationViolation, GlobalStopError):
                    raise
                except StrictAPIRequestError as exc:
                    search_provider_failure = True
                    round_row.update(
                        {
                            "failure_before_continuation": {
                                "failure_type": round_row.get("failure_type"),
                                "failure_detail": round_row.get("failure_detail"),
                            },
                            "failure_type": "SEARCH_PROVIDER_FAILURE",
                            "failure_detail": str(exc)[:1000],
                            "stop_reason": "SEARCH_PROVIDER_FAILURE",
                        }
                    )
                    stage_failures.append(
                        {"stage": "CONTINUATION_QUERY", "type": type(exc).__name__, "detail": str(exc)[:1000]}
                    )
                    stop_reason = "SEARCH_PROVIDER_FAILURE"
                    rounds.append({**round_row, "wall_seconds": time.perf_counter() - round_started})
                    break
                except Exception as exc:
                    stage_failures.append({"stage": "CONTINUATION_QUERY", "type": type(exc).__name__, "detail": str(exc)[:1000]})
                    round_row["stop_reason"] = "NO_VALID_CONTINUATION_QUERY"
                    stop_reason = round_row["stop_reason"]
            else:
                round_row["stop_reason"] = "SEARCH_BUDGET_EXHAUSTED"
                stop_reason = round_row["stop_reason"]
            rounds.append({**round_row, "wall_seconds": time.perf_counter() - round_started})
            break

    current_retrieval_status = retrieval_status(gate, rounds, opened_pages, verified_evidence, evidence_sufficient)
    if search_provider_failure:
        current_retrieval_status = "SEARCH_PROVIDER_FAILURE"
    elif base_stage_failed:
        current_retrieval_status = "NOT_ATTEMPTED_BASE_FAILURE"
    raw_nl = evidence_raw_nl(verified_evidence, current_retrieval_status)
    final_fields: dict[str, Any] = {
        "decision_state": None,
        "applicability": None,
        "patch": None,
        "mathematical_model": None,
        "native_model_or_code": None,
        "declared_solver_status": None,
        "actions": None,
        "objective": None,
        "reasoning": None,
    }
    final_contract_errors: list[str] = []
    final_solve: dict[str, Any] = {"attempted": False, "status": "NOT_STARTED"}
    final_provider_failure = False
    final_parse_failure = False
    try:
        if terminal_dependency_failure:
            final_solve = {
                "attempted": False,
                "status": "SKIPPED_BASE_FAILURE" if base_stage_failed else "SKIPPED_GATE_FAILURE",
            }
        elif search_provider_failure:
            final_solve = {"attempted": False, "status": "SKIPPED_SEARCH_PROVIDER_FAILURE"}
        else:
            if mode == "direct":
                final_payload = {
                    "public_prompt_zh": public["prompt_zh"],
                    "base_model": base,
                    "base_solver_attempt": base_solve,
                    "search_gate": gate,
                    "retrieval_status": current_retrieval_status,
                    "evidence_sufficient": evidence_sufficient,
                    "verified_verbatim_evidence": verified_evidence,
                }
                final_system = DIRECT_FINAL_SYSTEM
            else:
                final_payload = {
                    "public_prompt_zh": public["prompt_zh"],
                    "search_gate": gate,
                    "retrieval_status": current_retrieval_status,
                    "evidence_sufficient": evidence_sufficient,
                    "retrieved_evidence_raw_nl": raw_nl,
                }
                final_system = SEARCH_FIRST_FINAL_SYSTEM
            final_response = client.complete(
                [
                    {"role": "system", "content": final_system},
                    {"role": "user", "content": json.dumps(final_payload, ensure_ascii=False, separators=(",", ":"))},
                ],
                "final_model_and_solve",
            )
            final_value = extract_json_object(final_response["content"])
            write_json(attempt_dir / "final_model_content.json", final_value)
            final_fields, final_contract_errors = parse_final(final_value, output_schema)
            if gate.get("search_needed") is False and final_fields["decision_state"] != "NO_SEARCH":
                final_contract_errors.append("a non-triggered Search Gate requires NO_SEARCH")
            if gate.get("search_needed") is True and final_fields["decision_state"] == "NO_SEARCH":
                final_contract_errors.append("a triggered Search Gate cannot return NO_SEARCH")
            final_solve = execute_generated(final_fields["native_model_or_code"], output_schema, attempt_dir / "final_model_execution")
    except (ConfigurationViolation, GlobalStopError):
        raise
    except StrictAPIRequestError as exc:
        final_provider_failure = True
        stage_failures.append({"stage": "FINAL_MODEL_SOLVE", "type": type(exc).__name__, "detail": str(exc)[:1000]})
        final_solve = {"attempted": False, "status": "FINAL_PROVIDER_FAILURE"}
    except ValueError as exc:
        final_parse_failure = True
        stage_failures.append({"stage": "FINAL_MODEL_SOLVE", "type": type(exc).__name__, "detail": str(exc)[:1000]})
        final_solve = {"attempted": False, "status": "FINAL_PARSE_FAILURE"}
    except Exception as exc:
        final_parse_failure = True
        stage_failures.append({"stage": "FINAL_MODEL_SOLVE", "type": type(exc).__name__, "detail": str(exc)[:1000]})
        (attempt_dir / "error_traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
        final_solve = {"attempted": False, "status": "FINAL_RUNNER_FAILURE"}

    solver_actions, solver_objective, solver_contract_errors = solver_authoritative_answer(final_fields, final_solve)
    final_contract_errors.extend(solver_contract_errors)

    validate_search_budget(search_budget_units, len(opened_pages), len(page_attempts))
    accounting = summarize_calls(attempt_dir / "api_calls.jsonl")
    accounting.update(
        {
            "search_count": search_budget_units,
            "search_round_count": len(queries),
            "page_open_attempt_count": len(page_attempts),
            "readable_page_count": len(opened_pages),
            "verified_quote_count": len(verified_evidence),
            "wall_total_seconds": time.perf_counter() - started,
        }
    )
    answer_present = isinstance(solver_actions, list) and isinstance(solver_objective, dict)
    retrieval_failed = (
        gate.get("search_needed") is True
        and not search_provider_failure
        and current_retrieval_status != RETRIEVAL_COMPLETE
    )
    flags = {
        "configuration_violation": False,
        "provider_failure": (
            final_provider_failure
            or base_stage_provider_failure
            or gate_provider_failure
            or search_provider_failure
        ),
        "runner_failure": base_stage_runner_failure or gate_runner_failure,
        "retrieval_failure": retrieval_failed,
        "parse_failure": base_stage_parse_failure or final_parse_failure or gate_parse_failure,
        "output_contract_failure": bool(final_contract_errors) or (mode == "direct" and bool(base_contract_errors)),
        "solver_failure": (
            final_solve.get("status") != "OPTIMAL_EXACT_ACTION_MAPPING" or (
                mode == "direct" and base_solve.get("status") != "OPTIMAL_EXACT_ACTION_MAPPING"
            )
        ),
    }
    search_summary = {
        "gate": gate,
        "query_attempted": bool(queries),
        "search_count": search_budget_units,
        "search_round_count": len(queries),
        "queries": queries,
        "executed_queries": [
            executed
            for row in rounds
            for executed in row.get("executed_queries", [])
        ],
        "search_backend": "shubiaobiao_responses_web_search",
        "backend_fallback": False,
        "rounds": rounds,
        "result_count": len(all_results),
        "page_open_attempt_count": len(page_attempts),
        "page_http_success_count": sum(isinstance(row.get("status"), int) and 200 <= row["status"] < 300 for row in page_attempts),
        "readable_page_count": len(opened_pages),
        "verified_quote_count": len(verified_evidence),
        "evidence_sufficient": evidence_sufficient,
        "retrieval_status": current_retrieval_status,
        "stop_reason": stop_reason,
        "pages": [
            {key: page.get(key) for key in ("requested_url", "final_url", "title", "publisher", "content_type", "backend", "retrieval_round")}
            for page in opened_pages
        ],
    }
    output = unified_output(
        method=method,
        phase=phase,
        public=public,
        status=None,
        search=search_summary,
        decision_state=final_fields["decision_state"],
        applicability=final_fields["applicability"],
        patch=final_fields["patch"],
        actions=solver_actions,
        objective=solver_objective,
        flags=flags,
        failure_detail="; ".join(item["detail"] for item in stage_failures[-3:]) or None,
        native_artifacts={"attempt_dir": str(attempt_dir)},
        accounting=accounting,
        solver_status=str(final_solve.get("status")),
    )
    output.update(
        {
            "answer_present": answer_present,
            "pipeline_mode": mode,
            "base_model": base if mode == "direct" else None,
            "base_authoritative_answer": base_authoritative if mode == "direct" else None,
            "base_model_contract_errors": base_contract_errors if mode == "direct" else [],
            "base_stage_attempted": base_stage_attempted,
            "base_stage_status": base_stage_status,
            "base_solve": base_solve,
            "search_gate": gate,
            "query_rounds": rounds,
            "search_results": all_results,
            "page_open_attempts": page_attempts,
            "verified_evidence": verified_evidence,
            "quote_verification_failures": quote_failures,
            "retrieved_evidence_raw_nl": raw_nl if mode == "search_first" else None,
            "retrieval_status": current_retrieval_status,
            "final_mathematical_model": final_fields["mathematical_model"],
            "final_declared_solver_status": final_fields["declared_solver_status"],
            "final_solve": final_solve,
            "final_contract_errors": final_contract_errors,
            "reasoning": final_fields["reasoning"],
            "decision_comparison": decision_comparison(
                {**base, **base_authoritative},
                {**final_fields, "actions": solver_actions, "objective": solver_objective},
            ) if mode == "direct" else None,
            "stage_failures": stage_failures,
        }
    )
    write_json(
        attempt_dir / "search_trace.json",
        {
            "search_gate": gate,
            "queries": queries,
            "query_rounds": rounds,
            "search_results": all_results,
            "page_open_attempts": page_attempts,
            "opened_pages": opened_pages,
            "verified_evidence": verified_evidence,
            "quote_verification_failures": quote_failures,
        },
    )
    write_json(output_path, output)
    return output

"""Thin runtime adapter between the shared Harness and SearchWorthy pipeline.

This file binds the strict provider/search services, owns per-attempt artifacts
and unified output, and delegates scientific state transitions to
``searchworthy.pipeline``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any


EXPERIMENT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_ROOT = EXPERIMENT_ROOT / "scripts"
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from common import (  # noqa: E402
    ConfigurationViolation,
    GlobalStopError,
    INFRASTRUCTURE_STATUSES,
    StrictAPIClient,
    StrictAPIRequestError,
    bounded_futures,
    load_config,
    load_resumable_output,
    output_schema_for,
    public_cases,
    record_global_stop,
    selected_ids,
    shared_search_config,
    summarize_calls,
    unified_output,
    validate_formal_gate,
    write_json,
)
from web_retrieval import PublicWebRetriever, RetrievalFailure  # noqa: E402

from searchworthy.contracts import EvidenceDecision, InitialDecision, PublicCase, RetrievalTrace  # noqa: E402
from searchworthy.pipeline import (  # noqa: E402
    PipelineServices,
    SearchBudgetOverrun,
    initial_modeling,
    propose_evidence,
    run_case as run_pipeline_case,
)


METHOD = "SearchWorthy"
METHOD_SLUG = "searchworthy"


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


def method_root(phase: str) -> Path:
    return EXPERIMENT_ROOT / "runs" / phase / METHOD_SLUG


def make_services(client: StrictAPIClient, retriever: PublicWebRetriever) -> PipelineServices:
    def llm_call(messages: list[dict[str, str]], purpose: str) -> dict[str, Any]:
        return client.complete(messages, purpose)

    def initial(public: PublicCase) -> InitialDecision:
        return initial_modeling(public, llm_call)

    def searcher(gap_id: str, query: str) -> RetrievalTrace:
        started = time.perf_counter()
        try:
            search = retriever.search(query)
            pages, attempts = retriever.open_top(search["results"])
            executed_query = search.get("executed_query")
            executed_queries = search.get("executed_queries")
            return RetrievalTrace(
                gap_id=gap_id,
                planned_query=query,
                query_attempted=True,
                executed_query=executed_query,
                executed_queries=list(executed_queries) if isinstance(executed_queries, list) else [],
                query_budget_consumed=1,
                results_discarded=False,
                backend_raw_result_count=int(search.get("backend_raw_result_count") or 0),
                results=search.get("results", []),
                opened_pages=pages,
                page_attempts=attempts,
                wall_seconds=time.perf_counter() - started,
            )
        except RetrievalFailure as exc:
            provider_error = _strict_api_error_in_chain(exc)
            if provider_error is not None:
                raise StrictAPIRequestError(
                    str(provider_error),
                    provider_error.upstream_attempts,
                    status=provider_error.status,
                    failure_type=provider_error.failure_type,
                ) from exc
            context = exc.context if isinstance(exc.context, dict) else {}
            executed_queries = context.get("executed_queries")
            if not isinstance(executed_queries, list) or any(not isinstance(item, str) for item in executed_queries):
                executed_queries = []
            query_budget_consumed = context.get("query_budget_consumed", 1)
            if not isinstance(query_budget_consumed, int) or isinstance(query_budget_consumed, bool) or query_budget_consumed < 1:
                query_budget_consumed = 1
            results_discarded = context.get("results_discarded") is True
            if not executed_queries and not results_discarded and isinstance(context.get("executed_query"), str):
                executed_queries = [context["executed_query"]]
            backend_raw_result_count = context.get("backend_raw_result_count", 0)
            if not isinstance(backend_raw_result_count, int) or isinstance(backend_raw_result_count, bool) or backend_raw_result_count < 0:
                backend_raw_result_count = 0
            return RetrievalTrace(
                gap_id=gap_id,
                planned_query=query,
                query_attempted=True,
                executed_query=context.get("executed_query"),
                executed_queries=executed_queries,
                query_budget_consumed=query_budget_consumed,
                results_discarded=results_discarded,
                backend_raw_result_count=backend_raw_result_count,
                # A RetrievalFailure from PublicWebRetriever.search means that
                # no normalized candidate passed the exposure gate.  Preserve
                # the backend count above for diagnostics, but never expose
                # rejected raw candidates to the Agent or count them as
                # returned results.
                results=[],
                failure_type=exc.failure_type,
                failure_detail=exc.detail,
                wall_seconds=time.perf_counter() - started,
            )

    def evidence_proposer(
        public: PublicCase,
        state: Any,
        gap_id: str,
        trace: RetrievalTrace,
        current_ir: dict[str, Any],
    ) -> EvidenceDecision:
        return propose_evidence(public, state, gap_id, trace, current_ir, llm_call)

    return PipelineServices(initial_modeler=initial, searcher=searcher, evidence_proposer=evidence_proposer)


def _failure_output(
    phase: str,
    public: dict[str, Any],
    case_dir: Path,
    started: float,
    flag: str,
    detail: str,
) -> dict[str, Any]:
    attempt_dir = case_dir / "attempt_1"
    accounting = summarize_calls(attempt_dir / "api_calls.jsonl")
    accounting["wall_total_seconds"] = time.perf_counter() - started
    result = unified_output(
        method=METHOD,
        phase=phase,
        public=public,
        flags={flag: True},
        failure_detail=detail[:2000],
        accounting=accounting,
        native_artifacts={"error_traceback": str(attempt_dir / "error_traceback.txt")},
    )
    # Provider/controller failure has no observed search-gate verdict.  Omitting
    # search_performed lets the scorer mark it NOT_OBSERVED rather than a false
    # NOT_TRIGGERED success.
    result["retrieval_status"] = "FAILURE"
    write_json(case_dir / "unified_output.json", result)
    return result


def run_one(phase: str, eval_id: str) -> dict[str, Any]:
    public = public_cases()[eval_id]
    case_dir = method_root(phase) / eval_id
    output_path = case_dir / "unified_output.json"
    resumable = load_resumable_output(output_path, eval_id=eval_id, method=METHOD, phase=phase)
    if resumable is not None:
        return resumable
    started = time.perf_counter()
    attempt_dir = case_dir / "attempt_1"
    if attempt_dir.exists():
        return _failure_output(
            phase,
            public,
            case_dir,
            started,
            "runner_failure",
            "incomplete prior attempt exists; no model/search call was retried",
        )
    attempt_dir.mkdir(parents=True, exist_ok=False)

    client = StrictAPIClient.from_environment(attempt_dir, method=METHOD, task_id=eval_id)
    search_config = shared_search_config()
    retriever = PublicWebRetriever(
        max_results=int(search_config["max_exposed_results_per_query"]),
        max_open=int(search_config["max_opened_pages_per_query"]),
        search_client=client,
    )
    try:
        case_result = run_pipeline_case(
            {"eval_id": eval_id, "prompt_zh": public["prompt_zh"]},
            output_schema_for(public),
            make_services(client, retriever),
        )
        state_path = case_dir / "searchworthy_state.json"
        base_ir_path = attempt_dir / "base_ir.json"
        ir_path = attempt_dir / "current_ir.json"
        write_json(state_path, case_result["state"])
        write_json(base_ir_path, case_result["base_ir"])
        write_json(ir_path, case_result["current_ir"])
        accounting = summarize_calls(client.log_path)
        accounting["wall_total_seconds"] = time.perf_counter() - started
        accounting["search_count"] = case_result["search"]["search_count"]
        accounting["search_round_count"] = case_result["search"]["search_round_count"]
        status = "ABSTAIN" if case_result["status"] == "ABSTAIN" else None
        result = unified_output(
            method=METHOD,
            phase=phase,
            public=public,
            status=status,
            search=case_result["search"],
            decision_state=case_result["decision_state"],
            applicability=case_result["applicability"],
            patch=case_result["patch"],
            actions=case_result["actions"],
            objective=case_result["objective"],
            solver_status=case_result["solver_status"],
            failure_detail=case_result["failure_detail"],
            native_artifacts={
                "searchworthy_state": str(state_path),
                "base_ir": str(base_ir_path),
                "current_ir": str(ir_path),
                "api_calls": str(client.log_path),
            },
            accounting=accounting,
        )
        result["search_performed"] = case_result["search_performed"]
        result["retrieval_status"] = case_result["retrieval_status"]
        write_json(output_path, result)
        return result
    except SearchBudgetOverrun as exc:
        detail = (
            f"{METHOD} {eval_id}: prior={exc.prior_budget}, "
            f"remaining={exc.remaining_budget}, actual={exc.actual_consumed}"
        )
        record_global_stop("SEARCH_BUDGET_OVERRUN", detail)
        raise GlobalStopError(detail) from exc
    except (ConfigurationViolation, GlobalStopError):
        raise
    except StrictAPIRequestError as exc:
        return _failure_output(phase, public, case_dir, started, "provider_failure", str(exc))
    except (ValueError, KeyError, TypeError) as exc:
        (attempt_dir / "error_traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
        return _failure_output(
            phase,
            public,
            case_dir,
            started,
            "output_contract_failure",
            f"{type(exc).__name__}: {exc}",
        )
    except Exception as exc:
        (attempt_dir / "error_traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
        return _failure_output(phase, public, case_dir, started, "runner_failure", f"{type(exc).__name__}: {exc}")


def summary(phase: str, ids: list[str]) -> dict[str, Any]:
    outputs: list[dict[str, Any]] = []
    for eval_id in ids:
        path = method_root(phase) / eval_id / "unified_output.json"
        if path.is_file():
            outputs.append(json.loads(path.read_text(encoding="utf-8")))
    status_counts: dict[str, int] = {}
    decision_counts: dict[str, int] = {}
    for output in outputs:
        status = str(output.get("status"))
        decision = str(output.get("decision_state"))
        status_counts[status] = status_counts.get(status, 0) + 1
        decision_counts[decision] = decision_counts.get(decision, 0) + 1
    return {
        "method": METHOD,
        "phase": phase,
        "expected": len(ids),
        "completed": len(outputs),
        "status_counts": status_counts,
        "decision_state_counts": decision_counts,
        "calls": sum(int((output.get("accounting") or {}).get("calls") or 0) for output in outputs),
        "total_tokens": sum(int((output.get("accounting") or {}).get("total_tokens") or 0) for output in outputs),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SearchWorthy on SearchWorthyOR V1.6.1")
    parser.add_argument("--phase", choices=["smoke", "formal"], required=True)
    parser.add_argument("--task-ids", default="")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    load_config()
    if args.phase == "formal":
        if args.task_ids:
            raise SystemExit("Formal SearchWorthy must run all fixed 360 cases; subsets are forbidden")
        validate_formal_gate()
    if not 1 <= args.workers <= 10:
        raise SystemExit("SearchWorthy workers must be between 1 and 10")
    ids = selected_ids(args.phase, args.task_ids)
    root = method_root(args.phase)
    root.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        submit = lambda eval_id: executor.submit(run_one, args.phase, eval_id)
        completed = 0
        for eval_id, future in bounded_futures(submit, ids, args.workers):
            if future.cancelled():
                continue
            try:
                output = future.result()
            except Exception as exc:
                record_global_stop("METHOD_WORKER_FAILURE", f"{METHOD} {eval_id}: {type(exc).__name__}: {exc}")
                raise
            completed += 1
            if args.phase == "formal" and output.get("status") in INFRASTRUCTURE_STATUSES:
                record_global_stop("FORMAL_INFRASTRUCTURE_TERMINAL", f"{METHOD} {eval_id}: {output.get('status')}")
                raise RuntimeError(f"{METHOD} infrastructure terminal for {eval_id}: {output.get('status')}")
            current = summary(args.phase, ids)
            write_json(root / "summary.json", current)
            print(json.dumps({"completed_now": completed, "eval_id": eval_id, **current}, ensure_ascii=False), flush=True)
    final = summary(args.phase, ids)
    write_json(root / "summary.json", final)
    print(json.dumps(final, ensure_ascii=False))
    return 0 if final["completed"] == len(ids) else 1


if __name__ == "__main__":
    raise SystemExit(main())

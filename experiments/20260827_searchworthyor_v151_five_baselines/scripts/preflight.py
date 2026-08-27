from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import EXPERIMENT_ROOT, StrictAPIClient, load_api_key, read_json, shared_search_config, write_json
from web_retrieval import PublicWebRetriever


ROOT = EXPERIMENT_ROOT / "preflight"
SUMMARY = ROOT / "summary.json"
QUERY = "site:ecfr.gov current 14 CFR 121.467 flight attendant rest requirements"


def main() -> None:
    if SUMMARY.is_file():
        value = read_json(SUMMARY)
        if value.get("status") == "PASS":
            print(json.dumps(value, ensure_ascii=False))
            return
        raise SystemExit("preflight artifacts already exist without PASS; refusing to overwrite")
    if ROOT.exists() and any(ROOT.iterdir()):
        raise SystemExit("preflight directory is non-empty; refusing to overwrite raw artifacts")
    ROOT.mkdir(parents=True, exist_ok=True)
    search_config = shared_search_config()

    def run_chat() -> tuple[dict, float]:
        started = time.perf_counter()
        client = StrictAPIClient.from_environment(ROOT / "chat", "preflight_chat", "NOT_BENCHMARK")
        result = client.complete(
            [{"role": "user", "content": "Return exactly this JSON object and nothing else: {\"status\":\"ok\"}"}],
            "chat_endpoint",
        )
        return result, started

    def run_search() -> tuple[dict, float]:
        started = time.perf_counter()
        client = StrictAPIClient.from_environment(ROOT / "hosted_search", "preflight_search", "NOT_BENCHMARK")
        retriever = PublicWebRetriever(
            max_results=int(search_config["max_exposed_results_per_query"]),
            max_open=int(search_config["max_opened_pages_per_query"]),
            search_client=client,
        )
        return retriever.search(QUERY), started

    with ThreadPoolExecutor(max_workers=2) as executor:
        chat_future = executor.submit(run_chat)
        search_future = executor.submit(run_search)
        chat, chat_started = chat_future.result()
        search, search_started = search_future.result()
    raw = search["raw_response"]
    reasoning = raw.get("reasoning") if isinstance(raw, dict) else None
    actual_effort = reasoning.get("effort") if isinstance(reasoning, dict) else None
    actual_temperature = raw.get("temperature") if isinstance(raw, dict) else None
    if actual_effort != "xhigh" or actual_temperature != 1:
        raise RuntimeError("Responses endpoint did not echo xhigh/temperature=1")
    if search.get("web_search_call_count") != 1 or not search.get("results"):
        raise RuntimeError("hosted search did not produce one compliant tool call with relevant results")
    if search.get("backend") != "shubiaobiao_responses_web_search":
        raise RuntimeError("hosted search backend changed")
    secret = load_api_key().encode("utf-8")
    leaked = []
    for path in ROOT.rglob("*"):
        if path.is_file() and secret in path.read_bytes():
            leaked.append(str(path.relative_to(ROOT)))
    if leaked:
        raise RuntimeError(f"API key leaked into preflight artifacts: {leaked}")
    summary = {
        "status": "PASS",
        "launched_concurrently": True,
        "launch_skew_seconds": abs(chat_started - search_started),
        "chat_actual_model": chat["actual_model"],
        "responses_actual_model": search["actual_model"],
        "reasoning_effort": actual_effort,
        "temperature": actual_temperature,
        "web_search_call_count": search["web_search_call_count"],
        "planned_query": search["planned_query"],
        "executed_query": search["executed_query"],
        "query_rewritten": search["query_rewritten"],
        "backend_raw_result_count": search["backend_raw_result_count"],
        "relevant_operator_compliant_results": len(search["results"]),
        "backend": search["backend"],
        "fallback_used": False,
        "api_key_leakage": 0,
    }
    write_json(SUMMARY, summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()

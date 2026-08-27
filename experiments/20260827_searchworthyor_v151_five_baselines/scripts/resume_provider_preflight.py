from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from common import EXPERIMENT_ROOT, StrictAPIClient, load_api_key, shared_search_config, write_json
from web_retrieval import PublicWebRetriever


QUERY = "site:ecfr.gov current 14 CFR 121.467 flight attendant rest requirements"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one exact-provider hosted-search probe before resuming a stopped experiment.")
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.label):
        raise ValueError("label must contain only ASCII letters, numbers, underscore, or hyphen")
    root = EXPERIMENT_ROOT / "preflight" / f"resume_{args.label}"
    summary_path = root / "summary.json"
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"refusing to overwrite resume preflight artifacts: {root}")
    config = shared_search_config()
    client = StrictAPIClient.from_environment(root / "hosted_search", "resume_provider_preflight", "NOT_BENCHMARK")
    retriever = PublicWebRetriever(
        max_results=int(config["max_exposed_results_per_query"]),
        max_open=int(config["max_opened_pages_per_query"]),
        search_client=client,
    )
    result = retriever.search(QUERY)
    raw = result["raw_response"]
    reasoning = raw.get("reasoning") if isinstance(raw, dict) else None
    effort = reasoning.get("effort") if isinstance(reasoning, dict) else None
    temperature = raw.get("temperature") if isinstance(raw, dict) else None
    if result.get("actual_model") != "gpt-5.6-luna" or effort != "xhigh" or temperature != 1:
        raise RuntimeError("resume provider probe did not echo the frozen model configuration")
    if result.get("web_search_call_count") != 1 or not result.get("results"):
        raise RuntimeError("resume provider probe did not produce one compliant hosted-search call")
    if result.get("backend") != "shubiaobiao_responses_web_search":
        raise RuntimeError("resume provider probe backend changed")
    secret = load_api_key().encode("utf-8")
    leaked = [str(path.relative_to(root)) for path in root.rglob("*") if path.is_file() and secret in path.read_bytes()]
    if leaked:
        raise RuntimeError(f"API key leaked into resume preflight artifacts: {leaked}")
    summary = {
        "status": "PASS",
        "label": args.label,
        "actual_model": result["actual_model"],
        "reasoning_effort": effort,
        "temperature": temperature,
        "web_search_call_count": result["web_search_call_count"],
        "planned_query": result["planned_query"],
        "executed_query": result["executed_query"],
        "query_rewritten": result["query_rewritten"],
        "relevant_operator_compliant_results": len(result["results"]),
        "backend": result["backend"],
        "fallback_used": False,
        "api_key_leakage": 0,
    }
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

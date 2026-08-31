from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT))
sys.path.insert(0, str(EXPERIMENT_ROOT / "scripts"))

import common
import web_retrieval
from searchworthy import run_searchworthy


QUERIES = ["fixture rule", "site:one.example fixture rule", "site:two.example fixture rule"]


class FakeHTTPResponse:
    def __init__(self, body: dict[str, object]):
        self.status = 200
        self.body = body

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def geturl(self) -> str:
        return f"{common.BASE_URL}{common.RESPONSES_ENDPOINT}"

    def read(self) -> bytes:
        return json.dumps(self.body).encode("utf-8")


def provider_response(result_count: int = 15) -> dict[str, object]:
    return {
        "model": common.MODEL,
        "status": "completed",
        "output": [
            {
                "type": "web_search_call",
                "action": {"type": "search", "query": QUERIES[0], "queries": QUERIES},
                "results": [
                    {
                        "title": f"fixture rule result {index}",
                        "url": f"https://example.com/rule/{index}",
                        "snippet": "fixture rule official applicability",
                    }
                    for index in range(result_count)
                ],
            }
        ],
        "usage": {"input_tokens": 8, "output_tokens": 5, "total_tokens": 13},
    }


class HostedSearchExpansionTests(unittest.TestCase):
    def test_http_200_provider_expansion_is_accepted_logged_once_and_charged_once(self) -> None:
        response_body = provider_response(15)
        with tempfile.TemporaryDirectory() as raw:
            client = common.StrictAPIClient("secret", Path(raw), "SearchWorthy", "fixture")
            with (
                patch.object(common, "check_global_stop"),
                patch.object(common, "record_global_stop") as record_stop,
                patch.object(
                    common._NO_REDIRECT_OPENER,
                    "open",
                    return_value=FakeHTTPResponse(response_body),
                ) as opener,
            ):
                response = client.web_search(QUERIES[0], purpose="responses_web_search")
            rows = common.read_jsonl(client.log_path)
            saved = common.read_json(Path(raw) / "llm_calls" / "0001_responses_web_search_response.json")

        self.assertEqual(opener.call_count, 1)
        record_stop.assert_not_called()
        self.assertEqual(saved, response_body)
        self.assertEqual(response["executed_queries"], QUERIES)
        self.assertEqual(response["query_budget_units"], 1)
        self.assertIs(response["provider_query_expanded"], True)
        self.assertEqual(len(response["raw_results"]), 15)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["retrieval_contract_status"], "ACCEPTED_PROVIDER_EXPANSION")
        self.assertEqual(row["executed_queries"], QUERIES)
        self.assertEqual(row["executed_query_count"], 3)
        self.assertEqual(row["query_budget_units"], 1)
        self.assertEqual(row["backend_raw_result_count"], 15)
        self.assertIs(row["results_discarded"], False)

    def test_retriever_exposes_at_most_ten_results_and_preserves_provider_queries(self) -> None:
        class ExpansionClient:
            def web_search(self, query: str, purpose: str) -> dict[str, object]:
                del purpose
                body = provider_response(15)
                return {
                    "raw": body,
                    "executed_query": query,
                    "executed_queries": list(QUERIES),
                    "raw_results": body["output"][0]["results"],
                    "retry_events": [],
                    "tool_call_count": 1,
                    "actual_model": common.MODEL,
                }

        retriever = web_retrieval.PublicWebRetriever(max_results=10, search_client=ExpansionClient())
        result = retriever.search(QUERIES[0])

        self.assertEqual(len(result["results"]), 10)
        self.assertEqual(result["exposed_result_count"], 10)
        self.assertEqual(result["backend_raw_result_count"], 15)
        self.assertEqual(result["executed_queries"], QUERIES)
        self.assertEqual(result["executed_query_count"], 3)
        self.assertEqual(result["query_budget_consumed"], 1)
        self.assertIs(result["provider_query_expanded"], True)
        self.assertIs(result["results_discarded"], False)

    def test_searchworthy_trace_charges_one_round_and_keeps_expansion_diagnostic(self) -> None:
        results = [{"url": "https://example.com/rule", "title": "fixture rule", "snippet": "fixture"}]

        class ExpansionRetriever:
            def search(self, query: str) -> dict[str, object]:
                return {
                    "executed_query": query,
                    "executed_queries": list(QUERIES),
                    "backend_raw_result_count": 15,
                    "results": results,
                }

            def open_top(self, rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
                self.last_rows = rows
                return [], []

        services = run_searchworthy.make_services(SimpleNamespace(), ExpansionRetriever())
        trace = services.searcher("G1", QUERIES[0])

        self.assertEqual(trace.executed_queries, QUERIES)
        self.assertEqual(trace.query_budget_consumed, 1)
        self.assertIs(trace.results_discarded, False)
        self.assertEqual(trace.backend_raw_result_count, 15)
        self.assertEqual(trace.results, results)
        self.assertIsNone(trace.failure_type)


if __name__ == "__main__":
    unittest.main()

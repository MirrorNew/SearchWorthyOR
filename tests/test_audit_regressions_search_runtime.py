from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT))
sys.path.insert(0, str(EXPERIMENT_ROOT / "scripts"))

import common
import gated_search_pipeline
from searchworthy import run_searchworthy
from searchworthy.pipeline import SearchBudgetOverrun
from web_retrieval import RetrievalFailure


EVAL_ID = "SWOR-E-RUNTIME-FAILURE"
SCHEMA = {
    "actions": [{"id": "x", "type": "BINARY"}],
    "objective": {"accepted_units": {"unit": 1}, "canonical_unit": "unit"},
}
PUBLIC = {
    "eval_id": EVAL_ID,
    "prompt_zh": "fixture\n\n公开 output_schema：\n" + json.dumps(SCHEMA, ensure_ascii=False),
}
BASE_VALUE = {
    "mathematical_model": {
        "variables": [{"id": "x"}],
        "constraints": [],
        "objective": {"sense": "max", "expression": "x"},
        "assumptions": [],
    },
    "native_model_or_code": "fixture",
    "actions": [{"id": "x", "value": 1}],
    "objective": {"sense": "max", "value": 1, "unit": "unit"},
    "reasoning": "fixture",
}
FINAL_VALUE = {
    "decision_state": "RETAIN",
    "applicability": False,
    "patch": [],
    "mathematical_model": BASE_VALUE["mathematical_model"],
    "native_model_or_code": "fixture",
    "declared_solver_status": "MODELLED",
    "actions": [{"id": "x", "value": 1}],
    "objective": {"sense": "max", "value": 1, "unit": "unit"},
    "reasoning": "fixture",
}
SOLVED = {
    "attempted": True,
    "status": "OPTIMAL_EXACT_ACTION_MAPPING",
    "solver_actions": [{"id": "x", "value": 1}],
    "solver_objective": {"sense": "max", "value": 1.0, "unit": None},
}
GATE_VALUE = {
    "search_needed": True,
    "trigger_reason": "an external rule may change the model",
    "external_unknowns": ["external rule"],
    "first_query": "official external rule",
}


def search_config(max_queries: int) -> dict[str, int]:
    return {
        "max_queries_per_case": max_queries,
        "max_query_chars": 500,
        "max_exposed_results_per_query": 10,
        "max_opened_pages_per_query": 3,
        "max_successful_pages_per_case": 9,
        "max_page_attempts_per_case": 18,
    }


def successful_search(
    query: str,
    round_index: int = 1,
    executed_queries: list[str] | None = None,
) -> dict[str, object]:
    result = {
        "url": f"https://authority.example/rule-{round_index}",
        "title": "Official rule",
        "snippet": "external rule",
    }
    return {
        "executed_query": query,
        "executed_queries": list(executed_queries or [query]),
        "query_budget_consumed": 1,
        "results_discarded": False,
        "query_rewritten": False,
        "actual_model": "fixture-model",
        "backend_raw_result_count": 1,
        "normalized_raw_result_count": 1,
        "web_search_call_count": 1,
        "results": [result],
    }


class ScenarioRetriever:
    def __init__(self, scenario: str):
        self.scenario = scenario
        self.search_calls = 0

    def search(self, query: str) -> dict[str, object]:
        self.search_calls += 1
        if self.scenario == "provider_direct":
            raise common.StrictAPIRequestError(
                "hosted search unavailable",
                2,
                status=503,
                failure_type="SEARCH_BACKEND_FAILURE",
            )
        if self.scenario == "provider" or (self.scenario == "provider_second" and self.search_calls == 2):
            try:
                raise common.StrictAPIRequestError(
                    "hosted search unavailable",
                    2,
                    status=503,
                    failure_type="SEARCH_BACKEND_FAILURE",
                )
            except common.StrictAPIRequestError as exc:
                raise RetrievalFailure("SEARCH_BACKEND_FAILURE", "wrapped provider failure", status=503) from exc
        if self.scenario in {"empty", "provider_second"} or (
            self.scenario == "query_expansion_second"
            and self.search_calls == 1
        ):
            raise RetrievalFailure(
                "SEARCH_EMPTY_RESULTS",
                "no relevant allowed result",
                status=200,
                context={
                    "executed_query": query,
                    "executed_queries": [query],
                    "query_budget_consumed": 1,
                    "results_discarded": False,
                    "backend_raw_result_count": 0,
                },
            )
        if self.scenario == "operator":
            raise RetrievalFailure(
                "SEARCH_OPERATOR_VIOLATION",
                "no operator-compliant result",
                status=200,
                context={
                    "executed_query": query,
                    "executed_queries": [query],
                    "query_budget_consumed": 1,
                    "results_discarded": False,
                    "backend_raw_result_count": 1,
                },
            )
        if self.scenario in {"query_expansion", "query_expansion_second"}:
            extra_queries = ["provider query two"] if self.scenario == "query_expansion_second" else [
                "provider query two", "provider query three"
            ]
            return successful_search(query, self.search_calls, [query, *extra_queries])
        return successful_search(query, self.search_calls)

    def open_top(self, results: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        if self.scenario == "page":
            return [], [{"requested_url": results[0]["url"], "status": 503}]
        page = {
            "requested_url": results[0]["url"],
            "final_url": results[0]["url"],
            "title": "Official rule",
            "publisher": "authority.example",
            "content_type": "text/html",
            "backend": "direct_http",
            "visible_text": "The external rule applies to this case.",
        }
        return [page], [{"requested_url": results[0]["url"], "status": 200}]


class ExceptionRetriever:
    def __init__(self, error: RetrievalFailure):
        self.error = error

    def search(self, query: str) -> dict[str, object]:
        del query
        raise self.error

    def open_top(self, results: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        del results
        raise AssertionError("open_top must not run after a search failure")


class FakeClient:
    def __init__(self, provider_failure_purpose: str | None = None, *, forbid_final: bool = False):
        self.provider_failure_purpose = provider_failure_purpose
        self.forbid_final = forbid_final
        self.calls: list[str] = []

    def complete(self, messages: list[dict[str, str]], purpose: str) -> dict[str, str]:
        del messages
        self.calls.append(purpose)
        if purpose == "base_formulate_and_solve":
            return {"content": json.dumps(BASE_VALUE)}
        if purpose == "search_gate":
            return {"content": json.dumps(GATE_VALUE)}
        if purpose == self.provider_failure_purpose:
            raise common.StrictAPIRequestError(f"{purpose} unavailable", 2, status=503)
        if purpose.startswith("evidence_check_round_"):
            return {
                "content": json.dumps(
                    {
                        "pages": [],
                        "evidence_sufficient": False,
                        "missing_rule_reason": "evidence remains incomplete",
                        "next_query": None,
                    }
                )
            }
        if purpose.startswith("continuation_query_round_"):
            return {"content": json.dumps({"query": f"revised official external rule {purpose}"})}
        if purpose == "final_model_and_solve":
            if self.forbid_final:
                raise AssertionError("Final must not run after a search provider failure")
            return {"content": json.dumps(FINAL_VALUE)}
        raise AssertionError(f"unexpected purpose: {purpose}")


class SearchRuntimeRegressionTests(unittest.TestCase):
    def run_pipeline(
        self,
        mode: str,
        retriever: ScenarioRetriever,
        client: FakeClient,
        *,
        max_queries: int,
    ) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as raw:
            with (
                patch.object(gated_search_pipeline, "EXPERIMENT_ROOT", Path(raw)),
                patch.object(gated_search_pipeline, "public_cases", return_value={EVAL_ID: PUBLIC}),
                patch.object(gated_search_pipeline, "shared_search_config", return_value=search_config(max_queries)),
                patch.object(gated_search_pipeline.StrictAPIClient, "from_environment", return_value=client),
                patch.object(gated_search_pipeline, "PublicWebRetriever", return_value=retriever),
                patch.object(gated_search_pipeline, "execute_generated", return_value=SOLVED),
            ):
                return gated_search_pipeline.run_case(
                    mode,
                    "smoke",
                    EVAL_ID,
                    "Direct-v2" if mode == "direct" else "Search-First",
                    mode,
                )

    def test_searchworthy_unwraps_provider_failure_but_keeps_semantic_failure_as_trace(self) -> None:
        provider_services = run_searchworthy.make_services(object(), ScenarioRetriever("provider"))
        with self.assertRaises(common.StrictAPIRequestError):
            provider_services.searcher("G1", "official external rule")

        semantic_services = run_searchworthy.make_services(object(), ScenarioRetriever("empty"))
        trace = semantic_services.searcher("G1", "official external rule")
        self.assertEqual(trace.failure_type, "SEARCH_EMPTY_RESULTS")
        self.assertTrue(trace.query_attempted)

        context_provider = common.StrictAPIRequestError("context provider failure", 1, status=503)
        context_wrapped = RetrievalFailure("SEARCH_BACKEND_FAILURE", "implicit context wrapper")
        context_wrapped.__context__ = context_provider
        context_provider.__context__ = context_wrapped
        context_services = run_searchworthy.make_services(object(), ExceptionRetriever(context_wrapped))
        with self.assertRaises(common.StrictAPIRequestError):
            context_services.searcher("G1", "official external rule")

        semantic_cycle = RetrievalFailure("SEARCH_EMPTY_RESULTS", "semantic cycle")
        semantic_cycle.__context__ = semantic_cycle
        cycle_services = run_searchworthy.make_services(object(), ExceptionRetriever(semantic_cycle))
        cycle_trace = cycle_services.searcher("G1", "official external rule")
        self.assertEqual(cycle_trace.failure_type, "SEARCH_EMPTY_RESULTS")

    def test_all_search_api_stages_stop_both_baselines_before_final(self) -> None:
        scenarios = (
            ("retriever_wrapped", "provider", None, "SEARCH_RETRIEVAL"),
            ("retriever_direct", "provider_direct", None, "SEARCH_RETRIEVAL"),
            ("evidence", "success", "evidence_check_round_1", "EVIDENCE_CHECK"),
            ("continuation", "empty", "continuation_query_round_2", "CONTINUATION_QUERY"),
        )
        for mode in ("direct", "search_first"):
            for label, retriever_scenario, failure_purpose, expected_stage in scenarios:
                with self.subTest(mode=mode, stage=label):
                    retriever = ScenarioRetriever(retriever_scenario)
                    client = FakeClient(failure_purpose, forbid_final=True)
                    output = self.run_pipeline(mode, retriever, client, max_queries=3)
                    self.assertEqual(output["status"], "PROVIDER_FAILURE")
                    self.assertTrue(output["failure_flags"]["provider_failure"])
                    self.assertFalse(output["failure_flags"]["retrieval_failure"])
                    self.assertEqual(output["retrieval_status"], "SEARCH_PROVIDER_FAILURE")
                    self.assertEqual(output["final_solve"]["status"], "SKIPPED_SEARCH_PROVIDER_FAILURE")
                    self.assertNotIn("final_model_and_solve", client.calls)
                    self.assertEqual(output["stage_failures"][-1]["stage"], expected_stage)
                    self.assertEqual(retriever.search_calls, 1)
                    self.assertEqual(len(output["query_rounds"]), 1)
                    continuation_calls = [purpose for purpose in client.calls if purpose.startswith("continuation_query_")]
                    self.assertEqual(len(continuation_calls), 1 if label == "continuation" else 0)

    def test_second_round_provider_failure_is_terminal_and_not_overwritten(self) -> None:
        scenarios = (
            ("retriever", "provider_second", None, "SEARCH_RETRIEVAL"),
            ("evidence", "success", "evidence_check_round_2", "EVIDENCE_CHECK"),
        )
        for mode in ("direct", "search_first"):
            for label, retriever_scenario, failure_purpose, expected_stage in scenarios:
                with self.subTest(mode=mode, stage=label):
                    retriever = ScenarioRetriever(retriever_scenario)
                    client = FakeClient(failure_purpose, forbid_final=True)
                    output = self.run_pipeline(mode, retriever, client, max_queries=3)
                    self.assertEqual(output["status"], "PROVIDER_FAILURE")
                    self.assertTrue(output["failure_flags"]["provider_failure"])
                    self.assertEqual(output["retrieval_status"], "SEARCH_PROVIDER_FAILURE")
                    self.assertEqual(output["final_solve"]["status"], "SKIPPED_SEARCH_PROVIDER_FAILURE")
                    self.assertNotIn("final_model_and_solve", client.calls)
                    self.assertEqual(retriever.search_calls, 2)
                    self.assertEqual(len(output["query_rounds"]), 2)
                    self.assertNotEqual(output["query_rounds"][0]["failure_type"], "SEARCH_PROVIDER_FAILURE")
                    self.assertEqual(output["query_rounds"][1]["failure_type"], "SEARCH_PROVIDER_FAILURE")
                    self.assertEqual(output["stage_failures"][-1]["stage"], expected_stage)

    def test_semantic_search_failures_remain_retrieval_failures_and_allow_final(self) -> None:
        scenarios = (
            ("empty", "NO_RELEVANT_RESULTS"),
            ("operator", "NO_RELEVANT_RESULTS"),
            ("page", "PAGE_OPEN_FAILURE"),
        )
        for mode in ("direct", "search_first"):
            for scenario, expected_status in scenarios:
                with self.subTest(mode=mode, scenario=scenario):
                    client = FakeClient()
                    output = self.run_pipeline(mode, ScenarioRetriever(scenario), client, max_queries=1)
                    self.assertEqual(output["status"], "OK")
                    self.assertFalse(output["failure_flags"]["provider_failure"])
                    self.assertTrue(output["failure_flags"]["retrieval_failure"])
                    self.assertEqual(output["retrieval_status"], expected_status)
                    self.assertEqual(output["final_solve"]["status"], "OPTIMAL_EXACT_ACTION_MAPPING")
                    self.assertIn("final_model_and_solve", client.calls)
                    round_row = output["query_rounds"][0]
                    self.assertEqual(round_row["executed_queries"], [round_row["executed_query"]])
                    self.assertEqual(round_row["query_budget_consumed"], 1)
                    self.assertIs(round_row["results_discarded"], False)
                    self.assertIsInstance(round_row["backend_raw_result_count"], int)
                    self.assertEqual(output["search"]["executed_queries"], round_row["executed_queries"])

    def test_provider_expansion_is_one_call_one_budget_and_allows_evidence_and_final(self) -> None:
        for mode in ("direct", "search_first"):
            with self.subTest(mode=mode):
                client = FakeClient()
                retriever = ScenarioRetriever("query_expansion")
                output = self.run_pipeline(mode, retriever, client, max_queries=1)

                self.assertEqual(output["status"], "OK")
                self.assertFalse(output["failure_flags"]["provider_failure"])
                self.assertTrue(output["failure_flags"]["retrieval_failure"])
                self.assertEqual(output["retrieval_status"], "EVIDENCE_INCOMPLETE")
                self.assertEqual(output["final_solve"]["status"], "OPTIMAL_EXACT_ACTION_MAPPING")
                self.assertEqual(output["search"]["search_count"], 1)
                self.assertEqual(output["search"]["search_round_count"], 1)
                self.assertEqual(output["search"]["result_count"], 1)
                self.assertEqual(output["search"]["readable_page_count"], 1)
                self.assertEqual(output["search"]["verified_quote_count"], 0)
                self.assertEqual(len(output["query_rounds"]), 1)
                self.assertEqual(output["query_rounds"][0]["query_budget_consumed"], 1)
                self.assertFalse(output["query_rounds"][0]["results_discarded"])
                self.assertEqual(len(output["query_rounds"][0]["executed_queries"]), 3)
                self.assertEqual(retriever.search_calls, 1)
                self.assertTrue(any(purpose.startswith("evidence_check_") for purpose in client.calls))
                self.assertFalse(any(purpose.startswith("continuation_query_") for purpose in client.calls))
                self.assertIn("final_model_and_solve", client.calls)

    def test_second_round_provider_expansion_uses_two_total_call_units(self) -> None:
        for mode in ("direct", "search_first"):
            with self.subTest(mode=mode):
                client = FakeClient()
                retriever = ScenarioRetriever("query_expansion_second")
                output = self.run_pipeline(mode, retriever, client, max_queries=2)

                self.assertEqual(output["status"], "OK")
                self.assertEqual(output["search"]["search_count"], 2)
                self.assertEqual(output["search"]["search_round_count"], 2)
                self.assertEqual([row["query_budget_consumed"] for row in output["query_rounds"]], [1, 1])
                self.assertFalse(output["query_rounds"][-1]["results_discarded"])
                self.assertEqual(len(output["query_rounds"][-1]["executed_queries"]), 2)
                self.assertEqual(retriever.search_calls, 2)
                self.assertEqual(
                    len([purpose for purpose in client.calls if purpose.startswith("continuation_query_")]),
                    1,
                )
                self.assertTrue(any(purpose.startswith("evidence_check_") for purpose in client.calls))
                self.assertIn("final_model_and_solve", client.calls)

    def test_three_expanded_provider_calls_stay_within_three_call_budget(self) -> None:
        for mode in ("direct", "search_first"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as raw:
                client = FakeClient()
                retriever = ScenarioRetriever("query_expansion")
                with (
                    patch.object(gated_search_pipeline, "EXPERIMENT_ROOT", Path(raw)),
                    patch.object(gated_search_pipeline, "public_cases", return_value={EVAL_ID: PUBLIC}),
                    patch.object(gated_search_pipeline, "shared_search_config", return_value=search_config(3)),
                    patch.object(gated_search_pipeline.StrictAPIClient, "from_environment", return_value=client),
                    patch.object(gated_search_pipeline, "PublicWebRetriever", return_value=retriever),
                    patch.object(gated_search_pipeline, "execute_generated", return_value=SOLVED),
                    patch.object(gated_search_pipeline, "record_global_stop") as record_stop,
                ):
                    output = gated_search_pipeline.run_case(
                        mode,
                        "smoke",
                        EVAL_ID,
                        "Direct-v2" if mode == "direct" else "Search-First",
                        mode,
                    )

                record_stop.assert_not_called()
                self.assertEqual(output["status"], "OK")
                self.assertEqual(output["search"]["search_count"], 3)
                self.assertEqual(output["search"]["search_round_count"], 3)
                self.assertEqual([row["query_budget_consumed"] for row in output["query_rounds"]], [1, 1, 1])
                self.assertTrue(all(len(row["executed_queries"]) == 3 for row in output["query_rounds"]))
                self.assertEqual(retriever.search_calls, 3)
                self.assertEqual(len([p for p in client.calls if p.startswith("evidence_check_")]), 3)
                self.assertIn("final_model_and_solve", client.calls)
                output_path = Path(raw) / "runs" / "smoke" / mode / EVAL_ID / "unified_output.json"
                self.assertTrue(output_path.exists())

    def test_searchworthy_runner_promotes_budget_overrun_to_global_stop_without_terminal(self) -> None:
        overrun = SearchBudgetOverrun(prior_budget=1, remaining_budget=2, actual_consumed=3)
        with tempfile.TemporaryDirectory() as raw:
            with (
                patch.object(run_searchworthy, "EXPERIMENT_ROOT", Path(raw)),
                patch.object(run_searchworthy, "public_cases", return_value={EVAL_ID: PUBLIC}),
                patch.object(run_searchworthy, "output_schema_for", return_value=SCHEMA),
                patch.object(run_searchworthy, "shared_search_config", return_value=search_config(3)),
                patch.object(run_searchworthy.StrictAPIClient, "from_environment", return_value=object()),
                patch.object(run_searchworthy, "PublicWebRetriever", return_value=object()),
                patch.object(run_searchworthy, "run_pipeline_case", side_effect=overrun),
                patch.object(run_searchworthy, "record_global_stop") as record_stop,
            ):
                with self.assertRaises(common.GlobalStopError) as caught:
                    run_searchworthy.run_one("smoke", EVAL_ID)

            reason, detail = record_stop.call_args.args
            self.assertEqual(reason, "SEARCH_BUDGET_OVERRUN")
            self.assertIn("prior=1", detail)
            self.assertIn("remaining=2", detail)
            self.assertIn("actual=3", detail)
            self.assertIn("actual=3", str(caught.exception))
            output_path = Path(raw) / "runs" / "smoke" / "searchworthy" / EVAL_ID / "unified_output.json"
            self.assertFalse(output_path.exists())


if __name__ == "__main__":
    unittest.main()

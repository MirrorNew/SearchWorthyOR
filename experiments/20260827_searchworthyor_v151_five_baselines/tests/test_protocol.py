from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_ROOT))

import common  # noqa: E402
import gated_search_pipeline as pipeline  # noqa: E402
import run_direct  # noqa: E402
import run_local  # noqa: E402
import run_optiminer  # noqa: E402
import run_search_first  # noqa: E402
import web_retrieval  # noqa: E402
from web_retrieval import PublicWebRetriever, RetrievalFailure  # noqa: E402


def tiny_public(case_id: str = "SWOR-R001-C1") -> dict[str, Any]:
    schema = {
        "actions": [{"id": "swor_r001_a01", "meaning": "choose", "type": "BINARY"}],
        "objective": {"accepted_units": {"点": 1}, "canonical_unit": "点"},
        "schema_version": "searchworthyor.public_output.v1.1",
    }
    return {
        "id": "SWOR-R001",
        "case_id": case_id,
        "prompt_zh": "选择或不选择一个行动并最大化价值。\n\n公开 output_schema：\n" + json.dumps(schema, ensure_ascii=False),
    }


def math_model() -> dict[str, Any]:
    return {
        "variables": [{"id": "swor_r001_a01", "domain": "binary", "meaning": "choose"}],
        "objective": {"sense": "max", "expression": "x", "unit": "点"},
        "constraints": [{"name": "binary", "expression": "x in {0,1}", "meaning": "domain"}],
        "assumptions": [],
    }


def final_value() -> dict[str, Any]:
    return {
        "decision_state": "RETAIN",
        "applicability": False,
        "patch": [],
        "mathematical_model": math_model(),
        "native_model_or_code": "import gurobipy as gp\nm=gp.Model()\nx=m.addVar(vtype=gp.GRB.BINARY,name='swor_r001_a01')\nm.setObjective(x,gp.GRB.MAXIMIZE)\nm.optimize()",
        "declared_solver_status": "MODELLED",
        "actions": [{"id": "swor_r001_a01", "value": 1}],
        "objective": {"sense": "max", "value": 1.0, "unit": "点"},
        "reasoning": "base task solved",
    }


class FakeClient:
    def __init__(self, responses: list[dict[str, Any]]):
        self.responses = list(responses)
        self.purposes: list[str] = []

    def complete(self, messages: list[dict[str, str]], purpose: str) -> dict[str, Any]:
        del messages
        self.purposes.append(purpose)
        value = self.responses.pop(0)
        return {"content": json.dumps(value, ensure_ascii=False), "raw": value, "actual_model": common.MODEL, "usage": {}}

    def web_search(self, query: str, purpose: str = "web_search") -> dict[str, Any]:
        raise AssertionError(f"web search must not run for non-triggered gate: {query} {purpose}")


class BaseProviderFailureClient(FakeClient):
    def complete(self, messages: list[dict[str, str]], purpose: str) -> dict[str, Any]:
        if purpose == "base_formulate_and_solve":
            self.purposes.append(purpose)
            raise common.StrictAPIRequestError(
                "transient upstream failure",
                upstream_attempts=2,
                failure_type="URLError",
            )
        return super().complete(messages, purpose)


def solved_execution() -> dict[str, Any]:
    return {"attempted": True, "status": "OPTIMAL_EXACT_ACTION_MAPPING", "solver_actions": [{"id": "swor_r001_a01", "value": 1}], "solver_objective": {"sense": "max", "value": 1.0, "unit": None}}


def test_locked_configuration_and_shubiaobiao_provider() -> None:
    config = common.load_config()
    assert config["schema_version"] == "searchworthyor.v151.five_baselines.v1"
    assert config["provider"]["name"] == "shubiaobiao"
    assert config["provider"]["provider_fallback"] is False
    assert config["model"] == {"name": "gpt-5.6-luna", "reasoning_effort": "xhigh", "temperature": 1}
    assert common.shared_search_config()["max_queries_per_case"] == 3


def test_public_and_matrix_cardinality() -> None:
    public = common.public_cases()
    matrix = common.read_jsonl(common.EXPERIMENT_ROOT / "task_matrix.jsonl")
    assert len(public) == 240
    assert {case_id.rsplit("-C", 1)[1] for case_id in public} == {"1", "2"}
    assert len(matrix) == 1200
    assert len({row["instance_id"] for row in matrix}) == 1200


def test_smoke_is_one_paired_task_for_all_five_methods() -> None:
    config = common.load_config()
    assert common.smoke_ids() == ["SWOR-R001-C1", "SWOR-R001-C2"]
    assert config["phases"]["smoke"]["instances"] == 10
    assert all(method["smoke_workers"] == 1 for method in config["methods"].values())


def test_search_gate_contract_triggered_and_not_triggered() -> None:
    public = tiny_public()
    triggered = pipeline.parse_gate(
        {"search_needed": True, "trigger_reason": "rule may change feasibility", "external_unknowns": ["current threshold"], "first_query": "official current threshold"},
        public,
    )
    assert triggered["status"] == "TRIGGERED"
    assert pipeline.parse_gate(
        {"search_needed": False, "trigger_reason": "all facts are local", "external_unknowns": [], "first_query": None},
        public,
    )["status"] == "NOT_TRIGGERED"
    with pytest.raises(ValueError):
        pipeline.parse_gate(
            {"search_needed": False, "trigger_reason": "no", "external_unknowns": [], "first_query": "unwanted query"},
            public,
        )


def test_query_and_page_budgets() -> None:
    pipeline.validate_search_budget(3, 9, 18)
    with pytest.raises(ValueError):
        pipeline.validate_search_budget(4, 0, 0)
    with pytest.raises(ValueError):
        pipeline.validate_query("site:a.example site:b.example threshold", tiny_public())


def test_failed_page_opens_do_not_consume_readable_page_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    retriever = PublicWebRetriever(max_results=6, max_open=3)
    calls = 0

    def fake_get(url: str, stage: str) -> dict[str, Any]:
        nonlocal calls
        del stage
        calls += 1
        if calls <= 3:
            raise RetrievalFailure("PAGE_HTTP_403", "blocked", status=403, final_url=url)
        return {
            "status": 200,
            "content_type": "text/html; charset=utf-8",
            "data": ("<html><title>Rule</title><main>" + "authoritative rule text " * 20 + "</main></html>").encode(),
            "final_url": url,
            "headers": {},
            "redirects": [],
            "retry_events": [],
        }

    monkeypatch.setattr(retriever, "_get", fake_get)
    results = [{"rank": index, "title": "Rule", "url": f"https://example{index}.org/rule"} for index in range(1, 7)]
    pages, attempts = retriever.open_top(results)
    assert len(pages) == 3
    assert len(attempts) == 6
    assert calls == 6


def test_proxy_fake_ip_dns_is_allowed_only_for_hostnames(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        web_retrieval.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("198.18.0.173", 443))],
    )
    web_retrieval._assert_public("https://authority.example/rule")
    with pytest.raises(ValueError):
        web_retrieval._assert_public("https://198.18.0.173/rule")


def test_raw_nl_binds_url_and_verified_quote() -> None:
    text = pipeline.evidence_raw_nl(
        [{"final_url": "https://authority.example/rule", "publisher": "Authority", "quote": "Threshold is 50."}],
        "RETRIEVAL_PARTIAL",
    )
    assert "SOURCE_URL: https://authority.example/rule" in text
    assert "VERBATIM_EVIDENCE: Threshold is 50." in text


def test_search_first_non_trigger_still_models_and_solves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    public = tiny_public()
    fake = FakeClient(
        [
            {"search_needed": False, "trigger_reason": "local task is closed", "external_unknowns": [], "first_query": None},
            final_value(),
        ]
    )
    monkeypatch.setattr(pipeline, "EXPERIMENT_ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "public_cases", lambda: {public["case_id"]: public})
    monkeypatch.setattr(pipeline.StrictAPIClient, "from_environment", lambda *args, **kwargs: fake)
    monkeypatch.setattr(pipeline, "execute_generated", lambda *args, **kwargs: solved_execution())
    output = pipeline.run_case("search_first", "smoke", public["case_id"], run_search_first.METHOD, "search_first")
    assert fake.purposes == ["search_gate", "final_model_and_solve"]
    assert output["retrieval_status"] == "NOT_TRIGGERED"
    assert output["search"]["search_count"] == 0
    assert output["answer_present"] is True
    assert output["final_solve"]["attempted"] is True


def test_direct_builds_and_solves_base_before_non_triggered_final(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    public = tiny_public()
    base = {
        "mathematical_model": math_model(),
        "native_model_or_code": final_value()["native_model_or_code"],
        "actions": [{"id": "swor_r001_a01", "value": 1}],
        "objective": {"sense": "max", "value": 1.0, "unit": "点"},
        "reasoning": "base solved",
    }
    fake = FakeClient(
        [
            base,
            {"search_needed": False, "trigger_reason": "local task is closed", "external_unknowns": [], "first_query": None},
            final_value(),
        ]
    )
    monkeypatch.setattr(pipeline, "EXPERIMENT_ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "public_cases", lambda: {public["case_id"]: public})
    monkeypatch.setattr(pipeline.StrictAPIClient, "from_environment", lambda *args, **kwargs: fake)
    monkeypatch.setattr(pipeline, "execute_generated", lambda *args, **kwargs: solved_execution())
    output = pipeline.run_case("direct", "smoke", public["case_id"], run_direct.METHOD, "direct")
    assert fake.purposes == ["base_formulate_and_solve", "search_gate", "final_model_and_solve"]
    assert isinstance(output["base_model"]["mathematical_model"], dict)
    assert output["base_solve"]["attempted"] is True
    assert output["retrieval_status"] == "NOT_TRIGGERED"
    assert output["answer_present"] is True


def test_direct_records_base_provider_failure_but_still_finalizes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    public = tiny_public()
    fake = BaseProviderFailureClient(
        [
            {"search_needed": False, "trigger_reason": "local task is closed", "external_unknowns": [], "first_query": None},
            final_value(),
        ]
    )
    monkeypatch.setattr(pipeline, "EXPERIMENT_ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "public_cases", lambda: {public["case_id"]: public})
    monkeypatch.setattr(pipeline.StrictAPIClient, "from_environment", lambda *args, **kwargs: fake)
    monkeypatch.setattr(pipeline, "execute_generated", lambda *args, **kwargs: solved_execution())
    output = pipeline.run_case("direct", "smoke", public["case_id"], run_direct.METHOD, "direct")
    assert fake.purposes == ["base_formulate_and_solve", "search_gate", "final_model_and_solve"]
    assert output["base_stage_attempted"] is True
    assert output["base_stage_status"] == "PROVIDER_FAILURE"
    assert output["base_solve"]["attempted"] is False
    assert output["status"] == "PROVIDER_FAILURE"
    assert output["answer_present"] is True
    assert output["final_solve"]["attempted"] is True


def test_native_method_boundaries_and_optiminer_mapping() -> None:
    assert "PublicWebRetriever" not in Path(run_local.__file__).read_text(encoding="utf-8")
    command = run_optiminer.runner_command(common.EXPERIMENT_ROOT, common.EXPERIMENT_ROOT / "inputs" / "optiminer_benchmark.jsonl", "OMB001", common.EXPERIMENT_ROOT, "http://127.0.0.1:1/v1")
    assert command[command.index("--search-backend") + 1] == "arxiv_document"
    packet, mapping = run_optiminer.inputs()
    assert len(packet) == len(mapping) == 240
    assert mapping["SWOR-R001-C1"]["runner_id"] == "OMB001"
    assert mapping["SWOR-R001-C2"]["runner_id"] == "OMB002"


def test_chain_modes_are_distinct_but_share_executor() -> None:
    assert run_direct.run_one.__globals__["run_case"] is run_search_first.run_one.__globals__["run_case"]
    assert "Base OR model" in pipeline.DIRECT_GATE_SYSTEM
    assert "only the supplied public prompt_zh" in pipeline.SEARCH_FIRST_GATE_SYSTEM
    assert "Do not formulate" in pipeline.SEARCH_FIRST_GATE_SYSTEM

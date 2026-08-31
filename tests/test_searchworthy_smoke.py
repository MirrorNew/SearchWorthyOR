from __future__ import annotations

from collections import defaultdict
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from searchworthy.contracts import (
    Admission,
    AuditDimension,
    AuditSummary,
    CandidateGapDraft,
    EvidenceCard,
    EvidenceDecision,
    FactCoverageDraft,
    FactUsageStatus,
    GapRoute,
    InitialDecision,
    PatchPlan,
    PublicCase,
    RetrievalTrace,
)
from searchworthy.pipeline import PipelineServices, SearchBudgetOverrun, run_case
from searchworthy.run_searchworthy import make_services
from web_retrieval import RetrievalFailure


SCHEMA = {
    "actions": [{"id": "x", "type": "BINARY"}, {"id": "y", "type": "BINARY"}],
    "objective": {"accepted_units": {"点": 1}, "canonical_unit": "点"},
}
IR = {
    "variables": [{"id": "x", "type": "BINARY", "lb": 0, "ub": 1}, {"id": "y", "type": "BINARY", "lb": 0, "ub": 1}],
    "constraints": [{"name": "one", "terms": [{"var": "x", "coef": 1}, {"var": "y", "coef": 1}], "sense": "==", "rhs": 1}],
    "objective": {"direction": "max", "terms": [{"var": "x", "coef": 1}, {"var": "y", "coef": 2}], "constant": 0, "unit": "点"},
    "parameters": {},
}


def full_audit(*, overflow: int = 0) -> AuditSummary:
    return AuditSummary(True, True, {d: True for d in AuditDimension}, overflow > 0, overflow)


def forbidden_search(*args):
    raise AssertionError("search must not run")


def forbidden_evidence(*args):
    raise AssertionError("evidence LLM must not run")


def test_retrieval_failure_does_not_expose_rejected_raw_candidates() -> None:
    class EmptyRetriever:
        def search(self, query: str) -> dict[str, object]:
            raise RetrievalFailure(
                "SEARCH_EMPTY_RESULTS",
                "Responses search returned no relevant allowed result",
                context={
                    "raw_results": [{"url": f"https://example.com/{index}"} for index in range(11)],
                    "backend_raw_result_count": 11,
                    "executed_query": query,
                    "executed_queries": [query],
                    "query_budget_consumed": 1,
                    "results_discarded": False,
                },
            )

    services = make_services(object(), EmptyRetriever())  # type: ignore[arg-type]
    trace = services.searcher("G1", "official rule")

    assert trace.backend_raw_result_count == 11
    assert trace.results == []
    assert trace.failure_type == "SEARCH_EMPTY_RESULTS"


def boundary_variants(target: str) -> list[dict[str, object]]:
    return [
        {
            "target": target,
            "operation": "SET",
            "value": {"lb": 0, "ub": 0},
            "range_basis": "MODEL_BOUNDARY",
            "basis_quote": None,
        }
    ]


def test_self_contained_case_finishes_no_search() -> None:
    public = PublicCase("S1", "必须恰好选择一个方案。")
    initial = InitialDecision(
        IR,
        [FactCoverageDraft("必须恰好选择一个方案", "FEASIBILITY", ["constraint.one"], FactUsageStatus.MODELED, "modeled")],
        full_audit(),
        [],
        True,
    )
    services = PipelineServices(lambda _: initial, forbidden_search, forbidden_evidence)
    result = run_case(public, SCHEMA, services)
    assert result["status"] == "OK"
    assert result["decision_state"] == "NO_SEARCH"
    assert result["applicability"] is True
    assert result["search"]["search_count"] == 0
    assert result["search_performed"] is False
    assert result["retrieval_status"] == "NOT_SEARCHED"


def test_overflow_without_returned_gaps_abstains_without_query() -> None:
    public = PublicCase("S2", "规则信息仍有多个缺口。")
    initial = InitialDecision(
        IR,
        [FactCoverageDraft("规则信息仍有多个缺口", "RULE", [], FactUsageStatus.UNACCOUNTED, "overflow")],
        full_audit(overflow=2),
        [],
        False,
    )
    result = run_case(public, SCHEMA, PipelineServices(lambda _: initial, forbidden_search, forbidden_evidence))
    assert result["status"] == "ABSTAIN"
    assert result["search"]["search_count"] == 0


def test_overflow_can_search_a_returned_critical_gap_but_final_stays_abstain() -> None:
    public = PublicCase("S2-BOUNDED", "方案Y资格规则待核实。还有一个规则缺口未列出。")
    gap = CandidateGapDraft(
        ["方案Y资格规则待核实"],
        "ELIGIBILITY",
        "方案Y是否允许",
        "variable.y",
        GapRoute.EXTERNAL_RULE,
        boundary_variants("variable.y"),
        "方案Y 资格 官方规则",
    )
    initial = InitialDecision(
        IR,
        [
            FactCoverageDraft("方案Y资格规则待核实", "ELIGIBILITY", [], FactUsageStatus.UNACCOUNTED, "check"),
            FactCoverageDraft("还有一个规则缺口未列出", "RULE", [], FactUsageStatus.UNACCOUNTED, "overflow"),
        ],
        full_audit(overflow=1),
        [gap],
        False,
    )

    def searcher(gap_id: str, query: str) -> RetrievalTrace:
        return RetrievalTrace(gap_id, query, True, query)

    def reject_evidence(*_args) -> EvidenceDecision:
        return EvidenceDecision([], Admission.REJECT, None, None, "evidence remains insufficient")

    result = run_case(public, SCHEMA, PipelineServices(lambda _: initial, searcher, reject_evidence))
    assert result["status"] == "ABSTAIN"
    assert result["search"]["search_count"] == 1
    assert result["search_performed"] is True
    assert result["state"]["audit_summary"]["overflow_detected"] is True
    assert result["failure_detail"] == "decision-complete OR information state is not closed"


def test_provider_query_expansion_costs_one_round_and_reaches_evidence() -> None:
    public = PublicCase("S2-EXPANSION", "方案Y资格规则待核实。")
    gap = CandidateGapDraft(
        ["方案Y资格规则待核实"],
        "ELIGIBILITY",
        "方案Y是否允许",
        "variable.y",
        GapRoute.EXTERNAL_RULE,
        boundary_variants("variable.y"),
        "方案Y 资格 官方规则",
    )
    initial = InitialDecision(
        IR,
        [FactCoverageDraft("方案Y资格规则待核实", "ELIGIBILITY", [], FactUsageStatus.UNACCOUNTED, "check")],
        full_audit(),
        [gap],
        False,
    )

    def expanded_search(gap_id: str, query: str) -> RetrievalTrace:
        return RetrievalTrace(
            gap_id=gap_id,
            planned_query=query,
            query_attempted=True,
            executed_query=query,
            executed_queries=[query, "扩展查询二", "扩展查询三"],
            query_budget_consumed=1,
            results_discarded=False,
            backend_raw_result_count=32,
        )

    evidence_calls = 0

    def reject(public_case, state, gap_id, trace, current_ir):
        nonlocal evidence_calls
        evidence_calls += 1
        return EvidenceDecision([], Admission.REJECT, None, None, "insufficient")

    result = run_case(
        public,
        SCHEMA,
        PipelineServices(lambda _: initial, expanded_search, reject),
    )

    assert result["status"] == "ABSTAIN"
    assert result["retrieval_status"] == "SEARCH_FAILURE"
    assert result["search"]["search_count"] == 1
    assert result["search"]["search_round_count"] == 1
    assert result["search"]["rounds"][0]["result_count"] == 0
    assert result["search"]["pages"] == []
    assert result["search"]["verified_quote_count"] == 0
    assert result["search"]["rounds"][0]["backend_raw_result_count"] == 32
    assert result["search"]["rounds"][0]["results_discarded"] is False
    assert len(result["search"]["rounds"][0]["executed_queries"]) == 3
    assert evidence_calls == 1
    assert result["state"]["round"] == 1
    assert result["state"]["search_budget_left"] == 2


def test_program_unbound_information_target_is_auditable_abstain_without_search() -> None:
    public = PublicCase("S2U", "必须恰好选择一个方案。现实主体资格仍待核实。")
    gap = CandidateGapDraft(
        ["现实主体资格仍待核实"],
        "SUBJECT_ELIGIBILITY",
        "主体资格无法绑定现有行动 [PROGRAM_UNBOUND_OR_TARGET:applicability.subject_eligibility]",
        "applicability.subject_eligibility",
        GapRoute.OUT_OF_SCOPE,
        [],
        None,
    )
    unbound_audit = full_audit()
    unbound_audit.model_interface_to_grounding_complete = False
    initial = InitialDecision(
        IR,
        [
            FactCoverageDraft("必须恰好选择一个方案", "FEASIBILITY", ["constraint.one"], FactUsageStatus.MODELED, "modeled"),
            FactCoverageDraft("现实主体资格仍待核实", "SUBJECT_ELIGIBILITY", [], FactUsageStatus.UNACCOUNTED, "unbound"),
        ],
        unbound_audit,
        [gap],
        False,
    )
    result = run_case(public, SCHEMA, PipelineServices(lambda _: initial, forbidden_search, forbidden_evidence))
    state_gap = result["state"]["gaps"][0]
    assert result["status"] == "ABSTAIN"
    assert result["search"]["search_count"] == 0
    assert result["search_performed"] is False
    assert result["retrieval_status"] == "NOT_SEARCHED"
    assert state_gap["target"] is None
    assert state_gap["proposed_information_target"] == "applicability.subject_eligibility"
    assert state_gap["target_binding_status"] == "UNBOUND"
    assert state_gap["gap_route"] == "OUT_OF_SCOPE"
    assert state_gap["probe_coverage"] is False
    assert state_gap["state"] == "UNRESOLVED_ABSTAIN"
    assert "PROGRAM_UNBOUND_OR_TARGET" in state_gap["realized_effect"]["reason"]
    assert state_gap["realized_effect"]["normalization_record"] == {
        "original_target": "applicability.subject_eligibility",
        "original_gap_route": "OUT_OF_SCOPE",
        "original_first_query": None,
        "effective_target": None,
    }


def test_two_unbound_gaps_preserve_five_fact_links_and_never_search() -> None:
    missing_facts = [
        "主体资格仍待核实",
        "对象范围仍待核实",
        "例外条件仍待核实",
        "行动后果仍待核实",
        "适用时间仍待核实",
    ]
    public = PublicCase("S2U2", "必须恰好选择一个方案。" + "。".join(missing_facts) + "。")
    gaps = [
        CandidateGapDraft(
            missing_facts[:2],
            "SUBJECT_ELIGIBILITY",
            "主体资格无法绑定现有行动 [PROGRAM_UNBOUND_OR_TARGET:applicability.subject_eligibility]",
            "applicability.subject_eligibility",
            GapRoute.EXTERNAL_RULE,
            [],
            "主体资格 官方规则",
        ),
        CandidateGapDraft(
            missing_facts[2:],
            "OBJECT_SCOPE",
            "对象范围无法绑定现有行动 [PROGRAM_UNBOUND_OR_TARGET:applicability.object_scope]",
            "applicability.object_scope",
            GapRoute.EXTERNAL_RULE,
            [],
            "对象范围 官方规则",
        ),
    ]
    facts = [
        FactCoverageDraft("必须恰好选择一个方案", "FEASIBILITY", ["constraint.one"], FactUsageStatus.MODELED, "modeled"),
        *[
            FactCoverageDraft(quote, "REALITY_GAP", [], FactUsageStatus.UNACCOUNTED, "unbound")
            for quote in missing_facts
        ],
    ]
    unbound_audit = full_audit()
    unbound_audit.model_interface_to_grounding_complete = False
    initial = InitialDecision(IR, facts, unbound_audit, gaps, False)
    result = run_case(public, SCHEMA, PipelineServices(lambda _: initial, forbidden_search, forbidden_evidence))
    state = result["state"]
    assert result["status"] == "ABSTAIN"
    assert result["search"]["search_count"] == 0
    assert len(state["gaps"]) == 2
    assert sum(gap["target_binding_status"] == "UNBOUND" for gap in state["gaps"]) == 2
    assert sum(fact["usage_status"] == "UNACCOUNTED" and fact["gap_id"] is not None for fact in state["fact_coverage"]) == 5
    assert sum(len(gap["fact_quotes"]) for gap in state["gaps"]) == 5
    assert all(gap["realized_effect"]["normalization_record"]["original_first_query"] for gap in state["gaps"])
    assert all(gap["evidence"] is None and gap["patch"] is None for gap in state["gaps"])


def test_gap_link_contract_failure_abstains_atomically_without_search() -> None:
    public = PublicCase(
        "S2-LINK",
        "必须恰好选择一个方案。现实规则A仍待核实。机构 A 和机构 B 的材料齐全。",
    )
    audit = full_audit()
    audit.model_interface_to_grounding_complete = False
    initial = InitialDecision(
        IR,
        [
            FactCoverageDraft("必须恰好选择一个方案", "FEASIBILITY", ["constraint.one"], FactUsageStatus.MODELED, "modeled"),
            FactCoverageDraft("现实规则A仍待核实", "ELIGIBILITY", [], FactUsageStatus.UNACCOUNTED, "check A"),
            FactCoverageDraft("机构 A 和机构 B 的材料齐全", "CAPACITY", [], FactUsageStatus.UNACCOUNTED, "check materials"),
        ],
        audit,
        [
            CandidateGapDraft(
                ["现实规则A仍待核实"], "ELIGIBILITY", "方案X资格是否成立", "variable.x",
                GapRoute.EXTERNAL_RULE, boundary_variants("variable.x"), "方案X 资格 官方规则",
            ),
            CandidateGapDraft(
                ["机构A和机构B的材料齐全"], "CAPACITY", "材料是否足以证明容量", "variable.y",
                GapRoute.EXTERNAL_RULE, boundary_variants("variable.y"), "机构容量 官方规则",
            ),
        ],
        False,
    )
    result = run_case(public, SCHEMA, PipelineServices(lambda _: initial, forbidden_search, forbidden_evidence))
    state = result["state"]
    assert result["status"] == "ABSTAIN"
    assert result["failure_detail"] == "information audit failed: STAGE3_CANDIDATE_GAP_LINK_FAILURE"
    assert result["search"]["search_count"] == 0
    assert result["search_performed"] is False
    assert result["retrieval_status"] == "NOT_SEARCHED"
    assert result["base_ir"] == result["current_ir"]
    assert state["gaps"] == []
    assert state["information_audit_failure"] == {
        "code": "STAGE3_CANDIDATE_GAP_LINK_FAILURE",
        "invalid_gap_indices": [2],
        "unlinked_fact_indices": [3],
    }
    assert state["round"] == 0 and state["search_budget_left"] == 3
    assert state["evidence_ledger"] == []
    assert all(fact["gap_id"] is None for fact in state["fact_coverage"])


def test_gap_link_failure_does_not_hide_an_invalid_information_route() -> None:
    public = PublicCase("S2-LINK-ROUTE", "现实主体资格仍待核实。")
    audit = full_audit()
    audit.model_interface_to_grounding_complete = False
    initial = InitialDecision(
        IR,
        [FactCoverageDraft("现实主体资格仍待核实", "ELIGIBILITY", [], FactUsageStatus.UNACCOUNTED, "check")],
        audit,
        [
            CandidateGapDraft(
                ["并非原句"], "ELIGIBILITY", "主体资格缺口", "applicability.subject_eligibility",
                GapRoute.EXTERNAL_RULE, [], None,
            )
        ],
        False,
    )
    with pytest.raises(ValueError, match="route/query contract"):
        run_case(public, SCHEMA, PipelineServices(lambda _: initial, forbidden_search, forbidden_evidence))


@pytest.mark.parametrize(
    ("route", "query"),
    [
        (GapRoute.OUT_OF_SCOPE, "illegal query"),
        (GapRoute.LOCAL_FACT, "illegal query"),
        (GapRoute.EXTERNAL_RULE, None),
    ],
)
def test_bound_gap_route_query_contract_is_hard_gated(route: GapRoute, query: str | None) -> None:
    public = PublicCase("S2-BOUND-ROUTE", "现实主体资格仍待核实。")
    audit = full_audit()
    audit.model_interface_to_grounding_complete = False
    initial = InitialDecision(
        IR,
        [FactCoverageDraft("现实主体资格仍待核实", "ELIGIBILITY", [], FactUsageStatus.UNACCOUNTED, "check")],
        audit,
        [
            CandidateGapDraft(
                ["现实主体资格仍待核实"], "ELIGIBILITY", "方案X资格缺口", "variable.x",
                route, boundary_variants("variable.x"), query,
            )
        ],
        False,
    )
    with pytest.raises(ValueError, match="route/query contract"):
        run_case(public, SCHEMA, PipelineServices(lambda _: initial, forbidden_search, forbidden_evidence))


def test_gap_link_failure_does_not_hide_invalid_stage2_target_matrix() -> None:
    public = PublicCase("S2-LINK-FACT", "现实主体资格仍待核实。")
    audit = full_audit()
    audit.model_interface_to_grounding_complete = False
    initial = InitialDecision(
        IR,
        [
            FactCoverageDraft(
                "现实主体资格仍待核实", "ELIGIBILITY", ["variable.x"],
                FactUsageStatus.UNACCOUNTED, "invalid mapping",
            )
        ],
        audit,
        [
            CandidateGapDraft(
                ["并非原句"], "ELIGIBILITY", "主体资格缺口", "variable.x",
                GapRoute.EXTERNAL_RULE, boundary_variants("variable.x"), "主体资格 官方规则",
            )
        ],
        False,
    )
    with pytest.raises(ValueError, match="UNACCOUNTED fact must use mapped_targets"):
        run_case(public, SCHEMA, PipelineServices(lambda _: initial, forbidden_search, forbidden_evidence))


@pytest.mark.parametrize("target", ["applicability.unknown_dimension", "memory.subject_eligibility"])
def test_unknown_information_target_family_remains_a_contract_failure(target: str) -> None:
    public = PublicCase("S2X", "必须恰好选择一个方案。现实主体资格仍待核实。")
    gap = CandidateGapDraft(
        ["现实主体资格仍待核实"],
        "SUBJECT_ELIGIBILITY",
        "unknown target must not be normalized",
        target,
        GapRoute.OUT_OF_SCOPE,
        [],
        None,
    )
    initial = InitialDecision(
        IR,
        [
            FactCoverageDraft("必须恰好选择一个方案", "FEASIBILITY", ["constraint.one"], FactUsageStatus.MODELED, "modeled"),
            FactCoverageDraft("现实主体资格仍待核实", "SUBJECT_ELIGIBILITY", [], FactUsageStatus.UNACCOUNTED, "unbound"),
        ],
        full_audit(),
        [gap],
        False,
    )
    with pytest.raises(ValueError, match="allowed_gap_targets"):
        run_case(public, SCHEMA, PipelineServices(lambda _: initial, forbidden_search, forbidden_evidence))


def test_decision_critical_local_fact_abstains_without_web_guessing() -> None:
    public = PublicCase("S3", "现场容量未知。")
    gap = CandidateGapDraft(
        ["现场容量未知"], "CAPACITY", "容量是否允许选择X", "variable.x", GapRoute.LOCAL_FACT,
        boundary_variants("variable.x"),
        None,
    )
    initial = InitialDecision(IR, [FactCoverageDraft("现场容量未知", "CAPACITY", [], FactUsageStatus.UNACCOUNTED, "local")], full_audit(), [gap], False)
    result = run_case(public, SCHEMA, PipelineServices(lambda _: initial, forbidden_search, forbidden_evidence))
    assert result["status"] == "ABSTAIN"
    assert result["search"]["search_count"] == 0


def test_multi_gap_patches_use_same_current_ir() -> None:
    public = PublicCase("S4", "必须恰好选择一个方案。当前企业位于甲地。外部规则尚待核实。")
    schema3 = {
        "actions": [{"id": "x", "type": "BINARY"}, {"id": "y", "type": "BINARY"}, {"id": "z", "type": "BINARY"}],
        "objective": {"accepted_units": {"点": 1}, "canonical_unit": "点"},
    }
    ir3 = {
        "variables": [
            {"id": "x", "type": "BINARY", "lb": 0, "ub": 1},
            {"id": "y", "type": "BINARY", "lb": 0, "ub": 1},
            {"id": "z", "type": "BINARY", "lb": 0, "ub": 1},
        ],
        "constraints": [
            {
                "name": "one",
                "terms": [{"var": "x", "coef": 1}, {"var": "y", "coef": 1}, {"var": "z", "coef": 1}],
                "sense": "==",
                "rhs": 1,
            }
        ],
        "objective": {
            "direction": "max",
            "terms": [{"var": "x", "coef": 1}, {"var": "y", "coef": 2}, {"var": "z", "coef": 3}],
            "constant": 0,
            "unit": "点",
        },
        "parameters": {},
    }
    gaps = [
        CandidateGapDraft(
            ["当前企业位于甲地"], "JURISDICTION", "地点规则是否允许方案Z", "variable.z", GapRoute.EXTERNAL_RULE,
            boundary_variants("variable.z"),
            "甲地 适用范围 官方",
        ),
        CandidateGapDraft(
            ["外部规则尚待核实"], "ELIGIBILITY", "外部规则是否允许方案Y", "variable.y", GapRoute.EXTERNAL_RULE,
            boundary_variants("variable.y"),
            "方案Y 资格 官方",
        ),
    ]
    initial = InitialDecision(
        ir3,
        [
            FactCoverageDraft("必须恰好选择一个方案", "FEASIBILITY", ["constraint.one"], FactUsageStatus.MODELED, "modeled"),
            FactCoverageDraft("当前企业位于甲地", "JURISDICTION", [], FactUsageStatus.UNACCOUNTED, "check"),
            FactCoverageDraft("外部规则尚待核实", "COST", [], FactUsageStatus.UNACCOUNTED, "check"),
        ],
        full_audit(),
        gaps,
        False,
    )
    calls = defaultdict(int)

    def searcher(gap_id: str, query: str) -> RetrievalTrace:
        calls[gap_id] += 1
        text = "本规则适用于甲地企业，方案Z下界为0且上界为0。" if gap_id == "G1" else "适用规则要求方案Y下界为0且上界为0。"
        return RetrievalTrace(gap_id, query, True, query, opened_pages=[{"final_url": f"https://authority.example/{gap_id}", "visible_text": text}])

    def evidence(public_case, state, gap_id, trace, current_ir):
        if gap_id == "G1":
            cards = [
                EvidenceCard(
                    "E1L", "https://authority.example/G1", "方案Z下界为0且上界为0", "Z下界", "当前企业位于甲地", "本规则适用于甲地企业", "variable.z", True, True, True, True,
                    "parameters.lb", 0,
                ),
                EvidenceCard(
                    "E1U", "https://authority.example/G1", "方案Z下界为0且上界为0", "Z上界", "当前企业位于甲地", "本规则适用于甲地企业", "variable.z", True, True, True, True,
                    "parameters.ub", 0,
                ),
            ]
            plan = PatchPlan("SET_VARIABLE_BOUNDS", "variable.z", {"lb": 0, "ub": 0}, {"lb": 0.0, "ub": 1.0}, ["E1L", "E1U"])
            return EvidenceDecision(cards, Admission.ADMIT_PATCH, plan, None, "four gates pass")
        cards = [
            EvidenceCard(
                "E2L", "https://authority.example/G2", "方案Y下界为0且上界为0", "Y下界", "外部规则尚待核实", "适用规则要求方案Y下界为0且上界为0", "variable.y", True, True, True, True,
                "parameters.lb", 0,
            ),
            EvidenceCard(
                "E2U", "https://authority.example/G2", "方案Y下界为0且上界为0", "Y上界", "外部规则尚待核实", "适用规则要求方案Y下界为0且上界为0", "variable.y", True, True, True, True,
                "parameters.ub", 0,
            ),
        ]
        plan = PatchPlan("SET_VARIABLE_BOUNDS", "variable.y", {"lb": 0, "ub": 0}, {"lb": 0.0, "ub": 1.0}, ["E2L", "E2U"])
        return EvidenceDecision(cards, Admission.ADMIT_PATCH, plan, None, "four gates pass")

    result = run_case(public, schema3, PipelineServices(lambda _: initial, searcher, evidence))
    assert result["status"] == "OK"
    assert result["decision_state"] == "PATCH_CHANGES"
    assert result["search"]["search_count"] == 2
    assert result["search_performed"] is True
    assert result["retrieval_status"] == "RETRIEVAL_COMPLETE"
    assert result["search"]["readable_page_count"] == 2
    assert result["search"]["verified_quote_count"] == 2
    assert result["search"]["backend_fallback"] is False
    assert calls == {"G1": 1, "G2": 1}
    assert [gap["state"] for gap in result["state"]["gaps"]] == ["CLOSED_PATCH", "CLOSED_PATCH"]
    assert result["actions"] == [{"id": "x", "value": 1}, {"id": "y", "value": 0}, {"id": "z", "value": 0}]


def test_committed_patch_reprobes_every_remaining_open_gap() -> None:
    public = PublicCase("S4-REPROBE", "方案Y资格外部规则尚待核实。方案X资格规则尚待核实。")
    gaps = [
        CandidateGapDraft(
            ["方案Y资格外部规则尚待核实"], "ELIGIBILITY", "方案Y是否允许", "variable.y", GapRoute.EXTERNAL_RULE,
            boundary_variants("variable.y"),
            "方案Y 资格 官方",
        ),
        CandidateGapDraft(
            ["方案X资格规则尚待核实"], "ELIGIBILITY", "方案X是否允许", "variable.x", GapRoute.EXTERNAL_RULE,
            boundary_variants("variable.x"),
            "方案X 资格 官方",
        ),
    ]
    initial = InitialDecision(
        IR,
        [
            FactCoverageDraft("方案Y资格外部规则尚待核实", "ELIGIBILITY", [], FactUsageStatus.UNACCOUNTED, "check Y"),
            FactCoverageDraft("方案X资格规则尚待核实", "ELIGIBILITY", [], FactUsageStatus.UNACCOUNTED, "check X"),
        ],
        full_audit(),
        gaps,
        False,
    )
    calls: list[str] = []

    def searcher(gap_id: str, query: str) -> RetrievalTrace:
        calls.append(gap_id)
        text = "规则适用于本案。方案Y下界为0且上界为0。" if gap_id == "G1" else ""
        pages = [{"final_url": "https://authority.example/x", "visible_text": text}] if text else []
        return RetrievalTrace(gap_id, query, True, query, opened_pages=pages)

    def evidence(public_case, state, gap_id, trace, current_ir):
        if gap_id == "G1":
            cards = [
                EvidenceCard(
                    "EYL", "https://authority.example/x", "方案Y下界为0且上界为0", "Y下界", "方案Y资格外部规则尚待核实", "规则适用于本案", "variable.y", True, True, True, True,
                    "parameters.lb", 0,
                ),
                EvidenceCard(
                    "EYU", "https://authority.example/x", "方案Y下界为0且上界为0", "Y上界", "方案Y资格外部规则尚待核实", "规则适用于本案", "variable.y", True, True, True, True,
                    "parameters.ub", 0,
                ),
            ]
            plan = PatchPlan("SET_VARIABLE_BOUNDS", "variable.y", {"lb": 0, "ub": 0}, {"lb": 0.0, "ub": 1.0}, ["EYL", "EYU"])
            return EvidenceDecision(cards, Admission.ADMIT_PATCH, plan, None, "bind Y")
        return EvidenceDecision([], Admission.REJECT, None, None, "second gap remains unresolved")

    result = run_case(public, SCHEMA, PipelineServices(lambda _: initial, searcher, evidence))
    assert calls == ["G1", "G2"]
    assert result["status"] == "ABSTAIN"
    assert result["state"]["gaps"][0]["state"] == "CLOSED_PATCH"
    assert result["state"]["gaps"][1]["potential_effect"] == "FEASIBILITY_CHANGE"
    assert result["state"]["gaps"][1]["state"] == "UNRESOLVED_ABSTAIN"


def test_search_budget_is_case_global_and_never_exceeds_three() -> None:
    public = PublicCase("S5", "外部规则尚待核实。")
    gap = CandidateGapDraft(
        ["外部规则尚待核实"], "ELIGIBILITY", "方案Y是否允许", "variable.y", GapRoute.EXTERNAL_RULE,
        boundary_variants("variable.y"),
        "规则 查询 1",
    )
    initial = InitialDecision(IR, [FactCoverageDraft("外部规则尚待核实", "COST", [], FactUsageStatus.UNACCOUNTED, "check")], full_audit(), [gap], False)
    attempts = []

    def searcher(gap_id: str, query: str) -> RetrievalTrace:
        attempts.append(query)
        return RetrievalTrace(gap_id, query, True, query)

    def reject(public_case, state, gap_id, trace, current_ir):
        return EvidenceDecision([], Admission.REJECT, None, f"规则 查询 {state.round + 1}", "insufficient")

    result = run_case(public, SCHEMA, PipelineServices(lambda _: initial, searcher, reject))
    assert result["status"] == "ABSTAIN"
    assert result["search"]["search_count"] == 3
    assert len(attempts) == 3
    assert result["state"]["round"] == 3
    assert result["state"]["search_budget_left"] == 0


def test_second_round_provider_query_expansion_preserves_call_budget() -> None:
    public = PublicCase("S5-EXPANSION", "外部规则尚待核实。")
    gap = CandidateGapDraft(
        ["外部规则尚待核实"], "ELIGIBILITY", "方案Y是否允许", "variable.y", GapRoute.EXTERNAL_RULE,
        boundary_variants("variable.y"),
        "规则 查询 1",
    )
    initial = InitialDecision(
        IR,
        [FactCoverageDraft("外部规则尚待核实", "COST", [], FactUsageStatus.UNACCOUNTED, "check")],
        full_audit(),
        [gap],
        False,
    )
    attempts: list[str] = []
    evidence_calls = 0

    def searcher(gap_id: str, query: str) -> RetrievalTrace:
        attempts.append(query)
        if len(attempts) == 1:
            return RetrievalTrace(
                gap_id=gap_id,
                planned_query=query,
                query_attempted=True,
                executed_query=query,
                executed_queries=[query],
                backend_raw_result_count=0,
            )
        return RetrievalTrace(
            gap_id=gap_id,
            planned_query=query,
            query_attempted=True,
            executed_query=query,
            executed_queries=[query, "provider 扩展查询"],
            query_budget_consumed=1,
            results_discarded=False,
            backend_raw_result_count=11,
        )

    def reject_twice(public_case, state, gap_id, trace, current_ir):
        nonlocal evidence_calls
        evidence_calls += 1
        next_query = "规则 查询 2" if evidence_calls == 1 else None
        return EvidenceDecision([], Admission.REJECT, None, next_query, "insufficient")

    result = run_case(
        public,
        SCHEMA,
        PipelineServices(lambda _: initial, searcher, reject_twice),
    )

    assert result["status"] == "ABSTAIN"
    assert result["retrieval_status"] == "SEARCH_FAILURE"
    assert result["search"]["search_count"] == 2
    assert result["search"]["search_round_count"] == 2
    assert [row["query_budget_consumed"] for row in result["search"]["rounds"]] == [1, 1]
    assert result["search"]["rounds"][-1]["results_discarded"] is False
    assert len(result["search"]["rounds"][-1]["executed_queries"]) == 2
    assert evidence_calls == 2
    assert len(attempts) == 2
    assert result["state"]["round"] == 2
    assert result["state"]["search_budget_left"] == 1


def test_invalid_second_round_three_unit_trace_still_raises_infrastructure_overrun() -> None:
    public = PublicCase("S5-EXPANSION-OVERRUN", "外部规则尚待核实。")
    gap = CandidateGapDraft(
        ["外部规则尚待核实"], "ELIGIBILITY", "方案Y是否允许", "variable.y", GapRoute.EXTERNAL_RULE,
        boundary_variants("variable.y"),
        "规则 查询 1",
    )
    initial = InitialDecision(
        IR,
        [FactCoverageDraft("外部规则尚待核实", "COST", [], FactUsageStatus.UNACCOUNTED, "check")],
        full_audit(),
        [gap],
        False,
    )
    attempts: list[str] = []
    evidence_calls = 0

    def searcher(gap_id: str, query: str) -> RetrievalTrace:
        attempts.append(query)
        if len(attempts) == 1:
            return RetrievalTrace(
                gap_id=gap_id,
                planned_query=query,
                query_attempted=True,
                executed_query=query,
                executed_queries=[query],
            )
        return RetrievalTrace(
            gap_id=gap_id,
            planned_query=query,
            query_attempted=True,
            executed_query=query,
            executed_queries=[query, "provider 扩展查询二", "provider 扩展查询三"],
            query_budget_consumed=3,
            results_discarded=False,
            backend_raw_result_count=12,
        )

    def reject_once(public_case, state, gap_id, trace, current_ir):
        nonlocal evidence_calls
        evidence_calls += 1
        return EvidenceDecision([], Admission.REJECT, None, "规则 查询 2", "insufficient")

    with pytest.raises(SearchBudgetOverrun) as caught:
        run_case(public, SCHEMA, PipelineServices(lambda _: initial, searcher, reject_once))

    assert caught.value.prior_budget == 1
    assert caught.value.remaining_budget == 2
    assert caught.value.actual_consumed == 3
    assert evidence_calls == 1
    assert len(attempts) == 2

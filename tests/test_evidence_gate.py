from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from searchworthy.contracts import (
    Admission,
    AuditDimension,
    AuditSummary,
    CandidateGapDraft,
    EvidenceCard,
    EvidenceDecision,
    EvidenceRoute,
    FactCoverageDraft,
    FactUsageStatus,
    GapRoute,
    InitialDecision,
    PatchPlan,
    PotentialEffect,
    PublicCase,
    RetrievalTrace,
    StateUpdate,
    jsonable,
)
from searchworthy.evidence import assess_evidence, authorize_search, route_evidence
from searchworthy.or_model import solve_initial
from searchworthy.pipeline import initialize_state, record_search_round
from searchworthy.state import apply_state_update


SCHEMA = {"actions": [{"id": "x", "type": "BINARY"}], "objective": {"accepted_units": {"点": 1}, "canonical_unit": "点"}}
IR = {
    "variables": [{"id": "x", "type": "BINARY", "lb": 0, "ub": 1}],
    "constraints": [
        {"name": "rule_cap", "terms": [{"var": "x", "coef": 1}], "sense": "<=", "rhs": 100}
    ],
    "objective": {"direction": "max", "terms": [{"var": "x", "coef": 1}], "constant": 0, "unit": "点"},
    "parameters": {},
}


def active_state(route: GapRoute = GapRoute.EXTERNAL_RULE, target: str = "constraint.rule_cap"):
    public = PublicCase("Q1", "当前企业位于甲地。")
    query = "甲地 规则 官方" if route == GapRoute.EXTERNAL_RULE else None
    gap = CandidateGapDraft(["当前企业位于甲地"], "JURISDICTION", "规则是否限制方案X", target, route, [], query)
    initial = InitialDecision(
        IR,
        [FactCoverageDraft("当前企业位于甲地", "JURISDICTION", [], FactUsageStatus.UNACCOUNTED, "check")],
        AuditSummary(True, True, {d: True for d in AuditDimension}),
        [gap],
        False,
    )
    ir, capture = solve_initial(IR, SCHEMA)
    state = initialize_state(public, initial, ir, capture)
    state.gaps[0].potential_effect = PotentialEffect.DECISION_CHANGE
    state.gaps[0].probe_coverage = True
    decision = authorize_search(state, "G1")
    if route == GapRoute.EXTERNAL_RULE:
        assert decision.authorized
        state = apply_state_update(state, StateUpdate.search_authorized("G1"))
    return public, ir, state


def test_search_authorization_uses_solver_impact_and_external_route() -> None:
    _, _, state = active_state(GapRoute.EXTERNAL_RULE)
    assert state.active_gap_id == "G1"
    _, _, local = active_state(GapRoute.LOCAL_FACT)
    assert not authorize_search(local, "G1").authorized


def test_provider_query_expansion_consumes_one_search_call_budget() -> None:
    _, _, state = active_state(GapRoute.EXTERNAL_RULE)
    trace = RetrievalTrace(
        gap_id="G1",
        planned_query="甲地 规则 官方",
        query_attempted=True,
        executed_query="甲地 规则 官方",
        executed_queries=["甲地 规则 官方", "扩展查询二", "扩展查询三"],
        query_budget_consumed=1,
        results_discarded=False,
    )

    updated = record_search_round(state, "G1", trace)

    assert updated.round == 1
    assert updated.search_budget_left == 2
    assert state.round == 0
    assert state.search_budget_left == 3


def test_four_hard_gates_admit_correct_patch() -> None:
    public, ir, state = active_state(target="objective.x")
    trace = RetrievalTrace(
        "G1",
        "甲地 规则 官方",
        True,
        opened_pages=[{"final_url": "https://authority.example/rule", "visible_text": "本规则适用于甲地企业。方案X收益系数调整为3。"}],
    )
    cards = [EvidenceCard(
        "E1", "https://authority.example/rule", "方案X收益系数调整为3", "方案X系数为3", "当前企业位于甲地", "本规则适用于甲地企业", "objective.x", True, True, True, True,
        "parameters.coefficient", 3,
    )]
    plan = PatchPlan(
        "SET_OBJECTIVE_COEFFICIENT",
        "objective.x",
        {"coefficient": 3},
        1.0,
        ["E1"],
    )
    decision = assess_evidence(EvidenceDecision(cards, Admission.ADMIT_PATCH, plan, None, "supported"), state, "G1", trace, public.prompt_zh, ir)
    assert decision.admission == Admission.ADMIT_PATCH
    assert route_evidence(decision, 2) == EvidenceRoute.PATCH


def test_wrong_scope_or_target_cannot_be_compensated_by_authority() -> None:
    public, ir, state = active_state()
    trace = RetrievalTrace(
        "G1",
        "甲地 规则 官方",
        True,
        opened_pages=[{"final_url": "https://authority.example/rule", "visible_text": "本规则只适用于乙地企业。方案X必须满足上限。"}],
    )
    card = EvidenceCard(
        "E1", "https://authority.example/rule", "方案X必须满足上限", "规则", "当前企业位于甲地", "不存在的适用范围", "objective.x", True, True, True, True
    )
    plan = PatchPlan("SET_OBJECTIVE_COEFFICIENT", "constraint.rule_cap", {"coefficient": 3}, None, ["E1"])
    decision = assess_evidence(EvidenceDecision([card], Admission.ADMIT_PATCH, plan, "甲地 法规 正文", "authoritative"), state, "G1", trace, public.prompt_zh, ir)
    assert decision.admission == Admission.REJECT
    assert route_evidence(decision, 2) == EvidenceRoute.SEARCH_AGAIN


def test_scope_and_case_quotes_cannot_make_self_reported_not_applies_close() -> None:
    public, ir, state = active_state()
    trace = RetrievalTrace(
        "G1",
        "甲地 规则 官方",
        True,
        opened_pages=[{"final_url": "https://authority.example/rule", "visible_text": "本规则只适用于乙地企业。"}],
    )
    card = EvidenceCard(
        "E1", "https://authority.example/rule", "本规则只适用于乙地企业", "不适用于甲地", "当前企业位于甲地", "本规则只适用于乙地企业", "constraint.rule_cap", True, False, True, True
    )
    decision = assess_evidence(EvidenceDecision([card], Admission.NOT_APPLIES, None, None, "scope mismatch"), state, "G1", trace, public.prompt_zh, ir)
    assert decision.admission == Admission.REJECT
    assert route_evidence(decision, 2) == EvidenceRoute.ABSTAIN


def test_already_modeled_cannot_copy_a_structured_variable_target() -> None:
    public, ir, state = active_state(target="variable.x")
    trace = RetrievalTrace(
        "G1", "甲地 规则 官方", True,
        opened_pages=[{"final_url": "https://authority.example/rule", "visible_text": "本规则适用于甲地企业。正文没有变量边界。"}],
    )
    card = EvidenceCard(
        "E-DICT", "https://authority.example/rule", "正文没有变量边界", "复制当前边界", "当前企业位于甲地", "本规则适用于甲地企业", "variable.x", True, True, True, True,
        "target_value", {"lb": 0.0, "ub": 1.0},
    )
    decision = assess_evidence(
        EvidenceDecision([card], Admission.ALREADY_MODELED, None, None, "copy current dict"),
        state, "G1", trace, public.prompt_zh, ir,
    )
    assert decision.admission == Admission.REJECT
    assert decision.evidence_cards[0].bindable is False


def test_evidence_threshold_50_cannot_bind_patch_rhs_20() -> None:
    public, ir, state = active_state()
    trace = RetrievalTrace(
        "G1",
        "甲地 规则 官方",
        True,
        opened_pages=[{"final_url": "https://authority.example/rule", "visible_text": "本规则适用于甲地企业。方案X选择量上限为50。"}],
    )
    cards = [
        EvidenceCard(
            "E1", "https://authority.example/rule", "方案X选择量上限为50", "上限50", "当前企业位于甲地", "本规则适用于甲地企业", "constraint.rule_cap", True, True, True, True,
            "parameters.constraint.rhs", 50,
        ),
        EvidenceCard(
            "E2", "https://authority.example/rule", "方案X选择量上限为50", "不超过上限", "当前企业位于甲地", "本规则适用于甲地企业", "constraint.rule_cap", True, True, True, True,
            "parameters.constraint.sense", "<=",
        ),
    ]
    plan = PatchPlan(
        "UPSERT_CONSTRAINT",
        "constraint.rule_cap",
        {"constraint": {"name": "rule_cap", "terms": [{"var": "x", "coef": 1}], "sense": "<=", "rhs": 20}},
        None,
        ["E1", "E2"],
    )
    decision = assess_evidence(
        EvidenceDecision(cards, Admission.ADMIT_PATCH, plan, None, "bind 20"),
        state,
        "G1",
        trace,
        public.prompt_zh,
        ir,
    )
    assert decision.admission == Admission.REJECT


def test_upsert_terms_cannot_be_injected_outside_evidence() -> None:
    public, ir, state = active_state()
    trace = RetrievalTrace(
        "G1", "甲地 规则 官方", True,
        opened_pages=[{"final_url": "https://authority.example/rule", "visible_text": "本规则适用于甲地企业。方案X上限为50。"}],
    )
    cards = [
        EvidenceCard(
            "E1", "https://authority.example/rule", "方案X上限为50", "rhs 50", "当前企业位于甲地", "本规则适用于甲地企业", "constraint.rule_cap", True, True, True, True,
            "parameters.constraint.rhs", 50,
        ),
        EvidenceCard(
            "E2", "https://authority.example/rule", "方案X上限为50", "sense <=", "当前企业位于甲地", "本规则适用于甲地企业", "constraint.rule_cap", True, True, True, True,
            "parameters.constraint.sense", "<=",
        ),
    ]
    plan = PatchPlan(
        "UPSERT_CONSTRAINT",
        "constraint.rule_cap",
        {"constraint": {"name": "rule_cap", "terms": [{"var": "x", "coef": 999}], "sense": "<=", "rhs": 50}},
        None,
        ["E1", "E2"],
    )
    decision = assess_evidence(
        EvidenceDecision(cards, Admission.ADMIT_PATCH, plan, None, "inject terms"),
        state, "G1", trace, public.prompt_zh, ir,
    )
    assert decision.admission == Admission.REJECT


def test_same_target_binding_conflict_is_forced_to_conflict() -> None:
    public, ir, state = active_state()
    trace = RetrievalTrace(
        "G1",
        "甲地 规则 官方",
        True,
        opened_pages=[{
            "final_url": "https://authority.example/rule",
            "visible_text": "本规则适用于甲地企业。第一条正文称上限为50，第二条正文称上限为20。",
        }],
    )
    cards = [
        EvidenceCard(
            "E1", "https://authority.example/rule", "第一条正文称上限为50", "上限50", "当前企业位于甲地", "本规则适用于甲地企业", "constraint.rule_cap", True, True, True, True,
            "parameters.constraint.rhs", 50,
        ),
        EvidenceCard(
            "E2", "https://authority.example/rule", "第二条正文称上限为20", "上限20", "当前企业位于甲地", "本规则适用于甲地企业", "constraint.rule_cap", True, True, True, True,
            "parameters.constraint.rhs", 20,
        ),
    ]
    decision = assess_evidence(
        EvidenceDecision(cards, Admission.REJECT, None, None, "review"),
        state,
        "G1",
        trace,
        public.prompt_zh,
        ir,
    )
    assert decision.admission == Admission.CONFLICT
    assert all(card.consistent is False for card in decision.evidence_cards)


def test_prior_round_binding_conflict_cannot_be_forgotten() -> None:
    public, ir, state = active_state()
    first_trace = RetrievalTrace(
        "G1",
        "甲地 规则 官方",
        True,
        opened_pages=[{"final_url": "https://authority.example/first", "visible_text": "本规则适用于甲地企业。正文上限为50。"}],
    )
    first_card = EvidenceCard(
        "E1", "https://authority.example/first", "正文上限为50", "上限50", "当前企业位于甲地", "本规则适用于甲地企业", "constraint.rule_cap", True, True, True, True,
        "parameters.constraint.rhs", 50,
    )
    first = assess_evidence(
        EvidenceDecision([first_card], Admission.REJECT, None, "继续查规则", "need another source"),
        state,
        "G1",
        first_trace,
        public.prompt_zh,
        ir,
    )
    state = apply_state_update(state, StateUpdate.evidence_observed("G1", jsonable(first.evidence_cards)))

    second_trace = RetrievalTrace(
        "G1",
        "继续查规则",
        True,
        opened_pages=[{"final_url": "https://authority.example/second", "visible_text": "本规则适用于甲地企业。正文上限为20。"}],
    )
    second_card = EvidenceCard(
        "E2", "https://authority.example/second", "正文上限为20", "上限20", "当前企业位于甲地", "本规则适用于甲地企业", "constraint.rule_cap", True, True, True, True,
        "parameters.constraint.rhs", 20,
    )
    second = assess_evidence(
        EvidenceDecision([second_card], Admission.REJECT, None, None, "review"),
        state,
        "G1",
        second_trace,
        public.prompt_zh,
        ir,
    )
    assert second.admission == Admission.CONFLICT
    assert second.evidence_cards[0].consistent is False


def test_same_target_conflict_is_detected_across_different_gaps() -> None:
    public = PublicCase("Q-CROSS-GAP", "规则A尚待核实。规则B尚待核实。")
    gaps = [
        CandidateGapDraft(["规则A尚待核实"], "RULE", "规则A阈值", "constraint.rule_cap", GapRoute.EXTERNAL_RULE, [], "规则 A 官方"),
        CandidateGapDraft(["规则B尚待核实"], "RULE", "规则B阈值", "constraint.rule_cap", GapRoute.EXTERNAL_RULE, [], "规则 B 官方"),
    ]
    initial = InitialDecision(
        IR,
        [
            FactCoverageDraft("规则A尚待核实", "RULE", [], FactUsageStatus.UNACCOUNTED, "check A"),
            FactCoverageDraft("规则B尚待核实", "RULE", [], FactUsageStatus.UNACCOUNTED, "check B"),
        ],
        AuditSummary(True, True, {d: True for d in AuditDimension}),
        gaps,
        False,
    )
    ir, capture = solve_initial(IR, SCHEMA)
    state = initialize_state(public, initial, ir, capture)
    for gap in state.gaps:
        gap.potential_effect = PotentialEffect.DECISION_CHANGE
        gap.probe_coverage = True
    state = apply_state_update(state, StateUpdate.search_authorized("G1"))
    first_trace = RetrievalTrace(
        "G1", "规则 A 官方", True,
        opened_pages=[{"final_url": "https://authority.example/a", "visible_text": "本规则适用于该企业。规则A上限为50。"}],
    )
    first_card = EvidenceCard(
        "EA", "https://authority.example/a", "规则A上限为50", "A=50", "规则A尚待核实", "本规则适用于该企业", "constraint.rule_cap", True, True, True, True,
        "parameters.constraint.rhs", 50,
    )
    first = assess_evidence(
        EvidenceDecision([first_card], Admission.REJECT, None, None, "observe A"),
        state, "G1", first_trace, public.prompt_zh, ir,
    )
    state = apply_state_update(state, StateUpdate.evidence_observed("G1", jsonable(first.evidence_cards)))
    state = apply_state_update(state, StateUpdate.abstain("G1", "continue independent gap"))
    state = apply_state_update(state, StateUpdate.search_authorized("G2"))

    second_trace = RetrievalTrace(
        "G2", "规则 B 官方", True,
        opened_pages=[{"final_url": "https://authority.example/b", "visible_text": "本规则适用于该企业。规则B上限为20。"}],
    )
    second_card = EvidenceCard(
        "EB", "https://authority.example/b", "规则B上限为20", "B=20", "规则B尚待核实", "本规则适用于该企业", "constraint.rule_cap", True, True, True, True,
        "parameters.constraint.rhs", 20,
    )
    second = assess_evidence(
        EvidenceDecision([second_card], Admission.REJECT, None, None, "observe B"),
        state, "G2", second_trace, public.prompt_zh, ir,
    )
    assert second.admission == Admission.CONFLICT
    assert second.evidence_cards[0].consistent is False

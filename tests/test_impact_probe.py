from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from searchworthy.contracts import (
    AuditDimension,
    AuditSummary,
    CandidateGapDraft,
    FactCoverageDraft,
    FactUsageStatus,
    GapRoute,
    GapState,
    InitialDecision,
    PotentialEffect,
    PublicCase,
)
from searchworthy.evidence import authorize_search
from searchworthy.or_model import compare_solves, probe_all_gaps, probe_gap, solve_initial
from searchworthy.pipeline import initialize_state, variants_by_gap


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


def test_solver_probe_authorizes_only_observed_effect() -> None:
    ir, base = solve_initial(IR, SCHEMA)
    variants = [
        {
            "target": "variable.y",
            "operation": "SET",
            "value": {"lb": 0, "ub": 0},
            "range_basis": "MODEL_BOUNDARY",
            "basis_quote": None,
        }
    ]
    effect, coverage, diagnostic = probe_gap(ir, base, "variable.y", variants, SCHEMA, "题面")
    assert effect == PotentialEffect.DECISION_CHANGE
    assert coverage is True
    assert diagnostic["captures"][0]["solve"]["candidate_actions"] != base.actions


def test_program_materializes_empty_external_binary_disable_probe() -> None:
    public = PublicCase("P-PROGRAM-PROBE", "方案Y的现实资格规则未知。")
    draft = CandidateGapDraft(
        ["方案Y的现实资格规则未知"],
        "ELIGIBILITY",
        "方案Y是否具备资格",
        "variable.y",
        GapRoute.EXTERNAL_RULE,
        [],
        "方案Y 资格 官方",
    )
    initial = InitialDecision(
        IR,
        [FactCoverageDraft("方案Y的现实资格规则未知", "ELIGIBILITY", [], FactUsageStatus.UNACCOUNTED, "probe")],
        AuditSummary(True, True, {dimension: True for dimension in AuditDimension}),
        [draft],
        False,
    )
    ir, base = solve_initial(IR, SCHEMA)
    state = initialize_state(public, initial, ir, base)
    variants = variants_by_gap(state, [draft], ir)
    assert variants == {
        "G1": [
            {
                "target": "variable.y",
                "operation": "SET",
                "value": {"lb": 0, "ub": 0},
                "range_basis": "MODEL_BOUNDARY",
                "basis_quote": None,
            }
        ]
    }
    state = probe_all_gaps(state, ir, variants, SCHEMA, public.prompt_zh)
    assert state.gaps[0].potential_effect == PotentialEffect.DECISION_CHANGE
    assert state.gaps[0].probe_coverage is True
    assert authorize_search(state, "G1").authorized is True


def test_program_does_not_materialize_probe_for_local_fact_route() -> None:
    public = PublicCase("P-LOCAL", "方案Y资格记录未提供。")
    draft = CandidateGapDraft(
        ["方案Y资格记录未提供"],
        "ELIGIBILITY",
        "方案Y本地资格记录缺失",
        "variable.y",
        GapRoute.LOCAL_FACT,
        [],
        None,
    )
    initial = InitialDecision(
        IR,
        [FactCoverageDraft("方案Y资格记录未提供", "ELIGIBILITY", [], FactUsageStatus.UNACCOUNTED, "local")],
        AuditSummary(True, True, {dimension: True for dimension in AuditDimension}),
        [draft],
        False,
    )
    ir, base = solve_initial(IR, SCHEMA)
    state = initialize_state(public, initial, ir, base)
    assert variants_by_gap(state, [draft], ir) == {"G1": []}


def test_disabling_a_dominated_action_does_not_authorize_search() -> None:
    public = PublicCase("P-DOMINATED", "方案X的现实资格规则未知。")
    variant = {
        "target": "variable.x",
        "operation": "SET",
        "value": {"lb": 0, "ub": 0},
        "range_basis": "MODEL_BOUNDARY",
        "basis_quote": None,
    }
    draft = CandidateGapDraft(
        ["方案X的现实资格规则未知"],
        "ELIGIBILITY",
        "方案X是否具备资格",
        "variable.x",
        GapRoute.EXTERNAL_RULE,
        [variant],
        "方案X 资格 官方",
    )
    initial = InitialDecision(
        IR,
        [FactCoverageDraft("方案X的现实资格规则未知", "ELIGIBILITY", [], FactUsageStatus.UNACCOUNTED, "probe")],
        AuditSummary(True, True, {dimension: True for dimension in AuditDimension}),
        [draft],
        False,
    )
    ir, base = solve_initial(IR, SCHEMA)
    state = initialize_state(public, initial, ir, base)
    state = probe_all_gaps(state, ir, variants_by_gap(state, [draft], ir), SCHEMA, public.prompt_zh)
    assert state.gaps[0].potential_effect == PotentialEffect.NO_EFFECT
    assert state.gaps[0].probe_coverage is True
    decision = authorize_search(state, "G1")
    assert decision.authorized is False
    assert decision.reason == "NO_SOLVER_CRITICAL_EFFECT"


def test_no_effect_without_registered_range_cannot_close() -> None:
    ir, base = solve_initial(IR, SCHEMA)
    variant = {"target": "objective.x", "operation": "SET", "value": 1, "range_basis": "LLM_GUESS"}
    effect, coverage, _ = probe_gap(ir, base, "objective.x", [variant], SCHEMA, "题面")
    assert effect == PotentialEffect.UNKNOWN
    assert coverage is False


def test_arbitrary_prompt_quote_cannot_bind_an_objective_probe() -> None:
    public = PublicCase("P1", "规则成本未知。")
    draft = CandidateGapDraft(
        ["规则成本未知"],
        "COST",
        "成本是否改变",
        "objective.x",
        GapRoute.EXTERNAL_RULE,
        [{"target": "objective.x", "operation": "SET", "value": 1, "range_basis": "PROMPT", "basis_quote": "规则成本未知"}],
        "成本 规则 官方",
    )
    initial = InitialDecision(
        IR,
        [FactCoverageDraft("规则成本未知", "COST", [], FactUsageStatus.UNACCOUNTED, "probe")],
        AuditSummary(True, True, {d: True for d in AuditDimension}),
        [draft],
        False,
    )
    ir, base = solve_initial(IR, SCHEMA)
    state = initialize_state(public, initial, ir, base)
    state = probe_all_gaps(state, ir, variants_by_gap(state, [draft], ir), SCHEMA, public.prompt_zh)
    assert state.gaps[0].potential_effect == PotentialEffect.UNKNOWN
    assert state.gaps[0].probe_coverage is False
    assert state.gaps[0].state == GapState.OPEN
    assert state.fact_coverage[0].usage_status == FactUsageStatus.UNACCOUNTED


def test_eligible_action_ids_object_cannot_fake_a_constraint_probe() -> None:
    ir, base = solve_initial(IR, SCHEMA)
    variant = {
        "target": "constraint.eligibility",
        "operation": "SET",
        "value": {"eligible_action_ids": ["x"]},
        "range_basis": "MODEL_BOUNDARY",
        "basis_quote": None,
    }
    effect, coverage, diagnostic = probe_gap(
        ir,
        base,
        "constraint.eligibility",
        [variant],
        SCHEMA,
        "设备类别清单",
    )
    assert effect == PotentialEffect.UNKNOWN
    assert coverage is False
    assert "basis is not program-verifiable" in diagnostic["reason"]


def test_parameter_metadata_can_never_create_false_no_effect_closure() -> None:
    ir, base = solve_initial(IR, SCHEMA)
    variant = {"target": "parameter.threshold", "operation": "SET", "value": 3, "range_basis": "PROMPT", "basis_quote": "阈值为3"}
    effect, coverage, diagnostic = probe_gap(ir, base, "parameter.threshold", [variant], SCHEMA, "阈值为3")
    assert effect == PotentialEffect.UNKNOWN
    assert coverage is False
    assert "does not consume" in diagnostic["reason"]


def test_truncated_optimal_solution_pool_is_unknown_not_no_effect() -> None:
    _, base = solve_initial(IR, SCHEMA)
    candidate = copy.deepcopy(base)
    base.diagnostic["optimal_action_sets_truncated"] = True
    candidate.diagnostic["optimal_action_sets_truncated"] = True
    effect, _ = compare_solves(base, candidate)
    assert effect == PotentialEffect.UNKNOWN

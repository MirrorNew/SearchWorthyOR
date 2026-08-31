from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from searchworthy.contracts import (
    AuditDimension,
    AuditSummary,
    CandidateGapDraft,
    EvidenceCard,
    EvidenceDecision,
    FactCoverageDraft,
    FactUsageStatus,
    GapRoute,
    InitialDecision,
    PatchBundle,
    PatchOperation,
    PatchPlan,
    PotentialEffect,
    PublicCase,
    StateUpdate,
    GapState,
    jsonable,
)
from searchworthy.or_model import apply_patch_and_solve, compare_solves, compile_and_solve, solve_initial
from searchworthy.patch import PatchValidationError, apply_patch_transactionally, expand_patch_plan
from searchworthy.pipeline import initialize_state, record_solve_delta
from searchworthy.state import apply_state_update


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


def patch_ready_state():
    public = PublicCase("T1", "外部规则要求调整方案X收益。")
    gap = CandidateGapDraft(["外部规则要求调整方案X收益"], "COST", "收益是否调整", "objective.x", GapRoute.EXTERNAL_RULE, [], "收益 规则 官方")
    initial = InitialDecision(
        IR,
        [FactCoverageDraft("外部规则要求调整方案X收益", "COST", [], FactUsageStatus.UNACCOUNTED, "check")],
        AuditSummary(True, True, {d: True for d in AuditDimension}),
        [gap],
        False,
    )
    ir, capture = solve_initial(IR, SCHEMA)
    state = initialize_state(public, initial, ir, capture)
    state.gaps[0].potential_effect = PotentialEffect.DECISION_CHANGE
    state = apply_state_update(state, StateUpdate.search_authorized("G1"))
    card = EvidenceCard(
        "E1", "https://a", "coefficient 3", "c", "case", "scope", "objective.x", True, True, True, True,
        "parameters.coefficient", 3,
    )
    evidence = EvidenceDecision([card], "ADMIT_PATCH", None, None, "ok")
    state = apply_state_update(state, StateUpdate.patch_ready("G1", jsonable(evidence)))
    return state, ir, capture


def test_evidence_bound_patch_changes_canonical_ir_and_solver_decision() -> None:
    state, ir, base = patch_ready_state()
    plan = PatchPlan("SET_OBJECTIVE_COEFFICIENT", "objective.x", {"coefficient": 3}, 1.0, ["E1"])
    bundle = expand_patch_plan(state, ir, "G1", plan)
    patched = apply_patch_transactionally(ir, bundle, SCHEMA)
    capture = compile_and_solve(patched, SCHEMA)
    effect, _ = compare_solves(base, capture)
    assert effect == PotentialEffect.DECISION_CHANGE
    assert ir["objective"]["terms"][0]["coef"] == 1.0
    assert patched["objective"]["terms"][0]["coef"] == 3.0
    updated, committed = record_solve_delta(state, "G1", ir, patched, capture, bundle)
    assert committed == patched
    assert updated.gaps[0].state == GapState.CLOSED_PATCH
    assert updated.fact_coverage[0].usage_status == FactUsageStatus.MODELED
    assert updated.fact_coverage[0].mapped_targets == ["objective.x"]


def test_patch_bundle_is_transactional_when_later_operation_fails() -> None:
    _, ir, _ = patch_ready_state()
    original = copy.deepcopy(ir)
    bundle = PatchBundle(
        "G1",
        ["E1"],
        [
            PatchOperation("UPSERT", "constraint.force_x", None, {"name": "force_x", "terms": [{"var": "x", "coef": 1}], "sense": "==", "rhs": 1}),
            PatchOperation("SET", "objective.x", 1.0, "not-a-number"),
        ],
    )
    with pytest.raises(PatchValidationError):
        apply_patch_transactionally(ir, bundle, SCHEMA)
    assert ir == original


def test_before_guard_mismatch_is_rejected() -> None:
    state, ir, _ = patch_ready_state()
    plan = PatchPlan("SET_OBJECTIVE_COEFFICIENT", "objective.x", {"coefficient": 3}, 999, ["E1"])
    with pytest.raises(PatchValidationError, match="before_guard"):
        expand_patch_plan(state, ir, "G1", plan)


def test_patch_expansion_rechecks_exact_evidence_binding() -> None:
    state, ir, _ = patch_ready_state()
    plan = PatchPlan("SET_OBJECTIVE_COEFFICIENT", "objective.x", {"coefficient": 4}, 1.0, ["E1"])
    with pytest.raises(PatchValidationError, match="evidence bindings"):
        expand_patch_plan(state, ir, "G1", plan)


def test_infeasible_patch_is_rolled_back_and_abstains() -> None:
    state, ir, _ = patch_ready_state()
    state.gaps[0].target = "constraint.impossible"
    bundle = PatchBundle(
        "G1",
        ["E1"],
        [PatchOperation("UPSERT", "constraint.impossible", None, {"name": "impossible", "terms": [{"var": "x", "coef": 1}, {"var": "y", "coef": 1}], "sense": "<=", "rhs": 0})],
    )
    candidate, capture = apply_patch_and_solve(ir, bundle, SCHEMA)
    updated, committed = record_solve_delta(state, "G1", ir, candidate, capture, bundle)
    assert capture.feasible is False
    assert committed is ir
    assert updated.gaps[0].state == GapState.UNRESOLVED_ABSTAIN


def test_value_only_patch_with_stable_action_is_rolled_back() -> None:
    state, ir, _ = patch_ready_state()
    state.gaps[0].target = "objective.y"
    bundle = PatchBundle("G1", ["E1"], [PatchOperation("SET", "objective.y", 2.0, 3.0)])
    candidate, capture = apply_patch_and_solve(ir, bundle, SCHEMA)
    updated, committed = record_solve_delta(state, "G1", ir, candidate, capture, bundle)
    assert capture.actions == state.current_solve.actions
    assert committed is ir
    assert updated.gaps[0].state == GapState.UNRESOLVED_ABSTAIN


def test_parameter_patch_is_rejected_until_compiler_consumes_parameters() -> None:
    state, ir, _ = patch_ready_state()
    state.gaps[0].target = "parameter.threshold"
    plan = PatchPlan("SET_PARAMETER", "parameter.threshold", {"value": 3}, None, ["E1"])
    with pytest.raises(PatchValidationError):
        expand_patch_plan(state, ir, "G1", plan)


def test_remove_constraint_cannot_use_empty_unverifiable_binding() -> None:
    state, ir, _ = patch_ready_state()
    state.gaps[0].target = "constraint.one"
    plan = PatchPlan("REMOVE_CONSTRAINT", "constraint.one", {}, ir["constraints"][0], ["E1"])
    with pytest.raises(PatchValidationError, match="family"):
        expand_patch_plan(state, ir, "G1", plan)

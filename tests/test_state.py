from __future__ import annotations

import copy
import itertools
import json
import re
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from searchworthy.contracts import (
    Admission,
    AuditDimension,
    AuditSummary,
    CandidateGapDraft,
    EvidenceDecision,
    FactCoverageDraft,
    FactUsageStatus,
    GapRoute,
    InitialDecision,
    PotentialEffect,
    PublicCase,
    RetrievalTrace,
    StateUpdate,
    parse_initial_decision,
)
from searchworthy.or_model import compact_binary_upper_bound_constraints, solve_initial
from searchworthy.pipeline import (
    PipelineServices,
    PROGRAM_FACT_COVERAGE_CLOSURE_MARKER,
    _close_stage_fact_coverage,
    _compact_unit,
    _fact_unit_covered,
    _fact_unit_fully_covered,
    _prompt_fact_unit_spans,
    _quote_supports_applicability_target,
    finalize,
    initialize_state,
    prompt_fact_prefix,
    prompt_fact_units,
    run_case,
)
from searchworthy.state import apply_state_update, audit_complete, select_next_gap


def schema() -> dict:
    return {
        "actions": [{"id": "x", "type": "BINARY"}, {"id": "y", "type": "BINARY"}],
        "objective": {"accepted_units": {"点": 1}, "canonical_unit": "点"},
    }


def model_ir() -> dict:
    return {
        "variables": [
            {"id": "x", "type": "BINARY", "lb": 0, "ub": 1},
            {"id": "y", "type": "BINARY", "lb": 0, "ub": 1},
        ],
        "constraints": [{"name": "choose_one", "terms": [{"var": "x", "coef": 1}, {"var": "y", "coef": 1}], "sense": "==", "rhs": 1}],
        "objective": {"direction": "max", "terms": [{"var": "x", "coef": 1}, {"var": "y", "coef": 2}], "constant": 0, "unit": "点"},
        "parameters": {},
    }


def test_binary_upper_bound_compaction_preserves_every_assignment() -> None:
    ir = {
        "variables": [
            {"id": "x", "type": "BINARY", "lb": 0, "ub": 1},
            {"id": "y", "type": "BINARY", "lb": 0, "ub": 1},
            {"id": "z", "type": "BINARY", "lb": 0, "ub": 1},
        ],
        "constraints": [
            {"name": "tautology", "terms": [{"var": "x", "coef": 40}], "sense": "<=", "rhs": 55},
            {
                "name": "bad_pair",
                "terms": [{"var": "x", "coef": 40}, {"var": "y", "coef": 35}],
                "sense": "<=",
                "rhs": 70,
            },
            {
                "name": "dominated_triple",
                "terms": [{"var": "x", "coef": 40}, {"var": "y", "coef": 35}, {"var": "z", "coef": 30}],
                "sense": "<=",
                "rhs": 80,
            },
            {
                "name": "balance",
                "terms": [{"var": "x", "coef": 1}, {"var": "y", "coef": 1}, {"var": "z", "coef": 1}],
                "sense": ">=",
                "rhs": 1,
            },
        ],
        "objective": {"direction": "max", "terms": [{"var": "x", "coef": 1}], "constant": 0, "unit": "点"},
        "parameters": {},
    }
    compacted = compact_binary_upper_bound_constraints(ir)
    assert len(compacted["constraints"]) == 2

    def feasible(rows: list[dict], values: dict[str, int]) -> bool:
        for row in rows:
            lhs = sum(term["coef"] * values[term["var"]] for term in row["terms"])
            if row["sense"] == "<=" and lhs > row["rhs"]:
                return False
            if row["sense"] == ">=" and lhs < row["rhs"]:
                return False
            if row["sense"] == "==" and lhs != row["rhs"]:
                return False
        return True

    for bits in itertools.product((0, 1), repeat=3):
        values = dict(zip(("x", "y", "z"), bits))
        assert feasible(ir["constraints"], values) == feasible(compacted["constraints"], values)


def audit(*, overflow: int = 0) -> AuditSummary:
    return AuditSummary(
        True,
        True,
        {dimension: True for dimension in AuditDimension},
        overflow_detected=overflow > 0,
        overflow_count=overflow,
        self_contained_reason=None,
        prompt_fact_unit_total=1,
        prompt_fact_unit_covered=1,
        prompt_fact_coverage_ratio=1.0,
    )


def test_audit_requires_both_directions_and_exact_nine_dimensions() -> None:
    complete = audit()
    assert audit_complete(complete)
    incomplete = copy.deepcopy(complete)
    incomplete.negative_space_checked.pop(AuditDimension.COST_BENEFIT)
    assert not audit_complete(incomplete)
    overflow = audit(overflow=1)
    assert not audit_complete(overflow)


def test_initialization_verifies_quote_target_and_unaccounted_gap_link() -> None:
    public = PublicCase("E1", "必须恰好选择一个方案。现实规则阈值尚不明确。")
    initial = InitialDecision(
        model_ir(),
        [
            FactCoverageDraft("必须恰好选择一个方案", "FEASIBILITY", ["constraint.choose_one"], FactUsageStatus.MODELED, "进入约束"),
            FactCoverageDraft("现实规则阈值尚不明确", "THRESHOLD", [], FactUsageStatus.UNACCOUNTED, "需检查"),
        ],
        audit(),
        [CandidateGapDraft(["现实规则阈值尚不明确"], "THRESHOLD", "阈值是否限制方案X", "constraint.choose_one", GapRoute.EXTERNAL_RULE, [], "规则 阈值 官方")],
        False,
    )
    ir, capture = solve_initial(initial.model_ir, schema())
    state = initialize_state(public, initial, ir, capture)
    assert state.fact_coverage[1].gap_id == "G1"
    assert state.gaps[0].target == "constraint.choose_one"

    bad_quote = copy.deepcopy(initial)
    bad_quote.fact_coverage[0] = FactCoverageDraft("题面不存在", "FEASIBILITY", ["constraint.choose_one"], FactUsageStatus.MODELED, "bad")
    with pytest.raises(ValueError, match="absent"):
        initialize_state(public, bad_quote, ir, capture)

    bad_target = copy.deepcopy(initial)
    bad_target.fact_coverage[0] = FactCoverageDraft("必须恰好选择一个方案", "FEASIBILITY", ["constraint.missing"], FactUsageStatus.MODELED, "bad")
    with pytest.raises(ValueError, match="existing"):
        initialize_state(public, bad_target, ir, capture)

    for invented in ("constraint.invented", "parameter.invented"):
        invented_gap = copy.deepcopy(initial)
        invented_gap.candidate_gaps[0] = replace(invented_gap.candidate_gaps[0], target=invented)
        with pytest.raises(ValueError, match="allowed_gap_targets"):
            initialize_state(public, invented_gap, ir, capture)

    parameter_initial = copy.deepcopy(initial)
    parameter_initial.model_ir["parameters"] = {"threshold": 1}
    parameter_initial.candidate_gaps[0] = replace(parameter_initial.candidate_gaps[0], target="parameter.threshold")
    parameter_ir, parameter_capture = solve_initial(parameter_initial.model_ir, schema())
    with pytest.raises(ValueError, match="allowed_gap_targets"):
        initialize_state(public, parameter_initial, parameter_ir, parameter_capture)

    aggregate_objective_alias = copy.deepcopy(initial)
    aggregate_objective_alias.fact_coverage[0] = FactCoverageDraft(
        "必须恰好选择一个方案",
        "OBJECTIVE",
        ["objective.listing_value"],
        FactUsageStatus.MODELED,
        "aggregate objective aliases are not canonical term targets",
    )
    with pytest.raises(ValueError, match="existing canonical"):
        initialize_state(public, aggregate_objective_alias, ir, capture)

    mixed = copy.deepcopy(initial)
    mixed.fact_coverage[0] = FactCoverageDraft(
        "必须恰好选择一个方案",
        "FEASIBILITY_AND_SCOPE",
        ["constraint.choose_one", "applicability.capacity_feasibility"],
        FactUsageStatus.APPLICABILITY_USED,
        "one fact has model and applicability use",
    )
    mixed_state = initialize_state(public, mixed, ir, capture)
    assert mixed_state.fact_coverage[0].usage_status == FactUsageStatus.APPLICABILITY_USED

    invalid_mixed = copy.deepcopy(mixed)
    invalid_mixed.fact_coverage[0] = FactCoverageDraft(
        "必须恰好选择一个方案",
        "FEASIBILITY_AND_SCOPE",
        ["constraint.choose_one", "applicability.capacity_feasibility"],
        FactUsageStatus.MODELED,
        "MODELED cannot claim an applicability target",
    )
    with pytest.raises(ValueError, match="existing"):
        initialize_state(public, invalid_mixed, ir, capture)

    invalid_unaccounted = copy.deepcopy(initial)
    invalid_unaccounted.fact_coverage[1] = FactCoverageDraft(
        "现实规则阈值尚不明确",
        "THRESHOLD",
        ["variable.x"],
        FactUsageStatus.UNACCOUNTED,
        "UNACCOUNTED cannot pre-bind a target",
    )
    with pytest.raises(ValueError, match=r"mapped_targets=\[\]"):
        initialize_state(public, invalid_unaccounted, ir, capture)

    canonical_only_applicability = copy.deepcopy(initial)
    canonical_only_applicability.fact_coverage[0] = FactCoverageDraft(
        "必须恰好选择一个方案",
        "FEASIBILITY",
        ["constraint.choose_one"],
        FactUsageStatus.APPLICABILITY_USED,
        "an applicability row must name its applicability interface",
    )
    with pytest.raises(ValueError, match="APPLICABILITY_USED"):
        initialize_state(public, canonical_only_applicability, ir, capture)

    applicability_only = copy.deepcopy(initial)
    applicability_only.fact_coverage[0] = FactCoverageDraft(
        "必须恰好选择一个方案",
        "FEASIBILITY",
        ["applicability.capacity_feasibility"],
        FactUsageStatus.APPLICABILITY_USED,
        "valid applicability-only use",
    )
    assert initialize_state(public, applicability_only, ir, capture).fact_coverage[0].mapped_targets == [
        "applicability.capacity_feasibility"
    ]

    invented_applicability = copy.deepcopy(initial)
    invented_applicability.fact_coverage[0] = FactCoverageDraft(
        "必须恰好选择一个方案",
        "DOCUMENTATION",
        ["applicability.ser_documentation"],
        FactUsageStatus.APPLICABILITY_USED,
        "unregistered applicability dimensions are forbidden",
    )
    with pytest.raises(ValueError, match="APPLICABILITY_USED"):
        initialize_state(public, invented_applicability, ir, capture)

    parameter_initial = copy.deepcopy(initial)
    parameter_initial.model_ir["parameters"] = {"capacity": 1}
    parameter_initial.fact_coverage[0] = FactCoverageDraft(
        "必须恰好选择一个方案",
        "FEASIBILITY",
        ["parameter.capacity"],
        FactUsageStatus.MODELED,
        "parameters are not direct FactCoverage interfaces",
    )
    parameter_ir, parameter_capture = solve_initial(parameter_initial.model_ir, schema())
    with pytest.raises(ValueError, match="existing canonical"):
        initialize_state(public, parameter_initial, parameter_ir, parameter_capture)


def test_reality_interface_requires_quote_grounded_rule_witnesses() -> None:
    local_attribute = "2026年8月4日，公司持有电信经销商执照和有效证书，必须从两个型号中选择一个申报"
    public = PublicCase(
        "E1-REALITY-WITNESS",
        f"【本 case 权威事实】\n{local_attribute}。\n【优化骨架】",
    )
    rule_targets = [
        "applicability.subject_eligibility",
        "applicability.object_scope",
        "applicability.exception_exemption",
        "applicability.action_consequence",
    ]
    false_applicability = InitialDecision(
        model_ir(),
        [
            FactCoverageDraft(
                local_attribute,
                "REALITY_INTERFACE",
                ["constraint.choose_one", *rule_targets],
                FactUsageStatus.APPLICABILITY_USED,
                "attributes are not an operative rule",
            )
        ],
        audit(),
        [],
        True,
    )
    ir, capture = solve_initial(false_applicability.model_ir, schema())
    with pytest.raises(ValueError, match="target-specific operative rule"):
        initialize_state(public, false_applicability, ir, capture)

    scope_only = copy.deepcopy(false_applicability)
    scope_quote = "本次候选范围仅限型号A和型号B"
    scope_public = PublicCase(
        "E1-SCOPE-ONLY",
        f"【本 case 权威事实】\n{scope_quote}。\n【优化骨架】",
    )
    scope_only.fact_coverage[0] = FactCoverageDraft(
        scope_quote,
        "OBJECT_SCOPE_ONLY",
        rule_targets,
        FactUsageStatus.APPLICABILITY_USED,
        "one valid scope conclusion cannot close the other three dimensions",
    )
    with pytest.raises(ValueError, match="target-specific operative rule"):
        initialize_state(scope_public, scope_only, ir, capture)

    all_modeled = copy.deepcopy(false_applicability)
    all_modeled.fact_coverage[0] = FactCoverageDraft(
        local_attribute,
        "LOCAL_OR_INPUT",
        ["constraint.choose_one"],
        FactUsageStatus.MODELED,
        "malicious status change must not bypass the reality-interface audit",
    )
    with pytest.raises(ValueError, match="lacks quote-grounded reality-interface witnesses"):
        initialize_state(public, all_modeled, ir, capture)

    operative_quote = (
        "2026年8月4日依法明确该公司具备申报资格，所有候选型号均在适用范围内，"
        "题外例外均不适用，所有型号均可申报上市"
    )
    grounded_public = PublicCase(
        "E1-REALITY-GROUNDED",
        f"【本 case 权威事实】\n{operative_quote}。\n【优化骨架】",
    )
    grounded = InitialDecision(
        model_ir(),
        [
            FactCoverageDraft(
                operative_quote,
                "OPERATIVE_APPLICABILITY",
                [*rule_targets, "variable.x", "variable.y"],
                FactUsageStatus.APPLICABILITY_USED,
                "the prompt states the operative conclusion",
            )
        ],
        audit(),
        [],
        True,
    )
    grounded_ir, grounded_capture = solve_initial(grounded.model_ir, schema())
    assert initialize_state(grounded_public, grounded, grounded_ir, grounded_capture).self_contained

    one_action_only = copy.deepcopy(grounded)
    one_action_only.fact_coverage[0] = FactCoverageDraft(
        operative_quote,
        "OPERATIVE_APPLICABILITY",
        [*rule_targets, "variable.x"],
        FactUsageStatus.APPLICABILITY_USED,
        "a witness for one action cannot close another decision interface",
    )
    with pytest.raises(ValueError, match="decision interfaces"):
        initialize_state(grounded_public, one_action_only, grounded_ir, grounded_capture)

    a_only_quote = (
        "2026年8月4日，该公司具备申报资格，型号A在适用范围内且备案型号B1，"
        "不存在例外，型号A可申报上市"
    )
    public_schema = {
        "actions": [
            {"id": "x", "meaning": "申报型号A", "type": "BINARY"},
            {"id": "y", "meaning": "申报型号B", "type": "BINARY"},
        ],
        "objective": {"accepted_units": {"点": 1}, "canonical_unit": "点"},
    }
    a_only_public = PublicCase(
        "E1-FALSE-INTERFACE-BINDING",
        f"【本 case 权威事实】\n{a_only_quote}。\n公开 output_schema：\n"
        f"{json.dumps(public_schema, ensure_ascii=False, separators=(',', ':'))}",
    )
    false_multi_binding = InitialDecision(
        model_ir(),
        [
            FactCoverageDraft(
                a_only_quote,
                "ONE_ACTION_ONLY",
                [*rule_targets, "variable.x", "variable.y"],
                FactUsageStatus.APPLICABILITY_USED,
                "LLM falsely maps an A-only witness to A and B",
            )
        ],
        audit(),
        [],
        True,
    )
    binding_ir, binding_capture = solve_initial(false_multi_binding.model_ir, public_schema)
    with pytest.raises(ValueError, match=r"decision interfaces: variable\.y"):
        initialize_state(a_only_public, false_multi_binding, binding_ir, binding_capture)

    subject_quote = "2026年8月4日，公司具备申报资格"
    exception_quote = "不存在任何例外"
    generic_action_quote = "所有候选型号均可申报上市"
    generic_public = PublicCase(
        "E1-GENERIC-CROSS-DIMENSION",
        "【本 case 权威事实】\n"
        f"{subject_quote}。{exception_quote}。{generic_action_quote}。\n"
        "公开 output_schema：\n"
        f"{json.dumps(public_schema, ensure_ascii=False, separators=(',', ':'))}",
    )
    generic_cross_dimension = InitialDecision(
        model_ir(),
        [
            FactCoverageDraft(
                subject_quote,
                "SUBJECT",
                ["applicability.subject_eligibility"],
                FactUsageStatus.APPLICABILITY_USED,
                "subject only",
            ),
            FactCoverageDraft(
                exception_quote,
                "EXCEPTION",
                ["applicability.exception_exemption"],
                FactUsageStatus.APPLICABILITY_USED,
                "exception only",
            ),
            FactCoverageDraft(
                generic_action_quote,
                "GENERIC_ACTION",
                [
                    "applicability.object_scope",
                    "applicability.action_consequence",
                    "variable.x",
                    "variable.y",
                ],
                FactUsageStatus.APPLICABILITY_USED,
                "generic action permission cannot also prove object scope",
            ),
        ],
        audit(),
        [],
        True,
    )
    generic_ir, generic_capture = solve_initial(generic_cross_dimension.model_ir, public_schema)
    with pytest.raises(ValueError, match="target-specific operative rule"):
        initialize_state(generic_public, generic_cross_dimension, generic_ir, generic_capture)


def test_uncertain_applicability_cannot_close_any_dimension() -> None:
    public = PublicCase("E1-UNCERTAIN", "适用的司法管辖区未知。")
    initial = InitialDecision(
        model_ir(),
        [
            FactCoverageDraft(
                "适用的司法管辖区未知",
                "JURISDICTION",
                ["applicability.location_jurisdiction"],
                FactUsageStatus.APPLICABILITY_USED,
                "unknown is not grounded",
            )
        ],
        audit(),
        [],
        False,
    )
    ir, capture = solve_initial(initial.model_ir, schema())
    with pytest.raises(ValueError, match="uncertain or unverified"):
        initialize_state(public, initial, ir, capture)


def test_unsupported_applicability_is_only_demoted_for_open_non_self_contained_state() -> None:
    quote = "加入色素增加12点"
    public = PublicCase("E1-NORMALIZE", f"{quote}。")
    mixed = InitialDecision(
        model_ir(),
        [
            FactCoverageDraft(
                quote,
                "LOCAL_OBJECTIVE_GAIN",
                [
                    "applicability.action_consequence",
                    "applicability.cost_benefit",
                    "variable.x",
                    "objective.x",
                ],
                FactUsageStatus.APPLICABILITY_USED,
                "LLM confused objective gain with an operative consequence",
            )
        ],
        audit(),
        [],
        False,
    )
    ir, capture = solve_initial(mixed.model_ir, schema())
    original = copy.deepcopy(mixed)
    state = initialize_state(public, mixed, ir, capture)
    row = state.fact_coverage[0]
    assert row.usage_status == FactUsageStatus.APPLICABILITY_USED
    assert row.mapped_targets == ["applicability.cost_benefit", "variable.x", "objective.x"]
    assert "PROGRAM_NORMALIZED_UNSUPPORTED_APPLICABILITY" in row.reason
    assert state.audit_summary.negative_space_checked[AuditDimension.ACTION_CONSEQUENCE] is False
    assert state.audit_summary.model_interface_to_grounding_complete is False
    assert state.audit_summary.self_contained_reason == (
        "PROGRAM_NORMALIZED_UNSUPPORTED_APPLICABILITY: ACTION_CONSEQUENCE; grounding remains open"
    )
    assert mixed == original
    assert not _quote_supports_applicability_target(quote, "applicability.action_consequence")

    canonical_only = copy.deepcopy(mixed)
    canonical_only.fact_coverage[0] = FactCoverageDraft(
        quote,
        "LOCAL_OBJECTIVE_GAIN",
        ["applicability.action_consequence", "objective.x"],
        FactUsageStatus.APPLICABILITY_USED,
        "same label error with one canonical use",
    )
    canonical_state = initialize_state(public, canonical_only, ir, capture)
    assert canonical_state.fact_coverage[0].usage_status == FactUsageStatus.MODELED
    assert canonical_state.fact_coverage[0].mapped_targets == ["objective.x"]

    no_remaining_use = copy.deepcopy(mixed)
    no_remaining_use.fact_coverage[0] = FactCoverageDraft(
        quote,
        "MISLABELED",
        ["applicability.action_consequence"],
        FactUsageStatus.APPLICABILITY_USED,
        "nothing remains after conservative removal",
    )
    with pytest.raises(ValueError, match="left no model use"):
        initialize_state(public, no_remaining_use, ir, capture)

    claimed_closed = copy.deepcopy(mixed)
    claimed_closed.self_contained_candidate = True
    with pytest.raises(ValueError, match="target-specific operative rule"):
        initialize_state(public, claimed_closed, ir, capture)


def test_fragmented_exact_quotes_require_near_complete_unique_span_union() -> None:
    unit = (
        "A的铅、汞、镉分别为0.3、0.02、0.3 ppm，B的铅为0.7 ppm，C的汞为0.08 ppm，"
        "D的镉为0.8 ppm，四批砷检测均为0.3 ppm"
    )
    quotes = [
        "A的铅、汞、镉分别为0.3、0.02、0.3 ppm，",
        "B的铅为0.7 ppm，",
        "C的汞为0.08 ppm，",
        "D的镉为0.8 ppm，",
        "四批砷检测均为0.3 ppm。",
    ]
    assert _fact_unit_covered(unit, quotes)
    assert not _fact_unit_covered(unit, [quotes[0], quotes[0], quotes[2], quotes[3], quotes[4]])
    assert not _fact_unit_covered(unit, [quotes[0], quotes[2], quotes[3], quotes[4], "不存在的改写事实"])
    assert not _fact_unit_covered("甲乙丙丁戊己庚辛壬癸子丑", ["甲乙丙", "丁戊己", "庚辛壬", "癸子丑"])

    boundary_unit = "".join(chr(0x4E00 + index) for index in range(100))
    assert not _fact_unit_covered(boundary_unit, [boundary_unit[:36]])
    assert not _fact_unit_covered(boundary_unit, [boundary_unit[:84]])
    assert _fact_unit_covered(boundary_unit, [boundary_unit[:85]])
    assert not _fact_unit_covered(boundary_unit, [boundary_unit[:50], boundary_unit[:50]])
    assert not _fact_unit_covered(boundary_unit, [boundary_unit[:60], boundary_unit[20:80]])
    assert _fact_unit_covered(boundary_unit, [boundary_unit[:45], boundary_unit[55:]])


def test_v10_unbound_action_fixture_fails_before_bounded_search() -> None:
    root = Path(__file__).resolve().parents[1]
    response_path = root / "tests" / "fixtures" / "v10_unbound_action_initial.json"
    raw_initial = json.loads(response_path.read_text(encoding="utf-8"))
    initial = parse_initial_decision(raw_initial)
    original = copy.deepcopy(initial)

    public_record = next(
        json.loads(line)
        for line in (root / "inputs" / "public_cases.jsonl").read_text(encoding="utf-8").splitlines()
        if json.loads(line)["eval_id"] == "SWOR-E-04F844F016AF29729C4A"
    )
    public = PublicCase(public_record["eval_id"], public_record["prompt_zh"])
    output_schema = json.loads(public.prompt_zh.split("公开 output_schema：", 1)[1].strip())
    ir, capture = solve_initial(initial.model_ir, output_schema)
    state = initialize_state(public, initial, ir, capture)

    assert capture.status == "OPTIMAL"
    assert capture.objective is not None
    assert capture.objective["value"] == 68.0
    assert capture.objective["unit"] == "生产效用点"
    assert state.audit_summary.prompt_fact_unit_total == 12
    assert state.audit_summary.prompt_fact_unit_covered == 12
    assert state.audit_summary.prompt_fact_coverage_ratio == 1.0
    assert state.audit_summary.overflow_detected and state.audit_summary.overflow_count == 4
    assert state.gaps == []
    assert state.information_audit_failure == {
        "code": "STAGE3_CANDIDATE_GAP_LINK_FAILURE",
        "invalid_gap_indices": [1, 3],
        "unlinked_fact_indices": [],
    }
    gain_rows = [row for row in state.fact_coverage if row.quote in {"加入色素增加12点，", "不加入增加0点。"}]
    assert len(gain_rows) == 2
    assert all("applicability.action_consequence" not in row.mapped_targets for row in gain_rows)
    assert all("applicability.cost_benefit" in row.mapped_targets for row in gain_rows)
    assert initial == original

    search_calls: list[tuple[str, str]] = []

    def bounded_search(gap_id: str, query: str) -> RetrievalTrace:
        search_calls.append((query, gap_id))
        return RetrievalTrace(gap_id, query, True, query)

    services = PipelineServices(
        initial_modeler=lambda _: initial,
        searcher=bounded_search,
        evidence_proposer=lambda *_: EvidenceDecision(
            [], Admission.REJECT, None, None, "bounded exploration remains insufficient"
        ),
    )
    result = run_case(public, output_schema, services)
    assert result["status"] == "ABSTAIN"
    assert result["search_performed"] is False
    assert result["search"]["search_count"] == 0
    assert search_calls == []
    assert result["state"]["audit_summary"]["overflow_detected"] is True
    assert initial == original


def test_v13_title_filter_fixture_survives_bounded_overflow_search() -> None:
    root = Path(__file__).resolve().parents[1]
    response_path = root / "tests" / "fixtures" / "v13_title_filter_initial.json"
    initial = parse_initial_decision(json.loads(response_path.read_text(encoding="utf-8")))
    original = copy.deepcopy(initial)
    public_record = next(
        json.loads(line)
        for line in (root / "inputs" / "public_cases.jsonl").read_text(encoding="utf-8").splitlines()
        if json.loads(line)["eval_id"] == "SWOR-E-030F6C5D78703BAF8E04"
    )
    public = PublicCase(public_record["eval_id"], public_record["prompt_zh"])
    output_schema = json.loads(public.prompt_zh.split("公开 output_schema：", 1)[1].strip())
    ir, capture = solve_initial(initial.model_ir, output_schema)
    state = initialize_state(public, initial, ir, capture)

    assert state.audit_summary.prompt_fact_unit_total == 8
    assert state.audit_summary.prompt_fact_unit_covered == 8
    assert state.audit_summary.prompt_fact_coverage_ratio == 1.0
    assert state.audit_summary.overflow_detected and state.audit_summary.overflow_count == 3

    search_calls: list[tuple[str, str]] = []

    def bounded_search(gap_id: str, query: str) -> RetrievalTrace:
        search_calls.append((query, gap_id))
        return RetrievalTrace(gap_id, query, True, query)

    services = PipelineServices(
        initial_modeler=lambda _: initial,
        searcher=bounded_search,
        evidence_proposer=lambda *_: EvidenceDecision(
            [], Admission.REJECT, None, None, "bounded exploration remains insufficient"
        ),
    )
    result = run_case(public, output_schema, services)
    assert result["status"] == "ABSTAIN"
    assert result["search_performed"] is True
    assert result["search"]["search_count"] == len(search_calls)
    assert len(search_calls) >= 1
    assert result["state"]["audit_summary"]["overflow_detected"] is True
    assert initial == original


@pytest.mark.parametrize(
    ("quote", "target"),
    [
        ("公司是否具备申报资格尚待确认", "applicability.subject_eligibility"),
        ("设备A是否属于适用范围尚待核查", "applicability.object_scope"),
        ("是否存在例外情况尚待核查", "applicability.exception_exemption"),
        ("如果开展本次优化，必须恰好选择一个方案", "applicability.action_consequence"),
        ("if optimizing, must select one option", "applicability.action_consequence"),
        ("公司有资格证书", "applicability.subject_eligibility"),
        ("公司持有资格证书", "applicability.subject_eligibility"),
        ("该选择导致收益变化", "applicability.action_consequence"),
        ("该事实触发目标系数变化", "applicability.action_consequence"),
        ("方案A可获得12点收益", "applicability.action_consequence"),
        ("型号A可获得12点收益", "applicability.object_scope"),
        ("公司可获得12点收益", "applicability.subject_eligibility"),
        ("加入色素增加12点", "applicability.action_consequence"),
        ("不加入增加0点", "applicability.action_consequence"),
    ],
)
def test_attribute_question_and_plain_or_phrases_are_not_rule_witnesses(quote: str, target: str) -> None:
    assert not _quote_supports_applicability_target(quote, target)


@pytest.mark.parametrize(
    ("quote", "target"),
    [
        ("型号A不可能注册", "applicability.action_consequence"),
        ("A可登记", "applicability.action_consequence"),
        ("A不适用", "applicability.object_scope"),
        ("持证公司可申报该型号", "applicability.subject_eligibility"),
        ("不存在任何例外", "applicability.exception_exemption"),
        ("若登记方案A，必须缴纳12元附加费", "applicability.action_consequence"),
    ],
)
def test_direct_operative_conclusions_are_rule_witnesses(quote: str, target: str) -> None:
    assert _quote_supports_applicability_target(quote, target)


def test_exhaustive_action_conclusion_does_not_close_unrelated_dimensions() -> None:
    quote = "所有候选型号均可申报上市"
    assert _quote_supports_applicability_target(quote, "applicability.action_consequence")
    assert not _quote_supports_applicability_target(quote, "applicability.subject_eligibility")
    assert not _quote_supports_applicability_target(quote, "applicability.object_scope")
    assert not _quote_supports_applicability_target(quote, "applicability.exception_exemption")

    no_external_exception = "题外法律法规均不适用"
    assert _quote_supports_applicability_target(
        no_external_exception,
        "applicability.exception_exemption",
    )
    assert not _quote_supports_applicability_target(
        no_external_exception,
        "applicability.action_consequence",
    )


def test_authoritative_rule_material_keeps_no_search_reachable() -> None:
    authority = "2026年8月4日，海岬公司为两个设备安排申报"
    rule = "规则明确所有设备均可申报上市且不存在例外"
    optimization = "必须从两个设备中恰好选择一个"
    public = PublicCase(
        "E1-RULE-BLOCK",
        "\n".join(
            [
                "【本 case 权威事实】",
                f"{authority}。",
                "【随题规则材料】",
                f"{rule}。",
                "【优化骨架】",
                f"{optimization}。",
            ]
        ),
    )
    initial = InitialDecision(
        model_ir(),
        [
            FactCoverageDraft(authority, "LOCAL_FACT", ["variable.x", "variable.y"], FactUsageStatus.MODELED, "public actions"),
            FactCoverageDraft(rule, "RULE", ["constraint.choose_one"], FactUsageStatus.MODELED, "rule modeled"),
            FactCoverageDraft(optimization, "CAPACITY", ["constraint.choose_one"], FactUsageStatus.MODELED, "choose one"),
        ],
        audit(),
        [],
        True,
    )
    ir, capture = solve_initial(initial.model_ir, schema())
    assert initialize_state(public, initial, ir, capture).self_contained


def test_plain_choose_k_cost_benefit_does_not_require_reality_witnesses() -> None:
    quote = "必须从两个方案中恰好选择一个，方案价值分别为1点和2点"
    public = PublicCase("E1-PLAIN-OR", f"{quote}。")
    initial = InitialDecision(
        model_ir(),
        [
            FactCoverageDraft(
                quote,
                "OBJECTIVE_AND_CAPACITY",
                ["constraint.choose_one", "objective.x", "objective.y"],
                FactUsageStatus.MODELED,
                "ordinary OR inputs",
            )
        ],
        audit(),
        [],
        True,
    )
    ir, capture = solve_initial(initial.model_ir, schema())
    assert initialize_state(public, initial, ir, capture).self_contained

    header_only = PublicCase("E1-PLAIN-HEADER", f"【本 case 权威事实】\n{quote}。")
    assert initialize_state(header_only, initial, ir, capture).self_contained


def test_prompt_fact_units_cannot_be_silently_omitted() -> None:
    public = PublicCase(
        "E1-COVERAGE",
        "【优化骨架】\n用于测试的组合决策。事实A必须恰好选择一个方案；事实B限制同一选择。\n公开 output_schema：{}",
    )
    first = FactCoverageDraft(
        "事实A必须恰好选择一个方案",
        "FEASIBILITY",
        ["constraint.choose_one"],
        FactUsageStatus.MODELED,
        "modeled",
    )
    initial = InitialDecision(model_ir(), [first], audit(), [], True)
    ir, capture = solve_initial(initial.model_ir, schema())
    with pytest.raises(ValueError, match="FactCoverage omitted 1/2"):
        initialize_state(public, initial, ir, capture)

    complete = copy.deepcopy(initial)
    complete.fact_coverage.append(
        FactCoverageDraft(
            "事实B限制同一选择",
            "FEASIBILITY",
            ["constraint.choose_one"],
            FactUsageStatus.MODELED,
            "same canonical constraint",
        )
    )
    state = initialize_state(public, complete, ir, capture)
    assert state.audit_summary.prompt_fact_unit_total == 2
    assert state.audit_summary.prompt_fact_unit_covered == 2
    assert state.audit_summary.prompt_fact_coverage_ratio == 1.0


def test_prompt_fact_units_skip_nominal_choice_title_but_keep_choice_constraint() -> None:
    prompt = (
        "【优化骨架】\n"
        "新加坡电信设备上市申报选择。"
        "处理合同只能在其对应中心启用时选择；候选设备成本为12点。\n"
        "公开 output_schema：{}"
    )
    assert prompt_fact_units(prompt) == [
        "处理合同只能在其对应中心启用时选择",
        "候选设备成本为12点",
    ]

    for title in (
        "NG911工程交付排期",
        "美国Rule 144A票据批次分配",
        "美国固定生产场所班组与厕所容量配置",
        "美国危险废物episodic event项目组合",
        "Casgevy基因治疗名额分配",
        "美国陆上储油罐二次围护设计",
        "英国股票和股份ISA组合调整",
        "能源贸易商的跨期LNG头寸组合",
        "英格兰成人社会工作ASYE资助申请组合",
        "频道方案与商业租赁接入容量",
    ):
        assert prompt_fact_units(f"【优化骨架】\n{title}。候选设备成本为12点。") == ["候选设备成本为12点"]

    long_choice_fact = (
        "采购头寸可以用于库存或合同结算，转运头寸可以使用公司此前持有的库存，"
        "因此在不考虑外部限制时，八个头寸可以分别选择"
    )
    assert prompt_fact_units(f"【优化骨架】\n{long_choice_fact}。") == [long_choice_fact]
    assert prompt_fact_units("【优化骨架】\n决策日为2026年8月2日。") == ["决策日为2026年8月2日"]
    declarative_first_fact = "美国山原医疗机构为白班和夜班安排医生与护士"
    assert prompt_fact_units(f"【优化骨架】\n{declarative_first_fact}。") == [declarative_first_fact]

    ambiguous_facts = (
        "甲乙互斥",
        "预算10点",
        "A≤B",
        "选择X",
        "最多一个",
        "每仓容量十吨",
        "X取0或1",
        "甲优先于乙",
        "目标最大化收益",
        "选择方案",
        "甲乙互斥选择",
        "不选甲方案",
        "勿选甲方案",
        "仅选甲方案",
        "只选甲方案",
        "选甲方案",
        "排除甲方案",
        "关闭甲方案",
        "甲乙二选一方案",
        "甲乙不同时选择",
        "甲乙不兼容组合",
        "甲依赖乙选择",
        "先甲后乙安排",
    )
    for fact in ambiguous_facts:
        prompt = f"【优化骨架】\n{fact}。必须选择X。公开 output_schema：{{}}"
        assert prompt_fact_units(prompt) == [fact, "必须选择X"]


def test_v161_optimization_leads_exclude_113_titles_and_keep_seven_real_facts() -> None:
    root = Path(__file__).resolve().parents[1]
    records = [
        json.loads(line)
        for line in (root / "inputs" / "public_cases.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    lead_status: dict[str, bool] = {}
    for record in records:
        prompt = record["prompt_zh"]
        after_heading = prompt.split("【优化骨架】", 1)[1].lstrip()
        lead = _compact_unit(re.sub(r"【[^】]+】", "", re.split(r"[。；;\r\n]+", after_heading, 1)[0]))
        included = lead in prompt_fact_units(prompt)
        if lead in lead_status:
            assert lead_status[lead] is included
        lead_status[lead] = included

    kept = {lead for lead, included in lead_status.items() if included}
    assert len(records) == 360
    assert len(lead_status) == 120
    assert len(lead_status) - len(kept) == 113
    assert kept == {
        "2026年8月2日，爱尔兰环境部门为新包装废物责任计划安排执行事项",
        "2026年8月4日（星期二），新加坡海峡联航要把三项非定期飞行任务分配到四个机场—时段单元",
        "2026年8月2日，美国俄亥俄州河城电力企业制定年度公开计划：第1至第4季度的公开透明度更新次数Q1、Q2、Q3、Q4均可取0至2次，并可选择发布1份内部自愿年度摘要S",
        "2026年8月2日，英国东湾医疗委员会决定授标并签约的工作日以及是否启动书面陈述审查流程",
        "美国山原医疗机构为白班和夜班安排医生与护士",
        "决策日为2026年8月2日",
        "美国内华达州星脉电池实验室要把一只用于验证热管理性能的测试原型电池送往科罗拉多州独立测试中心",
    }


def test_output_schema_rows_cannot_enter_fact_coverage_or_gaps() -> None:
    public = PublicCase(
        "E1-SCHEMA-BOUNDARY",
        "必须恰好选择一个方案。\n公开 output_schema：\n{\"id\":\"x\",\"type\":\"BINARY\"}",
    )
    initial = InitialDecision(
        model_ir(),
        [
            FactCoverageDraft("必须恰好选择一个方案", "FEASIBILITY", ["constraint.choose_one"], FactUsageStatus.MODELED, "modeled"),
            FactCoverageDraft('{"id":"x","type":"BINARY"}', "SCHEMA", ["variable.x"], FactUsageStatus.MODELED, "schema metadata"),
        ],
        audit(),
        [],
        True,
    )
    ir, capture = solve_initial(initial.model_ir, schema())
    with pytest.raises(ValueError, match="auditable prompt prefix"):
        initialize_state(public, initial, ir, capture)

    gap_from_schema = copy.deepcopy(initial)
    gap_from_schema.fact_coverage = gap_from_schema.fact_coverage[:1]
    gap_from_schema.candidate_gaps = [
        CandidateGapDraft(
            ['{"id":"x","type":"BINARY"}'],
            "SCHEMA",
            "schema row is not a reality gap",
            "variable.x",
            GapRoute.EXTERNAL_RULE,
            [],
            "schema id official",
        )
    ]
    gap_from_schema.self_contained_candidate = False
    with pytest.raises(ValueError, match="auditable prompt prefix"):
        initialize_state(public, gap_from_schema, ir, capture)


def test_output_schema_boundary_is_a_heading_not_a_substring_cut() -> None:
    prompt = (
        "【优化骨架】\n"
        "任务组合。"
        "字段名请按 output_schema 登记。"
        "必须选择X。"
        "请按output_schema中的action_id返回最优行动。\n"
        "公开 output_schema：\n"
        '{"actions":[{"id":"x","type":"BINARY"}]}'
    )
    prefix = prompt_fact_prefix(prompt)
    assert "字段名请按 output_schema 登记" in prefix
    assert '"actions"' not in prefix
    assert prompt_fact_units(prompt) == ["字段名请按output_schema登记", "必须选择X"]


def test_v161_all_fact_spans_close_exactly_and_six_smoke_local_facts_are_audited() -> None:
    root = Path(__file__).resolve().parents[1]
    records = [
        json.loads(line)
        for line in (root / "inputs" / "public_cases.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    public = {row["eval_id"]: row["prompt_zh"] for row in records}
    total_units = 0
    total_unique_spans = 0
    ledger_units = 0
    ledger_pattern = re.compile(r"记录在|载于|记载在|台账|档案|清单|检验单|数据库")
    for prompt in public.values():
        prefix = prompt_fact_prefix(prompt)
        spans = _prompt_fact_unit_spans(prompt)
        total_units += len(spans)
        total_unique_spans += len({exact_span for _unit, exact_span in spans})
        closed = _close_stage_fact_coverage(prompt, [])
        quotes = [row["quote"] for row in closed]
        assert len(closed) == len({exact_span for _unit, exact_span in spans})
        assert all(
            row["or_role"] == PROGRAM_FACT_COVERAGE_CLOSURE_MARKER
            for row in closed
        )
        for unit, exact_span in spans:
            assert exact_span in prefix
            assert not re.search(
                r'output_schema|schema_version|accepted_units|"actions"',
                exact_span,
                flags=re.IGNORECASE,
            )
            assert _fact_unit_fully_covered(unit, quotes, exact_span)
            ledger_units += bool(ledger_pattern.search(exact_span))

    assert len(records) == 360
    assert total_units == 4569
    assert total_unique_spans == 4564
    assert ledger_units == 250

    expected_smoke_facts = {
        "SWOR-E-030F6C5D78703BAF8E04": {
            "各型号的设备类别及无线或有线功能记录在本次申报清单中"
        },
        "SWOR-E-04F844F016AF29729C4A": {
            "两份配方的成分、加工方法与产品名称载于质量台账",
            "各批次的色素身份、认证记录和杂质检测结果记载在质量检验单中",
        },
        "SWOR-E-0247CAEBBD83006BF60C": {"计划建立日期记录在护理计划台账中"},
        "SWOR-E-031125E1DD5B9C5ABB06": {"设施、人员和工作地点均在加拿大"},
        "SWOR-E-01B7C3B94C26D2E48F68": {
            "这些上限均包含等号",
            "账户支持的合同类型记录在保单台账中",
            "发行人归属与底层资产记录由账户资产台账给出",
        },
        "SWOR-E-031B50F9720A75381D3F": {
            "服务种类、与美国一般铁路系统的连接状态及运营方分类记录在本次运行档案中"
        },
    }
    assert set(expected_smoke_facts) == {
        "SWOR-E-030F6C5D78703BAF8E04",
        "SWOR-E-04F844F016AF29729C4A",
        "SWOR-E-0247CAEBBD83006BF60C",
        "SWOR-E-031125E1DD5B9C5ABB06",
        "SWOR-E-01B7C3B94C26D2E48F68",
        "SWOR-E-031B50F9720A75381D3F",
    }
    for eval_id, facts in expected_smoke_facts.items():
        assert facts <= set(prompt_fact_units(public[eval_id]))


def test_overflow_is_abstain_and_initial_llm_cannot_claim_irrelevance() -> None:
    public = PublicCase("E2", "现实规则阈值尚不明确。")
    initial = InitialDecision(
        model_ir(),
        [FactCoverageDraft("现实规则阈值尚不明确", "THRESHOLD", [], FactUsageStatus.UNACCOUNTED, "overflow")],
        audit(overflow=2),
        [],
        False,
    )
    ir, capture = solve_initial(initial.model_ir, schema())
    state = initialize_state(public, initial, ir, capture)
    assert finalize(state)["status"] == "ABSTAIN"

    bad = copy.deepcopy(initial)
    bad.fact_coverage[0] = FactCoverageDraft("现实规则阈值尚不明确", "THRESHOLD", [], FactUsageStatus.IRRELEVANT_JUSTIFIED, "LLM guessed")
    with pytest.raises(ValueError, match="IRRELEVANT"):
        initialize_state(public, bad, ir, capture)

    unlinked_returned_gap = copy.deepcopy(initial)
    unlinked_returned_gap.candidate_gaps = [
        CandidateGapDraft(
            ["另一个现实规则"],
            "ELIGIBILITY",
            "returned gap must still link",
            "variable.x",
            GapRoute.EXTERNAL_RULE,
            [],
            "另一个规则 官方",
        )
    ]
    unlinked_public = PublicCase("E2-UNLINKED", "现实规则阈值尚不明确。另一个现实规则。")
    with pytest.raises(ValueError, match="every Candidate Gap"):
        initialize_state(unlinked_public, unlinked_returned_gap, ir, capture)


def test_parser_rejects_more_than_three_candidate_gaps() -> None:
    checked = {dimension.value: True for dimension in AuditDimension}
    gap = {
        "fact_quotes": ["q"],
        "reality_role": "RULE",
        "gap_claim": "claim",
        "target": "constraint.slot",
        "gap_route": "EXTERNAL_RULE",
        "hypothetical_variants": [],
        "first_query": "official rule",
    }
    raw = {
        "model_ir": model_ir(),
        "fact_coverage": [{"quote": "q", "or_role": "RULE", "mapped_targets": [], "usage_status": "UNACCOUNTED", "reason": "r"}],
        "audit_summary": {
            "prompt_fact_to_model_complete": True,
            "model_interface_to_grounding_complete": True,
            "negative_space_checked": checked,
            "overflow_detected": True,
            "overflow_count": 1,
            "self_contained_reason": None,
        },
        "candidate_gaps": [gap, gap, gap, gap],
        "self_contained_candidate": False,
    }
    with pytest.raises(ValueError, match="at most three"):
        parse_initial_decision(raw)


def test_select_next_gap_is_read_only_and_uses_solver_effect_priority() -> None:
    public = PublicCase("E3", "规则A未知。规则B未知。")
    gaps = [
        CandidateGapDraft(["规则A未知"], "RULE", "A", "variable.x", GapRoute.EXTERNAL_RULE, [], "规则 A 官方"),
        CandidateGapDraft(["规则B未知"], "RULE", "B", "variable.y", GapRoute.EXTERNAL_RULE, [], "规则 B 官方"),
    ]
    initial = InitialDecision(
        model_ir(),
        [
            FactCoverageDraft("规则A未知", "RULE", [], FactUsageStatus.UNACCOUNTED, "r"),
            FactCoverageDraft("规则B未知", "RULE", [], FactUsageStatus.UNACCOUNTED, "r"),
        ],
        audit(),
        gaps,
        False,
    )
    ir, capture = solve_initial(initial.model_ir, schema())
    state = initialize_state(public, initial, ir, capture)
    state.gaps[0].potential_effect = PotentialEffect.VALUE_CHANGE
    state.gaps[1].potential_effect = PotentialEffect.FEASIBILITY_CHANGE
    assert select_next_gap(state) == "G2"
    assert state.active_gap_id is None


def test_one_fact_materializes_per_gap_and_closes_independently() -> None:
    public = PublicCase("E4", "同一现实规则同时决定方案X和方案Y的资格。")
    gaps = [
        CandidateGapDraft(["同一现实规则同时决定方案X和方案Y的资格"], "ELIGIBILITY", "X资格", "variable.x", GapRoute.EXTERNAL_RULE, [], "方案 X 资格 官方"),
        CandidateGapDraft(["同一现实规则同时决定方案X和方案Y的资格"], "ELIGIBILITY", "Y资格", "variable.y", GapRoute.EXTERNAL_RULE, [], "方案 Y 资格 官方"),
    ]
    initial = InitialDecision(
        model_ir(),
        [FactCoverageDraft("同一现实规则同时决定方案X和方案Y的资格", "ELIGIBILITY", [], FactUsageStatus.UNACCOUNTED, "r")],
        audit(),
        gaps,
        False,
    )
    ir, capture = solve_initial(initial.model_ir, schema())
    state = initialize_state(public, initial, ir, capture)
    assert [fact.fact_id for fact in state.fact_coverage] == ["F1", "F2"]
    assert [fact.gap_id for fact in state.fact_coverage] == ["G1", "G2"]
    assert all(fact.mapped_targets == [] for fact in state.fact_coverage)
    for gap in state.gaps:
        gap.potential_effect = PotentialEffect.DECISION_CHANGE
        gap.probe_coverage = True
    state = apply_state_update(state, StateUpdate.search_authorized("G1"))
    state = apply_state_update(state, StateUpdate.retain("G1", {"admission": "ALREADY_MODELED"}, True))
    g1_fact = next(fact for fact in state.fact_coverage if fact.gap_id == "G1")
    g2_fact = next(fact for fact in state.fact_coverage if fact.gap_id == "G2")
    assert g1_fact.usage_status == FactUsageStatus.MODELED
    assert g1_fact.mapped_targets == ["variable.x"]
    assert g2_fact.usage_status == FactUsageStatus.UNACCOUNTED
    assert g2_fact.mapped_targets == []
    assert finalize(state)["status"] == "ABSTAIN"

    state = apply_state_update(state, StateUpdate.search_authorized("G2"))
    state = apply_state_update(state, StateUpdate.retain("G2", {"admission": "NOT_APPLIES"}, False))
    g2_fact = next(fact for fact in state.fact_coverage if fact.gap_id == "G2")
    assert g2_fact.usage_status == FactUsageStatus.IRRELEVANT_JUSTIFIED
    assert g2_fact.mapped_targets == []
    result = finalize(state)
    assert result["decision_state"] == "RETAIN"
    assert result["applicability"] is False


def test_program_owned_no_effect_closure_keeps_empty_mapping() -> None:
    public = PublicCase("E5", "方案X的本地资格事实待核对。")
    initial = InitialDecision(
        model_ir(),
        [FactCoverageDraft("方案X的本地资格事实待核对", "ELIGIBILITY", [], FactUsageStatus.UNACCOUNTED, "r")],
        audit(),
        [CandidateGapDraft(["方案X的本地资格事实待核对"], "ELIGIBILITY", "X资格", "variable.x", GapRoute.LOCAL_FACT, [], None)],
        False,
    )
    ir, capture = solve_initial(initial.model_ir, schema())
    state = initialize_state(public, initial, ir, capture)
    state = apply_state_update(
        state,
        StateUpdate.probe("G1", PotentialEffect.NO_EFFECT, True, "exhaustive local check", exhaustive_local=True),
    )
    assert state.fact_coverage[0].usage_status == FactUsageStatus.IRRELEVANT_JUSTIFIED
    assert state.fact_coverage[0].mapped_targets == []

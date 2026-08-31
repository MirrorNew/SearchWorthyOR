from __future__ import annotations

import copy
import json
import unittest

from searchworthy.contracts import AuditDimension, PublicCase, parse_initial_decision
from searchworthy.or_model import solve_initial
from searchworthy.pipeline import (
    FACT_COVERAGE_SYSTEM,
    GAP_AUDIT_SYSTEM,
    INITIAL_SYSTEM,
    MODEL_IR_SYSTEM,
    PROGRAM_FACT_COVERAGE_AUDIT_REASON,
    PROGRAM_FACT_COVERAGE_CLOSURE_MARKER,
    PROGRAM_FACT_COVERAGE_CLOSURE_REASON,
    PipelineServices,
    _close_stage_fact_coverage,
    _extract_json,
    _fact_unit_covered,
    _fact_unit_fully_covered,
    _normalize_stage_fact_coverage,
    _normalize_unbound_gap_targets,
    _prompt_fact_unit_spans,
    _quote_binds_variable_target,
    _quote_in_prompt,
    initial_modeling,
    initialize_state,
    run_case,
)


MODEL_IR = {
    "variables": [{"id": "x", "type": "BINARY", "lb": 0, "ub": 1}],
    "constraints": [{"name": "choose", "terms": [{"var": "x", "coef": 1}], "sense": "==", "rhs": 1}],
    "objective": {"direction": "max", "terms": [{"var": "x", "coef": 1}], "constant": 0, "unit": "点"},
    "parameters": {},
}


def valid_initial_payload() -> dict[str, object]:
    return {
        "model_ir": copy.deepcopy(MODEL_IR),
        "fact_coverage": [
            {
                "quote": "现实资格规则未知",
                "or_role": "ELIGIBILITY",
                "mapped_targets": [],
                "usage_status": "UNACCOUNTED",
                "reason": "需要边界探测",
            }
        ],
        "audit_summary": {
            "prompt_fact_to_model_complete": True,
            "model_interface_to_grounding_complete": True,
            "negative_space_checked": {dimension.value: True for dimension in AuditDimension},
            "overflow_detected": False,
            "overflow_count": 0,
            "self_contained_reason": None,
        },
        "candidate_gaps": [
            {
                "fact_quotes": ["现实资格规则未知"],
                "reality_role": "决定行动是否可选",
                "gap_claim": "行动资格未知",
                "target": "variable.x",
                "gap_route": "EXTERNAL_RULE",
                "hypothetical_variants": [],
                "first_query": "官方 行动资格 规则",
            }
        ],
        "self_contained_candidate": False,
    }


def staged_llm(payload: dict[str, object], observed: dict[str, object] | None = None):
    def call(messages: list[dict[str, str]], purpose: str) -> dict[str, str]:
        if observed is not None:
            observed.setdefault("purposes", []).append(purpose)  # type: ignore[union-attr]
            observed.setdefault("messages", []).append(messages)  # type: ignore[union-attr]
        if purpose == "searchworthy_initial_model_ir":
            value = {"model_ir": payload["model_ir"]}
        elif purpose == "searchworthy_fact_coverage":
            value = {"fact_coverage": payload["fact_coverage"]}
        elif purpose == "searchworthy_gap_audit":
            value = {
                "audit_summary": payload["audit_summary"],
                "candidate_gaps": payload["candidate_gaps"],
                "self_contained_candidate": payload["self_contained_candidate"],
            }
        else:
            raise AssertionError(purpose)
        return {"content": json.dumps(value, ensure_ascii=False)}

    return call


class SearchWorthyPromptContractTests(unittest.TestCase):
    def test_split_initial_prompts_have_one_clear_stage_each(self) -> None:
        self.assertIn("stage 1/3", MODEL_IR_SYSTEM)
        self.assertIn("single top-level key model_ir", MODEL_IR_SYSTEM)
        self.assertIn("stage 2/3", FACT_COVERAGE_SYSTEM)
        self.assertIn("single top-level key fact_coverage", FACT_COVERAGE_SYSTEM)
        self.assertIn("stage 3/3", GAP_AUDIT_SYSTEM)
        self.assertIn("audit_summary, candidate_gaps, self_contained_candidate", GAP_AUDIT_SYSTEM)
        self.assertIn("allowed_gap_targets", GAP_AUDIT_SYSTEM)
        self.assertIn("allowed_information_targets", GAP_AUDIT_SYSTEM)
        self.assertIn("action_target_catalog", GAP_AUDIT_SYSTEM)
        self.assertIn("required_probe_targets", GAP_AUDIT_SYSTEM)
        self.assertIn("disable_probe_priority", GAP_AUDIT_SYSTEM)
        self.assertIn("applicability.* is an information-audit target", GAP_AUDIT_SYSTEM)
        self.assertIn("this is not OUT_OF_SCOPE", GAP_AUDIT_SYSTEM)
        self.assertIn("never shorten, translate or paraphrase", GAP_AUDIT_SYSTEM)
        self.assertIn("do not fan it out to other actions", GAP_AUDIT_SYSTEM)
        self.assertIn("bounded exploration", GAP_AUDIT_SYSTEM)
        self.assertIn("The program materializes the one exact disable Impact Probe", GAP_AUDIT_SYSTEM)

    def test_initial_prompt_exposes_every_parser_owned_nested_contract(self) -> None:
        required_fragments = (
            '"quote":"verbatim prompt quote"',
            '"or_role":"OR role"',
            '"mapped_targets"',
            '"usage_status":"MODELED|APPLICABILITY_USED|DERIVED|UNACCOUNTED"',
            "MODELED and DERIVED may map only to existing variable.*, constraint.* or objective.*",
            "never parameter.* or applicability.*",
            "APPLICABILITY_USED requires at least one of exactly applicability.subject_eligibility",
            "Never invent another applicability suffix",
            "choose APPLICABILITY_USED for every mixed row",
            "UNACCOUNTED uses mapped_targets=[]",
            "unless it represents an omitted gap counted by overflow_count",
            "Every returned Candidate Gap must still link to at least one UNACCOUNTED row",
            "Keep local case attributes separate from external operative rules",
            "does not mean an unstated law, regulation, policy or technical eligibility rule is automatically satisfied",
            "defines the requested decision/capacity, not whether every action is legally or operationally eligible",
            "A license/certificate/category record is only an attribute, not an eligibility conclusion",
            "explicitly states the operative rule that maps those attributes",
            "keep that use in a MODELED row and add a separate UNACCOUNTED row",
            "Choose-k, capacity, cost and benefit facts are ordinary OR inputs and are not search triggers",
            "A local objective gain, loss, score or cost maps to COST_BENEFIT",
            "it is never ACTION_CONSEQUENCE unless the same quote states a real-world permission",
            "A non-exhaustive quote about action A may map only the variable.* interface for A",
            "never map an A-only quote to A and B",
            "explicitly states a universal conclusion for all candidate actions",
            "A negative_space_checked boolean is not itself a grounding witness",
            "FactCoverage covers only the auditable prompt prefix",
            "Never create FactCoverage or Candidate Gap rows for output instructions",
            "Canonical objective targets are mechanically `objective.<term.var>`",
            "There is no aggregate objective ID",
            "never invent umbrella names such as objective.listing_value",
            '"prompt_fact_to_model_complete":true|false',
            '"model_interface_to_grounding_complete":true|false',
            '"negative_space_checked"',
            '"overflow_detected":true|false',
            '"overflow_count":0',
            '"self_contained_reason":"reason or null"',
            '"fact_quotes"',
            '"gap_route":"EXTERNAL_RULE|LOCAL_FACT|OUT_OF_SCOPE"',
            '"first_query":"query or null"',
            '"operation":"SET"',
            '"value":{"lb":0,"ub":0}',
            '"range_basis":"MODEL_BOUNDARY"',
            '"basis_quote":null',
            "it never forces selection",
            "Do not invent PROMPT or PREREGISTERED_RULE ranges",
            "self_contained_candidate is a JSON boolean",
            "No solver results, selected actions, objective value",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, INITIAL_SYSTEM)

        for dimension in (
            "SUBJECT_ELIGIBILITY",
            "LOCATION_JURISDICTION",
            "TIME_VERSION",
            "OBJECT_SCOPE",
            "UNIT_THRESHOLD",
            "CAPACITY_FEASIBILITY",
            "EXCEPTION_EXEMPTION",
            "ACTION_CONSEQUENCE",
            "COST_BENEFIT",
        ):
            with self.subTest(dimension=dimension):
                self.assertIn(f'"{dimension}":true|false', INITIAL_SYSTEM)

    def test_canonical_initial_decision_round_trips_through_live_entrypoint(self) -> None:
        observed: dict[str, object] = {}
        result = initial_modeling(PublicCase("P1", "现实资格规则未知。"), staged_llm(valid_initial_payload(), observed))
        self.assertFalse(result.self_contained_candidate)
        self.assertEqual(result.candidate_gaps[0].target, "variable.x")
        self.assertEqual(result.candidate_gaps[0].hypothetical_variants, [])
        self.assertEqual(
            observed["purposes"],
            ["searchworthy_initial_model_ir", "searchworthy_fact_coverage", "searchworthy_gap_audit"],
        )
        messages = observed["messages"]
        self.assertEqual(json.loads(messages[1][1]["content"])["model_ir"], MODEL_IR)  # type: ignore[index]
        self.assertEqual(json.loads(messages[1][1]["content"])["auditable_fact_units"], ["现实资格规则未知"])  # type: ignore[index]
        self.assertEqual(json.loads(messages[2][1]["content"])["fact_coverage"], valid_initial_payload()["fact_coverage"])  # type: ignore[index]
        self.assertEqual(
            json.loads(messages[2][1]["content"])["allowed_gap_targets"],  # type: ignore[index]
            ["constraint.choose", "objective.constant", "objective.x", "variable.x"],
        )
        self.assertEqual(
            json.loads(messages[2][1]["content"])["allowed_information_targets"],  # type: ignore[index]
            [f"applicability.{dimension.value.lower()}" for dimension in sorted(AuditDimension, key=lambda row: row.value)],
        )
        self.assertEqual(
            json.loads(messages[2][1]["content"])["action_target_catalog"],  # type: ignore[index]
            [
                {
                    "target": "variable.x",
                    "action_meaning": "x",
                    "base_bounds": {"lb": 0, "ub": 1},
                    "objective_direction": "max",
                    "objective_coefficient": 1,
                    "constraint_memberships": [
                        {"constraint": "choose", "coefficient": 1, "sense": "==", "rhs": 1}
                    ],
                    "base_selected_in_any_optimum": True,
                    "base_selected_in_all_optima": True,
                    "base_optimal_pool_complete": True,
                    "disable_probe_priority": "DECISION_CRITICAL",
                }
            ],
        )
        self.assertEqual(
            json.loads(messages[2][1]["content"])["required_probe_targets"],  # type: ignore[index]
            ["variable.x"],
        )

    def test_program_restores_unique_long_quote_and_targets_base_critical_action(self) -> None:
        fact = "机构甲和机构乙的所在地许可、服务区域、专业资质与外部资格规则均需要按照当前官方规则逐项核验"
        copied_with_two_character_omission = fact.replace("专业资质", "资质")
        prompt = (
            f"{fact}；计划必须恰好选择一家，成本分别为1点和2点。"
            "公开 output_schema："
            '{"actions":[{"id":"x","meaning":"机构甲","type":"BINARY"},'
            '{"id":"y","meaning":"机构乙","type":"BINARY"}],'
            '"objective":{"accepted_units":{"点":1},"canonical_unit":"点"}}'
        )
        payload = {
            "model_ir": {
                "variables": [
                    {"id": "x", "type": "BINARY", "lb": 0, "ub": 1},
                    {"id": "y", "type": "BINARY", "lb": 0, "ub": 1},
                ],
                "constraints": [
                    {
                        "name": "choose",
                        "terms": [{"var": "x", "coef": 1}, {"var": "y", "coef": 1}],
                        "sense": "==",
                        "rhs": 1,
                    }
                ],
                "objective": {
                    "direction": "min",
                    "terms": [{"var": "x", "coef": 1}, {"var": "y", "coef": 2}],
                    "constant": 0,
                    "unit": "点",
                },
                "parameters": {},
            },
            "fact_coverage": [
                {
                    "quote": fact,
                    "or_role": "external applicability",
                    "mapped_targets": [],
                    "usage_status": "UNACCOUNTED",
                    "reason": "missing current rule",
                },
                {
                    "quote": "计划必须恰好选择一家，成本分别为1点和2点",
                    "or_role": "choice and cost",
                    "mapped_targets": ["constraint.choose", "objective.x", "objective.y"],
                    "usage_status": "MODELED",
                    "reason": "canonical model",
                },
            ],
            "audit_summary": {
                "prompt_fact_to_model_complete": False,
                "model_interface_to_grounding_complete": False,
                "negative_space_checked": {dimension.value: True for dimension in AuditDimension},
                "overflow_detected": False,
                "overflow_count": 0,
                "self_contained_reason": "external action rule remains open",
            },
            "candidate_gaps": [
                {
                    "fact_quotes": [copied_with_two_character_omission],
                    "reality_role": "external action rule",
                    "gap_claim": "机构乙的外部资格未知",
                    "target": "variable.y",
                    "gap_route": "EXTERNAL_RULE",
                    "hypothetical_variants": [],
                    "first_query": "官方 机构乙 资格规则",
                }
            ],
            "self_contained_candidate": False,
        }
        initial = initial_modeling(PublicCase("P-CRITICAL", prompt), staged_llm(payload))
        gap = initial.candidate_gaps[0]
        self.assertEqual(gap.target, "variable.x")
        self.assertEqual(gap.fact_quotes, [fact])
        self.assertIn("PROGRAM_RESTORED_EXACT_FACT_QUOTE", gap.gap_claim)
        self.assertIn("PROGRAM_DECISION_CRITICAL_TARGET:variable.y->variable.x", gap.gap_claim)
        self.assertIn("机构甲", gap.first_query or "")

        substituted = copy.deepcopy(payload)
        substituted["candidate_gaps"][0]["fact_quotes"] = [fact.replace("专业", "行业")]  # type: ignore[index]
        normalized = _normalize_unbound_gap_targets(
            {
                "audit_summary": substituted["audit_summary"],
                "candidate_gaps": substituted["candidate_gaps"],
                "self_contained_candidate": False,
            },
            substituted["fact_coverage"],  # type: ignore[arg-type]
        )
        self.assertEqual(
            normalized["candidate_gaps"][0]["fact_quotes"],
            [fact.replace("专业", "行业")],
        )
        self.assertNotIn("PROGRAM_RESTORED_EXACT_FACT_QUOTE", normalized["candidate_gaps"][0]["gap_claim"])

    def test_program_closes_colon_truncation_with_an_exact_prompt_span(self) -> None:
        full_fact = (
            "经过本地预审，三家服务商均具备服务条件："
            "Alpha Home Care、Beta Health LLC和Gamma Services"
        )
        prompt = f"{full_fact}。必须选择方案X。公开 output_schema：{{}}"
        payload = valid_initial_payload()
        payload["fact_coverage"] = [
            {
                "quote": "经过本地预审，三家服务商均具备服务条件",
                "or_role": "LOCAL_REVIEW",
                "mapped_targets": ["applicability.location_jurisdiction"],
                "usage_status": "APPLICABILITY_USED",
                "reason": "provider list was truncated",
            },
            {
                "quote": "必须选择方案X",
                "or_role": "SELECTION",
                "mapped_targets": ["variable.x", "constraint.choose"],
                "usage_status": "MODELED",
                "reason": "canonical selection",
            },
        ]
        payload["audit_summary"]["prompt_fact_to_model_complete"] = False  # type: ignore[index]
        payload["audit_summary"]["model_interface_to_grounding_complete"] = False  # type: ignore[index]
        payload["audit_summary"]["overflow_detected"] = True  # type: ignore[index]
        payload["audit_summary"]["overflow_count"] = 1  # type: ignore[index]
        payload["audit_summary"]["self_contained_reason"] = "program closure remains open"  # type: ignore[index]
        payload["candidate_gaps"] = []
        payload["self_contained_candidate"] = False

        observed: dict[str, object] = {}
        result = initial_modeling(PublicCase("P-COLON", prompt), staged_llm(payload, observed))
        program_rows = [
            row
            for row in result.fact_coverage
            if row.or_role == PROGRAM_FACT_COVERAGE_CLOSURE_MARKER
        ]
        self.assertEqual(len(program_rows), 1)
        self.assertEqual(program_rows[0].quote, full_fact)
        self.assertIn("Alpha Home Care", program_rows[0].quote)
        self.assertIn(program_rows[0].quote, prompt)
        self.assertTrue(_quote_in_prompt(prompt, program_rows[0].quote))
        self.assertEqual(program_rows[0].mapped_targets, [])
        self.assertEqual(program_rows[0].usage_status.value, "UNACCOUNTED")
        self.assertEqual(program_rows[0].reason, PROGRAM_FACT_COVERAGE_CLOSURE_REASON)
        self.assertEqual(_prompt_fact_unit_spans(prompt)[0], (full_fact.replace(" ", ""), full_fact))
        self.assertEqual(
            observed["purposes"],
            ["searchworthy_initial_model_ir", "searchworthy_fact_coverage"],
        )

        covered = copy.deepcopy(payload)
        covered["fact_coverage"][0]["quote"] = full_fact  # type: ignore[index]
        covered_result = initial_modeling(PublicCase("P-COVERED", prompt), staged_llm(covered))
        self.assertFalse(
            any(
                row.or_role == PROGRAM_FACT_COVERAGE_CLOSURE_MARKER
                for row in covered_result.fact_coverage
            )
        )

        forged = copy.deepcopy(payload)
        forged["fact_coverage"].append(  # type: ignore[union-attr]
            {
                "quote": full_fact,
                "or_role": PROGRAM_FACT_COVERAGE_CLOSURE_MARKER,
                "mapped_targets": [],
                "usage_status": "UNACCOUNTED",
                "reason": PROGRAM_FACT_COVERAGE_CLOSURE_REASON,
            }
        )
        rejected: dict[str, object] = {}
        with self.assertRaisesRegex(ValueError, "program-owned closure row"):
            initial_modeling(PublicCase("P-FORGED", prompt), staged_llm(forged, rejected))
        self.assertEqual(
            rejected["purposes"],
            ["searchworthy_initial_model_ir", "searchworthy_fact_coverage"],
        )

        forbidden = lambda *_args: (_ for _ in ()).throw(
            AssertionError("Stage2 coverage failure must not search")
        )
        diagnostic_result = run_case(
            PublicCase("P-DIAGNOSTIC", prompt),
            {
                "actions": [{"id": "x", "type": "BINARY"}],
                "objective": {"accepted_units": {"点": 1}, "canonical_unit": "点"},
            },
            PipelineServices(lambda _public: result, forbidden, forbidden),
        )
        self.assertEqual(diagnostic_result["status"], "ABSTAIN")
        self.assertEqual(diagnostic_result["search"]["search_count"], 0)
        self.assertEqual(diagnostic_result["state"]["gaps"], [])
        self.assertEqual(
            diagnostic_result["state"]["information_audit_failure"],
            {
                "code": "STAGE2_FACT_COVERAGE_INCOMPLETE",
                "invalid_gap_indices": [],
                "unlinked_fact_indices": [3],
            },
        )
        self.assertFalse(
            diagnostic_result["state"]["audit_summary"]["prompt_fact_to_model_complete"]
        )
        self.assertFalse(
            diagnostic_result["state"]["audit_summary"]["model_interface_to_grounding_complete"]
        )
        self.assertEqual(
            diagnostic_result["state"]["audit_summary"]["self_contained_reason"],
            PROGRAM_FACT_COVERAGE_AUDIT_REASON,
        )

    def test_program_closure_requires_full_local_unit_coverage(self) -> None:
        first = "第一条事实包含Alpha Provider以及一项很长的本地服务条件"
        second = "第二条事实要求选择Beta Health LLC作为候选方案"
        prompt = f"{first}。{second}。公开 output_schema：{{}}"
        high_coverage_prefix = first[:-2]
        giant_quote = f"{first}。{second}"
        self.assertTrue(_fact_unit_covered(first, [high_coverage_prefix]))
        self.assertFalse(_fact_unit_fully_covered(first, [high_coverage_prefix]))
        self.assertFalse(_fact_unit_fully_covered(first, [giant_quote]))
        self.assertFalse(_fact_unit_fully_covered(second, [giant_quote]))

        rows = [
            {
                "quote": high_coverage_prefix,
                "or_role": "PARTIAL",
                "mapped_targets": [],
                "usage_status": "UNACCOUNTED",
                "reason": "legacy 85 percent prefix",
            },
            {
                "quote": giant_quote,
                "or_role": "GIANT",
                "mapped_targets": [],
                "usage_status": "UNACCOUNTED",
                "reason": "spans two units",
            },
        ]
        closed = _close_stage_fact_coverage(prompt, rows)
        program_quotes = {
            row["quote"]
            for row in closed
            if row["or_role"] == PROGRAM_FACT_COVERAGE_CLOSURE_MARKER
        }
        self.assertEqual(program_quotes, {first, second})

        comma_unit = "候选型号标记A至F，上市价值依次为68、63、59、74、71、66点"
        comma_quotes = ["候选型号标记A至F", "上市价值依次为68、63、59、74、71、66点"]
        self.assertTrue(_fact_unit_fully_covered(comma_unit, comma_quotes))
        self.assertTrue(_fact_unit_fully_covered(comma_unit, [f"{comma_unit}。"], comma_unit))
        comma_rows = [
            {
                "quote": quote,
                "or_role": "SPLIT_CLAUSE",
                "mapped_targets": [],
                "usage_status": "UNACCOUNTED",
                "reason": "complete fact text split at punctuation",
            }
            for quote in comma_quotes
        ]
        self.assertFalse(
            any(
                row["or_role"] == PROGRAM_FACT_COVERAGE_CLOSURE_MARKER
                for row in _close_stage_fact_coverage(
                    f"{comma_unit}。公开 output_schema：{{}}", comma_rows
                )
            )
        )

        first_occurrence = "甲公司允许乙设备"
        colon_occurrence = "甲公司：允许乙设备"
        occurrence_prompt = (
            f"{first_occurrence}。{colon_occurrence}。公开 output_schema：{{}}"
        )
        first_only_rows = [
            {
                "quote": first_occurrence,
                "or_role": "FIRST_FRAGMENT_ONLY",
                "mapped_targets": [],
                "usage_status": "UNACCOUNTED",
                "reason": "must not close the similar second fragment",
            }
        ]
        occurrence_closed = _close_stage_fact_coverage(occurrence_prompt, first_only_rows)
        self.assertEqual(
            [
                row["quote"]
                for row in occurrence_closed
                if row["or_role"] == PROGRAM_FACT_COVERAGE_CLOSURE_MARKER
            ],
            [colon_occurrence],
        )

        time_unit = "预约窗口为上午10:30开始"
        ratio_unit = "混合比例为原料1:2成品单位"
        self.assertFalse(
            _fact_unit_fully_covered(
                time_unit,
                ["预约窗口为上午10", "30开始"],
                time_unit,
            )
        )
        self.assertFalse(
            _fact_unit_fully_covered(
                ratio_unit,
                ["混合比例为原料1", "2成品单位"],
                ratio_unit,
            )
        )

        empty_payload = valid_initial_payload()
        empty_payload["fact_coverage"] = []
        empty_payload["audit_summary"]["prompt_fact_to_model_complete"] = False  # type: ignore[index]
        empty_payload["audit_summary"]["model_interface_to_grounding_complete"] = False  # type: ignore[index]
        empty_payload["audit_summary"]["overflow_detected"] = True  # type: ignore[index]
        empty_payload["audit_summary"]["overflow_count"] = 2  # type: ignore[index]
        empty_payload["candidate_gaps"] = []
        empty_payload["self_contained_candidate"] = False
        empty_observed: dict[str, object] = {}
        empty_result = initial_modeling(
            PublicCase("P-EMPTY-STAGE2", prompt),
            staged_llm(empty_payload, empty_observed),
        )
        self.assertEqual(
            {row.quote for row in empty_result.fact_coverage},
            {first, second},
        )
        self.assertTrue(
            all(
                row.or_role == PROGRAM_FACT_COVERAGE_CLOSURE_MARKER
                for row in empty_result.fact_coverage
            )
        )
        self.assertEqual(
            empty_observed["purposes"],
            ["searchworthy_initial_model_ir", "searchworthy_fact_coverage"],
        )

        heading_only = [
            {
                "quote": "【优化骨架】",
                "or_role": "HEADING",
                "mapped_targets": [],
                "usage_status": "UNACCOUNTED",
                "reason": "not an auditable unit",
            }
        ]
        heading_prompt = f"【优化骨架】\n{first}。公开 output_schema：{{}}"
        normalized = _normalize_stage_fact_coverage(heading_prompt, MODEL_IR, heading_only)
        self.assertEqual(normalized, [])
        self.assertEqual(
            [row["quote"] for row in _close_stage_fact_coverage(heading_prompt, normalized)],
            [first],
        )

    def test_stage3_raw_cannot_supply_a_program_owned_probe(self) -> None:
        for route, query in (("EXTERNAL_RULE", "官方 行动资格 规则"), ("LOCAL_FACT", None)):
            with self.subTest(route=route):
                payload = valid_initial_payload()
                gap = payload["candidate_gaps"][0]  # type: ignore[index]
                gap["gap_route"] = route
                gap["first_query"] = query
                gap["hypothetical_variants"] = [
                    {
                        "target": "variable.x",
                        "operation": "SET",
                        "value": {"lb": 0, "ub": 0},
                        "range_basis": "MODEL_BOUNDARY",
                        "basis_quote": None,
                    }
                ]
                with self.assertRaisesRegex(ValueError, "program-owned Impact Probes"):
                    initial_modeling(PublicCase("P-RAW-PROBE", "现实资格规则未知。"), staged_llm(payload))

    def test_registered_applicability_gap_is_marked_without_losing_raw_provenance(self) -> None:
        payload = valid_initial_payload()
        payload["audit_summary"]["model_interface_to_grounding_complete"] = False  # type: ignore[index]
        gap = payload["candidate_gaps"][0]  # type: ignore[index]
        gap["target"] = "applicability.subject_eligibility"
        gap["hypothetical_variants"] = []
        normalized = _normalize_unbound_gap_targets(
            {
                "audit_summary": payload["audit_summary"],
                "candidate_gaps": payload["candidate_gaps"],
                "self_contained_candidate": False,
            },
            payload["fact_coverage"],  # type: ignore[arg-type]
        )
        normalized_gap = normalized["candidate_gaps"][0]
        self.assertEqual(normalized_gap["target"], "applicability.subject_eligibility")
        self.assertEqual(normalized_gap["gap_route"], "EXTERNAL_RULE")
        self.assertEqual(normalized_gap["first_query"], "官方 行动资格 规则")
        self.assertIn("PROGRAM_UNBOUND_OR_TARGET:applicability.subject_eligibility", normalized_gap["gap_claim"])

        uppercase = copy.deepcopy(payload)
        uppercase_gap = uppercase["candidate_gaps"][0]  # type: ignore[index]
        uppercase_gap["target"] = "applicability.SUBJECT_ELIGIBILITY"
        uppercase_gap["hypothetical_variants"] = []
        normalized_uppercase = _normalize_unbound_gap_targets(
            {
                "audit_summary": uppercase["audit_summary"],
                "candidate_gaps": uppercase["candidate_gaps"],
                "self_contained_candidate": False,
            },
            uppercase["fact_coverage"],  # type: ignore[arg-type]
        )["candidate_gaps"][0]
        self.assertEqual(normalized_uppercase["target"], "applicability.subject_eligibility")
        self.assertIn("PROGRAM_UNBOUND_OR_TARGET:applicability.subject_eligibility", normalized_uppercase["gap_claim"])

        unknown = copy.deepcopy(normalized)
        unknown_gap = unknown["candidate_gaps"][0]
        unknown_gap["target"] = "applicability.unknown_dimension"
        self.assertEqual(
            _normalize_unbound_gap_targets(unknown, payload["fact_coverage"])["candidate_gaps"][0]["target"],  # type: ignore[arg-type]
            "applicability.unknown_dimension",
        )

        probed = copy.deepcopy(payload)
        probed_gap = probed["candidate_gaps"][0]  # type: ignore[index]
        probed_gap["target"] = "applicability.subject_eligibility"
        probed_gap["hypothetical_variants"] = [
            {
                "target": "applicability.subject_eligibility",
                "operation": "SET",
                "value": {"lb": 0, "ub": 0},
                "range_basis": "MODEL_BOUNDARY",
                "basis_quote": None,
            }
        ]
        probed_audit = _normalize_unbound_gap_targets(
            {
                "audit_summary": probed["audit_summary"],
                "candidate_gaps": probed["candidate_gaps"],
                "self_contained_candidate": False,
            },
            probed["fact_coverage"],  # type: ignore[arg-type]
        )
        self.assertEqual(probed_audit["candidate_gaps"][0]["target"], "applicability.subject_eligibility")
        with self.assertRaisesRegex(ValueError, "only support variable"):
            parse_initial_decision(
                {
                    "model_ir": probed["model_ir"],
                    "fact_coverage": probed["fact_coverage"],
                    **probed_audit,
                }
            )

    def test_pure_audit_only_grounding_contradiction_becomes_unbound_abstain(self) -> None:
        payload = valid_initial_payload()
        summary = payload["audit_summary"]  # type: ignore[assignment]
        summary["prompt_fact_to_model_complete"] = False
        summary["self_contained_reason"] = "存在未闭合的主体适用性事实"
        gap = payload["candidate_gaps"][0]  # type: ignore[index]
        gap.update(
            {
                "target": "applicability.subject_eligibility",
                "gap_route": "OUT_OF_SCOPE",
                "hypothetical_variants": [],
                "first_query": None,
            }
        )
        audit = {
            "audit_summary": summary,
            "candidate_gaps": payload["candidate_gaps"],
            "self_contained_candidate": False,
        }
        original = copy.deepcopy(audit)
        normalized = _normalize_unbound_gap_targets(audit, payload["fact_coverage"])  # type: ignore[arg-type]

        self.assertEqual(audit, original)
        self.assertIs(normalized["audit_summary"]["model_interface_to_grounding_complete"], False)
        self.assertIn(
            "PROGRAM_DOWNGRADED_AUDIT_ONLY_GROUNDING_CONTRADICTION",
            normalized["audit_summary"]["self_contained_reason"],
        )
        self.assertIn(
            "PROGRAM_UNBOUND_OR_TARGET:applicability.subject_eligibility",
            normalized["candidate_gaps"][0]["gap_claim"],
        )
        self.assertEqual(
            _normalize_unbound_gap_targets(normalized, payload["fact_coverage"]),  # type: ignore[arg-type]
            normalized,
        )

        initial = parse_initial_decision(
            {
                "model_ir": payload["model_ir"],
                "fact_coverage": payload["fact_coverage"],
                **normalized,
            }
        )
        forbidden = lambda *_args: (_ for _ in ()).throw(AssertionError("UNBOUND must not search or assess evidence"))
        result = run_case(
            PublicCase("P-CONTRADICTION", "现实资格规则未知。"),
            {
                "actions": [{"id": "x", "type": "BINARY"}],
                "objective": {"accepted_units": {"点": 1}, "canonical_unit": "点"},
            },
            PipelineServices(lambda _public: initial, forbidden, forbidden),
        )
        state_gap = result["state"]["gaps"][0]
        self.assertEqual(result["status"], "ABSTAIN")
        self.assertEqual(result["search"]["search_count"], 0)
        self.assertIsNone(result["state"]["information_audit_failure"])
        self.assertIsNone(state_gap["target"])
        self.assertEqual(state_gap["proposed_information_target"], "applicability.subject_eligibility")
        self.assertEqual(state_gap["target_binding_status"], "UNBOUND")
        self.assertEqual(state_gap["state"], "UNRESOLVED_ABSTAIN")

    def test_grounding_contradiction_preserves_nonexact_quote_as_audit_failure(self) -> None:
        payload = valid_initial_payload()
        payload["fact_coverage"].append(  # type: ignore[union-attr]
            {
                "quote": "外部主体规则未知。",
                "or_role": "SUBJECT",
                "mapped_targets": [],
                "usage_status": "UNACCOUNTED",
                "reason": "需要主体范围结论",
            }
        )
        summary = payload["audit_summary"]  # type: ignore[assignment]
        summary["prompt_fact_to_model_complete"] = False
        summary["self_contained_reason"] = "两条适用性事实仍未闭合"
        first_gap = payload["candidate_gaps"][0]  # type: ignore[index]
        first_gap.update(
            {
                "target": "applicability.subject_eligibility",
                "gap_route": "OUT_OF_SCOPE",
                "hypothetical_variants": [],
                "first_query": None,
            }
        )
        second_gap = copy.deepcopy(first_gap)
        second_gap.update(
            {
                "fact_quotes": ["外部主体规则未知"],
                "reality_role": "外部主体适用范围",
                "gap_claim": "外部主体范围未知",
                "target": "applicability.object_scope",
            }
        )
        payload["candidate_gaps"] = [first_gap, second_gap]
        normalized = _normalize_unbound_gap_targets(
            {
                "audit_summary": summary,
                "candidate_gaps": payload["candidate_gaps"],
                "self_contained_candidate": False,
            },
            payload["fact_coverage"],  # type: ignore[arg-type]
        )

        self.assertIs(normalized["audit_summary"]["model_interface_to_grounding_complete"], False)
        self.assertIn("PROGRAM_UNBOUND_OR_TARGET", normalized["candidate_gaps"][0]["gap_claim"])
        self.assertNotIn("PROGRAM_UNBOUND_OR_TARGET", normalized["candidate_gaps"][1]["gap_claim"])
        self.assertEqual(normalized["candidate_gaps"][1]["fact_quotes"], ["外部主体规则未知"])

        initial = parse_initial_decision(
            {
                "model_ir": payload["model_ir"],
                "fact_coverage": payload["fact_coverage"],
                **normalized,
            }
        )
        forbidden = lambda *_args: (_ for _ in ()).throw(AssertionError("audit failure must not search"))
        result = run_case(
            PublicCase("P-EXACT-SPAN", "现实资格规则未知；外部主体规则未知。"),
            {
                "actions": [{"id": "x", "type": "BINARY"}],
                "objective": {"accepted_units": {"点": 1}, "canonical_unit": "点"},
            },
            PipelineServices(lambda _public: initial, forbidden, forbidden),
        )
        self.assertEqual(result["status"], "ABSTAIN")
        self.assertEqual(result["search"]["search_count"], 0)
        self.assertEqual(result["state"]["gaps"], [])
        self.assertEqual(
            result["state"]["information_audit_failure"],
            {
                "code": "STAGE3_CANDIDATE_GAP_LINK_FAILURE",
                "invalid_gap_indices": [2],
                "unlinked_fact_indices": [2],
            },
        )

    def test_grounding_contradiction_does_not_repair_executable_or_malformed_rows(self) -> None:
        payload = valid_initial_payload()
        summary = payload["audit_summary"]  # type: ignore[assignment]
        summary["prompt_fact_to_model_complete"] = False
        summary["self_contained_reason"] = "存在未闭合的主体适用性事实"
        gap = payload["candidate_gaps"][0]  # type: ignore[index]
        gap.update(
            {
                "target": "applicability.subject_eligibility",
                "gap_route": "OUT_OF_SCOPE",
                "hypothetical_variants": [],
                "first_query": None,
            }
        )
        base = {
            "audit_summary": summary,
            "candidate_gaps": payload["candidate_gaps"],
            "self_contained_candidate": False,
        }
        gap_mutations = (
            ("uppercase_alias", {"target": "applicability.SUBJECT_ELIGIBILITY"}),
            ("local_fact", {"gap_route": "LOCAL_FACT"}),
            ("query", {"first_query": "不应授权的查询"}),
            ("variants", {"hypothetical_variants": [{"target": "variable.x"}]}),
            ("no_exact_anchor", {"fact_quotes": ["被改写的资格规则"]}),
        )
        candidates: list[tuple[str, dict[str, object]]] = []
        for label, mutation in gap_mutations:
            candidate = copy.deepcopy(base)
            candidate["candidate_gaps"][0].update(mutation)  # type: ignore[index]
            candidates.append((label, candidate))

        mixed = copy.deepcopy(base)
        executable = copy.deepcopy(mixed["candidate_gaps"][0])  # type: ignore[index]
        executable.update(
            {
                "target": "variable.x",
                "gap_route": "EXTERNAL_RULE",
                "first_query": "官方资格规则",
            }
        )
        mixed["candidate_gaps"].append(executable)  # type: ignore[union-attr]
        candidates.append(("mixed_executable", mixed))

        malformed = copy.deepcopy(base)
        malformed["candidate_gaps"][0]["extra"] = True  # type: ignore[index]
        candidates.append(("extra_key", malformed))

        prompt_complete = copy.deepcopy(base)
        prompt_complete["audit_summary"]["prompt_fact_to_model_complete"] = True  # type: ignore[index]
        candidates.append(("prompt_complete", prompt_complete))

        overflow = copy.deepcopy(base)
        overflow["audit_summary"]["overflow_detected"] = True  # type: ignore[index]
        overflow["audit_summary"]["overflow_count"] = 1  # type: ignore[index]
        candidates.append(("overflow", overflow))

        self_contained = copy.deepcopy(base)
        self_contained["self_contained_candidate"] = True
        candidates.append(("self_contained", self_contained))

        for label, candidate in candidates:
            with self.subTest(label=label):
                original = copy.deepcopy(candidate)
                normalized = _normalize_unbound_gap_targets(
                    candidate,
                    payload["fact_coverage"],  # type: ignore[arg-type]
                )
                self.assertEqual(candidate, original)
                self.assertIs(normalized["audit_summary"]["model_interface_to_grounding_complete"], True)
                self.assertNotIn(
                    "PROGRAM_DOWNGRADED_AUDIT_ONLY_GROUNDING_CONTRADICTION",
                    str(normalized["audit_summary"].get("self_contained_reason")),
                )

    def test_registered_alias_with_bad_fact_link_becomes_explicit_audit_failure(self) -> None:
        payload = valid_initial_payload()
        payload["audit_summary"]["model_interface_to_grounding_complete"] = False  # type: ignore[index]
        gap = payload["candidate_gaps"][0]  # type: ignore[index]
        gap["fact_quotes"] = ["现实资格规则未知且已被改写"]
        gap["target"] = "applicability.SUBJECT_ELIGIBILITY"
        gap["gap_route"] = "OUT_OF_SCOPE"
        gap["hypothetical_variants"] = []
        gap["first_query"] = None
        initial = initial_modeling(PublicCase("P-LINK", "现实资格规则未知。"), staged_llm(payload))
        self.assertEqual(initial.candidate_gaps[0].target, "applicability.subject_eligibility")
        self.assertNotIn("PROGRAM_UNBOUND_OR_TARGET", initial.candidate_gaps[0].gap_claim)

        forbidden = lambda *_args: (_ for _ in ()).throw(AssertionError("audit failure must not search"))
        result = run_case(
            PublicCase("P-LINK", "现实资格规则未知。"),
            {
                "actions": [{"id": "x", "type": "BINARY"}],
                "objective": {"accepted_units": {"点": 1}, "canonical_unit": "点"},
            },
            PipelineServices(lambda _public: initial, forbidden, forbidden),
        )
        self.assertEqual(result["status"], "ABSTAIN")
        self.assertEqual(result["search"]["search_count"], 0)
        self.assertEqual(result["state"]["gaps"], [])
        self.assertEqual(
            result["state"]["information_audit_failure"],
            {
                "code": "STAGE3_CANDIDATE_GAP_LINK_FAILURE",
                "invalid_gap_indices": [1],
                "unlinked_fact_indices": [1],
            },
        )

    def test_variable_gap_fact_quote_must_bind_its_public_action(self) -> None:
        model_ir = {
            "variables": [
                {"id": "x", "type": "BINARY", "lb": 0, "ub": 1},
                {"id": "y", "type": "BINARY", "lb": 0, "ub": 1},
            ],
            "constraints": [
                {
                    "name": "choose_one",
                    "terms": [{"var": "x", "coef": 1}, {"var": "y", "coef": 1}],
                    "sense": "==",
                    "rhs": 1,
                }
            ],
            "objective": {
                "direction": "max",
                "terms": [{"var": "x", "coef": 2}, {"var": "y", "coef": 1}],
                "constant": 0,
                "unit": "点",
            },
            "parameters": {},
        }
        schema = {
            "actions": [
                {"id": "x", "meaning": "选择方案X", "type": "BINARY"},
                {"id": "y", "meaning": "选择方案Y", "type": "BINARY"},
            ],
            "objective": {"accepted_units": {"点": 1}, "canonical_unit": "点"},
        }
        schema_text = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))

        def state_for(quote: str, target: str):
            prompt = f"{quote}。公开 output_schema：{schema_text}"
            payload = {
                "model_ir": model_ir,
                "fact_coverage": [
                    {
                        "quote": quote,
                        "or_role": "REALITY_GAP",
                        "mapped_targets": [],
                        "usage_status": "UNACCOUNTED",
                        "reason": "external action rule is missing",
                    }
                ],
                "audit_summary": {
                    "prompt_fact_to_model_complete": False,
                    "model_interface_to_grounding_complete": False,
                    "negative_space_checked": {
                        dimension.value: True for dimension in AuditDimension
                    },
                    "overflow_detected": False,
                    "overflow_count": 0,
                    "self_contained_reason": "external action rule is missing",
                },
                "candidate_gaps": [
                    {
                        "fact_quotes": [quote],
                        "reality_role": "ACTION_ELIGIBILITY",
                        "gap_claim": "external action rule is missing",
                        "target": target,
                        "gap_route": "EXTERNAL_RULE",
                        "hypothetical_variants": [],
                        "first_query": "official action eligibility rule",
                    }
                ],
                "self_contained_candidate": False,
            }
            initial = parse_initial_decision(payload)
            validated_ir, capture = solve_initial(model_ir, schema)
            return initialize_state(PublicCase("P-ACTION-BIND", prompt), initial, validated_ir, capture)

        mismatched = state_for("方案X的外部准入规则未知", "variable.y")
        self.assertEqual(mismatched.gaps, [])
        self.assertEqual(
            mismatched.information_audit_failure,
            {
                "code": "STAGE3_CANDIDATE_GAP_LINK_FAILURE",
                "invalid_gap_indices": [1],
                "unlinked_fact_indices": [],
            },
        )

        matched = state_for("方案X的外部准入规则未知", "variable.x")
        self.assertIsNone(matched.information_audit_failure)
        self.assertEqual([gap.target for gap in matched.gaps], ["variable.x"])

        universal = state_for("所有候选方案的外部准入规则未知", "variable.y")
        self.assertIsNone(universal.information_audit_failure)
        self.assertEqual([gap.target for gap in universal.gaps], ["variable.y"])

    def test_action_anchor_classifier_rejects_subset_numeric_and_short_id_collisions(self) -> None:
        plan_meanings = {"x": "选择方案X", "y": "选择方案Y"}
        self.assertFalse(
            _quote_binds_variable_target(
                "没有任何其他资产，方案X资格未知",
                "variable.y",
                plan_meanings,
            )
        )
        self.assertTrue(
            _quote_binds_variable_target(
                "选择方案X或选择方案Y的资格均未知",
                "variable.x",
                plan_meanings,
            )
        )
        self.assertTrue(
            _quote_binds_variable_target(
                "选择方案X或选择方案Y的资格均未知",
                "variable.y",
                plan_meanings,
            )
        )

        numbered = {"a_long_id": "选择方案1", "b_long_id": "选择方案2"}
        self.assertFalse(
            _quote_binds_variable_target(
                "审核日期为8月1日，资格规则未知",
                "variable.a_long_id",
                numbered,
            )
        )
        self.assertTrue(
            _quote_binds_variable_target(
                "方案1的资格规则未知",
                "variable.a_long_id",
                numbered,
            )
        )

        self.assertFalse(
            _quote_binds_variable_target(
                "候选色素X的资格未知",
                "variable.x",
                {"x": "选择方案甲", "y": "选择方案乙"},
            )
        )
        self.assertTrue(
            _quote_binds_variable_target(
                "所有候选行动均需资格核查",
                "variable.provider_long_id",
                {
                    "provider_long_id": "把QCN Home Care选为执行机构",
                    "other_long_id": "把Beta Health选为执行机构",
                },
            )
        )
        for negated_universal in (
            "并非所有候选行动都符合资格",
            "不是所有候选行动都符合资格",
            "并非每个候选行动都符合资格",
            "Not all candidate actions qualify",
            "Not necessarily all candidate actions qualify",
            "并非所有候选服务商都符合资格",
            "除方案X外，所有候选行动均需资格核查",
            "所有候选行动中方案X除外",
            "All candidate actions except option X require review",
        ):
            for target in ("variable.x", "variable.y"):
                self.assertFalse(
                    _quote_binds_variable_target(
                        negated_universal,
                        target,
                        plan_meanings,
                    ),
                    (negated_universal, target),
                )

        id_meanings = {
            "action-a": "选择方案甲",
            "action-b": "选择方案乙",
        }
        self.assertTrue(
            _quote_binds_variable_target(
                "action-a 的资格规则未知",
                "variable.action-a",
                id_meanings,
            )
        )
        self.assertFalse(
            _quote_binds_variable_target(
                "action-a-plus 的资格规则未知",
                "variable.action-a",
                id_meanings,
            )
        )
        self.assertFalse(
            _quote_binds_variable_target(
                "action-a.plus 的资格规则未知",
                "variable.action-a",
                id_meanings,
            )
        )
        line_meanings = {
            "route_a": "A线采用一名乘务员",
            "route_b": "B线采用一名乘务员",
        }
        self.assertTrue(
            _quote_binds_variable_target(
                "A线继续单人运营的条件未知",
                "variable.route_a",
                line_meanings,
            )
        )
        self.assertFalse(
            _quote_binds_variable_target(
                "A线继续单人运营的条件未知",
                "variable.route_b",
                line_meanings,
            )
        )

    def test_bad_link_cannot_hide_noncanonical_target_or_overflow_types(self) -> None:
        payload = valid_initial_payload()
        payload["audit_summary"]["model_interface_to_grounding_complete"] = False  # type: ignore[index]
        gap = payload["candidate_gaps"][0]  # type: ignore[index]
        gap["fact_quotes"] = ["被改写的现实资格规则"]
        gap["target"] = "applicability.subject_eligibility "
        gap["gap_route"] = "OUT_OF_SCOPE"
        gap["hypothetical_variants"] = []
        gap["first_query"] = None
        with self.assertRaisesRegex(ValueError, "exact canonical spelling"):
            initial_modeling(PublicCase("P-LINK-SPACE", "现实资格规则未知。"), staged_llm(payload))

        overflow = valid_initial_payload()
        overflow["audit_summary"]["overflow_detected"] = True  # type: ignore[index]
        overflow["audit_summary"]["overflow_count"] = True  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "overflow fields"):
            parse_initial_decision(overflow)

        mapped = valid_initial_payload()
        mapped_fact = mapped["fact_coverage"][0]  # type: ignore[index]
        mapped_fact["mapped_targets"] = ["variable.x "]
        mapped_fact["usage_status"] = "MODELED"
        with self.assertRaisesRegex(ValueError, "exact non-empty canonical"):
            parse_initial_decision(mapped)

    def test_unbound_normalizer_does_not_repair_malformed_fields(self) -> None:
        payload = valid_initial_payload()
        payload["audit_summary"]["model_interface_to_grounding_complete"] = False  # type: ignore[index]
        base_gap = payload["candidate_gaps"][0]  # type: ignore[index]
        base_gap["target"] = "applicability.SUBJECT_ELIGIBILITY"
        base_gap["hypothetical_variants"] = []
        for label, field, invalid in (
            ("empty_claim", "gap_claim", ""),
            ("invalid_route", "gap_route", "NOT_A_ROUTE"),
            ("object_query", "first_query", {"bad": 1}),
        ):
            with self.subTest(label=label):
                candidate = copy.deepcopy(payload)
                candidate["candidate_gaps"][0][field] = invalid  # type: ignore[index]
                normalized = _normalize_unbound_gap_targets(
                    {
                        "audit_summary": candidate["audit_summary"],
                        "candidate_gaps": candidate["candidate_gaps"],
                        "self_contained_candidate": False,
                    },
                    candidate["fact_coverage"],  # type: ignore[arg-type]
                )
                self.assertNotIn("PROGRAM_UNBOUND_OR_TARGET", str(normalized["candidate_gaps"][0].get("gap_claim")))
                with self.assertRaises((TypeError, ValueError)):
                    parse_initial_decision(
                        {
                            "model_ir": candidate["model_ir"],
                            "fact_coverage": candidate["fact_coverage"],
                            **normalized,
                        }
                    )

    def test_applicability_enum_aliases_are_exact_only(self) -> None:
        for dimension in AuditDimension:
            with self.subTest(dimension=dimension.value):
                payload = valid_initial_payload()
                payload["audit_summary"]["model_interface_to_grounding_complete"] = False  # type: ignore[index]
                gap = payload["candidate_gaps"][0]  # type: ignore[index]
                gap["target"] = f"applicability.{dimension.value}"
                gap["hypothetical_variants"] = []
                normalized = _normalize_unbound_gap_targets(
                    {
                        "audit_summary": payload["audit_summary"],
                        "candidate_gaps": payload["candidate_gaps"],
                        "self_contained_candidate": False,
                    },
                    payload["fact_coverage"],  # type: ignore[arg-type]
                )["candidate_gaps"][0]
                expected = f"applicability.{dimension.value.lower()}"
                self.assertEqual(normalized["target"], expected)
                self.assertIn(f"PROGRAM_UNBOUND_OR_TARGET:{expected}", normalized["gap_claim"])

        for target in (
            "applicability.Subject_Eligibility",
            "Applicability.SUBJECT_ELIGIBILITY",
            "applicability.SUBJECT_ELIGIBILITY ",
            "applicability.SUBJECT_ELIGIBILITY.extra",
            "applicability.UNKNOWN_DIMENSION",
            "variable.X",
        ):
            with self.subTest(rejected_alias=target):
                payload = valid_initial_payload()
                payload["audit_summary"]["model_interface_to_grounding_complete"] = False  # type: ignore[index]
                gap = payload["candidate_gaps"][0]  # type: ignore[index]
                gap["target"] = target
                gap["hypothetical_variants"] = []
                normalized = _normalize_unbound_gap_targets(
                    {
                        "audit_summary": payload["audit_summary"],
                        "candidate_gaps": payload["candidate_gaps"],
                        "self_contained_candidate": False,
                    },
                    payload["fact_coverage"],  # type: ignore[arg-type]
                )["candidate_gaps"][0]
                self.assertEqual(normalized["target"], target)
                self.assertNotIn("PROGRAM_UNBOUND_OR_TARGET", normalized["gap_claim"])

    def test_three_enum_aliases_fail_closed_before_search(self) -> None:
        payload = valid_initial_payload()
        payload["audit_summary"]["model_interface_to_grounding_complete"] = False  # type: ignore[index]
        base_gap = payload["candidate_gaps"][0]  # type: ignore[index]
        base_gap["hypothetical_variants"] = []
        base_gap["gap_route"] = "OUT_OF_SCOPE"
        base_gap["first_query"] = None
        payload["candidate_gaps"] = [
            {**copy.deepcopy(base_gap), "target": f"applicability.{dimension}"}
            for dimension in ("TIME_VERSION", "OBJECT_SCOPE", "UNIT_THRESHOLD")
        ]
        public = PublicCase("P1", "现实资格规则未知。")
        initial = initial_modeling(public, staged_llm(payload))
        forbidden = lambda *_args: (_ for _ in ()).throw(AssertionError("unbound aliases must not reach search/evidence"))
        result = run_case(
            public,
            {
                "actions": [{"id": "x", "type": "BINARY"}],
                "objective": {"accepted_units": {"点": 1}, "canonical_unit": "点"},
            },
            PipelineServices(lambda _public: initial, forbidden, forbidden),
        )
        self.assertEqual(result["status"], "ABSTAIN")
        self.assertEqual(result["search"]["search_count"], 0)
        self.assertEqual(
            [gap["proposed_information_target"] for gap in result["state"]["gaps"]],
            ["applicability.time_version", "applicability.object_scope", "applicability.unit_threshold"],
        )
        self.assertTrue(all(gap["target"] is None for gap in result["state"]["gaps"]))

    def test_registered_local_fact_gap_fails_closed_without_search(self) -> None:
        payload = valid_initial_payload()
        payload["audit_summary"]["model_interface_to_grounding_complete"] = False  # type: ignore[index]
        gap = payload["candidate_gaps"][0]  # type: ignore[index]
        gap.update(
            {
                "target": "applicability.OBJECT_SCOPE",
                "gap_route": "LOCAL_FACT",
                "hypothetical_variants": [],
                "first_query": None,
            }
        )
        public = PublicCase("P1", "现实资格规则未知。")
        initial = initial_modeling(public, staged_llm(payload))
        forbidden = lambda *_args: (_ for _ in ()).throw(AssertionError("local unbound gap must not search"))
        result = run_case(
            public,
            {
                "actions": [{"id": "x", "type": "BINARY"}],
                "objective": {"accepted_units": {"点": 1}, "canonical_unit": "点"},
            },
            PipelineServices(lambda _public: initial, forbidden, forbidden),
        )
        state_gap = result["state"]["gaps"][0]
        self.assertEqual(result["status"], "ABSTAIN")
        self.assertEqual(result["search"]["search_count"], 0)
        self.assertIsNone(state_gap["target"])
        self.assertEqual(state_gap["proposed_information_target"], "applicability.object_scope")
        self.assertEqual(state_gap["realized_effect"]["normalization_record"]["original_gap_route"], "LOCAL_FACT")

        for invalid in (
            {"first_query": "本地档案查询"},
            {
                "hypothetical_variants": [
                    {
                        "target": "variable.x",
                        "operation": "SET",
                        "value": {"lb": 0, "ub": 0},
                        "range_basis": "MODEL_BOUNDARY",
                        "basis_quote": None,
                    }
                ]
            },
        ):
            with self.subTest(invalid=invalid):
                candidate = copy.deepcopy(payload)
                candidate["candidate_gaps"][0].update(invalid)  # type: ignore[index]
                with self.assertRaises(ValueError):
                    initial_modeling(public, staged_llm(candidate))

    def test_gap_audit_runtime_enforces_allowed_target_membership(self) -> None:
        for target in ("parameter.invented", "constraint.invented"):
            with self.subTest(target=target):
                payload = valid_initial_payload()
                gap = payload["candidate_gaps"][0]  # type: ignore[index]
                gap["target"] = target
                gap["hypothetical_variants"] = []
                with self.assertRaisesRegex(ValueError, "allowed_gap_targets"):
                    initial_modeling(PublicCase("P1", "现实资格规则未知。"), staged_llm(payload))

        for target in (
            "applicability.Subject_Eligibility",
            "Applicability.SUBJECT_ELIGIBILITY",
            "applicability.SUBJECT_ELIGIBILITY ",
            "applicability.SUBJECT_ELIGIBILITY.extra",
            "applicability.UNKNOWN_DIMENSION",
            "variable.X",
        ):
            with self.subTest(rejected_runtime_alias=target):
                payload = valid_initial_payload()
                payload["audit_summary"]["model_interface_to_grounding_complete"] = False  # type: ignore[index]
                gap = payload["candidate_gaps"][0]  # type: ignore[index]
                gap["target"] = target
                gap["hypothetical_variants"] = []
                gap["gap_route"] = "OUT_OF_SCOPE"
                gap["first_query"] = None
                with self.assertRaises(ValueError):
                    initial_modeling(PublicCase("P1", "现实资格规则未知。"), staged_llm(payload))

        payload = valid_initial_payload()
        payload["model_ir"]["parameters"] = {"threshold": 1}  # type: ignore[index]
        gap = payload["candidate_gaps"][0]  # type: ignore[index]
        gap["target"] = "parameter.threshold"
        gap["hypothetical_variants"] = []
        with self.assertRaisesRegex(ValueError, "parameters=\\{\\}"):
            initial_modeling(PublicCase("P1", "现实资格规则未知。"), staged_llm(payload))

    def test_program_normalizes_authoritative_rule_join_and_residual_closure(self) -> None:
        prompt = """【本 case 权威事实】
甲账户支持非养老金合同；十块债券由互不关联的发行人直接发行，不含基金或合伙企业底层资产。
【随题规则材料】
支持非养老金合同的账户须满足分散要求；各项投资须满足相应上限；养老金合同不进入该测试。
【优化骨架】
选择方案X，入选金额恰好100且无其他资产。合同类型记录在台账中；发行人归属与底层资产记录由账户资产台账给出。
公开 output_schema：{}"""
        model_ir = {
            "variables": [{"id": "x", "type": "BINARY", "lb": 0, "ub": 1}],
            "constraints": [{"name": "balance", "terms": [{"var": "x", "coef": 100}], "sense": "==", "rhs": 100}],
            "objective": {"direction": "max", "terms": [{"var": "x", "coef": 1}], "constant": 0, "unit": "点"},
            "parameters": {},
        }
        rows = [
            {
                "quote": "甲账户支持非养老金合同",
                "or_role": "case attribute",
                "mapped_targets": ["applicability.subject_eligibility", "applicability.object_scope"],
                "usage_status": "APPLICABILITY_USED",
                "reason": "case side",
            },
            {
                "quote": "十块债券由互不关联的发行人直接发行，不含基金或合伙企业底层资产",
                "or_role": "case asset attribute",
                "mapped_targets": ["applicability.object_scope"],
                "usage_status": "APPLICABILITY_USED",
                "reason": "case asset side",
            },
            {
                "quote": "支持非养老金合同的账户须满足分散要求",
                "or_role": "operative rule",
                "mapped_targets": ["applicability.subject_eligibility", "applicability.object_scope", "constraint.balance"],
                "usage_status": "APPLICABILITY_USED",
                "reason": "rule side",
            },
            {
                "quote": "养老金合同不进入该测试",
                "or_role": "exception",
                "mapped_targets": ["applicability.exception_exemption"],
                "usage_status": "APPLICABILITY_USED",
                "reason": "rule exception",
            },
            {
                "quote": "选择方案X",
                "or_role": "decision",
                "mapped_targets": ["variable.x"],
                "usage_status": "MODELED",
                "reason": "action",
            },
            {
                "quote": "入选金额恰好100",
                "or_role": "balance",
                "mapped_targets": ["constraint.balance"],
                "usage_status": "MODELED",
                "reason": "balance",
            },
            {
                "quote": "无其他资产",
                "or_role": "residual closure",
                "mapped_targets": [],
                "usage_status": "UNACCOUNTED",
                "reason": "no separate variable",
            },
            {
                "quote": "合同类型记录在台账中",
                "or_role": "provenance",
                "mapped_targets": [],
                "usage_status": "UNACCOUNTED",
                "reason": "ledger",
            },
            {
                "quote": "发行人归属与底层资产记录由账户资产台账给出",
                "or_role": "asset provenance",
                "mapped_targets": [],
                "usage_status": "UNACCOUNTED",
                "reason": "asset ledger",
            },
        ]
        normalized = _normalize_stage_fact_coverage(prompt, model_ir, rows)
        ledger = next(row for row in normalized if row["quote"] == "合同类型记录在台账中")
        self.assertEqual(ledger["usage_status"], "APPLICABILITY_USED")
        self.assertEqual(ledger["mapped_targets"], ["applicability.subject_eligibility"])
        self.assertIn("PROGRAM_REDUNDANT_PROVENANCE_BOUND", ledger["reason"])
        asset_ledger = next(
            row for row in normalized if row["quote"] == "发行人归属与底层资产记录由账户资产台账给出"
        )
        self.assertEqual(asset_ledger["usage_status"], "APPLICABILITY_USED")
        self.assertEqual(asset_ledger["mapped_targets"], ["applicability.object_scope"])
        self.assertIn("PROGRAM_REDUNDANT_PROVENANCE_BOUND", asset_ledger["reason"])
        residual = next(row for row in normalized if row["quote"] == "无其他资产")
        self.assertEqual(residual["usage_status"], "MODELED")
        self.assertEqual(residual["mapped_targets"], ["constraint.balance"])
        case_row = next(row for row in normalized if row["quote"] == "甲账户支持非养老金合同")
        self.assertIn("PROGRAM_COMPOSED_WITH_IN_PROMPT_RULE", case_row["reason"])
        self.assertEqual(
            [row["quote"] for row in normalized if row["usage_status"] == "UNACCOUNTED"],
            [],
        )

    def test_program_keeps_provenance_open_without_a_verified_case_rule_join(self) -> None:
        model_ir = copy.deepcopy(MODEL_IR)
        ledger_row = {
            "quote": "合同类型记录在保单台账中",
            "or_role": "provenance",
            "mapped_targets": [],
            "usage_status": "UNACCOUNTED",
            "reason": "ledger only",
        }
        concrete_row = {
            "quote": "甲账户支持非养老金合同",
            "or_role": "case attribute",
            "mapped_targets": ["applicability.subject_eligibility"],
            "usage_status": "APPLICABILITY_USED",
            "reason": "case side",
        }
        rule = """【随题规则材料】
支持非养老金合同的账户须满足分散要求。
【优化骨架】"""
        cases = (
            (
                "missing concrete value",
                f"{rule}合同类型记录在保单台账中。公开 output_schema：{{}}",
                [ledger_row],
            ),
            (
                "uncertain concrete value",
                f"甲账户是否支持非养老金合同待核实。{rule}合同类型记录在保单台账中。公开 output_schema：{{}}",
                [
                    {
                        **concrete_row,
                        "quote": "甲账户是否支持非养老金合同待核实",
                    },
                    ledger_row,
                ],
            ),
            (
                "missing rule material",
                "甲账户支持非养老金合同。合同类型记录在保单台账中。公开 output_schema：{}",
                [concrete_row, ledger_row],
            ),
        )
        for label, prompt, rows in cases:
            with self.subTest(label=label):
                normalized = _normalize_stage_fact_coverage(prompt, model_ir, copy.deepcopy(rows))
                ledger = next(row for row in normalized if row["quote"] == ledger_row["quote"])
                self.assertEqual(ledger["usage_status"], "UNACCOUNTED")
                self.assertEqual(ledger["mapped_targets"], [])
                self.assertNotIn("PROGRAM_REDUNDANT_PROVENANCE_BOUND", ledger["reason"])

    def test_program_does_not_compose_plain_attribute_without_rule_material(self) -> None:
        prompt = "甲公司持有许可证。必须选择方案X。公开 output_schema：{}"
        model_ir = {
            "variables": [{"id": "x", "type": "BINARY", "lb": 0, "ub": 1}],
            "constraints": [{"name": "choose", "terms": [{"var": "x", "coef": 1}], "sense": "==", "rhs": 1}],
            "objective": {"direction": "max", "terms": [{"var": "x", "coef": 1}], "constant": 0, "unit": "点"},
            "parameters": {},
        }
        rows = [
            {
                "quote": "甲公司持有许可证",
                "or_role": "attribute and claimed eligibility",
                "mapped_targets": ["variable.x", "applicability.subject_eligibility"],
                "usage_status": "APPLICABILITY_USED",
                "reason": "license",
            },
            {
                "quote": "必须选择方案X",
                "or_role": "selection",
                "mapped_targets": ["variable.x", "constraint.choose"],
                "usage_status": "MODELED",
                "reason": "selection",
            },
        ]
        normalized = _normalize_stage_fact_coverage(prompt, model_ir, rows)
        attribute_rows = [row for row in normalized if row["quote"] == "甲公司持有许可证"]
        self.assertEqual({row["usage_status"] for row in attribute_rows}, {"MODELED", "UNACCOUNTED"})
        modeled = next(row for row in attribute_rows if row["usage_status"] == "MODELED")
        self.assertEqual(modeled["mapped_targets"], ["variable.x"])
        self.assertNotIn("PROGRAM_COMPOSED_WITH_IN_PROMPT_RULE", modeled["reason"])

    def test_archived_invented_shape_remains_rejected(self) -> None:
        bad = valid_initial_payload()
        bad["fact_coverage"] = [
            {"fact_quote": "现实资格规则未知", "usage_status": "UNACCOUNTED", "model_use": "missing"}
        ]
        bad["audit_summary"] = {"information_grounding": [], "overflow_detected": False, "overflow_count": 0}
        bad["self_contained_candidate"] = {
            "selected_actions": [{"action_id": "x"}],
            "objective": {"value": 1, "unit": "点"},
        }
        with self.assertRaises(ValueError):
            initial_modeling(PublicCase("P1", "现实资格规则未知。"), staged_llm(bad))

    def test_json_parser_repairs_only_one_missing_outer_brace(self) -> None:
        complete = json.dumps({"model_ir": MODEL_IR}, ensure_ascii=False)
        self.assertEqual(_extract_json(complete[:-1]), {"model_ir": MODEL_IR})
        with self.assertRaisesRegex(ValueError, "no JSON object"):
            _extract_json('{"model_ir":{"variables":[]')

    def test_eligible_action_ids_pseudo_constraint_is_rejected_at_parse_time(self) -> None:
        bad = valid_initial_payload()
        gap = bad["candidate_gaps"][0]  # type: ignore[index]
        gap["target"] = "constraint.eligibility"  # type: ignore[index]
        gap["hypothetical_variants"] = [  # type: ignore[index]
            {
                "target": "constraint.eligibility",
                "operation": "SET",
                "value": {"eligible_action_ids": ["x"]},
                "range_basis": "MODEL_BOUNDARY",
                "basis_quote": None,
            }
        ]
        with self.assertRaisesRegex(ValueError, "only support variable"):
            parse_initial_decision(bad)


if __name__ == "__main__":
    unittest.main()

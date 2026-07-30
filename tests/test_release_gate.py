from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from audit_duplicates_and_leakage import (  # noqa: E402
    _group_quota_completion_audit,
    _interface_minority_audit,
    audit_records,
    evidence_role_leakage_audit,
    metadata_decoder_audit,
)
from validate_dataset_schema import (  # noqa: E402
    sha256_json,
    validate_decision_certificate,
    validate_evidence_record,
    validate_solver_results,
    validate_source_passport,
    validate_typed_patch,
)


def error_codes(errors):
    return {entry.code for entry in errors}


class EvidenceMetadataContractTests(unittest.TestCase):
    def test_role_bearing_source_kind_is_rejected(self):
        errors = validate_evidence_record(
            {
                "id": "DOC-OPAQUE",
                "source_kind": "distractor",
                "content": "候选规则文本",
                "content_sha256": "0" * 64,
                "source_passport": {},
                "applicability": {"gold_status_exposed": False},
            },
            "evidence",
        )
        self.assertIn("evidence.source_kind_invalid", error_codes(errors))

    def test_periodic_applicable_evidence_position_is_rejected(self):
        evidence = [
            {
                "id": f"DOC-{index:016X}",
                "source_kind": "policy_document",
                "source_passport": {
                    "availability": "candidate-corpus",
                    "version": "v1",
                    "issuer": "issuer",
                },
            }
            for index in range(400)
        ]
        gold = [
            {
                "applicability": {
                    "selected_evidence_id": evidence[index * 4]["id"]
                }
            }
            for index in range(100)
        ]
        result = evidence_role_leakage_audit(evidence, gold)
        self.assertEqual(
            result["row_position_modulo_attack"]["maximum_selected_rate"],
            1.0,
        )
        self.assertFalse(result["passed"])

    def test_snapshot_field_presence_role_leak_is_rejected(self):
        evidence = [
            {
                "id": f"DOC-{index:016X}",
                "source_kind": "policy_document",
                "source_passport": {
                    "availability": "candidate-corpus",
                    "version": "v1",
                    "issuer": "issuer",
                },
                **({"snapshot_ref": f"SNAP-{index}"} if index % 4 == 0 else {}),
            }
            for index in range(400)
        ]
        gold = [
            {
                "applicability": {
                    "selected_evidence_id": evidence[index * 4]["id"]
                }
            }
            for index in range(100)
        ]
        result = evidence_role_leakage_audit(evidence, gold)
        self.assertEqual(
            result["structural_signature_attack"]["maximum_selected_rate"],
            1.0,
        )
        self.assertFalse(result["passed"])

    def test_content_length_role_leak_is_rejected(self):
        evidence = [
            {
                "id": f"DOC-{index:016X}",
                "source_kind": "policy_document",
                "content": ("适用规则正文" * 20 if index % 4 == 0 else "候选正文"),
            }
            for index in range(400)
        ]
        gold = [
            {
                "applicability": {
                    "selected_evidence_id": evidence[index * 4]["id"]
                }
            }
            for index in range(100)
        ]
        result = evidence_role_leakage_audit(evidence, gold)
        self.assertEqual(
            result["surface_length_attack"]["maximum_selected_rate"],
            1.0,
        )
        self.assertFalse(result["passed"])


def valid_certificate(
    *,
    base_actions=None,
    patched_actions=None,
    base_objective=None,
    patched_objective=None,
):
    objective = sha256_json({"sense": "min", "objective": {"terms": {"x": 1}}})
    base_actions = [[1, 0], [0, 1]] if base_actions is None else base_actions
    patched_actions = [[1, 1]] if patched_actions is None else patched_actions
    base_objective = objective if base_objective is None else base_objective
    patched_objective = objective if patched_objective is None else patched_objective
    base_set = {str(action) for action in base_actions}
    intersection = [
        action for action in patched_actions if str(action) in base_set
    ]
    return {
        "certificate_method": "complete_binary_enumeration",
        "complete_action_sets": True,
        "multiple_optima_handling": "full_action_set",
        "base_acceptable_actions": base_actions,
        "patched_acceptable_actions": patched_actions,
        "intersection": intersection,
        "intersection_empty": not intersection,
        "base_world": {
            "base_id": "BASE-001",
            "objective_fingerprint": base_objective,
        },
        "patched_world": {
            "base_id": "BASE-001",
            "objective_fingerprint": patched_objective,
        },
        "passed": not intersection,
    }


def solver_result(action, objective=1.0, *, solver="gurobi", assignment=None):
    return {
        "solver": solver,
        "version": "test-1.0",
        "status": "OPTIMAL",
        "objective": objective,
        "projected_action": action,
        "assignment": {} if assignment is None else assignment,
        "max_constraint_violation": 0.0,
        "integrality_violation": 0.0,
        "bound_violation": 0.0,
    }


def certified_world(actions, *, objective=1.0, gurobi_action=None, copt_action=None):
    gurobi_action = actions[0] if gurobi_action is None else gurobi_action
    copt_action = actions[0] if copt_action is None else copt_action
    return {
        "exact_enumeration": {
            "status": "OPTIMAL",
            "objective": objective,
            "optimal_actions": actions,
            "complete": True,
        },
        "gurobi": solver_result(gurobi_action, objective, solver="gurobi"),
        "copt": solver_result(copt_action, objective, solver="copt"),
        "checks": {
            "all_optimal": True,
            "objectives_agree": True,
            "solver_actions_in_exact_set": True,
            "residuals_pass": True,
            "integrality_pass": True,
            "passed": True,
        },
    }


def valid_passport_and_applicability():
    passport = {
        "source_id": "SRC-001",
        "publisher": "Authority",
        "title": "Applicable policy",
        "document_type": "policy",
        "source_uri": "https://authority.example/policy/1",
        "jurisdiction": "CN-SH",
        "entity_scope": "hospital-A",
        "version": "2026.1",
        "effective_from": "2026-01-01",
        "effective_to": "2026-12-31",
        "retrieved_at": "2026-07-29T10:00:00+08:00",
        "content_sha256": "1" * 64,
        "authoritative": True,
        "superseded_by": None,
    }
    applicability = {
        "verdict": "applicable",
        "required_jurisdiction": "CN-SH",
        "required_entity_scope": "hospital-A",
        "decision_time": "2026-07-15",
        "jurisdiction_match": True,
        "entity_match": True,
        "version_current": True,
        "effective_at_decision_time": True,
        "exception_checked": True,
        "rationale": "The jurisdiction, entity and effective period all match.",
    }
    return passport, applicability


class DecisionCertificateTests(unittest.TestCase):
    def test_same_objective_disjoint_complete_action_sets_are_retained(self):
        certificate = valid_certificate()
        objective = certificate["base_world"]["objective_fingerprint"]

        errors = validate_decision_certificate(
            certificate,
            "gold.decision_certificate",
            base_id="BASE-001",
            objective_fingerprint=objective,
        )

        self.assertEqual(errors, [])

    def test_different_objectives_with_common_action_are_rejected(self):
        certificate = valid_certificate(
            base_actions=[[1, 0], [0, 1]],
            patched_actions=[[1, 0], [1, 1]],
            patched_objective="2" * 64,
        )

        errors = validate_decision_certificate(
            certificate,
            "gold.decision_certificate",
            base_id="BASE-001",
            objective_fingerprint=certificate["base_world"][
                "objective_fingerprint"
            ],
        )

        codes = error_codes(errors)
        self.assertIn("certificate.intersection_nonempty", codes)
        self.assertIn("certificate.cross_world_objective_mismatch", codes)

    def test_compact_world_certificate_recomputes_empty_intersection(self):
        objective = "a" * 64
        certificate = {
            "method": "complete_binary_enumeration",
            "worlds": {
                "base": {
                    "action_set_complete": True,
                    "objective_fingerprint": objective,
                    "optimal_actions": [[1, 0], [0, 1]],
                },
                "patched": {
                    "action_set_complete": True,
                    "objective_fingerprint": objective,
                    "optimal_actions": [[1, 1]],
                },
            },
            "intersection": [],
            "intersection_empty": True,
            "passed": True,
        }

        errors = validate_decision_certificate(
            certificate,
            "gold.decision_certificate",
            base_id="BASE-001",
            objective_fingerprint=objective,
        )

        self.assertEqual(errors, [])

    def test_incumbent_only_multiple_optima_comparison_is_rejected(self):
        incumbent_only = {
            "base": {
                "gurobi": solver_result([1, 0]),
                "copt": solver_result([0, 1]),
                "checks": {
                    "all_optimal": True,
                    "objectives_agree": True,
                    "solver_actions_in_exact_set": True,
                    "residuals_pass": True,
                    "integrality_pass": True,
                    "passed": True,
                },
            },
            "patched": {
                "gurobi": solver_result([1, 1]),
                "copt": solver_result([1, 1]),
                "checks": {
                    "all_optimal": True,
                    "objectives_agree": True,
                    "solver_actions_in_exact_set": True,
                    "residuals_pass": True,
                    "integrality_pass": True,
                    "passed": True,
                },
            },
        }

        _, errors = validate_solver_results(
            incumbent_only, "gold.solver_results", tolerance=1e-6
        )

        self.assertIn("solver.exact_missing", error_codes(errors))


class PatchTests(unittest.TestCase):
    def test_pure_numeric_patch_is_rejected(self):
        before = {"objective": {"terms": {"x": 10}}}
        after = {"objective": {"terms": {"x": 12}}}
        patch = {
            "patch_class": "quota_risk_service_objective",
            "claim_id": "CLAIM-001",
            "model_slot": "constraints.quota.rhs",
            "operation": "change_quota",
            "before": before,
            "after": after,
            "before_hash": sha256_json(before),
            "after_hash": sha256_json(after),
            "base_model_hash": "3" * 64,
            "patched_model_hash": "4" * 64,
            "structural": True,
        }

        errors = validate_typed_patch(
            patch,
            "gold.typed_patch",
            expected_patch_class="quota_risk_service_objective",
        )

        self.assertIn("patch.numeric_only", error_codes(errors))

    def test_compact_typed_op_numeric_literal_only_is_rejected(self):
        patch = {
            "ops": [
                {
                    "op": "modify",
                    "slot_type": "constraint",
                    "evidence_claim_id": "CLAIM-001",
                    "model_slot_id": "constraints/quota/rhs",
                    "code_region_id": "patched_ir.json#/constraints/2",
                    "before_expression": "quota_rhs = 10",
                    "after_expression": "quota_rhs = 12",
                }
            ],
            "minimality_check": "single directly bound operation",
            "pure_numeric_parameter_fill": False,
            "structural": True,
            "base_model_hash": "3" * 64,
            "patched_model_hash": "4" * 64,
        }

        errors = validate_typed_patch(
            patch,
            "gold.typed_patch",
            expected_patch_class="quota_risk_service_objective",
        )

        self.assertIn("patch.numeric_only", error_codes(errors))


class ApplicabilityTests(unittest.TestCase):
    def test_wrong_jurisdiction_is_rejected(self):
        passport, applicability = valid_passport_and_applicability()
        passport["jurisdiction"] = "CN-BJ"

        errors = validate_source_passport(
            passport,
            applicability,
            "gold.source_passport",
            evidence_mode="real-web",
        )

        self.assertIn("source.wrong_jurisdiction", error_codes(errors))

    def test_old_version_is_rejected(self):
        passport, applicability = valid_passport_and_applicability()
        passport["effective_to"] = "2026-06-30"
        applicability["version_current"] = False
        applicability["effective_at_decision_time"] = False

        errors = validate_source_passport(
            passport,
            applicability,
            "gold.source_passport",
            evidence_mode="real-web",
        )

        codes = error_codes(errors)
        self.assertIn("source.old_version", codes)
        self.assertIn("source.version_current_false", codes)


class SolverTests(unittest.TestCase):
    def test_solver_objective_and_action_disagreement_is_rejected(self):
        base = certified_world([[1, 0], [0, 1]])
        base["copt"] = solver_result([1, 1], objective=1.25)
        patched = certified_world([[1, 1]], objective=2.0)

        _, errors = validate_solver_results(
            {"base": base, "patched": patched},
            "gold.solver_results",
            tolerance=1e-6,
        )

        codes = error_codes(errors)
        self.assertIn("solver.objective_disagreement", codes)
        self.assertIn("solver.action_disagreement", codes)
        self.assertIn("solver.cross_backend_objective_disagreement", codes)

    def test_forged_complete_flag_is_rejected_by_independent_enumeration(self):
        ir = {
            "task_id": "SWOR-001",
            "base_id": "BASE-001",
            "world": "base",
            "sense": "min",
            "objective": {"constant": 0, "terms": {"x": 0, "y": 0}},
            "variables": [
                {"name": "x", "vartype": "B", "lb": 0, "ub": 1},
                {"name": "y", "vartype": "B", "lb": 0, "ub": 1},
            ],
            "constraints": [
                {"name": "choose_one", "terms": {"x": 1, "y": 1}, "sense": "==", "rhs": 1}
            ],
            "action_projection": ["x", "y"],
        }
        forged_world = {
            "exact_enumeration": {
                "status": "OPTIMAL",
                "objective": 0.0,
                "optimal_actions": [[1, 0]],
                "complete": True,
            },
            "gurobi": solver_result(
                [1, 0],
                0.0,
                solver="gurobi",
                assignment={"x": 1.0, "y": 0.0},
            ),
            "copt": solver_result(
                [1, 0],
                0.0,
                solver="copt",
                assignment={"x": 1.0, "y": 0.0},
            ),
            "checks": {
                "all_optimal": True,
                "objectives_agree": True,
                "solver_actions_in_exact_set": True,
                "residuals_pass": True,
                "integrality_pass": True,
                "passed": True,
            },
        }

        _, errors = validate_solver_results(
            {"base": forged_world, "patched": forged_world},
            "gold.solver_results",
            tolerance=1e-6,
            model_irs={"base": ir, "patched": {**ir, "world": "patched"}},
        )

        self.assertIn("solver.exact_action_set_disagreement", error_codes(errors))


class DuplicateLeakageTests(unittest.TestCase):
    def test_normalized_duplicate_and_private_key_leak_are_rejected(self):
        tasks = [
            {
                "id": "SWOR-001",
                "base_id": "BASE-001",
                "problem_zh": "Ａ 任务  文本",
                "answer": 1,
            },
            {
                "id": "SWOR-002",
                "base_id": "BASE-002",
                "problem_zh": "a 任务 文本",
            },
        ]

        report = audit_records(tasks, [], [])

        codes = error_codes(report.errors)
        self.assertIn("duplicate.problem_text", codes)
        self.assertIn("leakage.private_key_in_public", codes)

    def test_patch_class_decodable_from_public_id_is_rejected(self):
        labels = [
            "eligibility_domain",
            "temporal_coupling",
            "conditional_auxiliary",
            "quota_risk_service_objective",
        ]
        tasks = []
        gold = []
        for index in range(100):
            task_id = f"SWOR{index + 1:03d}"
            tasks.append(
                {
                    "id": task_id,
                    "problem_zh": f"唯一公开问题文本 {index}",
                    "decision_time": "2026-01-01",
                    "entity": f"主体 {index}",
                    "jurisdiction": "测试辖区",
                    "allowed_retrieval_interfaces": ["semantic_search"],
                }
            )
            gold.append(
                {
                    "id": task_id,
                    "base_id": f"BASE-{index:03d}",
                    "patch_class": labels[index % 4],
                }
            )

        report = audit_records(tasks, [], gold)

        self.assertIn(
            "leakage.metadata_decoder_above_random",
            error_codes(report.errors),
        )

    def test_patch_class_decodable_from_release_row_is_rejected(self):
        labels = [
            "eligibility_domain",
            "temporal_coupling",
            "conditional_auxiliary",
            "quota_risk_service_objective",
        ]
        tasks = []
        gold = []
        for index in range(100):
            task_id = f"SWOR{((index * 53 + 17) % 100) + 1:03d}"
            tasks.append(
                {
                    "id": task_id,
                    "problem_zh": f"独立公开问题文本 {index}",
                    "decision_time": "2026-01-01",
                    "entity": f"主体 {((index * 29) % 100):03d}",
                    "jurisdiction": "测试辖区",
                    "allowed_retrieval_interfaces": ["semantic_search"],
                }
            )
            gold.append(
                {
                    "id": task_id,
                    "base_id": f"BASE-{index:03d}",
                    "patch_class": labels[index % 4],
                }
            )

        decoder = metadata_decoder_audit(tasks, gold)

        self.assertEqual(decoder["attacks"]["release_row_mod_4"], 1.0)
        self.assertEqual(
            decoder["robustness"]["leave_one_out_majority"]["attacks"][
                "release_row_mod_4"
            ],
            1.0,
        )
        self.assertFalse(decoder["passed"])

    def test_repeated_public_group_quota_is_rejected(self):
        labels = [
            "eligibility_domain",
            "temporal_coupling",
            "conditional_auxiliary",
            "quota_risk_service_objective",
        ]
        rows = []
        for group_index in range(10):
            for label in labels:
                for repetition in range(2):
                    rows.append(
                        (
                            f"T-{group_index}-{label}-{repetition}",
                            label,
                            {
                                "retrieval_interface": "private",
                                "entity_prefix": f"group-{group_index}",
                            },
                        )
                    )

        result = _group_quota_completion_audit(rows)

        self.assertEqual(result["leave_one_out_accuracy"], 1.0)
        self.assertGreaterEqual(result["maximum_gated_accuracy"], 0.35)

    def test_interface_level_balanced_quota_is_rejected(self):
        labels = [
            "eligibility_domain",
            "temporal_coupling",
            "conditional_auxiliary",
            "quota_risk_service_objective",
        ]
        rows = []
        for index in range(100):
            interface = "private" if index < 80 else "web"
            rows.append(
                (
                    f"SWOR{index + 1:03d}",
                    labels[index % 4],
                    {
                        "retrieval_interface": interface,
                        "entity_prefix": f"group-{index // 10}",
                    },
                )
            )

        result = _interface_minority_audit(rows)

        self.assertEqual(result["leave_one_out_accuracy"], 1.0)
        self.assertGreaterEqual(result["maximum_gated_accuracy"], 0.35)

    def test_redacted_private_policy_template_reuse_is_rejected(self):
        tasks = [
            {
                "id": "SWOR001",
                "problem_zh": "主体甲在辖区甲完成唯一任务。",
                "entity": "主体甲",
                "jurisdiction": "辖区甲",
                "decision_time": "2026-01-01",
            },
            {
                "id": "SWOR002",
                "problem_zh": "主体乙在辖区乙处理另一项业务。",
                "entity": "主体乙",
                "jurisdiction": "辖区乙",
                "decision_time": "2026-02-02",
            },
        ]
        gold = [
            {
                "id": "SWOR001",
                "base_id": "BASE-001",
                "evidence_mode": "fresh-private",
                "evidence_ids": ["DOC-1"],
                "claim_to_model_mapping": [{"claim_zh": "动作甲不得采用。"}],
            },
            {
                "id": "SWOR002",
                "base_id": "BASE-002",
                "evidence_mode": "fresh-private",
                "evidence_ids": ["DOC-2"],
                "claim_to_model_mapping": [{"claim_zh": "动作乙不得采用。"}],
            },
        ]
        evidence = [
            {
                "id": "DOC-1",
                "content": "主体甲 辖区甲 2026-01-01 第一条范围。动作甲不得采用。第五条留痕。",
                "source_passport": {},
            },
            {
                "id": "DOC-2",
                "content": "主体乙 辖区乙 2026-02-02 第一条范围。动作乙不得采用。第五条留痕。",
                "source_passport": {},
            },
        ]

        report = audit_records(tasks, evidence, gold)

        self.assertIn(
            "duplicate.private_document_template",
            error_codes(report.errors),
        )


if __name__ == "__main__":
    unittest.main()

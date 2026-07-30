from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from audit_structure_and_provenance import (  # noqa: E402
    audit_public_base_binding,
    audit_structure_records,
    canonical_structural_fingerprint,
    structurally_isomorphic,
)


def error_codes(report):
    return {entry.code for entry in report.errors}


def compact_ir(*, renamed=False, coefficient=1, sense="==", with_aux=False):
    x_name = "decision_alpha" if renamed else "x"
    y_name = "decision_beta" if renamed else "y"
    variables = [
        {"name": x_name, "vartype": "B", "lb": 0, "ub": 1},
        {"name": y_name, "vartype": "B", "lb": 0, "ub": 1},
    ]
    if with_aux:
        variables.append({"name": "z", "vartype": "B", "lb": 0, "ub": 1})
    constraints = [
        {
            "name": "renamed_constraint" if renamed else "choose",
            "terms": {x_name: coefficient, y_name: coefficient},
            "sense": sense,
            "rhs": 1,
        }
    ]
    if renamed:
        variables.reverse()
        constraints.reverse()
    return {
        "sense": "max",
        "variables": variables,
        "constraints": constraints,
        "objective": {
            "terms": {x_name: 9 * coefficient, y_name: 2 * coefficient},
            "constant": 0,
        },
        "action_projection": [x_name, y_name],
    }


def gold_row(task_id, family="routing_transport"):
    return {
        "id": task_id,
        "family": family,
        "action_projection": {"variables": ["x", "y"]},
        "base_audit": {
            "base_kind": "source_native",
            "status": "unchanged_pass",
            "source_dataset": "SOURCE",
            "source_id": task_id,
            "source_problem_sha256": "a" * 64,
        },
    }


def staged(task_id, status="unchanged_pass"):
    return {
        "source_dataset": "SOURCE",
        "source_id": task_id,
        "source_hash": "a" * 64,
        "status": status,
    }


class StructuralFingerprintTests(unittest.TestCase):
    def test_renaming_reordering_and_coefficient_magnitude_do_not_change_fingerprint(self):
        original = compact_ir(coefficient=1)
        renamed = compact_ir(renamed=True, coefficient=7)

        self.assertEqual(
            canonical_structural_fingerprint(original),
            canonical_structural_fingerprint(renamed),
        )
        self.assertTrue(structurally_isomorphic(original, renamed))

    def test_sign_sense_and_action_aux_role_are_retained(self):
        original = compact_ir()
        negative = compact_ir(coefficient=-1)
        other_sense = compact_ir(sense="<=")
        auxiliary = compact_ir()
        auxiliary["action_projection"] = ["x"]

        for changed in (negative, other_sense, auxiliary):
            self.assertNotEqual(
                canonical_structural_fingerprint(original),
                canonical_structural_fingerprint(changed),
            )
            self.assertFalse(structurally_isomorphic(original, changed))

    def test_all_dataset_and_within_family_template_collisions_are_rejected(self):
        first = gold_row("SWOR001")
        second = gold_row("SWOR002")
        models = {
            "SWOR001": {"base": compact_ir(), "patched": compact_ir()},
            "SWOR002": {
                "base": compact_ir(renamed=True, coefficient=5),
                "patched": compact_ir(renamed=True, coefficient=5),
            },
        }
        second["action_projection"] = {
            "variables": ["decision_alpha", "decision_beta"]
        }

        report = audit_structure_records(
            [first, second],
            [staged("SWOR001"), staged("SWOR002")],
            models,
        )

        codes = error_codes(report)
        self.assertIn("structure.template_collision_all", codes)
        self.assertIn("structure.template_collision_family", codes)
        self.assertEqual(len(report.stats["all_collision_groups"]), 1)


class ProvenanceTests(unittest.TestCase):
    def test_pending_source_certification_is_release_blocking(self):
        row = gold_row("SWOR001")
        row["base_audit"]["status"] = "pending_source_certification"

        report = audit_structure_records(
            [row],
            [staged("SWOR001", "selected_for_manual_review")],
            {"SWOR001": {"base": compact_ir(), "patched": compact_ir()}},
        )

        self.assertIn("provenance.base_not_certified", error_codes(report))

    def test_new_compact_adaptation_cannot_be_unchanged(self):
        row = gold_row("SWOR001")
        row["base_audit"]["base_kind"] = "new_compact_adaptation"

        report = audit_structure_records(
            [row],
            [staged("SWOR001")],
            {"SWOR001": {"base": compact_ir(), "patched": compact_ir()}},
        )

        self.assertIn(
            "provenance.adaptation_cannot_be_unchanged", error_codes(report)
        )

    def test_staging_manual_review_cannot_back_source_certification(self):
        row = gold_row("SWOR001")

        report = audit_structure_records(
            [row],
            [staged("SWOR001", "selected_for_manual_review")],
            {"SWOR001": {"base": compact_ir(), "patched": compact_ir()}},
        )

        self.assertIn("provenance.staging_still_manual_review", error_codes(report))


class ProjectionAndEnumerationTests(unittest.TestCase):
    def test_projection_order_must_match_across_worlds_and_gold(self):
        row = gold_row("SWOR001")
        patched = compact_ir()
        patched["action_projection"] = ["y", "x"]

        report = audit_structure_records(
            [row],
            [staged("SWOR001")],
            {"SWOR001": {"base": compact_ir(), "patched": patched}},
        )

        self.assertIn("structure.projection_changed", error_codes(report))

    def test_patch_only_auxiliary_must_not_enter_projection(self):
        row = gold_row("SWOR001")
        patched = compact_ir(with_aux=True)
        patched["action_projection"].append("z")

        report = audit_structure_records(
            [row],
            [staged("SWOR001")],
            {"SWOR001": {"base": compact_ir(), "patched": patched}},
        )

        self.assertIn("structure.patch_aux_in_projection", error_codes(report))

    def test_exact_enumeration_rejects_more_than_twenty_or_nonbinary_variables(self):
        row = gold_row("SWOR001")
        too_large = compact_ir()
        too_large["variables"] = [
            {"name": f"x_{index}", "vartype": "B", "lb": 0, "ub": 1}
            for index in range(21)
        ]
        too_large["constraints"] = []
        too_large["objective"] = {
            "terms": {f"x_{index}": 1 for index in range(21)},
            "constant": 0,
        }
        too_large["action_projection"] = [f"x_{index}" for index in range(21)]
        nonbinary = deepcopy(too_large)
        nonbinary["variables"] = nonbinary["variables"][:2]
        nonbinary["variables"][0]["vartype"] = "I"
        nonbinary["objective"]["terms"] = {"x_0": 1, "x_1": 1}
        nonbinary["action_projection"] = ["x_0", "x_1"]

        report = audit_structure_records(
            [row],
            [staged("SWOR001")],
            {"SWOR001": {"base": too_large, "patched": nonbinary}},
        )

        codes = error_codes(report)
        self.assertIn("structure.enum_limit_exceeded", codes)
        self.assertIn("structure.enum_nonbinary", codes)


class PublicBaseBindingTests(unittest.TestCase):
    def binding_fixture(self):
        problem = (
            "候选如下：\n"
            "- 方案A：收益 9，占用资源 2。\n"
            "- 方案B：收益 2，占用资源 3。\n"
            "基础模型的业务约束为：\n"
            "- 方案A、方案B中恰好选择一个。\n"
            "- 资源占用为方案A=2、方案B=3；总占用不超过3。"
        )
        public = [{"id": "SWOR001", "problem_zh": problem}]
        gold = [
            {
                "id": "SWOR001",
                "base_audit": {
                    "public_problem_sha256": __import__("hashlib")
                    .sha256(problem.encode("utf-8"))
                    .hexdigest()
                },
            }
        ]
        base = {
            "variables": [
                {"name": "x", "semantic_name": "方案A"},
                {"name": "y", "semantic_name": "方案B"},
            ],
            "objective": {"terms": {"x": 9, "y": 2}},
            "constraints": [
                {
                    "name": "choose",
                    "source": "public_problem",
                    "terms": {"x": 1, "y": 1},
                    "requirement_zh": "方案A、方案B中恰好选择一个",
                },
                {
                    "name": "capacity",
                    "source": "public_problem",
                    "terms": {"x": 2, "y": 3},
                    "requirement_zh": "资源占用为方案A=2、方案B=3；总占用不超过3",
                },
            ],
            "action_projection": ["x", "y"],
        }
        return public, gold, {"SWOR001": {"base": base}}

    def test_complete_public_binding_passes(self):
        public, gold, models = self.binding_fixture()
        self.assertEqual(audit_public_base_binding(public, gold, models), [])

    def test_diversified_public_prose_still_binds_coefficients_and_requirements(self):
        public, gold, models = self.binding_fixture()
        problem = public[0]["problem_zh"]
        problem = problem.replace("- 方案A：收益 9", "- 方案A：可贡献 9 点收益")
        problem = problem.replace(
            "- 方案A、方案B中恰好选择一个。",
            "- 基础约束：方案A、方案B中恰好选择一个。",
        )
        public[0]["problem_zh"] = problem
        gold[0]["base_audit"]["public_problem_sha256"] = __import__(
            "hashlib"
        ).sha256(problem.encode("utf-8")).hexdigest()

        self.assertEqual(audit_public_base_binding(public, gold, models), [])

    def test_hidden_constraint_scope_is_rejected(self):
        public, gold, models = self.binding_fixture()
        requirement = "至少选择一个候选"
        models["SWOR001"]["base"]["constraints"][0]["terms"] = {"x": 1}
        models["SWOR001"]["base"]["constraints"][0][
            "requirement_zh"
        ] = requirement
        public[0]["problem_zh"] = public[0]["problem_zh"].replace(
            "方案A、方案B中恰好选择一个", requirement
        )
        gold[0]["base_audit"]["public_problem_sha256"] = __import__(
            "hashlib"
        ).sha256(public[0]["problem_zh"].encode("utf-8")).hexdigest()

        errors = audit_public_base_binding(public, gold, models)

        self.assertIn(
            "base_binding.constraint_scope_hidden",
            {entry.code for entry in errors},
        )

    def test_hidden_weight_is_rejected(self):
        public, gold, models = self.binding_fixture()
        models["SWOR001"]["base"]["constraints"][1][
            "requirement_zh"
        ] = "资源总占用不超过3"
        public[0]["problem_zh"] = public[0]["problem_zh"].replace(
            "资源占用为方案A=2、方案B=3；总占用不超过3",
            "资源总占用不超过3",
        )
        gold[0]["base_audit"]["public_problem_sha256"] = __import__(
            "hashlib"
        ).sha256(public[0]["problem_zh"].encode("utf-8")).hexdigest()

        errors = audit_public_base_binding(public, gold, models)

        self.assertIn(
            "base_binding.weight_hidden",
            {entry.code for entry in errors},
        )


if __name__ == "__main__":
    unittest.main()

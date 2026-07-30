"""Regression checks for the strict OptMinerBench provenance certification."""

from __future__ import annotations

import hashlib
import json
import math
import unittest
from pathlib import Path


DATASET_ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = DATASET_ROOT / "audits" / "optminer_source_certification.jsonl"
SUMMARY_PATH = (
    DATASET_ROOT / "audits" / "optminer_source_certification_summary.json"
)


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class OptMinerSourceCertificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = read_jsonl(AUDIT_PATH)
        cls.summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))

    def test_frozen_counts_and_unique_ids(self) -> None:
        self.assertEqual(len(self.rows), 57)
        self.assertEqual(len({row["source_id"] for row in self.rows}), 57)
        self.assertEqual(self.summary["status_counts"], {"certified": 30, "failed": 27})
        self.assertEqual(
            self.summary["actual_linearity_counts"],
            {
                "linear_or_mixed_integer_linear": 43,
                "not_linear_milp": 14,
            },
        )
        self.assertFalse(self.summary["passed"])

    def test_legacy_answer_never_enters_audit_or_gold(self) -> None:
        for row in self.rows:
            self.assertEqual(row["legacy_answer_policy"], "not_read_not_gold")
            self.assertNotIn("answer", row)
            self.assertNotIn("legacy_answer", row)

    def test_certified_rows_have_two_optimal_solvers(self) -> None:
        certified = [row for row in self.rows if row["status"] == "certified"]
        self.assertEqual(len(certified), 30)
        for row in certified:
            self.assertEqual(
                row["actual_linearity"]["status"],
                "linear_or_mixed_integer_linear",
            )
            gurobi = row["solver_results"]["gurobi"]
            copt = row["solver_results"]["copt"]
            self.assertEqual(gurobi["status"], "OPTIMAL")
            self.assertEqual(copt["status"], "OPTIMAL")
            self.assertTrue(
                math.isclose(
                    float(gurobi["objective"]),
                    float(copt["objective"]),
                    rel_tol=1e-7,
                    abs_tol=1e-6,
                )
            )
            self.assertTrue(row["solver_checks"]["passed"])

    def test_failed_rows_are_explicitly_explained(self) -> None:
        failed = [row for row in self.rows if row["status"] == "failed"]
        self.assertEqual(len(failed), 27)
        for row in failed:
            self.assertTrue(row["reason"])
            self.assertIn(
                row["actual_linearity"]["status"],
                {"linear_or_mixed_integer_linear", "not_linear_milp"},
            )
            self.assertIn("solver_results", row)

        license_failures = [
            row for row in failed if row["reason"] == "gurobi_license_size_limit"
        ]
        self.assertEqual(len(license_failures), 13)
        for row in license_failures:
            self.assertEqual(row["solver_results"]["gurobi"]["status"], "LICENSE_SIZE_LIMIT")
            self.assertEqual(row["solver_results"]["copt"]["status"], "OPTIMAL")

        nonlinear_failures = [
            row
            for row in failed
            if row["actual_linearity"]["status"] == "not_linear_milp"
        ]
        self.assertEqual(len(nonlinear_failures), 14)
        for row in nonlinear_failures:
            self.assertTrue(
                row["reason"].startswith(
                    "nonlinear_or_nonlinearizable_structure:"
                )
            )
            self.assertIsNotNone(
                row["solver_results"]["legacy_gurobi_execution"]
            )
            self.assertEqual(
                row["solver_results"]["copt_rebuild"]["status"],
                "NOT_ATTEMPTED_IR_EXPORT_FAILED",
            )

    def test_ir_certificate_hashes_and_risk_fields(self) -> None:
        for row in self.rows:
            self.assertIn("source_family_suggestion", row)
            self.assertEqual(
                row["problem_to_ir_semantic_risk"]["status"],
                "not_semantically_certified",
            )
            self.assertTrue(
                row["problem_to_ir_semantic_risk"][
                    "required_next_gate"
                ].startswith("two_blind_reviewers")
            )
            if "ir_path" not in row:
                continue
            ir_path = DATASET_ROOT / row["ir_path"]
            certificate_path = DATASET_ROOT / row["certificate_path"]
            self.assertTrue(ir_path.is_file())
            self.assertTrue(certificate_path.is_file())
            self.assertEqual(sha256(ir_path), row["ir_sha256"])
            self.assertEqual(
                sha256(certificate_path), row["certificate_sha256"]
            )


if __name__ == "__main__":
    unittest.main()

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from solver_backend import certify_world_pair, enumerate_optimal_actions, project_action


class SolverBackendTest(unittest.TestCase):
    def base_ir(self):
        return {
            "model_id": "fixture",
            "sense": "max",
            "variables": [
                {"name": "x0", "vartype": "B", "lb": 0, "ub": 1},
                {"name": "x1", "vartype": "B", "lb": 0, "ub": 1},
                {"name": "x2", "vartype": "B", "lb": 0, "ub": 1},
            ],
            "objective": {"constant": 0, "terms": {"x0": 3, "x1": 2, "x2": 1}},
            "constraints": [
                {
                    "name": "choose_one",
                    "sense": "==",
                    "rhs": 1,
                    "terms": {"x0": 1, "x1": 1, "x2": 1},
                }
            ],
            "action_projection": ["x0", "x1", "x2"],
        }

    def test_complete_enumeration(self):
        result = enumerate_optimal_actions(self.base_ir())
        self.assertEqual(result["optimal_actions"], [[1, 0, 0]])
        self.assertTrue(result["complete"])

    def test_pair_certificate(self):
        base = self.base_ir()
        patched = self.base_ir()
        patched["model_id"] = "fixture_patched"
        patched["variables"][0]["ub"] = 0
        certificate = certify_world_pair(base, patched)
        self.assertTrue(certificate["passed"])
        self.assertTrue(certificate["intersection_empty"])

    def test_projection_preserves_continuous_values(self):
        ir = self.base_ir()
        ir["variables"] = [
            {"name": "integer_action", "vartype": "I", "lb": 0, "ub": 10},
            {"name": "continuous_action", "vartype": "C", "lb": 0, "ub": 10},
        ]
        ir["action_projection"] = ["integer_action", "continuous_action"]

        projected = project_action(
            ir, {"integer_action": 2.0, "continuous_action": 2.75}
        )

        self.assertEqual(projected, (2, 2.75))


if __name__ == "__main__":
    unittest.main()

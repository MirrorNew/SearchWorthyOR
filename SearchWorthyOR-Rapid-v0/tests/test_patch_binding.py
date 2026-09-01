from __future__ import annotations

import copy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_batch import patch_delta_targets


def _model() -> dict:
    return {
        "variables": [{"name": "x", "type": "BINARY", "lb": 0, "ub": 1}],
        "objective": {"sense": "min", "constant": 0, "coefficients": {"x": 1}, "meaning": "cost"},
        "constraints": [{"name": "base_cap", "sense": "<=", "rhs": 1, "coefficients": {"x": 1}}],
    }


def test_patch_bindings_can_only_point_to_actual_model_deltas() -> None:
    base = _model()
    patched = copy.deepcopy(base)
    patched["constraints"].append({"name": "rule_gate", "sense": "=", "rhs": 0, "coefficients": {"x": 1}})
    assert patch_delta_targets(base, patched) == {"constraint:rule_gate"}
    assert "constraint:base_cap" not in patch_delta_targets(base, patched)

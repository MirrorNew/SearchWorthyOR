from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from solve_model_pair import evaluate, load_model, redundant_constraints


def _model(variant: str, extra_constraints: list[dict]) -> dict:
    return {
        "schema_version": "searchworthyor.rapid_model_ir.v0",
        "id": "SWOR-R999",
        "variant": variant,
        "family": "production_capacity",
        "source_candidate_id": "fixture",
        "variables": [
            {"name": "x_a", "type": "BINARY", "lb": 0, "ub": 1, "meaning": "A"},
            {"name": "x_b", "type": "BINARY", "lb": 0, "ub": 1, "meaning": "B"},
        ],
        "objective": {
            "sense": "min", "constant": 0, "coefficients": {"x_a": 1, "x_b": 2},
            "meaning": "cost", "unit": "unit",
        },
        "constraints": [
            {"name": "choose", "sense": ">=", "rhs": 1, "coefficients": {"x_a": 1, "x_b": 1}, "meaning": "choose"},
            *extra_constraints,
        ],
        "action_projection": ["x_a", "x_b"],
    }


def test_solver_and_complete_action_intersection(tmp_path: Path) -> None:
    import json

    base = tmp_path / "base.json"
    patched = tmp_path / "patched.json"
    base.write_text(json.dumps(_model("base", [])), encoding="utf-8")
    patched.write_text(
        json.dumps(
            _model(
                "patched",
                [{"name": "forbid_a", "sense": "=", "rhs": 0, "coefficients": {"x_a": 1}, "meaning": "rule"}],
            )
        ),
        encoding="utf-8",
    )
    result = evaluate(base, patched)
    assert result["base_optimal_actions"] == [{"x_a": 1, "x_b": 0}]
    assert result["patched_optimal_actions"] == [{"x_a": 0, "x_b": 1}]
    assert result["common_optimal_action_feasible"] is False
    assert result["optimal_action_changed"] is True


def test_redundancy_check_keeps_one_of_duplicate_constraints() -> None:
    model = _model(
        "base",
        [{"name": "choose_duplicate", "sense": ">=", "rhs": 1, "coefficients": {"x_a": 1, "x_b": 1}, "meaning": "duplicate"}],
    )
    assert redundant_constraints(model) == ["choose"]


def test_redundancy_check_accepts_independent_constraints() -> None:
    model = _model(
        "base",
        [{"name": "cap_a", "sense": "<=", "rhs": 0, "coefficients": {"x_a": 1}, "meaning": "cap"}],
    )
    assert redundant_constraints(model) == []


def test_base_action_projection_must_cover_every_nonfixed_decision(tmp_path: Path) -> None:
    import json

    model = _model("base", [])
    model["action_projection"] = ["x_a"]
    path = tmp_path / "base.json"
    path.write_text(json.dumps(model), encoding="utf-8")
    try:
        load_model(path)
    except ValueError as exc:
        assert "incomplete base action projection" in str(exc)
    else:
        raise AssertionError("omitted decision variable was accepted")


def test_sub_micro_coefficients_are_rejected_before_tolerance_can_create_false_ties(tmp_path: Path) -> None:
    import json

    model = _model("base", [])
    model["objective"]["coefficients"]["x_b"] = 1e-9
    path = tmp_path / "base.json"
    path.write_text(json.dumps(model), encoding="utf-8")
    try:
        load_model(path)
    except ValueError as exc:
        assert "unsafe sub-micro numeric magnitude" in str(exc)
    else:
        raise AssertionError("unsafe sub-micro coefficient was accepted")

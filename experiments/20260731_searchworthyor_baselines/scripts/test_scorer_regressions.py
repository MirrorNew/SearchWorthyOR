from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import score_submissions


def build_oracle_fixture(dataset_root: Path) -> dict:
    gold = score_submissions.read_jsonl(
        dataset_root / "private" / "gold.jsonl"
    )[0]
    task_id = gold["id"]
    model_dir = dataset_root / "models" / task_id
    base_ir = json.loads(
        (model_dir / "base_ir.json").read_text(encoding="utf-8")
    )
    patched_ir = json.loads(
        (model_dir / "patched_ir.json").read_text(encoding="utf-8")
    )
    solver = json.loads(
        (model_dir / "solver_results.json").read_text(encoding="utf-8")
    )
    evidence_id = gold["applicability"]["selected_evidence_id"]
    return {
        "task_id": task_id,
        "baseline": "oracle_scorer_fixture_not_a_baseline",
        "condition": "oracle_evidence",
        "requested_model": "fixture",
        "actual_model": "fixture",
        "requested_reasoning_effort": "high",
        "reasoning_fallback": False,
        "generated_once": True,
        "search_trace": [
            {
                "query": "<oracle-fixture>",
                "results": [{"rank": 1, "id": evidence_id, "score": 1.0}],
            }
        ],
        "selected_evidence_ids": [evidence_id],
        "applicability": gold["applicability"],
        "base_ir": base_ir,
        "typed_patch": gold["typed_patch"],
        "patched_ir": patched_ir,
        "gurobi_code": str(model_dir / "gurobi_model.py"),
        "gurobi_result": solver["patched"]["gurobi"],
        "claim_to_model_mapping": gold["claim_to_model_mapping"],
        "usage": {"fixture": True},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument(
        "--fixture",
        type=Path,
        help="optional fixture JSONL; defaults to a fixture derived from Gold",
    )
    args = parser.parse_args()

    fixture = (
        score_submissions.read_jsonl(args.fixture)[0]
        if args.fixture
        else build_oracle_fixture(args.dataset_root)
    )
    gold_rows = score_submissions.read_jsonl(
        args.dataset_root / "private" / "gold.jsonl"
    )
    gold = {row["id"]: row for row in gold_rows}[fixture["task_id"]]
    backend = score_submissions.load_solver_backend(args.dataset_root)

    oracle_score = score_submissions.score_one(
        fixture, gold, args.dataset_root, backend
    )
    assert oracle_score["model_success"] is True
    assert oracle_score["strict_e2e"] is True
    assert oracle_score["base_model_success"] is True
    assert oracle_score["model_structurally_changed"] is True
    assert oracle_score["decision_changed_from_base"] is True
    assert oracle_score["evidence_driven_model_change"] is True

    forged = copy.deepcopy(fixture)
    forged["patched_ir"] = None
    forged["base_ir"] = None
    forged["typed_patch"] = {"ops": []}
    forged["applicability"] = {}
    forged["claim_to_model_mapping"] = []
    forged_score = score_submissions.score_one(
        forged, gold, args.dataset_root, backend
    )
    assert forged_score["outcome_match"] is True
    assert forged_score["replay_available"] is False
    assert forged_score["trace_complete"] is False
    assert forged_score["model_success"] is False
    assert forged_score["strict_e2e"] is False

    nonempty_forged_trace = copy.deepcopy(fixture)
    nonempty_forged_trace["applicability"] = {"status": "pass"}
    nonempty_forged_trace["typed_patch"] = {
        "ops": [{"op": "add", "after_expression": "0 <= 1"}]
    }
    nonempty_forged_trace["claim_to_model_mapping"] = [
        {"claim_id": "fabricated", "equations": ["0 <= 1"]}
    ]
    nonempty_trace_score = score_submissions.score_one(
        nonempty_forged_trace, gold, args.dataset_root, backend
    )
    assert nonempty_trace_score["trace_complete"] is True
    assert nonempty_trace_score["model_success"] is True
    assert nonempty_trace_score["applicability_exact_match"] is False
    assert nonempty_trace_score["typed_patch_exact_match"] is False
    assert nonempty_trace_score["claim_mapping_exact_match"] is False
    assert nonempty_trace_score["strict_e2e"] is False

    decision_equivalent = copy.deepcopy(fixture)
    decision_equivalent["patched_ir"]["variables"].append(
        {
            "name": "z_equivalent",
            "vartype": "B",
            "lb": 0,
            "ub": 1,
            "semantic_name": "等价线性化辅助变量",
        }
    )
    evidence_constraint = decision_equivalent["patched_ir"][
        "constraints"
    ].pop()
    assert evidence_constraint["terms"] == {"x_0": 1, "x_1": 1}
    assert evidence_constraint["sense"] == "<="
    assert evidence_constraint["rhs"] == 1
    decision_equivalent["patched_ir"]["constraints"].extend(
        [
            {
                "name": "equivalent_trigger_link",
                "sense": "==",
                "rhs": 0,
                "terms": {"x_0": 1, "z_equivalent": -1},
            },
            {
                "name": "equivalent_trigger_exclusion",
                "sense": "<=",
                "rhs": 1,
                "terms": {"z_equivalent": 1, "x_1": 1},
            },
        ]
    )
    decision_equivalent_score = score_submissions.score_one(
        decision_equivalent, gold, args.dataset_root, backend
    )
    assert decision_equivalent_score["semantic_patched_ir_match"] is False
    assert decision_equivalent_score["projected_feasible_set_match"] is True
    assert decision_equivalent_score["optimal_action_set_match"] is True
    assert decision_equivalent_score["decision_model_equivalent"] is True

    incumbent_only = copy.deepcopy(fixture)
    incumbent_only["patched_ir"]["objective"]["constant"] = (
        fixture["gurobi_result"]["objective"]
    )
    incumbent_only["patched_ir"]["objective"]["terms"] = {
        name: 0
        for name in incumbent_only["patched_ir"]["objective"]["terms"]
    }
    incumbent_only_score = score_submissions.score_one(
        incumbent_only, gold, args.dataset_root, backend
    )
    assert incumbent_only_score["outcome_match"] is True
    assert incumbent_only_score["projected_feasible_set_match"] is True
    assert incumbent_only_score["optimal_action_set_match"] is False
    assert incumbent_only_score["decision_model_equivalent"] is False

    provenance_fixture = {
        "selected_evidence_ids": ["DOC-EXTERNAL"],
        "selected_urls": [],
        "typed_patch": {
            "ops": [{"evidence_id": "DOC-EXTERNAL"}]
        },
        "claim_to_model_mapping": [
            {"evidence_id": "TASK_SWOR_TEST"},
            {"evidence_id": "DOC-EXTERNAL"},
            {"evidence_id": "DERIVED_FROM_PATCHED_MODEL"},
        ],
    }
    assert score_submissions.mapping_evidence_consistent(
        provenance_fixture, retrieval_required=True
    )
    provenance_fixture["claim_to_model_mapping"].append(
        {"evidence_id": "DOC-UNSELECTED"}
    )
    assert not score_submissions.mapping_evidence_consistent(
        provenance_fixture, retrieval_required=True
    )

    alternate_optimum = {
        "gurobi_result": {
            "status": "OPTIMAL",
            "objective": 10,
            "projected_action": [1, 0],
        },
        "usage": {
            "model_code_execution": {
                "passed": True,
                "result": {
                    "status": "OPTIMAL",
                    "objective": 10,
                    "projected_action": [0, 1],
                },
            },
            "trusted_exact_enumeration": {
                "optimal_actions": [[1, 0], [0, 1]],
            },
        },
    }
    assert score_submissions.code_ir_consistent(alternate_optimum)
    nonoptimal_code_action = copy.deepcopy(alternate_optimum)
    nonoptimal_code_action["usage"]["model_code_execution"]["result"][
        "projected_action"
    ] = [0, 0]
    assert not score_submissions.code_ir_consistent(nonoptimal_code_action)

    print(
        json.dumps(
            {
                "oracle_strict_e2e": oracle_score["strict_e2e"],
                "oracle_evidence_driven_model_change": oracle_score[
                    "evidence_driven_model_change"
                ],
                "forged_outcome_match": forged_score["outcome_match"],
                "forged_model_success": forged_score["model_success"],
                "forged_strict_e2e": forged_score["strict_e2e"],
                "nonempty_forged_trace_complete": nonempty_trace_score[
                    "trace_complete"
                ],
                "nonempty_forged_strict_e2e": nonempty_trace_score[
                    "strict_e2e"
                ],
                "equivalent_rewrite_semantic_match": (
                    decision_equivalent_score["semantic_patched_ir_match"]
                ),
                "equivalent_rewrite_decision_equivalent": (
                    decision_equivalent_score["decision_model_equivalent"]
                ),
                "incumbent_only_outcome_match": incumbent_only_score[
                    "outcome_match"
                ],
                "incumbent_only_optimal_action_set_match": (
                    incumbent_only_score["optimal_action_set_match"]
                ),
                "incumbent_only_decision_equivalent": incumbent_only_score[
                    "decision_model_equivalent"
                ],
                "local_provenance_allowed": True,
                "unselected_external_provenance_rejected": True,
                "alternate_optimal_code_action_allowed": True,
                "nonoptimal_code_action_rejected": True,
                "passed": True,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

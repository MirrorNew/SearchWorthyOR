from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from review_artifact_fingerprint import compute_fingerprint, declared_artifact_paths
from validate_batch import quantitative_compliance_leakage, repeated_long_sentences


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def test_fingerprint_detects_artifact_changes_but_ignores_release_status(tmp_path: Path) -> None:
    task_id = "SWOR-R001"
    batch = tmp_path / "batches" / "batch_01"
    model_dir = batch / "models" / task_id
    model_dir.mkdir(parents=True)
    task = {"id": task_id, "problem_zh": "原始题面"}
    audit = {
        "id": task_id,
        "base_model_path": f"batches/batch_01/models/{task_id}/base_ir.json",
        "patched_model_path": f"batches/batch_01/models/{task_id}/patched_ir.json",
        "solve_result_path": f"batches/batch_01/models/{task_id}/solve_result.json",
        "independent_review": "PENDING",
        "status": "GENERATED_SELF_CHECK_PASS",
        "rule_claim": "规则原子",
    }
    _write_json(batch / "public" / "tasks_zh.jsonl", task)
    _write_json(batch / "private" / "rapid_audit.jsonl", audit)
    for filename, variant in (("base_ir.json", "base"), ("patched_ir.json", "patched")):
        _write_json(model_dir / filename, {"id": task_id, "variant": variant})
    _write_json(model_dir / "solve_result.json", {"id": task_id, "optimal_action_changed": True})

    original = compute_fingerprint(tmp_path, 1, task_id)
    audit["independent_review"] = "PASS"
    audit["status"] = "RAPID_V0_PASS"
    _write_json(batch / "private" / "rapid_audit.jsonl", audit)
    assert compute_fingerprint(tmp_path, 1, task_id) == original

    task["problem_zh"] = "被修改后的题面"
    _write_json(batch / "public" / "tasks_zh.jsonl", task)
    assert compute_fingerprint(tmp_path, 1, task_id) != original


def test_declared_artifact_paths_reject_noncanonical_or_escaping_paths(tmp_path: Path) -> None:
    task_id = "SWOR-R001"
    audit = {
        "base_model_path": f"batches/batch_01/models/{task_id}/base_ir.json",
        "patched_model_path": f"batches/batch_01/models/{task_id}/patched_ir.json",
        "solve_result_path": f"batches/batch_01/models/{task_id}/solve_result.json",
    }
    assert declared_artifact_paths(tmp_path, 1, task_id, audit)["patched_model_path"] == (
        tmp_path / "batches" / "batch_01" / "models" / task_id / "patched_ir.json"
    ).resolve()
    audit["patched_model_path"] = "../outside.json"
    try:
        declared_artifact_paths(tmp_path, 1, task_id, audit)
    except ValueError as exc:
        assert "noncanonical_task_artifact_path" in str(exc)
    else:
        raise AssertionError("escaping artifact path was accepted")


def test_repeated_long_sentences_detects_internal_copy_paste() -> None:
    repeated = "本次地点是公共道路道口，且不存在法定豁免"
    assert repeated_long_sentences(f"{repeated}。正常业务说明。{repeated}。") == [repeated]
    assert repeated_long_sentences("短句。短句。另一条完整且不重复的业务说明。") == []


def test_quantitative_compliance_leakage_detects_rule_answer_in_requirement() -> None:
    leaked = "通知安排还须符合发现停机后60分钟内报告的现行要求"
    assert quantitative_compliance_leakage(f"业务背景。{leaked}。请给出最优方案与总成本。") == [leaked]
    assert quantitative_compliance_leakage(
        "业务背景。通知安排还须符合加利福尼亚州当日适用的停机报告规定。请给出最优方案与总成本。"
    ) == []

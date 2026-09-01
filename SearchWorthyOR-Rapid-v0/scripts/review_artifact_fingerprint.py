from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def declared_artifact_paths(root: Path, batch: int, task_id: str, audit: dict[str, Any]) -> dict[str, Path]:
    task_dir = root / "batches" / f"batch_{batch:02d}" / "models" / task_id
    expected = {
        "base_model_path": task_dir / "base_ir.json",
        "patched_model_path": task_dir / "patched_ir.json",
        "solve_result_path": task_dir / "solve_result.json",
    }
    resolved: dict[str, Path] = {}
    for field, expected_path in expected.items():
        declared = Path(audit[field])
        if declared.is_absolute():
            raise ValueError(f"{task_id}:{field}:absolute_path_not_allowed")
        declared_path = (root / declared).resolve()
        if declared_path != expected_path.resolve():
            raise ValueError(f"{task_id}:{field}:noncanonical_task_artifact_path")
        resolved[field] = declared_path
    return resolved


def compute_fingerprint(root: Path, batch: int, task_id: str) -> str:
    batch_dir = root / "batches" / f"batch_{batch:02d}"
    task = next(row for row in read_jsonl(batch_dir / "public" / "tasks_zh.jsonl") if row["id"] == task_id)
    audit = next(row for row in read_jsonl(batch_dir / "private" / "rapid_audit.jsonl") if row["id"] == task_id)
    audit_core = {key: value for key, value in audit.items() if key not in {"independent_review", "status"}}
    paths = declared_artifact_paths(root, batch, task_id, audit)
    payload = {
        "task": task,
        "audit_core": audit_core,
        "base_ir": json.loads(paths["base_model_path"].read_text(encoding="utf-8")),
        "patched_ir": json.loads(paths["patched_model_path"].read_text(encoding="utf-8")),
        "solve_result": json.loads(paths["solve_result_path"].read_text(encoding="utf-8")),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rapid-root", type=Path, required=True)
    parser.add_argument("--batch", type=int, required=True, choices=range(1, 6))
    parser.add_argument("--id")
    args = parser.parse_args()
    root = args.rapid_root.resolve()
    task_ids = [args.id] if args.id else [
        row["id"] for row in read_jsonl(root / "batches" / f"batch_{args.batch:02d}" / "public" / "tasks_zh.jsonl")
    ]
    print(json.dumps({task_id: compute_fingerprint(root, args.batch, task_id) for task_id in task_ids}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

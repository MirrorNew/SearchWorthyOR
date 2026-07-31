from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    manifest = json.loads(
        (root / "RUN_SNAPSHOT_MANIFEST.json").read_text(
            encoding="utf-8-sig"
        )
    )
    errors: list[str] = []
    expected_dirs: set[str] = set()
    for method in manifest["methods"]:
        label = method["label"]
        rows = method["tasks"]
        recomputed_counts = {
            status: sum(row["status"] == status for row in rows)
            for status in method["counts"]
        }
        if recomputed_counts != method["counts"]:
            errors.append(f"{label}: count mismatch")
        if method["task_count"] != len(rows):
            errors.append(f"{label}: task_count mismatch")
        for row in rows:
            task_id = row["task_id"]
            task_dir = root / label / row["shard"] / task_id
            expected_dirs.add(task_dir.relative_to(root).as_posix())
            status = row["status"]
            submission_path = task_dir / "submission.json"
            failure_path = task_dir / "failure.json"
            if status in {
                "submission",
                "recovered_submission",
                "submission_with_prior_failure",
            }:
                if not submission_path.is_file():
                    errors.append(f"{label}/{task_id}: missing submission")
                    continue
                submission = json.loads(
                    submission_path.read_text(encoding="utf-8-sig")
                )
                if submission.get("task_id") != task_id:
                    errors.append(
                        f"{label}/{task_id}: submission task mismatch"
                    )
                if submission.get("gurobi_code") != "model.py":
                    errors.append(
                        f"{label}/{task_id}: nonportable code path"
                    )
                code_path = task_dir / "model.py"
                if not code_path.is_file():
                    errors.append(f"{label}/{task_id}: missing model.py")
                elif sha256_file(code_path) != row["code_sha256"]:
                    errors.append(f"{label}/{task_id}: code hash mismatch")
                if status == "recovered_submission" and not (
                    failure_path.is_file()
                    and (task_dir / "resume_resolution.json").is_file()
                ):
                    errors.append(
                        f"{label}/{task_id}: incomplete recovery provenance"
                    )
                if (
                    status == "submission_with_prior_failure"
                    and not failure_path.is_file()
                ):
                    errors.append(
                        f"{label}/{task_id}: missing prior failure"
                    )
            elif status == "failure":
                if not failure_path.is_file() or submission_path.exists():
                    errors.append(f"{label}/{task_id}: invalid failure state")
            elif status == "incomplete":
                errors.append(f"{label}/{task_id}: incomplete task")
            else:
                errors.append(f"{label}/{task_id}: unknown status {status}")

    actual_dirs = {
        path.relative_to(root).as_posix()
        for method_dir in root.iterdir()
        if method_dir.is_dir()
        for shard_dir in method_dir.glob("shard*")
        if shard_dir.is_dir()
        for path in shard_dir.glob("SWOR*")
        if path.is_dir()
    }
    if actual_dirs != expected_dirs:
        errors.append("task directory set differs from manifest")
    result = {
        "ok": not errors,
        "method_count": len(manifest["methods"]),
        "task_count": len(expected_dirs),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

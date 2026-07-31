from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_run(raw: str) -> tuple[str, Path]:
    if "=" not in raw:
        raise ValueError("--run must be LABEL=PATH")
    label, path = raw.split("=", 1)
    if not label or not path:
        raise ValueError("--run must be LABEL=PATH")
    if any(char not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for char in label):
        raise ValueError(f"unsafe run label: {label}")
    return label, Path(path).resolve()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="append", required=True)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()

    destination = args.destination.resolve()
    if destination.exists():
        raise FileExistsError(
            f"destination already exists; refusing overwrite: {destination}"
        )
    destination.mkdir(parents=True)
    methods = []
    labels: set[str] = set()
    for raw_run in args.run:
        label, run_root = parse_run(raw_run)
        if label in labels:
            raise ValueError(f"duplicate run label: {label}")
        labels.add(label)
        if not run_root.is_dir():
            raise NotADirectoryError(run_root)

        shard_dirs = sorted(
            path
            for path in run_root.glob("shard*")
            if path.is_dir()
        )
        if shard_dirs:
            task_dirs = sorted(
                (
                    task_dir
                    for shard_dir in shard_dirs
                    for task_dir in shard_dir.glob("SWOR*")
                    if task_dir.is_dir()
                ),
                key=lambda path: path.name,
            )
        else:
            task_dirs = sorted(
                (
                    task_dir
                    for task_dir in run_root.glob("SWOR*")
                    if task_dir.is_dir()
                ),
                key=lambda path: path.name,
            )
        rows = []
        seen: set[str] = set()
        for task_dir in task_dirs:
            task_id = task_dir.name
            shard = (
                task_dir.parent.name
                if shard_dirs
                else "shard0"
            )
            if task_id in seen:
                raise ValueError(f"{label}: duplicate task directory {task_id}")
            seen.add(task_id)
            submission_path = task_dir / "submission.json"
            failure_path = task_dir / "failure.json"
            resolution_path = task_dir / "resume_resolution.json"
            target_dir = destination / label / shard / task_id
            row: dict[str, Any] = {"task_id": task_id, "shard": shard}
            if submission_path.exists():
                submission = read_json(submission_path)
                if submission.get("task_id") != task_id:
                    raise ValueError(f"{label}: mismatched submission {task_id}")
                code_path = Path(submission["gurobi_code"]).resolve()
                try:
                    code_path.relative_to(run_root)
                except ValueError as error:
                    raise ValueError(
                        f"{label}: code escapes run root for {task_id}"
                    ) from error
                if not code_path.is_file():
                    raise FileNotFoundError(code_path)
                target_dir.mkdir(parents=True, exist_ok=True)
                target_code = target_dir / "model.py"
                shutil.copy2(code_path, target_code)
                public_submission = dict(submission)
                public_submission["gurobi_code"] = "model.py"
                target_submission = target_dir / "submission.json"
                target_submission.write_text(
                    json.dumps(
                        public_submission,
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                if failure_path.exists():
                    shutil.copy2(
                        failure_path,
                        target_dir / "failure.json",
                    )
                row.update(
                    {
                        "status": (
                            "recovered_submission"
                            if resolution_path.exists()
                            else (
                                "submission_with_prior_failure"
                                if failure_path.exists()
                                else "submission"
                            )
                        ),
                        "submission_sha256": sha256_file(submission_path),
                        "public_submission_path": (
                            target_submission.relative_to(
                                destination
                            ).as_posix()
                        ),
                        "code_path": target_code.relative_to(
                            destination
                        ).as_posix(),
                        "code_bytes": target_code.stat().st_size,
                        "code_sha256": sha256_file(target_code),
                    }
                )
            elif failure_path.exists():
                failure = read_json(failure_path)
                target_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(failure_path, target_dir / "failure.json")
                row.update(
                    {
                        "status": "failure",
                        "failure": failure,
                        "failure_sha256": sha256_file(failure_path),
                    }
                )
            else:
                row["status"] = "incomplete"
            if resolution_path.exists():
                row["resume_resolution"] = read_json(resolution_path)
                row["resume_resolution_sha256"] = sha256_file(
                    resolution_path
                )
                shutil.copy2(
                    resolution_path,
                    target_dir / "resume_resolution.json",
                )
            rows.append(row)
        counts = {
            status: sum(row["status"] == status for row in rows)
            for status in (
                "submission",
                "recovered_submission",
                "submission_with_prior_failure",
                "failure",
                "incomplete",
            )
        }
        methods.append(
            {
                "label": label,
                "task_count": len(rows),
                "counts": counts,
                "tasks": rows,
            }
        )

    manifest = {
        "schema_version": 1,
        "scope": (
            "Generated Gurobi programs plus task-level failure and recovery "
            "status; prompts, model responses, and event logs are excluded."
        ),
        "methods": methods,
    }
    (destination / "RUN_SNAPSHOT_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "destination": str(destination),
                "method_count": len(methods),
                "task_count": sum(row["task_count"] for row in methods),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

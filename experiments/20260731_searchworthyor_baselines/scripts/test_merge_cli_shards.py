from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    merge_script = Path(__file__).with_name("merge_cli_shards.py")
    with tempfile.TemporaryDirectory() as raw_tmp:
        root = Path(raw_tmp)
        dataset = root / "dataset"
        shard = root / "runs" / "shard0"
        tasks = [{"id": "SWOR001"}, {"id": "SWOR002"}]
        tasks_path = dataset / "public" / "tasks_zh.jsonl"
        tasks_path.parent.mkdir(parents=True)
        tasks_path.write_text(
            "".join(json.dumps(row) + "\n" for row in tasks),
            encoding="utf-8",
        )

        write_json(
            shard / "SWOR001" / "submission.json",
            {"task_id": "SWOR001", "result": "kept"},
        )
        write_json(
            shard / "SWOR001" / "failure.json",
            {"task_id": "SWOR001", "message": "stale pre-recovery"},
        )
        write_json(
            shard / "SWOR002" / "failure.json",
            {"task_id": "SWOR002", "message": "active"},
        )
        # A targeted resume may overwrite these shard aggregates. They must not
        # override the immutable task-level artifacts above.
        (shard / "submissions.jsonl").write_text("", encoding="utf-8")
        write_json(shard / "failures.json", [])

        output = root / "merged.jsonl"
        completed = subprocess.run(
            [
                sys.executable,
                str(merge_script),
                "--dataset-root",
                str(dataset),
                "--shard-root",
                str(root / "runs"),
                "--output",
                str(output),
                "--expected",
                "2",
                "--allow-active-failures",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr or completed.stdout)

        merged = [
            json.loads(line)
            for line in output.read_text(encoding="utf-8").splitlines()
        ]
        audit = json.loads(
            output.with_suffix(".merge_audit.json").read_text(
                encoding="utf-8"
            )
        )
        assert [row["task_id"] for row in merged] == ["SWOR001"]
        assert audit["recovered_failure_count"] == 1
        assert [row["task_id"] for row in audit["active_failures"]] == [
            "SWOR002"
        ]
        assert audit["uncovered"] == []
        assert audit["passed"] is True

    print("merge_cli_shards task-level authority regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

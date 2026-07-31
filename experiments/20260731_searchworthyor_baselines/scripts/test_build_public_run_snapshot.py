from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    script = Path(__file__).with_name("build_public_run_snapshot.py")
    verifier = Path(__file__).with_name(
        "verify_public_run_snapshot.py"
    )
    with tempfile.TemporaryDirectory() as raw_tmp:
        root = Path(raw_tmp)
        run_root = root / "run"
        success = run_root / "shard0" / "SWOR001"
        failed = run_root / "shard0" / "SWOR002"
        success.mkdir(parents=True)
        failed.mkdir(parents=True)
        code = success / "model.py"
        code.write_text("import gurobipy as gp\n", encoding="utf-8")
        (success / "submission.json").write_text(
            json.dumps(
                {
                    "task_id": "SWOR001",
                    "gurobi_code": str(code),
                }
            ),
            encoding="utf-8",
        )
        (success / "failure.json").write_text(
            json.dumps(
                {
                    "task_id": "SWOR001",
                    "type": "RuntimeError",
                    "message": "recovered test",
                }
            ),
            encoding="utf-8",
        )
        (success / "resume_resolution.json").write_text(
            json.dumps({"status": "recovered"}),
            encoding="utf-8",
        )
        (failed / "failure.json").write_text(
            json.dumps(
                {
                    "task_id": "SWOR002",
                    "type": "RuntimeError",
                    "message": "test",
                }
            ),
            encoding="utf-8",
        )
        destination = root / "snapshot"
        direct_root = root / "direct"
        direct_task = direct_root / "SWOR003"
        direct_task.mkdir(parents=True)
        direct_code = direct_task / "model.py"
        direct_code.write_text("import gurobipy as gp\n", encoding="utf-8")
        (direct_task / "submission.json").write_text(
            json.dumps(
                {
                    "task_id": "SWOR003",
                    "gurobi_code": str(direct_code),
                }
            ),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                sys.executable,
                str(script),
                "--run",
                f"method={run_root}",
                "--run",
                f"direct={direct_root}",
                "--destination",
                str(destination),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr or completed.stdout)
        manifest = json.loads(
            (destination / "RUN_SNAPSHOT_MANIFEST.json").read_text(
                encoding="utf-8"
            )
        )
        method = manifest["methods"][0]
        assert method["task_count"] == 2
        assert method["counts"]["recovered_submission"] == 1
        assert method["counts"]["failure"] == 1
        public_task = (
            destination / "method" / "shard0" / "SWOR001"
        )
        assert (public_task / "model.py").is_file()
        public_submission = json.loads(
            (public_task / "submission.json").read_text(encoding="utf-8")
        )
        assert public_submission["gurobi_code"] == "model.py"
        assert (public_task / "failure.json").is_file()
        assert (public_task / "resume_resolution.json").is_file()
        assert (
            destination
            / "method"
            / "shard0"
            / "SWOR002"
            / "failure.json"
        ).is_file()
        direct = manifest["methods"][1]
        assert direct["task_count"] == 1
        assert (
            destination
            / "direct"
            / "shard0"
            / "SWOR003"
            / "submission.json"
        ).is_file()
        verified = subprocess.run(
            [
                sys.executable,
                str(verifier),
                "--root",
                str(destination),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if verified.returncode != 0:
            raise AssertionError(verified.stderr or verified.stdout)
        assert "gurobi_code" not in json.dumps(manifest)

    print("build_public_run_snapshot regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

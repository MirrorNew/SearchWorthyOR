"""Prepare paired public-only ORLM runs; live execution requires --run."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(folder, isolation=False):
    command = [sys.executable, str(HERE / "run_worker.py"), str(folder)]
    if isolation:
        command.append("--check-isolation")
    start = time.monotonic()
    try:
        proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=60 if isolation else 1215,
                              env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
        stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as exc:
        def decode(value):
            return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else (value or "")
        stdout, stderr, code = decode(exc.stdout), decode(exc.stderr), -1
    prefix = "isolation_" if isolation else ""
    (folder / f"{prefix}stdout.txt").write_text(stdout, encoding="utf-8")
    (folder / f"{prefix}stderr.txt").write_text(stderr, encoding="utf-8")
    result = {"method": folder.parent.name, "eval_id": folder.name, "returncode": code,
              "seconds": round(time.monotonic() - start, 3), "watchdog_timeout": code == -1}
    write(folder / f"{prefix}execution.json", result)
    print(json.dumps(result), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--check-isolation", action="store_true")
    args = parser.parse_args()
    if not args.name.replace("_", "").replace("-", "").isalnum():
        raise ValueError("Batch name must be a simple unique name")
    batch = HERE / "batches" / args.name
    batch.mkdir(parents=True, exist_ok=False)
    baseline = json.loads((ROOT / "reevaluation/config.deepseek.portable.v1.6.3.json").read_text(encoding="utf-8"))
    old_config = ROOT / "experiments/deepseek_20261107/deepseek_standard_knowledge_20261107_v1/standard_knowledge_on/run_3/standard_knowledge_on/SWOR-E-FF73D1A55AE1AC3CB584/config.json"
    credential_path = json.loads(old_config.read_text(encoding="utf-8"))["credential_dpapi"]
    assert Path(credential_path).is_file()
    baseline.pop("benchmark", None)
    baseline.pop("credential_file", None)
    baseline.update(credential_dpapi=credential_path, standard_protocol="legacy_knowledge_v1")
    cases = [json.loads(line) for line in (HERE / "public_cases.jsonl").read_text(encoding="utf-8").splitlines()]
    if args.case:
        cases = [row for row in cases if row["id"] in args.case]
        assert len(cases) == len(set(args.case))
    assert cases
    code_files = sorted((ROOT / "agent").rglob("*.py")) + sorted((ROOT / "reevaluation").glob("*.py")) + sorted(HERE.glob("*.py"))
    hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in code_files}
    folders = []
    for public in cases:
        for method in ("standard", "swagent"):
            folder = batch / method / public["id"]
            config = {**baseline, "method": method}
            write(folder / "input.json", public)
            write(folder / "config.json", config)
            write(folder / "manifest.json", {"id": public["id"], "method": method, "condition": "C3-style",
                  "input_sha256": sha(folder / "input.json"), "config_sha256": sha(folder / "config.json"),
                  "code_sha256": hashes, "public_cases_sha256": sha(HERE / "public_cases.jsonl"),
                  "solver": "COPT", "source_answers_excluded": True})
            folders.append(folder)
    write(batch / "batch_manifest.json", {"name": args.name, "case_count": len(cases), "runs": len(folders),
          "methods": ["standard-online", "swagent-online"], "workers": args.workers,
          "model": baseline["model"], "budgets": baseline["budgets"], "code_sha256": hashes,
          "selection": [c["id"] for c in cases], "prepared_only": not args.run})
    if args.check_isolation:
        results = [execute(folder, isolation=True) for folder in folders[:2]]
        assert all(result["returncode"] == 0 for result in results)
    if args.run:
        records = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(execute, folder) for folder in folders]
            for future in as_completed(futures):
                records.append(future.result())
                write(batch / "progress.json", {"completed": len(records), "total": len(folders), "records": records})
        write(batch / "completion.json", {"complete": len(records) == len(folders), "records": records})


if __name__ == "__main__":
    main()

"""Execute supplied reference code separately from public-only model experiments."""
from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
SOURCE = OUT.parent / "SFT1991_sample20/SFT1991_sample20"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(case):
    target = OUT / "cases" / case.name
    target.mkdir(parents=True, exist_ok=True)
    answer = case / "答案.md"
    text = answer.read_text(encoding="utf-8-sig")
    blocks = re.findall(r"```(?:python|Python|py)\s*\n(.*?)```", text, re.S)
    if len(blocks) != 1:
        raise ValueError(f"Expected one reference code block: {case.name}")
    code = blocks[0]
    ast.parse(code)
    program = target / "reference.py"
    program.write_text(code, encoding="utf-8")
    record = {"source_id": case.name, "answer_sha256": digest(answer),
              "program_sha256": digest(program), "code_extraction": "single Python fenced block, unchanged",
              "source_files": {p.relative_to(case).as_posix(): digest(p) for p in sorted(case.rglob("*")) if p.is_file()},
              "scope": "execution of supplied reference, not independent semantic certification"}
    start = time.monotonic()
    try:
        proc = subprocess.run([sys.executable, str(OUT / "execute_one.py"), str(program), str(target)],
                              cwd=case, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}, timeout=180)
        stdout, stderr = proc.stdout, proc.stderr
        record["returncode"] = proc.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        stdout = stdout.decode("utf-8", errors="replace") if isinstance(stdout, bytes) else stdout
        stderr = stderr.decode("utf-8", errors="replace") if isinstance(stderr, bytes) else stderr
        record["status"] = "PROCESS_TIMEOUT"
    record["seconds"] = round(time.monotonic() - start, 3)
    (target / "stdout.txt").write_text(stdout, encoding="utf-8")
    (target / "stderr.txt").write_text(stderr, encoding="utf-8")
    results = [line[len("RESULT_JSON:"):] for line in stdout.splitlines() if line.startswith("RESULT_JSON:")]
    if results:
        record["result"] = json.loads(results[-1])
        record["status"] = record["result"].get("status", "UNKNOWN")
    else:
        record.setdefault("status", "NO_RESULT_JSON")
    record["source_unchanged"] = all(digest(case / name) == value for name, value in record["source_files"].items())
    (target / "record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"source_id": case.name, "status": record["status"],
                      "objective_value": record.get("result", {}).get("objective_value"),
                      "seconds": record["seconds"]}, ensure_ascii=False), flush=True)
    return record


if __name__ == "__main__":
    cases = sorted(p for p in SOURCE.iterdir() if p.is_dir())
    assert len(cases) == 20
    with ThreadPoolExecutor(max_workers=2) as pool:
        records = list(pool.map(execute, cases))
    (OUT / "reference_results.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


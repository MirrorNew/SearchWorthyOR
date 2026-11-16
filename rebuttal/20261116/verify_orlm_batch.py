"""Post-run provenance and completion checks; does not execute or score agents."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch")
    args = parser.parse_args()
    here = BASE / "orlm_c3"
    batch = here / "batches" / args.batch
    manifest = read(batch / "batch_manifest.json")
    complete = read(batch / "completion.json")
    assert complete["complete"] and len(complete["records"]) == manifest["runs"]
    for relative, expected in manifest["code_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    source = read(here / "source_manifest.json")
    public_sha = sha(here / "public_cases.jsonl")
    assert public_sha == source["public_cases_sha256"]
    source_files = 0
    for entry in source["entries"]:
        for item in entry["included_files"]:
            path = ROOT / source["source_root"] / entry["source_id"] / item["relative_path"]
            assert sha(path) == item["sha256"], path
            source_files += 1
    references = read(BASE / "orlm_reference/reference_results.json")
    for reference in references:
        answer = ROOT / source["source_root"] / reference["source_id"] / "答案.md"
        assert sha(answer) == reference["answer_sha256"], answer
    public = {r["id"]: r for r in lines(here / "public_cases.jsonl")}
    observed_models = Counter()
    checks = []
    configurations = {}
    for method in ("standard", "swagent"):
        for eval_id in manifest["selection"]:
            folder = batch / method / eval_id
            case = folder / "case"
            run_manifest = read(folder / "manifest.json")
            assert run_manifest["code_sha256"] == manifest["code_sha256"]
            assert run_manifest["public_cases_sha256"] == public_sha
            assert sha(folder / "input.json") == run_manifest["input_sha256"]
            assert sha(folder / "config.json") == run_manifest["config_sha256"]
            assert read(folder / "input.json") == public[eval_id] == read(case / "input.json")
            config = read(folder / "config.json")
            assert config.pop("method") == method
            configurations[(eval_id, method)] = config
            execution = read(folder / "execution.json")
            assert execution in complete["records"]
            isolation = read(case / "isolation_verified.json")
            assert isolation["pass"] and isolation["blocked_probes"] == 5
            accesses = lines(case / "access.jsonl")
            denied = [a for a in accesses if not a["allowed"]]
            expected_probes = [BASE / "SFT1991_sample20/SFT1991_sample20/B01_00413/答案.md",
                               BASE / "orlm_reference/reference_results.json",
                               ROOT / "datasets/SearchWorthyOR-v1.6.3/private/gold.jsonl",
                               here / "public_cases.jsonl", folder / "input.json"]
            assert [Path(a["path"]) for a in denied[:5]] == expected_probes
            for access in accesses:
                path = Path(access["path"])
                if access["allowed"]:
                    assert any(path.is_relative_to(p) for p in (case, ROOT / "agent", ROOT / "reevaluation")), path
            calls = lines(case / "api_calls.jsonl") if (case / "api_calls.jsonl").exists() else []
            for call in calls:
                if call.get("kind") == "model":
                    assert call["requested_model"] == "deepseek-flash"
            models = Counter(c["actual_model"] for c in calls if c.get("kind") == "model" and c.get("actual_model"))
            assert set(models).issubset({"deepseek-flash"}), models
            observed_models.update(models)
            checks.append({"eval_id": eval_id, "method": method, "input_match": True,
                           "isolation_probes_passed": True, "denied_accesses": len(denied),
                           "additional_denied_accesses": denied[5:],
                           "execution_returncode": execution["returncode"],
                           "watchdog_timeout": execution["watchdog_timeout"], "observed_models": dict(models)})
    for eval_id in manifest["selection"]:
        assert configurations[(eval_id, "standard")] == configurations[(eval_id, "swagent")]
    report = {"batch": args.batch, "pass": True, "attempts": len(checks),
              "all_attempts_terminated": True, "unchanged_code_files": len(manifest["code_sha256"]),
              "unchanged_public_source_files": source_files, "paired_inputs_and_configs_match": True,
              "unchanged_reference_answer_files": len(references),
              "public_cases_sha256": public_sha, "observed_model_calls": dict(observed_models),
              "scope": "Checks recorded project-root file access after public input loading; not an OS-wide filesystem sandbox or business-feasibility certificate.",
              "runs": checks}
    (batch / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "runs"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

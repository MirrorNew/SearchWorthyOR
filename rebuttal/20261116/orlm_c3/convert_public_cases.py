"""Build the ORLM C3 public inputs from question.md and data/*.csv only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "rebuttal" / "20261116" / "SFT1991_sample20" / "SFT1991_sample20"
OUT = Path(__file__).resolve().parent
PROMPT_LIMIT = 240_000
OUTPUT_SCHEMA = {
    "schema_version": "orlm.free_milp.v1",
    "actions": [],
    "objective": {
        "canonical_unit": "objective_units",
        "accepted_units": {"objective_units": 1},
    },
}


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def decode_utf8(path: Path) -> tuple[str, bytes]:
    content = path.read_bytes()
    return content.decode("utf-8"), content


def dump_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def build_case(case_dir: Path):
    case_id = case_dir.name
    prompt_path = case_dir / "题面.md"
    data_dir = case_dir / "data"
    if not prompt_path.is_file() or not data_dir.is_dir():
        raise ValueError(f"required question/data directory missing for {case_id}")

    # The allowlist is deliberate: no answer file, reference model, or other
    # case artifact is opened by this converter.
    prompt_text, prompt_bytes = decode_utf8(prompt_path)
    source_files = [{"path": prompt_path, "relative_path": "题面.md", "text": prompt_text,
                     "bytes": prompt_bytes}]
    csv_paths = sorted((path for path in data_dir.iterdir()
                        if path.is_file() and path.suffix.lower() == ".csv"), key=lambda path: path.name)
    if not csv_paths:
        raise ValueError(f"no data CSV files found for {case_id}")
    parts = [prompt_text]
    for csv_path in csv_paths:
        csv_text, csv_bytes = decode_utf8(csv_path)
        source_files.append({"path": csv_path, "relative_path": f"data/{csv_path.name}",
                             "text": csv_text, "bytes": csv_bytes})
        parts.extend(["\n\n数据文件：", csv_path.name, "\n", csv_text])
    # The legacy Standard payload carries the prompt only, as on the original
    # benchmark. Embed the same public schema so both methods receive it.
    parts.extend(["\n\n公开 output_schema：\n", dump_json(OUTPUT_SCHEMA)])
    prompt = "".join(parts)
    prompt_bytes_combined = prompt.encode("utf-8")
    if len(prompt) >= PROMPT_LIMIT:
        raise ValueError(f"prompt length {len(prompt)} reaches/exceeds {PROMPT_LIMIT}: {case_id}")

    eval_id = f"ORLM-SFT1991-{case_id}"
    case_obj = {"id": eval_id, "prompt": prompt, "output_schema": OUTPUT_SCHEMA}
    line = dump_json(case_obj)
    line_bytes = (line + "\n").encode("utf-8")
    included_files = []
    for source in source_files:
        included_files.append({
            "relative_path": source["relative_path"],
            "sha256": sha256_bytes(source["bytes"]),
            "bytes": len(source["bytes"]),
            "characters": len(source["text"]),
        })
    input_descriptor = dump_json(included_files).encode("utf-8")
    entry = {
        "source_id": case_id,
        "id": eval_id,
        "included_files": included_files,
        "prompt_sha256": sha256_bytes(prompt_bytes_combined),
        "prompt_characters": len(prompt),
        "input_sha256": sha256_bytes(input_descriptor),
        "input_sha256_definition": "SHA256 of compact UTF-8 JSON for included_files in listed order",
        "public_case_line_sha256": sha256_bytes(line_bytes),
        "answers_excluded": True,
    }
    return case_obj, line_bytes, entry


def main():
    case_dirs = sorted((path for path in SOURCE_ROOT.iterdir() if path.is_dir()), key=lambda path: path.name)
    if len(case_dirs) != 20:
        raise ValueError(f"expected exactly 20 case directories; found {len(case_dirs)}")
    case_lines, entries = [], []
    for case_dir in case_dirs:
        _, line_bytes, entry = build_case(case_dir)
        case_lines.append(line_bytes)
        entries.append(entry)

    public_cases_path = OUT / "public_cases.jsonl"
    public_cases_bytes = b"".join(case_lines)
    public_cases_path.write_bytes(public_cases_bytes)
    manifest = {
        "schema": "orlm_c3_source_manifest.v1",
        "classification": "C3_style_user_assigned_information_complete",
        "deployment_provenance": "unverified; no real deployment claim",
        "source_root": "rebuttal/20261116/SFT1991_sample20/SFT1991_sample20",
        "public_cases_file": "rebuttal/20261116/orlm_c3/public_cases.jsonl",
        "public_cases_sha256": sha256_bytes(public_cases_bytes),
        "public_case_count": len(entries),
        "prompt_limit_characters_exclusive": PROMPT_LIMIT,
        "answers_excluded": True,
        "entries": entries,
    }
    (OUT / "source_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "public_cases": str(public_cases_path),
        "public_cases_sha256": manifest["public_cases_sha256"],
        "source_manifest": str(OUT / "source_manifest.json"),
        "cases": len(entries),
        "total_included_files": sum(len(entry["included_files"]) for entry in entries),
        "max_prompt_characters": max(entry["prompt_characters"] for entry in entries),
        "min_prompt_characters": min(entry["prompt_characters"] for entry in entries),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

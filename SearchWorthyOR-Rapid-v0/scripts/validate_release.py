from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from solve_model_pair import load_model
from validate_batch import topology_hash
from review_artifact_fingerprint import compute_fingerprint
from review_contract import reviewer_assignment_errors
from source_contract import (
    canonical_url,
    load_source_catalog,
    official_host,
    receipt_binding_errors,
    resolve_source_binding,
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    payload = path.read_bytes()
    if payload.startswith(b"\xef\xbb\xbf") or b"\r" in payload:
        raise ValueError(f"{path}: must be UTF-8 without BOM and LF-only")
    return [json.loads(line) for line in payload.decode("utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def duplicate_groups(values: list[tuple[str, str]]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for task_id, value in values:
        groups.setdefault(value, []).append(task_id)
    return {value: task_ids for value, task_ids in groups.items() if len(task_ids) > 1}


def release_mode_errors(skip_batch_solves: bool, write_release: bool) -> list[str]:
    return ["write_release_requires_batch_validation"] if skip_batch_solves and write_release else []


def release_critical_files(root: Path) -> list[Path]:
    roots = [root / name for name in ("public", "private", "batches", "schemas", "config", "scripts", "tests")]
    excluded_dirs = {".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache"}
    files: list[Path] = []
    for directory in roots:
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            relative_parts = path.relative_to(root).parts
            if not path.is_file() or any(part in excluded_dirs for part in relative_parts):
                continue
            if path.name.startswith(("_", "~")) or path.suffix.casefold() in {".pyc", ".pyo", ".tmp"}:
                continue
            files.append(path)
    files.extend(
        path for path in (root / ".gitattributes", root / "README.md", root / "生成方法.md")
        if path.is_file()
    )
    return sorted(files, key=lambda path: str(path.relative_to(root)).replace("\\", "/"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rapid-root", type=Path, required=True)
    parser.add_argument("--skip-batch-solves", action="store_true")
    parser.add_argument("--write-release", action="store_true")
    args = parser.parse_args()
    root = args.rapid_root.resolve()
    errors: list[str] = release_mode_errors(args.skip_batch_solves, args.write_release)

    if not args.skip_batch_solves:
        for batch in range(1, 6):
            result = subprocess.run(
                [sys.executable, str(root / "scripts" / "validate_batch.py"), "--rapid-root", str(root), "--batch", str(batch)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode != 0:
                errors.append(f"batch_{batch:02d}_validation_failed")

    tasks: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    review_schema = json.loads((root / "schemas" / "independent_review.schema.json").read_text(encoding="utf-8"))
    review_validator = Draft202012Validator(review_schema, format_checker=FormatChecker())
    for batch in range(1, 6):
        batch_dir = root / "batches" / f"batch_{batch:02d}"
        try:
            tasks.extend(read_jsonl(batch_dir / "public" / "tasks_zh.jsonl"))
            audits.extend(read_jsonl(batch_dir / "private" / "rapid_audit.jsonl"))
            batch_reviews = read_jsonl(batch_dir / "private" / "independent_review.jsonl")
            reviews.extend(batch_reviews)
            for row in batch_reviews:
                for issue in review_validator.iter_errors(row):
                    errors.append(f"{row.get('id')}:review_schema:{'/'.join(map(str, issue.path))}:{issue.message}")
        except Exception as exc:
            errors.append(f"batch_{batch:02d}_read:{type(exc).__name__}:{exc}")

    expected_ids = [f"SWOR-R{number:03d}" for number in range(1, 101)]
    for label, rows in (("tasks", tasks), ("audits", audits), ("reviews", reviews)):
        ids = [row.get("id") for row in rows]
        if ids != expected_ids:
            errors.append(f"{label}_ids_or_count_invalid")

    contract = json.loads((root / "config" / "rapid_contract.json").read_text(encoding="utf-8"))
    primary_by_task, candidate_by_id, reservations_by_task = load_source_catalog(root)
    allowed_hosts_by_task: dict[str, set[str]] = {}
    for audit in audits:
        binding_errors, allowed_hosts = resolve_source_binding(
            audit, primary_by_task, candidate_by_id, reservations_by_task
        )
        allowed_hosts_by_task[audit.get("id")] = allowed_hosts
        errors.extend(f"{audit.get('id')}:source_binding:{error}" for error in binding_errors)
    if dict(Counter(row.get("family") for row in audits)) != contract["families"]:
        errors.append("family_quota_invalid")
    if dict(Counter(row.get("patch_class") for row in audits)) != contract["patch_classes"]:
        errors.append("patch_class_quota_invalid")
    over_cap = {
        key: count for key, count in Counter(row.get("source_document_key") for row in audits).items()
        if count > contract["per_page_task_cap"]
    }
    if over_cap:
        errors.append(f"source_document_cap_exceeded:{over_cap}")
    over_url_cap = {
        key: count for key, count in Counter(canonical_url(row.get("final_url", "")) for row in audits).items()
        if count > contract["per_page_task_cap"]
    }
    if over_url_cap:
        errors.append(f"source_url_cap_exceeded:{over_url_cap}")
    regulation_duplicates = duplicate_groups([
        (row.get("id", ""), row.get("regulation_key", "")) for row in audits
    ])
    if regulation_duplicates:
        errors.append(f"regulation_atoms_not_unique:{regulation_duplicates}")
    excerpt_duplicates = duplicate_groups([
        (
            row.get("id", ""),
            hashlib.sha256(re.sub(r"\s+", " ", row.get("support_excerpt", "")).strip().casefold().encode("utf-8")).hexdigest(),
        )
        for row in audits
    ])
    if excerpt_duplicates:
        errors.append(f"support_excerpts_not_unique:{excerpt_duplicates}")

    review_by_id = {row.get("id"): row for row in reviews}
    boolean_review_fields = [
        key for key, value in review_schema["properties"].items()
        if value == {"type": "boolean"}
    ]
    for audit in audits:
        task_id = audit.get("id")
        review = review_by_id.get(task_id)
        if review is None:
            continue
        if review.get("reviewer_id") == audit.get("generator_id"):
            errors.append(f"{task_id}:reviewer_is_generator")
        task_number = int(task_id.removeprefix("SWOR-R"))
        batch_number = (task_number - 1) // 20 + 1
        errors.extend(
            f"{task_id}:{error}"
            for error in reviewer_assignment_errors(contract, batch_number, review.get("reviewer_id"))
        )
        if review.get("artifact_fingerprint") != compute_fingerprint(root, batch_number, task_id):
            errors.append(f"{task_id}:stale_review_artifact_fingerprint")
        if review.get("status") != "PASS" or any(review.get(field) is not True for field in boolean_review_fields):
            errors.append(f"{task_id}:independent_review_not_pass")
        if audit.get("independent_review") != "PASS" or audit.get("status") != "RAPID_V0_PASS":
            errors.append(f"{task_id}:audit_not_release_pass")

    base_hash_rows: list[tuple[str, str]] = []
    topology_hash_rows: list[tuple[str, str]] = []
    for audit in audits:
        try:
            path = root / audit["base_model_path"]
            task_id = audit.get("id", "")
            base_hash_rows.append((task_id, hashlib.sha256(path.read_bytes()).hexdigest()))
            topology_hash_rows.append((task_id, topology_hash(load_model(path))))
        except Exception as exc:
            errors.append(f"{audit.get('id')}:base_identity:{type(exc).__name__}:{exc}")
    base_content_duplicates = duplicate_groups(base_hash_rows)
    if base_content_duplicates:
        errors.append(f"base_content_not_unique:{base_content_duplicates}")
    base_topology_duplicates = duplicate_groups(topology_hash_rows)
    if base_topology_duplicates:
        errors.append(f"base_topology_not_unique:{base_topology_duplicates}")

    repeated_ngrams: Counter[str] = Counter()
    ngram_task_ids: dict[str, set[str]] = {}
    for row in tasks:
        body = re.sub(r"请给出最优[^。]*。\s*$", "", row.get("problem_zh", ""))
        normalized = re.sub(r"\s+", "", body)
        normalized = re.sub(r"[A-Za-z0-9._-]+", "#", normalized)
        task_ngrams = {normalized[index:index + 14] for index in range(max(0, len(normalized) - 13))}
        repeated_ngrams.update(task_ngrams)
        for gram in task_ngrams:
            ngram_task_ids.setdefault(gram, set()).add(row.get("id", ""))
    templates = [
        gram for gram, count in repeated_ngrams.items()
        if count >= 5
        and "请给出最优" not in gram
        and "唯一目标" not in gram
        and "2026年8月2日" not in gram
    ]
    if templates:
        first_template = sorted(templates)[0]
        errors.append(f"global_template_ngram:{first_template}:{sorted(ngram_task_ids[first_template])}")

    try:
        source_rows = read_jsonl(root / "private" / "source_recheck.jsonl")
        if [row.get("id") for row in source_rows] != expected_ids:
            errors.append("source_recheck_ids_or_count_invalid")
        if any(row.get("status") != "PASS" for row in source_rows):
            errors.append("source_recheck_has_failures")
        audit_by_id = {row.get("id"): row for row in audits}
        for row in source_rows:
            task_id = row.get("id")
            audit = audit_by_id.get(task_id)
            if audit is None:
                continue
            for field in receipt_binding_errors(audit, row):
                errors.append(f"{task_id}:source_receipt_binding_mismatch:{field}")
            if official_host(row.get("final_url", "")) not in allowed_hosts_by_task.get(task_id, set()):
                errors.append(f"{task_id}:source_receipt_redirect_host_not_approved")
        over_content_cap = {
            key: count for key, count in Counter(row.get("content_sha256") for row in source_rows).items()
            if key and count > contract["per_page_task_cap"]
        }
        if over_content_cap:
            errors.append(f"source_content_cap_exceeded:{over_content_cap}")
    except Exception as exc:
        errors.append(f"source_recheck_missing_or_invalid:{type(exc).__name__}:{exc}")

    if errors:
        print(json.dumps({"status": "FAIL", "error_count": len(errors), "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    if args.write_release:
        write_jsonl(root / "public" / "tasks_zh.jsonl", tasks)
        write_jsonl(root / "private" / "rapid_audit.jsonl", audits)
        write_jsonl(root / "private" / "independent_review.jsonl", reviews)
        files = release_critical_files(root)
        manifest = {
            "schema_version": "searchworthyor.rapid_manifest.v0",
            "task_count": 100,
            "files": {str(path.relative_to(root)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
        }
        (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": "PASS", "task_count": 100, "release_written": args.write_release}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

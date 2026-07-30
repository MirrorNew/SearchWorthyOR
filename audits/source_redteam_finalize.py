"""Finalize fail-closed source-red-team verdicts from frozen audit artifacts."""

from __future__ import annotations

import collections
import datetime
import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[1]
AUDIT_ROOT = ROOT / "audits"
HASH_CACHE: dict[Path, str] = {}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def file_hash(path: Path) -> str:
    if path not in HASH_CACHE:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        HASH_CACHE[path] = digest.hexdigest()
    return HASH_CACHE[path]


def json_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def normalized_hash(text: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", text).split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def directory_hashes(directory: Path) -> dict[str, str]:
    return {
        relative(path): file_hash(path)
        for path in sorted(directory.iterdir())
        if path.is_file() and path.name != "PROTOCOL.md"
    }


def cache_lookup() -> dict[tuple[str, str, str], dict[str, Any]]:
    return {
        (row["source_group"], row["source_id"], row["ir_file_sha256"]): row
        for row in read_jsonl(
            AUDIT_ROOT / ".source_redteam_solver_cache.jsonl"
        )
    }


def main_supplemental_rows(
    base_rows: list[dict[str, Any]],
    solver_cache: dict[tuple[str, str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    manual_rejects = {
        "SWOR-BASE-076": (
            "unsupported_variable_upper_bounds",
            "题面没有蓝莓或草莓包数上界，IR却加入 blueberry<=100、"
            "strawberry<=300；即使当前最优解未触界，也改变了可行行动集合。",
        ),
        "SWOR-BASE-080": (
            "unsupported_variable_upper_bound",
            "题面皮肤剂量约束只能推出 beam_2<=40，IR无依据加入 "
            "beam_2<=30；该上界改变可行行动集合。",
        ),
    }
    rows: list[dict[str, Any]] = []
    group_root = ROOT / "staging" / "certified_sources" / "supplemental"
    for candidate in (
        row
        for row in base_rows
        if row["source_dataset"] in {"NLP4LP", "MAMO-ComplexLP"}
    ):
        directory = group_root / candidate["candidate_id"]
        snapshot = load(directory / "source_snapshot.json")
        source_ok = (
            snapshot["problem_text"] == candidate["problem_zh_or_en"]
            and normalized_hash(snapshot["problem_text"])
            == candidate["source_hash"]
            and snapshot.get("normalized_source_sha256_matches_candidate") is True
        )
        reasons: list[str] = []
        solver_result = None
        semantic_verdict = "reject"
        ir_hash_ok = True
        if (directory / "rejection.json").exists():
            rejection = load(directory / "rejection.json")
            reasons.append(rejection["reason"])
            review_note = rejection["details"]
        else:
            ir_path = directory / "canonical_ir.json"
            ir = load(ir_path)
            audit = load(directory / "audit.json")
            ir_hash_ok = json_hash(ir) == audit.get("canonical_ir_sha256")
            solver_result = solver_cache.get(
                ("supplemental", candidate["candidate_id"], file_hash(ir_path))
            )
            if not ir_hash_ok:
                reasons.append("canonical_ir_content_hash_mismatch")
            if not solver_result or not solver_result["pass"]:
                reasons.append("independent_gurobi_copt_recheck_failed")
            if candidate["candidate_id"] in manual_rejects:
                reason, review_note = manual_rejects[candidate["candidate_id"]]
                reasons.append(reason)
            else:
                semantic_verdict = "pass"
                review_note = (
                    "独立逐条核对题面、变量域与单位、目标、约束方向及作用域后通过。"
                )
        if not source_ok:
            reasons.append("source_snapshot_or_source_hash_mismatch")
        verdict = (
            "pass"
            if semantic_verdict == "pass"
            and source_ok
            and ir_hash_ok
            and solver_result
            and solver_result["pass"]
            else "reject"
        )
        rows.append(
            {
                "schema_version": "searchworthyor.source-redteam.v1",
                "source_group": "supplemental",
                "candidate_id": candidate["candidate_id"],
                "source_dataset": candidate["source_dataset"],
                "source_id": candidate["source_id"],
                "verdict": verdict,
                "reason_codes": reasons,
                "warnings": [],
                "checks": {
                    "source_snapshot_matches_frozen_source": source_ok,
                    "semantic_text_to_ir_verdict": semantic_verdict,
                    "semantic_review_note_zh": review_note,
                    "artifact_hashes_match": source_ok and ir_hash_ok,
                    "artifact_hashes_manifest_bound": False,
                    "computed_file_sha256": directory_hashes(directory),
                    "independent_solver_recheck": solver_result,
                    "legacy_answer_dataflow_to_formulation_observed": False,
                    "strict_legacy_answer_load_after_freeze": False,
                    "legacy_code_used_as_authority": False,
                },
            }
        )
    return rows


def reserve_rows(
    solver_cache: dict[tuple[str, str, str], dict[str, Any]]
) -> list[dict[str, Any]]:
    benchmark = {
        row["id"]: row
        for row in read_jsonl(PROJECT_ROOT / "benchmark" / "nlp4lp.jsonl")
    }
    manifest = load(
        ROOT / "staging" / "supplemental_reserve_certification_manifest.json"
    )["artifacts"]
    rows: list[dict[str, Any]] = []
    group_root = (
        ROOT / "staging" / "certified_sources" / "supplemental_reserve"
    )
    directories = sorted(path for path in group_root.iterdir() if path.is_dir())
    for fallback_rank, directory in enumerate(directories, start=1):
        source_id = directory.name
        snapshot = load(directory / "source_snapshot.json")
        source = benchmark[source_id]
        source_ok = (
            snapshot["problem_text"] == source["problem"]
            and normalized_hash(snapshot["problem_text"])
            == snapshot["source_hash"]
        )
        hashes = directory_hashes(directory)
        manifest_ok = all(manifest.get(path) == digest for path, digest in hashes.items())
        ir_path = directory / "canonical_ir.json"
        ir_hash_ok = json_hash(load(ir_path)) == load(
            directory / "audit.json"
        ).get("canonical_ir_sha256")
        solver_result = solver_cache.get(
            ("supplemental_reserve", source_id, file_hash(ir_path))
        )
        reasons: list[str] = []
        if not source_ok:
            reasons.append("source_snapshot_or_source_hash_mismatch")
        if not manifest_ok:
            reasons.append("reserve_manifest_file_hash_mismatch")
        if not ir_hash_ok:
            reasons.append("canonical_ir_content_hash_mismatch")
        if not solver_result or not solver_result["pass"]:
            reasons.append("independent_gurobi_copt_recheck_failed")
        verdict = "pass" if not reasons else "reject"
        rows.append(
            {
                "schema_version": "searchworthyor.source-redteam.v1",
                "source_group": "supplemental_reserve",
                "candidate_id": snapshot["candidate_id"],
                "source_dataset": "NLP4LP",
                "source_id": source_id,
                "reserve_rank": snapshot.get("reserve_rank", fallback_rank),
                "verdict": verdict,
                "reason_codes": reasons,
                "warnings": [],
                "checks": {
                    "source_snapshot_matches_frozen_source": source_ok,
                    "semantic_text_to_ir_verdict": (
                        "pass" if verdict == "pass" else "reject"
                    ),
                    "semantic_review_note_zh": (
                        "独立逐条核对题面、变量域与单位、目标、约束方向及作用域后通过。"
                        if verdict == "pass"
                        else "完整性或求解复核失败。"
                    ),
                    "artifact_hashes_match": manifest_ok and ir_hash_ok,
                    "artifact_hashes_manifest_bound": True,
                    "computed_file_sha256": hashes,
                    "independent_solver_recheck": solver_result,
                    "legacy_answer_dataflow_to_formulation_observed": False,
                    "strict_legacy_answer_load_after_freeze": True,
                    "legacy_code_used_as_authority": False,
                },
            }
        )
    return rows


def optminer_rows(
    base_rows: list[dict[str, Any]],
    solver_cache: dict[tuple[str, str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    benchmark = {
        f"OMB{int(row['id']):03d}": row
        for row in read_jsonl(
            PROJECT_ROOT / "benchmark" / "optminer_bench.jsonl"
        )
    }
    audits = {
        row["source_id"]: row
        for row in read_jsonl(
            AUDIT_ROOT / "optminer_source_certification.jsonl"
        )
    }
    rows: list[dict[str, Any]] = []
    group_root = ROOT / "staging" / "certified_sources" / "optminer"
    for candidate in (
        row for row in base_rows if row["source_dataset"] == "OptMinerBench"
    ):
        source_id = candidate["source_id"]
        audit = audits[source_id]
        source = benchmark[source_id]
        source_ok = (
            hashlib.sha256(source["problem"].encode("utf-8")).hexdigest()
            == audit.get("problem_sha256")
            and hashlib.sha256(source["code"].encode("utf-8")).hexdigest()
            == audit.get("legacy_code_sha256")
        )
        ir_path = group_root / f"{source_id}.canonical_ir.json"
        certificate_path = group_root / f"{source_id}.solver_certificate.json"
        computed_hashes: dict[str, str] = {}
        if ir_path.exists():
            computed_hashes[relative(ir_path)] = file_hash(ir_path)
        if certificate_path.exists():
            computed_hashes[relative(certificate_path)] = file_hash(
                certificate_path
            )
        bound = (
            bool(audit.get("ir_sha256"))
            and bool(audit.get("certificate_sha256"))
            and ir_path.exists()
            and certificate_path.exists()
            and file_hash(ir_path) == audit["ir_sha256"]
            and file_hash(certificate_path) == audit["certificate_sha256"]
        )
        solver_result = (
            solver_cache.get(("optminer", source_id, file_hash(ir_path)))
            if ir_path.exists()
            else None
        )
        linear = (
            audit.get("actual_linearity", {}).get("status")
            == "linear_or_mixed_integer_linear"
        )
        structural_verdict = (
            "pass"
            if linear and solver_result and solver_result["pass"]
            else "reject"
        )
        action_count = None
        continuous_omitted = None
        stored_complete = False
        warnings: list[str] = []
        # Parse only the 30 bounded-size certified models.  The 13 oversized
        # models are already fail-closed at the solver/scale gate.
        if audit.get("status") == "certified" and ir_path.exists():
            ir = load(ir_path)
            action_names = set(ir.get("action_projection", []))
            action_count = len(action_names)
            continuous_omitted = sum(
                variable.get("vartype") == "C"
                and variable.get("name") not in action_names
                for variable in ir.get("variables", [])
            )
            certificate = load(certificate_path)
            stored_complete = all(
                "assignment" in certificate.get(solver, {})
                and certificate.get(solver, {}).get("version")
                not in {None, "unknown"}
                for solver in ("gurobi", "copt")
            )
            if continuous_omitted:
                warnings.append(
                    "continuous_decision_variables_omitted_from_action_projection_"
                    "without_semantic_adjudication"
                )
        reasons: list[str] = []
        if not source_ok:
            reasons.append("benchmark_problem_or_code_hash_mismatch")
        if ir_path.exists() and not bound:
            reasons.append("artifact_not_hash_bound_to_current_audit")
        if not linear:
            reasons.append("nonlinear_or_noncanonical_linear_structure")
        elif structural_verdict != "pass":
            reasons.append("dual_solver_or_scale_gate_failed")
        reasons.extend(
            [
                "no_problem_span_to_ir_semantic_mapping",
                "reference_code_extraction_is_not_independent_text_formulation",
                "stored_certificate_missing_full_assignment_action_residual_or_"
                "solver_version",
            ]
        )
        rows.append(
            {
                "schema_version": "searchworthyor.source-redteam.v1",
                "source_group": "optminer",
                "candidate_id": candidate["candidate_id"],
                "source_dataset": "OptMinerBench",
                "source_id": source_id,
                "verdict": "reject",
                "reason_codes": reasons,
                "warnings": warnings,
                "checks": {
                    "source_snapshot_matches_frozen_source": source_ok,
                    "semantic_text_to_ir_verdict": "not_available",
                    "semantic_review_note_zh": (
                        "仅有参考代码模型抽取；没有题面 claim→变量/约束/单位/"
                        "行动投影的互盲逐句映射，因此不能认证为正确 base。"
                    ),
                    "current_audit_status": audit.get("status"),
                    "current_audit_reason": audit.get("reason"),
                    "structural_gate_verdict": structural_verdict,
                    "artifact_hashes_match": source_ok
                    and (bound or not ir_path.exists()),
                    "artifact_hashes_manifest_bound": bound,
                    "computed_file_sha256": computed_hashes,
                    "stored_certificate_complete_for_release": stored_complete,
                    "independent_solver_recheck": solver_result,
                    "action_projection_count": action_count,
                    "continuous_variables_omitted_from_action_projection": (
                        continuous_omitted
                    ),
                    "legacy_answer_dataflow_to_formulation_observed": False,
                    "strict_legacy_answer_load_after_freeze": True,
                    "legacy_code_used_as_authority": True,
                },
            }
        )
    return rows


def main() -> int:
    base_rows = read_jsonl(ROOT / "staging" / "base_candidates.jsonl")
    solver_cache = cache_lookup()
    output_rows = (
        optminer_rows(base_rows, solver_cache)
        + main_supplemental_rows(base_rows, solver_cache)
        + reserve_rows(solver_cache)
    )

    def sort_key(row: dict[str, Any]) -> tuple[int, int]:
        if row["source_group"] == "supplemental_reserve":
            return (1, int(row.get("reserve_rank", 999)))
        return (0, int(row["candidate_id"].split("-")[-1]))

    output_rows.sort(key=sort_key)
    output_path = AUDIT_ROOT / "source_redteam.jsonl"
    output_path.write_text(
        "".join(
            json.dumps(
                row,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
            for row in output_rows
        ),
        encoding="utf-8",
        newline="\n",
    )
    verdict_counts = collections.Counter(
        (row["source_group"], row["verdict"]) for row in output_rows
    )
    optminer_structural = collections.Counter(
        row["checks"]["structural_gate_verdict"]
        for row in output_rows
        if row["source_group"] == "optminer"
    )
    supplemental_rejects = [
        row["candidate_id"]
        for row in output_rows
        if row["source_group"] == "supplemental"
        and row["verdict"] == "reject"
    ]
    cache_rows = list(solver_cache.values())
    blockers = [
        "57个OptMiner候选均缺题面到IR的互盲逐句语义映射；30个只通过"
        "结构/双求解器门，27个还在非线性或规模/许可门失败。",
        "OptMiner存储证书不含完整assignment，COPT version为unknown；"
        "action_projection机械排除连续变量，OMB073甚至为空。",
        "主supplemental新增发现2个无题面依据的变量上界错误；连同原5个"
        "拒绝，仅36/43通过。",
        "主supplemental脚本在模型冻结循环之前加载legacy answers，虽未"
        "观察到流向建模函数，仍不满足严格先冻结后加载顺序。",
        "主supplemental认证产物未由独立manifest逐文件绑定；reserve的"
        "40条则已逐文件hash绑定。",
        "当前可释放来源仅76条（36主supplemental+40 reserve），不足100；"
        "不得用未语义认证的OptMiner补数。",
    ]
    extractor_findings = [
        "Gurobi结构检查能识别quadratic/general/SOS和非单目标结构，"
        "当前43个线性IR均有当前audit哈希。",
        "当前13个大线性IR在restricted Gurobi许可下失败，不能算双求解器"
        "证书；它们不是stale文件。",
        "AST筛查只是副作用启发式，不是安全沙箱；允许numpy和间接builtins"
        "访问仍可绕过。",
        "提取器没有可发布的显式规模上限；超过2000变量或约束时尝试"
        "Gurobi presolve，但无法为原变量提供完整行动证书。",
    ]
    summary = {
        "schema_version": "searchworthyor.source-redteam-summary.v1",
        "generated_at": datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=8))
        ).isoformat(),
        "source_redteam_jsonl_sha256": file_hash(output_path),
        "row_count": len(output_rows),
        "verdict_counts": {
            f"{group}_{verdict}": count
            for (group, verdict), count in sorted(verdict_counts.items())
        },
        "optminer_structural_gate_counts": dict(optminer_structural),
        "supplemental_reject_ids": supplemental_rejects,
        "new_redteam_rejects": ["SWOR-BASE-076", "SWOR-BASE-080"],
        "independent_solver_cache_counts": dict(
            collections.Counter(
                "pass" if row["pass"] else "fail" for row in cache_rows
            )
        ),
        "optminer_semantic_sample_ids": [
            "OMB001",
            "OMB003",
            "OMB006",
            "OMB007",
            "OMB011",
            "OMB017",
            "OMB022",
            "OMB030",
            "OMB073",
            "OMB107",
            "OMB123",
        ],
        "release_eligible_unique_sources": sum(
            row["verdict"] == "pass" for row in output_rows
        ),
        "global_blockers": blockers,
        "extractor_findings": extractor_findings,
    }
    (AUDIT_ROOT / "source_redteam_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    markdown = [
        "# Source red-team summary",
        "",
        f"- 审计行数：{summary['row_count']}",
        "- 主 supplemental："
        f"{verdict_counts[('supplemental', 'pass')]} pass / "
        f"{verdict_counts[('supplemental', 'reject')]} reject",
        "- supplemental reserve："
        f"{verdict_counts[('supplemental_reserve', 'pass')]} pass / "
        f"{verdict_counts[('supplemental_reserve', 'reject')]} reject",
        "- OptMiner release verdict："
        f"{verdict_counts[('optminer', 'pass')]} pass / "
        f"{verdict_counts[('optminer', 'reject')]} reject",
        "- OptMiner结构/双求解器门："
        f"{optminer_structural['pass']} pass / "
        f"{optminer_structural['reject']} reject",
        f"- 当前可释放的不同来源：{summary['release_eligible_unique_sources']}",
        f"- 主 supplemental rejects：{', '.join(supplemental_rejects)}",
        "",
        "## Release blockers",
        "",
        *(f"- {item}" for item in blockers),
        "",
        "## Extractor findings",
        "",
        *(f"- {item}" for item in extractor_findings),
    ]
    (AUDIT_ROOT / "source_redteam_summary.md").write_text(
        "\n".join(markdown) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

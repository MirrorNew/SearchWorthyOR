from __future__ import annotations

import argparse
import collections
import datetime as dt
import difflib
import hashlib
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any, Iterable


CLAUSE_RE = re.compile(r"第[^条\n]+条【([^】]+)】(.*)")
DATE_RE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(ordered[lo])
    return float(ordered[lo] * (hi - pos) + ordered[hi] * (pos - lo))


def summary(values: Iterable[float]) -> dict[str, float]:
    xs = [float(v) for v in values]
    if not xs:
        return {"min": 0.0, "mean": 0.0, "median": 0.0, "p95": 0.0, "max": 0.0}
    return {
        "min": min(xs),
        "mean": statistics.fmean(xs),
        "median": statistics.median(xs),
        "p95": percentile(xs, 0.95),
        "max": max(xs),
    }


def clause_fields(content: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in content.splitlines():
        match = CLAUSE_RE.fullmatch(line.strip())
        if match:
            fields[match.group(1).strip()] = re.sub(r"\s+", " ", match.group(2).strip())
    return fields


def latest_date(content: str) -> str:
    dates = ["-".join(match) for match in DATE_RE.findall(content)]
    return max(dates, default="")


def queryless_majority_choice(documents: list[dict[str, Any]]) -> str:
    parsed = {doc["id"]: clause_fields(doc["content"]) for doc in documents}
    all_labels = sorted({label for fields in parsed.values() for label in fields})
    modes: dict[str, set[str]] = {}
    for label in all_labels:
        values = [parsed[doc["id"]].get(label, "") for doc in documents]
        counter = collections.Counter(values)
        best = max(counter.values())
        modes[label] = {value for value, count in counter.items() if count == best and value}

    stable_labels = [
        "发布登记",
        "权限属性",
        "适用辖区",
        "适用主体",
        "例外核验",
    ]
    scored: list[tuple[int, str, str]] = []
    for doc in documents:
        fields = parsed[doc["id"]]
        score = sum(fields.get(label, "") in modes.get(label, set()) for label in stable_labels)
        scored.append((score, latest_date(doc["content"]), doc["id"]))
    scored.sort(reverse=True)
    return scored[0][2]


def queryless_medoid_choice(documents: list[dict[str, Any]]) -> str:
    normalized = {
        doc["id"]: re.sub(r"\s+", " ", doc["content"].casefold()).strip()
        for doc in documents
    }
    scores: list[tuple[float, str]] = []
    for doc in documents:
        doc_id = doc["id"]
        similarity_sum = sum(
            difflib.SequenceMatcher(None, normalized[doc_id], normalized[other["id"]]).ratio()
            for other in documents
            if other["id"] != doc_id
        )
        scores.append((similarity_sum, doc_id))
    scores.sort(reverse=True)
    return scores[0][1]


def variable_map(ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {variable["name"]: variable for variable in ir["variables"]}


def constraint_map(ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {constraint["name"]: constraint for constraint in ir["constraints"]}


def bound_signature(value: float) -> str:
    if value < 0:
        return "neg"
    if value > 0:
        return "pos"
    return "zero"


def patch_signature(
    base_ir: dict[str, Any],
    patched_ir: dict[str, Any],
) -> str:
    base_vars = variable_map(base_ir)
    patched_vars = variable_map(patched_ir)
    base_constraints = constraint_map(base_ir)
    patched_constraints = constraint_map(patched_ir)
    action = set(base_ir["action_projection"])

    added_vars = [
        (
            patched_vars[name]["vartype"],
            bound_signature(float(patched_vars[name]["lb"])),
            bound_signature(float(patched_vars[name]["ub"])),
        )
        for name in sorted(set(patched_vars) - set(base_vars))
    ]
    changed_vars = []
    for name in sorted(set(base_vars) & set(patched_vars)):
        before = base_vars[name]
        after = patched_vars[name]
        if (before["vartype"], before["lb"], before["ub"]) != (
            after["vartype"],
            after["lb"],
            after["ub"],
        ):
            changed_vars.append(
                (
                    before["vartype"],
                    bound_signature(float(before["lb"])),
                    bound_signature(float(before["ub"])),
                    after["vartype"],
                    bound_signature(float(after["lb"])),
                    bound_signature(float(after["ub"])),
                )
            )

    added_constraints = []
    for name in sorted(set(patched_constraints) - set(base_constraints)):
        constraint = patched_constraints[name]
        terms = constraint["terms"]
        signs = sorted("pos" if float(value) > 0 else "neg" for value in terms.values())
        added_constraints.append(
            (
                constraint["sense"],
                bound_signature(float(constraint["rhs"])),
                len(terms),
                sum(variable in action for variable in terms),
                len(terms) - sum(variable in action for variable in terms),
                tuple(signs),
            )
        )
    payload = {
        "added_vars": sorted(added_vars),
        "changed_vars": sorted(changed_vars),
        "added_constraints": sorted(added_constraints),
        "objective_changed": canonical_json(base_ir["objective"])
        != canonical_json(patched_ir["objective"]),
    }
    return sha256_text(canonical_json(payload))[:16]


def minimum_hamming(
    base_actions: list[list[int]],
    patched_actions: list[list[int]],
) -> int:
    return min(
        sum(int(left != right) for left, right in zip(base, patched))
        for base in base_actions
        for patched in patched_actions
    )


def analyze_task(
    dataset_root: Path,
    task: dict[str, Any],
    gold: dict[str, Any],
) -> dict[str, Any]:
    task_id = task["id"]
    model_dir = dataset_root / "models" / task_id
    base_ir = json.loads((model_dir / "base_ir.json").read_text(encoding="utf-8"))
    patched_ir = json.loads((model_dir / "patched_ir.json").read_text(encoding="utf-8"))
    solver = json.loads((model_dir / "solver_results.json").read_text(encoding="utf-8"))

    base_vars = variable_map(base_ir)
    patched_vars = variable_map(patched_ir)
    base_constraints = constraint_map(base_ir)
    patched_constraints = constraint_map(patched_ir)

    added_variables = sorted(set(patched_vars) - set(base_vars))
    removed_variables = sorted(set(base_vars) - set(patched_vars))
    changed_domains = [
        name
        for name in sorted(set(base_vars) & set(patched_vars))
        if (base_vars[name]["vartype"], base_vars[name]["lb"], base_vars[name]["ub"])
        != (
            patched_vars[name]["vartype"],
            patched_vars[name]["lb"],
            patched_vars[name]["ub"],
        )
    ]
    added_constraints = sorted(set(patched_constraints) - set(base_constraints))
    removed_constraints = sorted(set(base_constraints) - set(patched_constraints))
    changed_constraints = [
        name
        for name in sorted(set(base_constraints) & set(patched_constraints))
        if canonical_json(base_constraints[name]) != canonical_json(patched_constraints[name])
    ]

    base_actions = solver["base"]["exact_enumeration"]["optimal_actions"]
    patched_actions = solver["patched"]["exact_enumeration"]["optimal_actions"]
    base_obj = float(solver["base"]["exact_enumeration"]["objective"])
    patched_obj = float(solver["patched"]["exact_enumeration"]["objective"])
    patch_ops = gold["typed_patch"]["ops"]

    direct_small_append = (
        not removed_variables
        and not removed_constraints
        and not changed_constraints
        and len(added_variables) <= 1
        and len(added_constraints) <= 2
        and len(patch_ops) <= 3
    )

    return {
        "id": task_id,
        "family": gold["family"],
        "patch_class": gold["patch_class"],
        "evidence_mode": gold["evidence_mode"],
        "base_variables": len(base_vars),
        "patched_variables": len(patched_vars),
        "added_variables": added_variables,
        "removed_variables": removed_variables,
        "changed_domains": changed_domains,
        "base_constraints": len(base_constraints),
        "patched_constraints": len(patched_constraints),
        "added_constraints": added_constraints,
        "removed_constraints": removed_constraints,
        "changed_constraints": changed_constraints,
        "objective_changed": canonical_json(base_ir["objective"])
        != canonical_json(patched_ir["objective"]),
        "patch_ops": len(patch_ops),
        "patch_op_types": [op.get("op", "") for op in patch_ops],
        "patch_slot_types": [op.get("slot_type", "") for op in patch_ops],
        "minimum_action_hamming": minimum_hamming(base_actions, patched_actions),
        "base_optimal_actions": len(base_actions),
        "patched_optimal_actions": len(patched_actions),
        "objective_delta": patched_obj - base_obj,
        "objective_relative_delta": (
            (patched_obj - base_obj) / max(abs(base_obj), 1e-12)
        ),
        "direct_small_append": direct_small_append,
        "patch_signature": patch_signature(base_ir, patched_ir),
        "decision_intersection_empty": bool(solver["intersection_empty"]),
        "gold_adjudication": gold.get("adjudication", {}).get("label"),
    }


def build_report(dataset_root: Path) -> dict[str, Any]:
    tasks = read_jsonl(dataset_root / "public" / "tasks_zh.jsonl")
    gold_rows = read_jsonl(dataset_root / "private" / "gold.jsonl")
    evidence_rows = read_jsonl(dataset_root / "private" / "evidence_corpus.jsonl")
    gold_by_id = {row["id"]: row for row in gold_rows}
    evidence_by_id = {row["id"]: row for row in evidence_rows}

    per_task = [analyze_task(dataset_root, task, gold_by_id[task["id"]]) for task in tasks]

    majority_hits = 0
    medoid_hits = 0
    queryless_rows = []
    for gold in gold_rows:
        comparisons = gold["applicability"]["comparison"]
        candidate_ids = [row["evidence_id"] for row in comparisons]
        documents = [evidence_by_id[evidence_id] for evidence_id in candidate_ids]
        target = gold["applicability"]["selected_evidence_id"]
        majority = queryless_majority_choice(documents)
        medoid = queryless_medoid_choice(documents)
        majority_hits += int(majority == target)
        medoid_hits += int(medoid == target)
        queryless_rows.append(
            {
                "id": gold["id"],
                "target": target,
                "majority_choice": majority,
                "majority_correct": majority == target,
                "medoid_choice": medoid,
                "medoid_correct": medoid == target,
            }
        )

    patch_ops = collections.Counter(
        op
        for row in per_task
        for op in row["patch_op_types"]
        if op
    )
    patch_slots = collections.Counter(
        slot
        for row in per_task
        for slot in row["patch_slot_types"]
        if slot
    )
    signatures = collections.Counter(row["patch_signature"] for row in per_task)
    adjudications = collections.Counter(row["gold_adjudication"] for row in per_task)

    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "dataset_root": str(dataset_root.resolve()),
        "counts": {
            "tasks": len(tasks),
            "gold": len(gold_rows),
            "evidence_documents": len(evidence_rows),
            "families": dict(collections.Counter(row["family"] for row in per_task)),
            "patch_classes": dict(
                collections.Counter(row["patch_class"] for row in per_task)
            ),
            "evidence_modes": dict(
                collections.Counter(row["evidence_mode"] for row in per_task)
            ),
            "gold_adjudications": dict(adjudications),
        },
        "structural_patch": {
            "all_nonempty": all(
                row["added_variables"]
                or row["removed_variables"]
                or row["changed_domains"]
                or row["added_constraints"]
                or row["removed_constraints"]
                or row["changed_constraints"]
                or row["objective_changed"]
                for row in per_task
            ),
            "objective_changed_tasks": sum(row["objective_changed"] for row in per_task),
            "variable_added_tasks": sum(bool(row["added_variables"]) for row in per_task),
            "variable_removed_tasks": sum(bool(row["removed_variables"]) for row in per_task),
            "domain_changed_tasks": sum(bool(row["changed_domains"]) for row in per_task),
            "constraint_added_tasks": sum(bool(row["added_constraints"]) for row in per_task),
            "constraint_removed_tasks": sum(bool(row["removed_constraints"]) for row in per_task),
            "constraint_changed_tasks": sum(bool(row["changed_constraints"]) for row in per_task),
            "direct_small_append_tasks": sum(row["direct_small_append"] for row in per_task),
            "patch_ops_per_task": summary(row["patch_ops"] for row in per_task),
            "added_variables_per_task": summary(
                len(row["added_variables"]) for row in per_task
            ),
            "added_constraints_per_task": summary(
                len(row["added_constraints"]) for row in per_task
            ),
            "patch_op_types": dict(patch_ops),
            "patch_slot_types": dict(patch_slots),
            "unique_anonymized_patch_signatures": len(signatures),
            "largest_patch_signature_frequency": max(signatures.values()),
            "patch_signature_histogram": dict(signatures),
        },
        "decision_effect": {
            "all_intersections_empty": all(
                row["decision_intersection_empty"] for row in per_task
            ),
            "minimum_action_hamming": summary(
                row["minimum_action_hamming"] for row in per_task
            ),
            "base_optimal_action_count": summary(
                row["base_optimal_actions"] for row in per_task
            ),
            "patched_optimal_action_count": summary(
                row["patched_optimal_actions"] for row in per_task
            ),
            "objective_relative_delta_abs": summary(
                abs(row["objective_relative_delta"]) for row in per_task
            ),
        },
        "queryless_evidence_attack": {
            "uses_task_text": False,
            "candidate_group_source": "gold comparison, standing in for the four retrieved candidates",
            "majority_plus_latest_accuracy": majority_hits / len(gold_rows),
            "full_text_medoid_accuracy": medoid_hits / len(gold_rows),
            "random_baseline": 0.25,
            "rows": queryless_rows,
        },
        "per_task": per_task,
    }


def render_markdown(report: dict[str, Any]) -> str:
    counts = report["counts"]
    patch = report["structural_patch"]
    effect = report["decision_effect"]
    attack = report["queryless_evidence_attack"]
    adjudications = ", ".join(
        f"`{key}`={value}" for key, value in counts["gold_adjudications"].items()
    )
    return f"""# SearchWorthyOR 数据结构与非平凡性审计

生成时间：{report["generated_at"]}

## 数据与 Gold 状态

- 任务：{counts["tasks"]}
- Gold：{counts["gold"]}
- 证据文档：{counts["evidence_documents"]}
- Gold adjudication：{adjudications}

## 模型补丁的真实结构规模

- 100 条是否都有非空结构变化：{patch["all_nonempty"]}
- 增加变量的任务：{patch["variable_added_tasks"]}
- 修改变量域的任务：{patch["domain_changed_tasks"]}
- 增加约束的任务：{patch["constraint_added_tasks"]}
- 修改既有约束的任务：{patch["constraint_changed_tasks"]}
- 修改目标结构的任务：{patch["objective_changed_tasks"]}
- 满足“至多 1 个新变量、至多 2 个新约束、至多 3 个 Gold op，且只追加不改写”的任务：
  {patch["direct_small_append_tasks"]}/{counts["tasks"]}
- 每题 Gold op：均值 {patch["patch_ops_per_task"]["mean"]:.2f}，中位数
  {patch["patch_ops_per_task"]["median"]:.2f}，最大 {patch["patch_ops_per_task"]["max"]:.0f}
- 每题新增约束：均值 {patch["added_constraints_per_task"]["mean"]:.2f}，最大
  {patch["added_constraints_per_task"]["max"]:.0f}
- 变量名与系数值匿名化后的 patch 签名：{patch["unique_anonymized_patch_signatures"]} 种；
  最大单一签名覆盖 {patch["largest_patch_signature_frequency"]} 题。

## 决策影响

- base/patched 完整最优行动集合是否全部不相交：{effect["all_intersections_empty"]}
- 两集合最小 Hamming 距离：均值 {effect["minimum_action_hamming"]["mean"]:.3f}，
  中位数 {effect["minimum_action_hamming"]["median"]:.3f}，最大
  {effect["minimum_action_hamming"]["max"]:.0f}
- 目标值相对变化绝对值：均值 {effect["objective_relative_delta_abs"]["mean"]:.4f}，
  中位数 {effect["objective_relative_delta_abs"]["median"]:.4f}

这说明证据补丁确实改变了最优行动，而不只是改变解释文本或 RHS 数字；但结构改动是否足够困难，
还要结合下面的低能力对照判断。

## 不看题面的证据选择攻击

- 条款多数值 + 最晚日期 tie-break：{attack["majority_plus_latest_accuracy"]:.1%}
- 全文 medoid：{attack["full_text_medoid_accuracy"]:.1%}
- 随机基线：{attack["random_baseline"]:.1%}

攻击不读取 public task，只查看一题的四份候选文档。若其准确率显著高于随机，
则 corpus-search 高分不能单独证明 Agent 理解了实体、日期、辖区、主体和例外。

## 当前解释边界

1. Gold 模型证书可以用于评测“给定证据后的结构建模与 Gurobi 求解”。
2. 当前盲审 adjudication 必须与 baseline 分数同时披露，不能把数据称为已通过 release gate。
3. 搜索能力必须通过 queryless、distractor-only 和 counterfactual-swap 负对照后才可归因。
4. 若大多数 patch 落入小规模直接追加，数据更像 evidence-to-formulation 单步转换测试，
   不能直接代表开放世界的复杂 OR 搜索建模。
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--json-out", required=True, type=Path)
    parser.add_argument("--markdown-out", required=True, type=Path)
    args = parser.parse_args()

    report = build_report(args.dataset_root)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.markdown_out.write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "tasks": report["counts"]["tasks"],
                "gold_adjudications": report["counts"]["gold_adjudications"],
                "queryless_majority_accuracy": report["queryless_evidence_attack"][
                    "majority_plus_latest_accuracy"
                ],
                "queryless_medoid_accuracy": report["queryless_evidence_attack"][
                    "full_text_medoid_accuracy"
                ],
                "unique_patch_signatures": report["structural_patch"][
                    "unique_anonymized_patch_signatures"
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

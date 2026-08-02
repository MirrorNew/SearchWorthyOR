from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
import networkx as nx

from solve_model_pair import evaluate, load_model, redundant_constraints


BANNED_PUBLIC_FRAGMENTS = (
    "http://", "https://", "SRCV2-", "W-D-", "规则原子", "结构补丁",
    "evidence-to", "claim-to", "需要检索", "搜索过程", "来源裁决",
    "Gurobi", "COPT", "数学模型", "增加约束", "修改变量",
    "除上述条件外，不使用隐含", "所有可行方案均按题面给定",
    "可作出的动作包括", "每项动作只有选择或不选择两种状态",
    "最终安排还须符合上述规定", "在满足这些运营条件以及合规要求的前提下",
    "开始本期定案", "候选数据如下", "只以压低", "只以提高",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    payload = path.read_bytes()
    if payload.startswith(b"\xef\xbb\xbf") or b"\r" in payload:
        raise ValueError(f"{path}: must be UTF-8 without BOM and LF-only")
    rows = []
    for number, line in enumerate(payload.decode("utf-8").splitlines(), 1):
        if not line.strip():
            raise ValueError(f"{path}:{number}: blank line")
        rows.append(json.loads(line))
    return rows


def structural_signature(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "variables": [
            (item["name"], item["type"], item["lb"], item["ub"])
            for item in model["variables"]
        ],
        "objective_sense": model["objective"]["sense"],
        "objective_support": sorted(
            name for name, coefficient in model["objective"]["coefficients"].items()
            if abs(float(coefficient)) > 1e-12
        ),
        "constraints": [
            (item["name"], item["sense"], tuple(sorted(item["coefficients"])))
            for item in model["constraints"]
        ],
        "action_projection": model["action_projection"],
    }


def patch_delta_targets(base: dict[str, Any], patched: dict[str, Any]) -> set[str]:
    base_variables = {item["name"]: item for item in base["variables"]}
    patched_variables = {item["name"]: item for item in patched["variables"]}
    base_constraints = {item["name"]: item for item in base["constraints"]}
    patched_constraints = {item["name"]: item for item in patched["constraints"]}
    targets = {
        f"variable:{name}"
        for name, item in patched_variables.items()
        if name not in base_variables or item != base_variables[name]
    }
    targets.update(
        f"constraint:{name}"
        for name, item in patched_constraints.items()
        if name not in base_constraints or item != base_constraints[name]
    )
    if base["objective"] != patched["objective"]:
        targets.add(f"objective:{patched['objective'].get('meaning', '')}")
    return targets


def topology_hash(model: dict[str, Any]) -> str:
    graph = nx.Graph()
    variable_index = {item["name"]: index for index, item in enumerate(model["variables"])}
    action_names = set(model["action_projection"])
    objective_support = {
        name for name, coefficient in model["objective"]["coefficients"].items()
        if abs(float(coefficient)) > 1e-12
    }
    for item in model["variables"]:
        domain_kind = "binary" if item["type"] == "BINARY" else (
            "fixed_integer" if item["lb"] == item["ub"] else "bounded_integer"
        )
        graph.add_node(
            f"v{variable_index[item['name']]}",
            label=f"var:{domain_kind}:action={item['name'] in action_names}:objective={item['name'] in objective_support}",
        )
    graph.add_node("objective", label=f"objective:{model['objective']['sense']}")
    for name, coefficient in model["objective"]["coefficients"].items():
        if abs(float(coefficient)) > 1e-12:
            graph.add_edge("objective", f"v{variable_index[name]}", label="+" if coefficient > 0 else "-")
    for index, constraint in enumerate(model["constraints"]):
        node = f"c{index}"
        graph.add_node(node, label=f"constraint:{constraint['sense']}")
        for name, coefficient in constraint["coefficients"].items():
            if abs(float(coefficient)) > 1e-12:
                graph.add_edge(node, f"v{variable_index[name]}", label="+" if coefficient > 0 else "-")
    return nx.weisfeiler_lehman_graph_hash(graph, node_attr="label", edge_attr="label")


def repeated_long_sentences(problem: str, minimum_length: int = 12) -> list[str]:
    sentences = [re.sub(r"\s+", "", part).strip() for part in re.split(r"[。！？]", problem)]
    counts = Counter(sentence for sentence in sentences if len(sentence) >= minimum_length)
    return sorted(sentence for sentence, count in counts.items() if count > 1)


def quantitative_compliance_leakage(problem: str) -> list[str]:
    leaked: list[str] = []
    for sentence in re.split(r"[。！？]", problem):
        marker = re.search(r"(?:需要|必须|还应|还须|须).{0,12}(?:遵守|符合)", sentence)
        if marker is None:
            continue
        requirement = sentence[marker.end():]
        if re.search(r"\d+(?:\.\d+)?\s*(?:%|％|年|月|日|天|小时|分钟|个|项|类|份|次|吨|千克|公斤|万元|亿元|分)", requirement):
            leaked.append(sentence.strip())
            continue
        if re.search(r"(?:至少|至多|不得|只能|方可|必须在|应在)", requirement):
            leaked.append(sentence.strip())
    return leaked


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rapid-root", type=Path, required=True)
    parser.add_argument("--batch", type=int, required=True, choices=range(1, 6))
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    root = args.rapid_root.resolve()
    batch_dir = root / "batches" / f"batch_{args.batch:02d}"
    task_path = batch_dir / "public" / "tasks_zh.jsonl"
    audit_path = batch_dir / "private" / "rapid_audit.jsonl"
    errors: list[str] = []
    try:
        tasks = read_jsonl(task_path)
        audits = read_jsonl(audit_path)
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "errors": [f"read:{type(exc).__name__}:{exc}"]}, ensure_ascii=False))
        return 1
    first = (args.batch - 1) * 20 + 1
    expected_ids = [f"SWOR-R{number:03d}" for number in range(first, first + 20)]
    task_ids = [row.get("id") for row in tasks]
    audit_ids = [row.get("id") for row in audits]
    accepted_ids = expected_ids[:len(tasks)] if args.allow_partial else expected_ids
    if task_ids != accepted_ids:
        errors.append("public_ids_or_count_invalid")
    if audit_ids != accepted_ids or len(audits) != len(tasks):
        errors.append("audit_ids_or_count_invalid")
    audit_schema = json.loads((root / "schemas" / "rapid_audit.schema.json").read_text(encoding="utf-8"))
    model_schema = json.loads((root / "schemas" / "model_ir.schema.json").read_text(encoding="utf-8"))
    audit_validator = Draft202012Validator(audit_schema, format_checker=FormatChecker())
    model_validator = Draft202012Validator(model_schema)
    task_by_id = {row.get("id"): row for row in tasks}
    for row in tasks:
        task_id = row.get("id")
        if set(row) != {"id", "problem_zh"}:
            errors.append(f"{task_id}:public_fields_invalid")
        problem = row.get("problem_zh")
        if not isinstance(problem, str) or len(problem) < 120:
            errors.append(f"{task_id}:problem_too_short")
            continue
        if "某" in problem:
            errors.append(f"{task_id}:contains_某")
        duplicate_sentences = repeated_long_sentences(problem)
        if duplicate_sentences:
            errors.append(f"{task_id}:repeated_sentence:{duplicate_sentences[0]}")
        compliance_leakage = quantitative_compliance_leakage(problem)
        if compliance_leakage:
            errors.append(f"{task_id}:quantitative_compliance_leakage:{compliance_leakage[0]}")
        if re.search(r"[〇零一二三四五六七八九十百千万两]+(?:家|项|类|名|份|个|天|日|小时|分钟|吨|万元|亿元|分|点|次|条|组|架|辆|所|座|期|年|月)", problem):
            errors.append(f"{task_id}:non_arabic_numeric_surface")
        for fragment in BANNED_PUBLIC_FRAGMENTS:
            if fragment.casefold() in problem.casefold():
                errors.append(f"{task_id}:public_leakage:{fragment}")
        if re.search(r"(?:第\s*\d+\s*条|§\s*\d+|Article\s+\d+)", problem, re.IGNORECASE):
            errors.append(f"{task_id}:exact_clause_leakage")
        if not re.search(r"20\d{2}年\d{1,2}月\d{1,2}日", problem):
            errors.append(f"{task_id}:decision_date_not_explicit")
        if not re.search(r"(?:需要|必须|还应|还须|须).{0,12}(?:遵守|符合)", problem):
            errors.append(f"{task_id}:natural_compliance_requirement_missing")
        if len(re.findall(r"(?:目标|目的|最小化|最大化|最低|最高)", problem)) == 0:
            errors.append(f"{task_id}:single_objective_not_stated")
        if not re.search(r"请给出最优[^。]{0,40}(?:目标值|总成本|总利润|总收益|总风险|方案)[^。]*。\s*$", problem):
            errors.append(f"{task_id}:final_question_not_minimal")
    repeated_ngrams: Counter[str] = Counter()
    for row in tasks:
        body = re.sub(r"请给出最优[^。]*。\s*$", "", row.get("problem_zh", ""))
        normalized = re.sub(r"\s+", "", body)
        normalized = re.sub(r"[A-Za-z0-9._-]+", "#", normalized)
        repeated_ngrams.update({normalized[index:index + 14] for index in range(max(0, len(normalized) - 13))})
    template_ngrams = [
        gram for gram, count in repeated_ngrams.items()
        if count >= 5
        and "请给出最优" not in gram
        and "唯一目标" not in gram
        and "2026年8月2日" not in gram
    ]
    if template_ngrams:
        errors.append(f"cross_task_template_ngram:{sorted(template_ngrams)[0]}")
    objective_fraction_suffixes: Counter[str] = Counter()
    for audit in audits:
        task_id = audit.get("id")
        for issue in audit_validator.iter_errors(audit):
            errors.append(f"{task_id}:audit_schema:{'/'.join(map(str, issue.path))}:{issue.message}")
        try:
            base_path = root / audit["base_model_path"]
            patched_path = root / audit["patched_model_path"]
            result_path = root / audit["solve_result_path"]
            base = load_model(base_path)
            patched = load_model(patched_path)
            task_fraction_suffixes = set()
            for coefficient in base["objective"]["coefficients"].values():
                rendered = f"{abs(float(coefficient)):.8f}".rstrip("0").rstrip(".")
                if "." in rendered:
                    task_fraction_suffixes.add(rendered.split(".", 1)[1])
            objective_fraction_suffixes.update(task_fraction_suffixes)
            for issue in model_validator.iter_errors(base):
                errors.append(f"{task_id}:base_schema:{'/'.join(map(str, issue.path))}:{issue.message}")
            for issue in model_validator.iter_errors(patched):
                errors.append(f"{task_id}:patched_schema:{'/'.join(map(str, issue.path))}:{issue.message}")
            if base["id"] != task_id or patched["id"] != task_id:
                errors.append(f"{task_id}:model_id_mismatch")
            if base["family"] != audit.get("family") or patched["family"] != audit.get("family"):
                errors.append(f"{task_id}:model_family_not_audit")
            if (
                base["source_candidate_id"] != audit.get("source_candidate_id")
                or patched["source_candidate_id"] != audit.get("source_candidate_id")
            ):
                errors.append(f"{task_id}:model_source_candidate_not_audit")
            if base["objective"]["sense"] != patched["objective"]["sense"]:
                errors.append(f"{task_id}:objective_direction_changed")
            if structural_signature(base) == structural_signature(patched):
                errors.append(f"{task_id}:patch_is_numeric_only_or_empty")
            directly_fixed_actions = set()
            action_names = set(base["action_projection"])
            for constraint in base["constraints"]:
                if len(constraint["coefficients"]) != 1:
                    continue
                name, coefficient = next(iter(constraint["coefficients"].items()))
                if name not in action_names or abs(float(coefficient)) <= 1e-12:
                    continue
                implied_value = float(constraint["rhs"]) / float(coefficient)
                variable = next(item for item in base["variables"] if item["name"] == name)
                if constraint["sense"] == "=" or (
                    constraint["sense"] == "<=" and implied_value <= variable["lb"]
                ) or (
                    constraint["sense"] == ">=" and implied_value >= variable["ub"]
                ):
                    directly_fixed_actions.add(name)
            if directly_fixed_actions:
                errors.append(f"{task_id}:base_directly_fixed_pseudo_decisions:{','.join(sorted(directly_fixed_actions))}")
            base_constraint_names = {constraint["name"] for constraint in base["constraints"]}
            for variant_name, model in (("base", base), ("patched", patched)):
                redundant = redundant_constraints(model)
                if variant_name == "patched":
                    redundant = [name for name in redundant if name not in base_constraint_names]
                if redundant:
                    errors.append(f"{task_id}:{variant_name}_redundant_constraints:{','.join(redundant)}")
                used_variables = set(model["objective"]["coefficients"]) | set(model["action_projection"])
                used_variables.update(name for constraint in model["constraints"] for name in constraint["coefficients"])
                orphaned = sorted({item["name"] for item in model["variables"]} - used_variables)
                if orphaned:
                    errors.append(f"{task_id}:{variant_name}_orphan_variables:{','.join(orphaned)}")
            variable_names = {item["name"] for item in base["variables"]}
            aligned_names = {item["variable"] for item in audit["variable_alignment"]}
            if variable_names != aligned_names:
                errors.append(f"{task_id}:base_variable_alignment_incomplete")
            constraint_names = {item["name"] for item in base["constraints"]}
            aligned_constraints = {item["constraint"] for item in audit["constraint_alignment"]}
            if constraint_names != aligned_constraints:
                errors.append(f"{task_id}:base_constraint_alignment_incomplete")
            problem = task_by_id[task_id]["problem_zh"]
            patched_variables = {item["name"] for item in patched["variables"]}
            patched_constraints = {item["name"] for item in patched["constraints"]}
            delta_targets = patch_delta_targets(base, patched)
            for item in audit.get("task_local_fact_alignment", []):
                public_basis = item["public_basis"]
                if public_basis not in problem:
                    errors.append(f"{task_id}:local_fact_not_public:{public_basis}")
                if ":" not in item["patch_binding"]:
                    continue
                binding_kind, binding_name = item["patch_binding"].split(":", 1)
                if binding_kind == "variable" and binding_name not in patched_variables:
                    errors.append(f"{task_id}:local_fact_unknown_variable:{binding_name}")
                elif binding_kind == "constraint" and binding_name not in patched_constraints:
                    errors.append(f"{task_id}:local_fact_unknown_constraint:{binding_name}")
                elif binding_kind == "objective" and binding_name != patched["objective"].get("meaning"):
                    errors.append(f"{task_id}:local_fact_unknown_objective:{binding_name}")
                if item["patch_binding"] not in delta_targets:
                    errors.append(f"{task_id}:local_fact_binding_not_model_delta:{item['patch_binding']}")
            numeric_alignment = audit["numeric_alignment"]
            covered_numeric_spans: set[tuple[int, int]] = set()
            for item in numeric_alignment:
                surface = item["surface"]
                if surface not in problem:
                    errors.append(f"{task_id}:numeric_surface_not_in_problem:{item['surface']}")
                    continue
                start = 0
                while True:
                    index = problem.find(surface, start)
                    if index < 0:
                        break
                    end = index + len(surface)
                    for number in re.finditer(r"\d+(?:\.\d+)?%?", problem):
                        if index <= number.start() and number.end() <= end:
                            covered_numeric_spans.add(number.span())
                    start = index + 1
            uncovered_numbers = [match.group(0) for match in re.finditer(r"\d+(?:\.\d+)?%?", problem) if match.span() not in covered_numeric_spans]
            if uncovered_numbers:
                errors.append(f"{task_id}:unbound_public_numbers:{','.join(uncovered_numbers)}")
            regenerated = evaluate(base_path, patched_path)
            recorded = json.loads(result_path.read_text(encoding="utf-8"))
            if regenerated != recorded:
                errors.append(f"{task_id}:solve_result_not_reproducible")
            if regenerated["common_optimal_action_feasible"]:
                errors.append(f"{task_id}:optimal_action_sets_overlap")
        except Exception as exc:
            errors.append(f"{task_id}:model_validation:{type(exc).__name__}:{exc}")
        if task_id not in task_by_id:
            errors.append(f"{task_id}:audit_without_public_task")
    repeated_fraction = [suffix for suffix, count in objective_fraction_suffixes.items() if count >= 8]
    if repeated_fraction:
        errors.append(f"repeated_objective_fraction_pattern:{sorted(repeated_fraction)[0]}")
    source_documents = [row.get("source_document_key") for row in audits]
    if any(count > 3 for count in __import__("collections").Counter(source_documents).values()):
        errors.append("source_document_cap_exceeded")
    base_hashes = []
    for audit in audits:
        try:
            base_hashes.append(hashlib.sha256((root / audit["base_model_path"]).read_bytes()).hexdigest())
        except Exception:
            pass
    if len(base_hashes) != len(set(base_hashes)):
        errors.append("duplicate_base_model_bytes")
    topology_hashes = []
    for audit in audits:
        try:
            topology_hashes.append(topology_hash(load_model(root / audit["base_model_path"])))
        except Exception:
            pass
    if len(topology_hashes) != len(set(topology_hashes)):
        errors.append("duplicate_base_model_topology")
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "batch": args.batch, "task_count": len(tasks), "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

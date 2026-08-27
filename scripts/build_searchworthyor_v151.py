from __future__ import annotations

import argparse
import itertools
import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable


WORKFLOW_ROOT = Path(__file__).resolve().parents[1]
SOURCE = WORKFLOW_ROOT / "datasets" / "SearchWorthyOR-v1.4.4"
TARGET = WORKFLOW_ROOT / "datasets" / "SearchWorthyOR-v1.5.1"
SPEC_SOURCE = SOURCE / "V151_CASE_REPAIR_SKILL_DRAFT_zh.md"
README_TEMPLATE = Path(__file__).with_name("v151_README_zh.md")
REPAIR_PARTS = [Path(__file__).with_name(f"v151_case_repairs_{part}.json") for part in "ABC"]

EXPECTED_TASK_IDS = [f"SWOR-R{index:03d}" for index in range(1, 121)]
EXPECTED_CASE_FIELDS = {"decision_date", "jurisdiction", "regulated_subject", "boundary_facts"}
ALLOWED_ISSUES = {f"L{index}" for index in range(1, 8)}

CASE_BASE_SEMANTICS_CONTRACT = (
    "本 case 的日期、辖区、主体和对象属性由“本 case 权威事实”给出；候选 action_id、题内数值与成本、预算、"
    "互斥关系、基础约束和目标函数由“优化骨架”给出，候选行动均为当前业务可执行选项。"
)
INTERPRETATION_PRIORITY = (
    "本 case 权威事实描述现实对象、主体、辖区与日期；优化骨架描述候选行动、题内数值和基础模型。"
    "外部权威证据只提供题外规则边界，题内业务事实提供规则后果与候选行动之间的映射。"
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def is_placeholder_action_meaning(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("题面第")
        and value.endswith("项候选行动（按首次出现顺序）")
    )


def expand_placeholder_action_meanings(records: dict[str, dict[str, Any]]) -> None:
    """Persist explicit action semantics for legacy position-only public labels."""
    source_tasks = {row["id"]: row for row in read_jsonl(SOURCE / "public" / "tasks_zh.jsonl")}
    source_gold = {row["id"]: row for row in read_jsonl(SOURCE / "private" / "gold.jsonl")}
    positional_meta = "题面候选按首次出现顺序对应output_schema行动；请返回最优行动、目标值及单位。"
    canonical_output_request = "请按output_schema中的action_id返回最优行动，并给出目标值及其单位。"
    for task_id in EXPECTED_TASK_IDS:
        record = records[task_id]
        overrides = record["output_schema_meaning_overrides"]
        if not isinstance(overrides, dict):
            raise AssertionError(f"{task_id}: output_schema_meaning_overrides must be an object")
        mapping = source_gold[task_id]["public_to_private_action_map"]
        base_ir = read_json(SOURCE / "models" / task_id / "base_ir.json")
        variable_meanings = {row["name"]: row["meaning"] for row in base_ir["variables"]}
        derived_ids: list[str] = []
        for action in source_tasks[task_id]["output_schema"]["actions"]:
            public_id = action["id"]
            if not is_placeholder_action_meaning(action.get("meaning")) or public_id in overrides:
                continue
            private_name = mapping.get(public_id)
            meaning = variable_meanings.get(private_name)
            if not isinstance(meaning, str) or not meaning.strip() or is_placeholder_action_meaning(meaning):
                raise AssertionError(
                    f"{task_id}/{public_id}: cannot replace position-only action meaning from Base IR"
                )
            overrides[public_id] = meaning
            derived_ids.append(public_id)
        removed_meta = positional_meta in source_tasks[task_id]["problem_zh"]
        if removed_meta and positional_meta not in {
            replacement["old"] for replacement in record["source_replacements"]
        }:
            record["source_replacements"].append(
                {"old": positional_meta, "new": canonical_output_request}
            )
        if derived_ids or removed_meta:
            issues = (["L3"] if removed_meta else []) + (["L5"] if derived_ids else [])
            for issue in issues:
                if issue not in record["issue_types"]:
                    record["issue_types"].append(issue)
            record["issue_types"].sort(key=lambda value: int(value[1:]))
            record["review_outcome"] = "FIX"
            notes: list[str] = []
            if derived_ids:
                notes.append(
                    f"将{len(derived_ids)}个仅按出现顺序解释的公开action meaning替换为Base IR中的明确业务语义"
                )
            if removed_meta:
                notes.append("删除题面中的顺序映射元说明")
            record["review_notes"] = record["review_notes"].rstrip("。") + "；" + "；".join(notes) + "。"


def expand_objective_unit_corrections(records: dict[str, dict[str, Any]]) -> None:
    """Record and repair source Gold equivalents that violate public unit factors."""
    source_tasks = {row["id"]: row for row in read_jsonl(SOURCE / "public" / "tasks_zh.jsonl")}
    source_gold = {row["id"]: row for row in read_jsonl(SOURCE / "private" / "gold.jsonl")}
    source_cases: dict[str, dict[str, dict[str, Any]]] = {}
    for row in read_jsonl(SOURCE / "private" / "applicability_gold.jsonl"):
        suffix = row["case_id"].rsplit("-", 1)[-1]
        source_cases.setdefault(row["source_task_id"], {})[suffix] = row
    for task_id in EXPECTED_TASK_IDS:
        record = records[task_id]
        accepted_units = source_tasks[task_id]["output_schema"]["objective"]["accepted_units"]
        contracts = {
            "private/gold.jsonl": source_gold[task_id]["objective_value_contract"],
            "models/solve_result.json": read_json(
                SOURCE / "models" / task_id / "solve_result.json"
            )["objective_value_contract"],
            "private/applicability_gold.jsonl:C1": source_cases[task_id]["C1"]["gold_objective"],
            "private/applicability_gold.jsonl:C2": source_cases[task_id]["C2"]["gold_objective"],
        }
        corrections: list[dict[str, Any]] = []
        for location, contract in contracts.items():
            corrected = objective_contract_with_value(
                contract, float(contract["canonical_value"]), accepted_units
            )
            if corrected != contract:
                corrections.append(
                    {"location": location, "old": deepcopy(contract), "new": corrected}
                )
        if not corrections:
            record["objective_unit_correction"] = None
            continue
        record["objective_unit_correction"] = {
            "corrections": corrections,
            "reason": "按公开 accepted_units 的换算因子重建 accepted_equivalents。",
        }
        if "L6" not in record["issue_types"]:
            record["issue_types"].append("L6")
            record["issue_types"].sort(key=lambda value: int(value[1:]))
        record["review_outcome"] = "FIX"
        record["review_notes"] = (
            record["review_notes"].rstrip("。")
            + "；修正目标值 accepted_equivalents 与公开 accepted_units 不一致的问题。"
        )


def load_repairs() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path in REPAIR_PARTS:
        if not path.is_file():
            raise FileNotFoundError(path)
        payload = read_json(path)
        if payload.get("schema_version") != "searchworthyor.v151.case_repairs.v1":
            raise AssertionError(f"{path.name}: repair schema mismatch")
        part = payload.get("records")
        if not isinstance(part, dict):
            raise AssertionError(f"{path.name}: records must be an object")
        overlap = set(records) & set(part)
        if overlap:
            raise AssertionError(f"duplicate repair records: {sorted(overlap)}")
        records.update(part)
    if sorted(records) != EXPECTED_TASK_IDS:
        missing = sorted(set(EXPECTED_TASK_IDS) - set(records))
        extra = sorted(set(records) - set(EXPECTED_TASK_IDS))
        raise AssertionError(f"repair records must cover R001-R120 exactly; missing={missing}, extra={extra}")
    required = {
        "review_outcome",
        "issue_types",
        "preserved",
        "source_replacements",
        "output_schema_meaning_overrides",
        "case_facts",
        "changed_factor",
        "non_applicability_reason",
        "evidence_review",
        "local_action_mapping",
        "gold_update",
        "review_notes",
    }
    for task_id, record in records.items():
        record.setdefault("model_objective_meaning_override", None)
        missing = required - set(record)
        if missing:
            raise AssertionError(f"{task_id}: repair record missing {sorted(missing)}")
        if record["review_outcome"] not in {"FIX", "KEEP"}:
            raise AssertionError(f"{task_id}: invalid review_outcome")
        if not isinstance(record["issue_types"], list) or not set(record["issue_types"]) <= ALLOWED_ISSUES:
            raise AssertionError(f"{task_id}: invalid issue_types")
        if set(record["case_facts"]) != {"C1", "C2"}:
            raise AssertionError(f"{task_id}: case_facts must contain C1/C2")
        for suffix in ("C1", "C2"):
            facts = record["case_facts"][suffix]
            if set(facts) != EXPECTED_CASE_FIELDS:
                raise AssertionError(f"{task_id}-{suffix}: case fact fields changed")
            if any(value is None or value == "" for value in facts.values()):
                raise AssertionError(f"{task_id}-{suffix}: empty case fact")
        if record["changed_factor"] not in EXPECTED_CASE_FIELDS:
            raise AssertionError(f"{task_id}: invalid changed_factor")
        if record["case_facts"]["C1"] == record["case_facts"]["C2"]:
            raise AssertionError(f"{task_id}: C1/C2 facts are identical")
        if len(str(record["non_applicability_reason"]).strip()) < 20:
            raise AssertionError(f"{task_id}: non_applicability_reason is too short")
        if record["gold_update"] is not None and "L6" not in record["issue_types"]:
            record["issue_types"].append("L6")
        if any(
            key in record["evidence_review"]
            for key in ("official_evidence_override", "official_evidence_node_overrides")
        ) and "L5" not in record["issue_types"]:
            record["issue_types"].append("L5")
        record["issue_types"].sort(key=lambda value: int(value[1:]))
    expand_placeholder_action_meanings(records)
    expand_objective_unit_corrections(records)
    return records


def copy_source(update_existing: bool) -> None:
    if not SOURCE.is_dir():
        raise FileNotFoundError(SOURCE)
    if TARGET.exists() and not update_existing:
        raise FileExistsError(f"refusing to overwrite existing target without --update-existing: {TARGET}")
    ignored = shutil.ignore_patterns(
        "validation_report.json",
        "README.md",
        "MODEL_IO_CONTRACT_zh.md",
        "V143_REPAIR_AUDIT_zh.md",
        "V144_MANUAL_REVIEW_zh.md",
        "V151_CASE_REPAIR_SKILL_DRAFT_zh.md",
    )
    shutil.copytree(SOURCE, TARGET, dirs_exist_ok=update_existing, ignore=ignored)


def render_case_problem_zh(source_problem_zh: str, case_facts: dict[str, Any]) -> str:
    return (
        "【本 case 权威事实】\n"
        + json.dumps(case_facts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n\n【基础优化语义合同】"
        + CASE_BASE_SEMANTICS_CONTRACT
        + "\n\n【解释优先级】"
        + INTERPRETATION_PRIORITY
        + "\n\n【优化骨架】\n"
        + source_problem_zh
    )


def render_prompt(case: dict[str, Any]) -> str:
    return (
        case["problem_zh"]
        + "\n\n公开 output_schema：\n"
        + json.dumps(case["output_schema"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def apply_source_replacements(task_id: str, problem: str, replacements: list[dict[str, str]]) -> str:
    if not isinstance(replacements, list):
        raise AssertionError(f"{task_id}: source_replacements must be a list")
    for index, replacement in enumerate(replacements, 1):
        if set(replacement) != {"old", "new"}:
            raise AssertionError(f"{task_id}: replacement {index} must contain exact old/new keys")
        old = replacement["old"]
        new = replacement["new"]
        if not isinstance(old, str) or not old:
            raise AssertionError(f"{task_id}: replacement {index} has empty old text")
        count = problem.count(old)
        if count != 1:
            raise AssertionError(f"{task_id}: replacement {index} old text occurs {count} times")
        problem = problem.replace(old, new, 1)
    return problem


def action_index(output_schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    actions = output_schema.get("actions")
    if not isinstance(actions, list):
        raise AssertionError("output_schema.actions must be a list")
    indexed = {row["id"]: row for row in actions}
    if len(indexed) != len(actions):
        raise AssertionError("duplicate public action id")
    return indexed


def sync_action_meanings(
    task_id: str,
    task: dict[str, Any],
    gold: dict[str, Any],
    overrides: dict[str, str],
) -> None:
    if not isinstance(overrides, dict):
        raise AssertionError(f"{task_id}: output_schema_meaning_overrides must be an object")
    actions = action_index(task["output_schema"])
    unknown = set(overrides) - set(actions)
    if unknown:
        raise AssertionError(f"{task_id}: unknown action meaning overrides {sorted(unknown)}")
    for public_id, meaning in overrides.items():
        if not isinstance(meaning, str) or not meaning.strip():
            raise AssertionError(f"{task_id}/{public_id}: empty action meaning")
        actions[public_id]["meaning"] = meaning
        private_name = gold["public_to_private_action_map"][public_id]
        for variant in ("base", "patched"):
            path = TARGET / "models" / task_id / f"{variant}_ir.json"
            ir = read_json(path)
            matched = [row for row in ir["variables"] if row["name"] == private_name]
            if len(matched) != 1:
                raise AssertionError(f"{task_id}/{variant}: action variable {private_name} not unique")
            matched[0]["meaning"] = meaning
            write_json(path, ir)


def sync_model_objective_meaning(task_id: str, meaning: Any) -> None:
    if meaning is None:
        return
    if not isinstance(meaning, str) or not meaning.strip():
        raise AssertionError(f"{task_id}: model objective meaning override must be non-empty")
    for variant in ("base", "patched"):
        path = TARGET / "models" / task_id / f"{variant}_ir.json"
        ir = read_json(path)
        ir["objective"]["meaning"] = meaning
        write_json(path, ir)


def upsert_named_patch(
    rows: list[dict[str, Any]],
    replacement: dict[str, Any],
    task_id: str,
    label: str,
) -> None:
    name = replacement["name"]
    indices = [index for index, row in enumerate(rows) if row.get("name") == name]
    if len(indices) > 1:
        raise AssertionError(f"{task_id}: {label} contains duplicate rows named {name}")
    if indices:
        rows[indices[0]] = deepcopy(replacement)
    else:
        rows.append(deepcopy(replacement))


def remove_named_patch(
    rows: list[dict[str, Any]],
    name: str,
    task_id: str,
    label: str,
) -> None:
    indices = [index for index, row in enumerate(rows) if row.get("name") == name]
    if len(indices) != 1:
        raise AssertionError(
            f"{task_id}: {label} must contain exactly one row named {name} before removal"
        )
    rows.pop(indices[0])


def apply_gold_update(
    task_id: str,
    update: dict[str, Any] | None,
    gold: dict[str, Any],
    asset: dict[str, Any],
    app_rows: list[dict[str, Any]],
    search_row: dict[str, Any],
) -> None:
    if update is None:
        return
    if not isinstance(update, dict) or not update.get("reason"):
        raise AssertionError(f"{task_id}: malformed gold_update")
    patch_elements = update.get("patch_elements")
    if patch_elements is None:
        patch_element = update.get("patch_element")
        patch_elements = [patch_element] if patch_element is not None else []
    remove_patch_names = update.get("remove_patch_names", [])
    if not isinstance(patch_elements, list) or not isinstance(remove_patch_names, list):
        raise AssertionError(f"{task_id}: malformed Gold Patch edit lists")
    if not patch_elements and not remove_patch_names:
        raise AssertionError(f"{task_id}: gold_update requires a Patch addition, replacement, or removal")
    if any(not isinstance(name, str) or not name for name in remove_patch_names):
        raise AssertionError(f"{task_id}: remove_patch_names must contain non-empty names")
    if len(remove_patch_names) != len(set(remove_patch_names)):
        raise AssertionError(f"{task_id}: duplicate remove_patch_names")
    positive = next(row for row in app_rows if row["applicability"] is True)
    patched_path = TARGET / gold["patched_model_path"]
    patched = read_json(patched_path)
    for name in remove_patch_names:
        remove_named_patch(gold["correct_patch_elements"], name, task_id, "private/gold")
        remove_named_patch(asset["patch_elements"], name, task_id, "task_assets")
        remove_named_patch(
            search_row["corresponding_patch_elements"], name, task_id, "search_necessity"
        )
        remove_named_patch(
            positive["gold_patch_elements"], name, task_id, "applicability Gold"
        )
        remove_named_patch(patched["constraints"], name, task_id, "patched IR")
    for patch_element in patch_elements:
        if (
            not isinstance(patch_element, dict)
            or patch_element.get("op") != "add_constraint"
            or set(patch_element) != {"op", "name", "after"}
        ):
            raise AssertionError(
                f"{task_id}: Gold correction supports complete add_constraint elements only"
            )
        upsert_named_patch(gold["correct_patch_elements"], patch_element, task_id, "private/gold")
        upsert_named_patch(asset["patch_elements"], patch_element, task_id, "task_assets")
        upsert_named_patch(
            search_row["corresponding_patch_elements"],
            patch_element,
            task_id,
            "search_necessity",
        )
        upsert_named_patch(
            positive["gold_patch_elements"], patch_element, task_id, "applicability Gold"
        )
        replacement_constraint = deepcopy(patch_element["after"])
        indices = [
            index
            for index, row in enumerate(patched["constraints"])
            if row.get("name") == patch_element["name"]
        ]
        if len(indices) > 1:
            raise AssertionError(f"{task_id}: patched IR constraint {patch_element['name']} is duplicated")
        if indices:
            patched["constraints"][indices[0]] = replacement_constraint
        else:
            patched["constraints"].append(replacement_constraint)
    write_json(patched_path, patched)

    if "official_evidence" in update:
        evidence = deepcopy(update["official_evidence"])
        if not isinstance(evidence, list) or not evidence:
            raise AssertionError(f"{task_id}: official_evidence update must be non-empty")
        asset["official_evidence"] = evidence
        search_row["required_pages"] = list(dict.fromkeys(node["url"] for node in evidence))
        search_row["required_quotes"] = list(dict.fromkeys(node["quote"] for node in evidence))


def apply_evidence_override(
    task_id: str,
    evidence_review: dict[str, Any],
    asset: dict[str, Any],
    search_row: dict[str, Any],
) -> None:
    if not isinstance(evidence_review, dict):
        raise AssertionError(f"{task_id}: evidence_review must be an object")
    evidence = evidence_review.get("official_evidence_override")
    if evidence is not None:
        if not isinstance(evidence, list) or not evidence:
            raise AssertionError(f"{task_id}: official_evidence_override must be a non-empty list")
        asset["official_evidence"] = deepcopy(evidence)

    node_overrides = evidence_review.get("official_evidence_node_overrides")
    if node_overrides is not None:
        if not isinstance(node_overrides, list) or not node_overrides:
            raise AssertionError(
                f"{task_id}: official_evidence_node_overrides must be a non-empty list"
            )
        merged = deepcopy(asset["official_evidence"])
        positions = {node["source_node_id"]: index for index, node in enumerate(merged)}
        if len(positions) != len(merged):
            raise AssertionError(f"{task_id}: duplicate existing evidence source_node_id")
        for node in node_overrides:
            source_node_id = node.get("source_node_id")
            if not isinstance(source_node_id, str) or not source_node_id:
                raise AssertionError(f"{task_id}: evidence node override lacks source_node_id")
            if source_node_id in positions:
                merged[positions[source_node_id]] = deepcopy(node)
            else:
                positions[source_node_id] = len(merged)
                merged.append(deepcopy(node))
        asset["official_evidence"] = merged

    if evidence is not None or node_overrides is not None:
        final_evidence = asset["official_evidence"]
        search_row["required_pages"] = list(dict.fromkeys(node["url"] for node in final_evidence))
        search_row["required_quotes"] = list(dict.fromkeys(node["quote"] for node in final_evidence))


def enumerate_ir(ir: dict[str, Any]) -> tuple[int, float, list[dict[str, int]]]:
    variables = ir["variables"]
    names = [variable["name"] for variable in variables]
    domains = [range(int(variable["lb"]), int(variable["ub"]) + 1) for variable in variables]
    feasible_rows: list[tuple[float, dict[str, int]]] = []
    for values in itertools.product(*domains):
        assignment = dict(zip(names, values))
        valid = True
        for constraint in ir["constraints"]:
            lhs = sum(float(coef) * assignment[name] for name, coef in constraint["coefficients"].items())
            rhs = float(constraint["rhs"])
            sense = constraint["sense"]
            if sense == "=":
                valid = abs(lhs - rhs) <= 1e-9
            elif sense == "<=":
                valid = lhs <= rhs + 1e-9
            elif sense == ">=":
                valid = lhs >= rhs - 1e-9
            else:
                raise AssertionError(f"{ir['id']}: unknown constraint sense {sense}")
            if not valid:
                break
        if not valid:
            continue
        objective = ir["objective"]
        value = float(objective.get("constant", 0)) + sum(
            float(coef) * assignment[name] for name, coef in objective["coefficients"].items()
        )
        feasible_rows.append((value, assignment))
    if not feasible_rows:
        raise AssertionError(f"{ir['id']}: model is infeasible")
    direction = ir["objective"]["sense"]
    if direction == "max":
        optimum = max(value for value, _ in feasible_rows)
    elif direction == "min":
        optimum = min(value for value, _ in feasible_rows)
    else:
        raise AssertionError(f"{ir['id']}: unknown objective sense {direction}")
    projection = ir.get("action_projection") or names
    unique_actions = {
        tuple((name, assignment[name]) for name in projection)
        for value, assignment in feasible_rows
        if abs(value - optimum) <= 1e-9
    }
    actions = [dict(items) for items in sorted(unique_actions)]
    return len(feasible_rows), float(optimum), actions


def objective_contract_with_value(
    contract: dict[str, Any],
    value: float,
    accepted_units: dict[str, Any] | None = None,
) -> dict[str, Any]:
    updated = deepcopy(contract)
    old = float(updated["canonical_value"])
    updated["canonical_value"] = float(value)
    if accepted_units is not None:
        canonical_unit = updated["canonical_unit"]
        if canonical_unit not in accepted_units:
            raise AssertionError(f"canonical unit {canonical_unit!r} is absent from accepted_units")
        seen_units: set[str] = set()
        for equivalent in updated.get("accepted_equivalents", []):
            unit = equivalent["unit"]
            if unit in seen_units or unit not in accepted_units:
                raise AssertionError(f"accepted equivalent unit {unit!r} is duplicated or unsupported")
            seen_units.add(unit)
            factor = float(accepted_units[unit])
            if factor <= 0:
                raise AssertionError(f"accepted unit {unit!r} has a non-positive factor")
            equivalent["value"] = float(value) / factor
        return updated
    for equivalent in updated.get("accepted_equivalents", []):
        previous = float(equivalent["value"])
        equivalent["value"] = float(value if abs(old) <= 1e-12 else value * previous / old)
    return updated


def recompute_task(
    task_id: str,
    gold: dict[str, Any],
    accepted_units: dict[str, Any],
) -> dict[str, Any]:
    task_dir = TARGET / "models" / task_id
    base = read_json(task_dir / "base_ir.json")
    patched = read_json(task_dir / "patched_ir.json")
    base_count, base_objective, base_actions = enumerate_ir(base)
    patched_count, patched_objective, patched_actions = enumerate_ir(patched)
    result = read_json(task_dir / "solve_result.json")
    contract = objective_contract_with_value(
        result["objective_value_contract"], patched_objective, accepted_units
    )
    common = [row for row in base_actions if row in patched_actions]
    result.update(
        {
            "solver": "complete enumeration (V1.5.1 rebuild verification)",
            "base_status": "OPTIMAL",
            "base_feasible_assignment_count": base_count,
            "base_objective": base_objective,
            "base_incumbent": base_actions[0],
            "base_optimal_actions": base_actions,
            "patched_status": "OPTIMAL",
            "patched_feasible_assignment_count": patched_count,
            "patched_objective": patched_objective,
            "patched_incumbent": patched_actions[0],
            "patched_optimal_actions": patched_actions,
            "common_optimal_action_feasible": bool(common),
            "common_optimal_actions": common,
            "optimal_action_changed": not bool(common),
            "objective_value_contract": contract,
        }
    )
    write_json(task_dir / "solve_result.json", result)
    gold["base_optimal_action_set"] = deepcopy(base_actions)
    gold["patched_optimal_action_set"] = deepcopy(patched_actions)
    gold["objective_value_contract"] = deepcopy(contract)
    return result


def public_action_rows(
    private_rows: list[dict[str, int]],
    public_to_private: dict[str, str],
) -> list[list[dict[str, Any]]]:
    private_to_public = {private: public for public, private in public_to_private.items()}
    if len(private_to_public) != len(public_to_private):
        raise AssertionError("public/private action map is not one-to-one")
    return [
        [
            {"id": private_to_public[name], "value": value}
            for name, value in sorted(row.items(), key=lambda item: private_to_public[item[0]])
        ]
        for row in private_rows
    ]


def sync_case_gold(
    task_id: str,
    app_rows: list[dict[str, Any]],
    gold: dict[str, Any],
    asset: dict[str, Any],
    result: dict[str, Any],
) -> None:
    official_support = [
        {
            "location": None,
            "node_id": node["source_node_id"],
            "publisher": node["publisher"],
            "quote": node["quote"],
            "url": node["url"],
        }
        for node in asset["official_evidence"]
    ]
    for row in app_rows:
        row["official_support"] = deepcopy(official_support)
        if row["applicability"] is False:
            row["decision_state"] = "RETAIN"
            row["gold_patch_elements"] = []
            row["gold_action_set"] = public_action_rows(
                result["base_optimal_actions"], gold["public_to_private_action_map"]
            )
            row["gold_objective"] = objective_contract_with_value(
                result["objective_value_contract"], result["base_objective"]
            )
        else:
            row["decision_state"] = "PATCH_CHANGES"
            row["gold_patch_elements"] = deepcopy(gold["correct_patch_elements"])
            row["gold_action_set"] = public_action_rows(
                result["patched_optimal_actions"], gold["public_to_private_action_map"]
            )
            row["gold_objective"] = deepcopy(result["objective_value_contract"])


def rebuild_evidence_derivatives(
    assets: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    omissions: list[dict[str, Any]] = []
    hardening: list[dict[str, Any]] = []
    for task_id in sorted(assets):
        asset = assets[task_id]
        if asset["task_mode"] != "multi_hop_revision":
            continue
        responsibilities: list[dict[str, Any]] = []
        for node in asset["official_evidence"]:
            responsibilities.append(
                {
                    "node_id": node["node_id"],
                    "source_node_id": node["source_node_id"],
                    "role": node["role"],
                    "responsibility": node["information_responsibility"],
                    "supported_patch_slots": deepcopy(node["supported_patch_slots"]),
                    "support_target_type": node["support_target_type"],
                    "support_targets": deepcopy(node["support_targets"]),
                }
            )
            omissions.append(
                {
                    "task_id": task_id,
                    "omitted_node_id": node["node_id"],
                    "source_node_id": node["source_node_id"],
                    "node_role": node["role"],
                    "information_responsibility": node["information_responsibility"],
                    "omission_effect": node.get("omission_effect"),
                    "supported_patch_slots": deepcopy(node["supported_patch_slots"]),
                    "support_target_type": node["support_target_type"],
                    "support_targets": deepcopy(node["support_targets"]),
                    "publisher": node["publisher"],
                    "quote": node["quote"],
                    "url": node["url"],
                    "structural_binding_complete": True,
                    "empirical_omission_test_status": "NOT_RUN",
                    "remaining_evidence_uniquely_determines_gold_patch": None,
                    "audit_note": "V1.5.1 records the structural dependency without claiming an unexecuted omission experiment.",
                }
            )
        hardening.append(
            {
                "id": task_id,
                "change_class": "V1.5.1 evidence binding preservation; no synthetic empirical omission claim",
                "node_information_responsibilities": responsibilities,
                "evidence_order": [node["node_id"] for node in asset["official_evidence"]],
                "canonical_source_order": [node["source_node_id"] for node in asset["official_evidence"]],
                "empirical_omission_test_status": "NOT_RUN",
            }
        )
    return omissions, hardening


def build_state_spec() -> dict[str, Any]:
    return {
        "schema_version": "searchworthyor.decision_state.v1",
        "dataset_version": "SearchWorthyOR-v1.5.1",
        "visibility": "PRIVATE_SCORER_ONLY",
        "allowed_states": {
            "RETAIN": {
                "meaning_zh": "题外规则对当前 case 不产生模型修改；保留 Base IR 与基础解。",
                "required_applicability": False,
                "required_patch_cardinality": 0,
                "target_model_variant": "base",
                "decision_change_from_base": False,
            },
            "PATCH_CHANGES": {
                "meaning_zh": "题外规则适用于当前 case，并支持非空 typed Patch；重求解后的最优决策相对 Base IR 改变。",
                "required_applicability": True,
                "required_patch_cardinality": "NONZERO",
                "target_model_variant": "patched",
                "decision_change_from_base": True,
            },
        },
        "excluded_states": ["PATCH_STABLE"],
        "pair_rule": "Every source task has one RETAIN C1 case and one PATCH_CHANGES C2 case.",
        "public_input_rule": "Only id, case_id and canonical prompt_zh are model input.",
    }


def build_io_contract() -> str:
    return """# SearchWorthyOR-v1.5.1 统一输入输出合同

## 输入

每个模型调用只使用 `id`、`case_id` 和 `prompt_zh`。`prompt_zh` 已包含本 case 客观事实、基础优化语义合同、解释优先级、优化骨架和公开 `output_schema`。不得向模型提供 `private/` 中的状态、证据 Gold、Patch、行动 Gold、目标 Gold 或变量映射。

## Agent 输出

```json
{
  "decision_state": "RETAIN or PATCH_CHANGES",
  "applicability": true,
  "patch": [],
  "actions": [{"id": "public_action_id", "value": 0}],
  "objective": {"sense": "min or max", "value": 0.0, "unit": "unit"}
}
```

- `RETAIN`：`applicability=false` 且 `patch=[]`，行动与目标来自 Base IR。
- `PATCH_CHANGES`：`applicability=true` 且 `patch` 非空，行动与目标来自 patched IR。
- `actions` 完整覆盖公开 action ID；`objective` 给出方向、数值与单位。
- 本版本不允许 `PATCH_STABLE`。

JSON 格式纠错、重试和格式微调仍属于实验 runner，不属于数据集 Gold。
"""


def compact_repair_table(records: dict[str, dict[str, Any]]) -> str:
    lines = [
        "| 任务 | 结论 | L 类别 | 主差异轴 | source 精确修改 | schema meaning | Gold |",
        "|---|---|---|---|---:|---:|---|",
    ]
    for task_id in EXPECTED_TASK_IDS:
        row = records[task_id]
        issues = ",".join(row["issue_types"]) if row["issue_types"] else "无"
        gold = (
            "修改"
            if row["gold_update"] is not None or row["objective_unit_correction"] is not None
            else "保持"
        )
        lines.append(
            f"| {task_id} | {row['review_outcome']} | {issues} | {row['changed_factor']} | "
            f"{len(row['source_replacements'])} | {len(row['output_schema_meaning_overrides'])} | {gold} |"
        )
    return "\n".join(lines)


def readme_repair_details(records: dict[str, dict[str, Any]]) -> str:
    parts: list[str] = []
    for task_id in EXPECTED_TASK_IDS:
        row = records[task_id]
        parts.extend(
            [
                f"### {task_id}",
                "",
                f"- 结论：`{row['review_outcome']}`；问题类型：{', '.join(row['issue_types']) or '无'}。",
                f"- 保持：{row['preserved']}",
                f"- 主差异轴：`{row['changed_factor']}`。",
                f"- C1：`{json.dumps(row['case_facts']['C1'], ensure_ascii=False, sort_keys=True)}`",
                f"- C2：`{json.dumps(row['case_facts']['C2'], ensure_ascii=False, sort_keys=True)}`",
                f"- C1 不适用原因：{row['non_applicability_reason']}",
                f"- 题内行动映射：{row['local_action_mapping']}",
            ]
        )
        if row["source_replacements"]:
            parts.append("- source 精确替换：")
            for replacement in row["source_replacements"]:
                parts.append(f"  - 旧：`{replacement['old']}`")
                parts.append(f"  - 新：`{replacement['new']}`")
        else:
            parts.append("- source 精确替换：无。")
        parts.append(
            "- output_schema meaning 修改：`"
            + json.dumps(row["output_schema_meaning_overrides"], ensure_ascii=False, sort_keys=True)
            + "`"
        )
        parts.append(
            "- IR 目标 meaning 修改：`"
            + json.dumps(row["model_objective_meaning_override"], ensure_ascii=False)
            + "`"
        )
        parts.append(
            "- Gold 修改：`"
            + json.dumps(row["gold_update"], ensure_ascii=False, sort_keys=True)
            + "`"
        )
        parts.append(
            "- 目标单位修正：`"
            + json.dumps(row["objective_unit_correction"], ensure_ascii=False, sort_keys=True)
            + "`"
        )
        parts.append(
            "- 证据复核：`"
            + json.dumps(row["evidence_review"], ensure_ascii=False, sort_keys=True)
            + "`"
        )
        parts.append(f"- 复核说明：{row['review_notes']}")
        parts.append("")
    return "\n".join(parts).rstrip()


def build_readme(records: dict[str, dict[str, Any]]) -> str:
    if not README_TEMPLATE.is_file():
        raise FileNotFoundError(README_TEMPLATE)
    template = README_TEMPLATE.read_text(encoding="utf-8")
    table_token = "{{REPAIR_TABLE}}"
    detail_token = "{{REPAIR_DETAILS}}"
    if template.count(table_token) != 1 or template.count(detail_token) != 1:
        raise AssertionError("V1.5.1 README template must contain one table and one detail token")
    return template.replace(table_token, compact_repair_table(records)).replace(
        detail_token, readme_repair_details(records)
    )


def build_repair_markdown(rows: list[dict[str, Any]]) -> str:
    parts = [
        "# SearchWorthyOR-v1.5.1 全量逐题修复与人工语义复核记录",
        "",
        "复核日期：2026-08-26",
        "",
        "本记录覆盖 120 个 source task 的 240 个最终 `prompt_zh`。每题均核对 source、C1/C2 客观事实、题内行动映射、题外官方证据、typed Patch、Base/patched IR 与重求解结果。",
    ]
    for row in rows:
        parts.extend(
            [
                "",
                f"## {row['source_task_id']}",
                "",
                f"- 审查结论：`{row['review_outcome']}`；问题类型：{', '.join(row['issue_types']) or '无'}。",
                f"- 保持内容：{row['preserved']}",
                f"- 主差异轴：`{row['changed_factor']}`；C1=`RETAIN`，C2=`PATCH_CHANGES`。",
                f"- 题内行动映射：{row['local_action_mapping']}",
                f"- Gold：{'已同步修改' if row['gold_update'] is not None else '保持原 typed Patch；已全量重求解'}。",
                f"- Base 重求解：可行解 {row['base_solve']['feasible_assignment_count']}，目标 {row['base_solve']['objective']}。",
                f"- Patched 重求解：可行解 {row['patched_solve']['feasible_assignment_count']}，目标 {row['patched_solve']['objective']}。",
                f"- 语义复核：{row['review_notes']}",
                "- C1 客观事实：`" + json.dumps(row["case_facts"]["C1"], ensure_ascii=False, sort_keys=True) + "`",
                "- C2 客观事实：`" + json.dumps(row["case_facts"]["C2"], ensure_ascii=False, sort_keys=True) + "`",
            ]
        )
        if row["source_replacements"]:
            parts.append("- source 精确修改：")
            for replacement in row["source_replacements"]:
                parts.append(f"  - 原文：`{replacement['old']}`")
                parts.append(f"  - 新文：`{replacement['new']}`")
        else:
            parts.append("- source 精确修改：无。")
        parts.append("- 官方依据：")
        for node in row["official_basis"]:
            parts.append(f"  - {node['publisher']}，{node['url']}，节点 `{node['source_node_id']}`。")
    return "\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Overwrite the same deterministic V1.5.1 outputs without deleting the target directory.",
    )
    args = parser.parse_args()
    repairs = load_repairs()
    copy_source(args.update_existing)

    tasks = {row["id"]: row for row in read_jsonl(TARGET / "public" / "tasks_zh.jsonl")}
    cases = read_jsonl(TARGET / "public" / "applicability_cases_zh.jsonl")
    gold = {row["id"]: row for row in read_jsonl(TARGET / "private" / "gold.jsonl")}
    assets = {row["id"]: row for row in read_jsonl(TARGET / "private" / "task_assets.jsonl")}
    app_gold = read_jsonl(TARGET / "private" / "applicability_gold.jsonl")
    search_rows = {row["task_id"]: row for row in read_jsonl(TARGET / "private" / "search_necessity.jsonl")}
    cases_by_task: dict[str, dict[str, dict[str, Any]]] = {}
    app_by_task: dict[str, list[dict[str, Any]]] = {}
    for row in cases:
        suffix = row["case_id"].rsplit("-", 1)[-1]
        cases_by_task.setdefault(row["source_task_id"], {})[suffix] = row
    for row in app_gold:
        app_by_task.setdefault(row["source_task_id"], []).append(row)

    repair_output_rows: list[dict[str, Any]] = []
    solve_results: dict[str, dict[str, Any]] = {}
    for task_id in EXPECTED_TASK_IDS:
        record = repairs[task_id]
        task = tasks[task_id]
        task["problem_zh"] = apply_source_replacements(
            task_id, task["problem_zh"], record["source_replacements"]
        )
        sync_action_meanings(task_id, task, gold[task_id], record["output_schema_meaning_overrides"])
        sync_model_objective_meaning(task_id, record["model_objective_meaning_override"])
        pair = cases_by_task[task_id]
        if set(pair) != {"C1", "C2"}:
            raise AssertionError(f"{task_id}: expected canonical C1/C2 public cases")
        for suffix in ("C1", "C2"):
            public = pair[suffix]
            public["case_facts"] = deepcopy(record["case_facts"][suffix])
            public["output_schema"] = deepcopy(task["output_schema"])
            public["base_semantics_contract"] = CASE_BASE_SEMANTICS_CONTRACT
            public["problem_zh"] = render_case_problem_zh(task["problem_zh"], public["case_facts"])
            public["prompt_zh"] = render_prompt(public)

        private_pair = app_by_task[task_id]
        if len(private_pair) != 2:
            raise AssertionError(f"{task_id}: expected two applicability Gold rows")
        negative = next(row for row in private_pair if row["applicability"] is False)
        positive = next(row for row in private_pair if row["applicability"] is True)
        negative["changed_factor"] = record["changed_factor"]
        negative["changed_factors"] = [
            key
            for key in sorted(EXPECTED_CASE_FIELDS)
            if record["case_facts"]["C1"][key] != record["case_facts"]["C2"][key]
        ]
        if record["changed_factor"] not in negative["changed_factors"]:
            raise AssertionError(f"{task_id}: changed_factor is not an actual C1/C2 difference")
        negative["negative_value"] = deepcopy(record["case_facts"]["C1"][record["changed_factor"]])
        negative["positive_value"] = deepcopy(record["case_facts"]["C2"][record["changed_factor"]])
        negative["non_applicability_reason"] = record["non_applicability_reason"]

        decision = assets[task_id]["applicability_decision"]
        c2_facts = record["case_facts"]["C2"]
        decision.update(
            {
                "decision_date": c2_facts["decision_date"],
                "jurisdiction": c2_facts["jurisdiction"],
                "subject": c2_facts["regulated_subject"],
                "exceptions": deepcopy(c2_facts["boundary_facts"]),
            }
        )
        if "date" in decision:
            decision["date"] = c2_facts["decision_date"]

        apply_gold_update(
            task_id,
            record["gold_update"],
            gold[task_id],
            assets[task_id],
            private_pair,
            search_rows[task_id],
        )
        apply_evidence_override(
            task_id,
            record["evidence_review"],
            assets[task_id],
            search_rows[task_id],
        )
        result = recompute_task(
            task_id,
            gold[task_id],
            task["output_schema"]["objective"]["accepted_units"],
        )
        solve_results[task_id] = result
        if not result["optimal_action_changed"]:
            raise AssertionError(f"{task_id}: PATCH_CHANGES no longer changes the optimal action")
        sync_case_gold(task_id, private_pair, gold[task_id], assets[task_id], result)
        search_rows[task_id]["corresponding_patch_elements"] = deepcopy(assets[task_id]["patch_elements"])
        search_rows[task_id]["required_pages"] = list(
            dict.fromkeys(node["url"] for node in assets[task_id]["official_evidence"])
        )
        search_rows[task_id]["required_quotes"] = list(
            dict.fromkeys(node["quote"] for node in assets[task_id]["official_evidence"])
        )

        full_record = deepcopy(record)
        full_record["source_task_id"] = task_id
        full_record["official_basis"] = [
            {
                "source_node_id": node["source_node_id"],
                "publisher": node["publisher"],
                "url": node["url"],
                "quote": node["quote"],
                "supported_patch_slots": deepcopy(node["supported_patch_slots"]),
            }
            for node in assets[task_id]["official_evidence"]
        ]
        full_record["base_solve"] = {
            "status": result["base_status"],
            "feasible_assignment_count": result["base_feasible_assignment_count"],
            "objective": result["base_objective"],
            "optimal_actions": deepcopy(result["base_optimal_actions"]),
        }
        full_record["patched_solve"] = {
            "status": result["patched_status"],
            "feasible_assignment_count": result["patched_feasible_assignment_count"],
            "objective": result["patched_objective"],
            "optimal_actions": deepcopy(result["patched_optimal_actions"]),
        }
        full_record["reviewed_by"] = "Codex parallel per-pair semantic review"
        full_record["review_date"] = "2026-08-26"
        repair_output_rows.append(full_record)

    omissions, hardening = rebuild_evidence_derivatives(assets)
    write_jsonl(TARGET / "public" / "tasks_zh.jsonl", [tasks[task_id] for task_id in EXPECTED_TASK_IDS])
    write_jsonl(
        TARGET / "public" / "applicability_cases_zh.jsonl",
        [cases_by_task[task_id][suffix] for task_id in EXPECTED_TASK_IDS for suffix in ("C1", "C2")],
    )
    write_jsonl(TARGET / "private" / "gold.jsonl", [gold[task_id] for task_id in EXPECTED_TASK_IDS])
    write_jsonl(TARGET / "private" / "task_assets.jsonl", [assets[task_id] for task_id in EXPECTED_TASK_IDS])
    write_jsonl(
        TARGET / "private" / "applicability_gold.jsonl",
        [
            row
            for task_id in EXPECTED_TASK_IDS
            for row in sorted(app_by_task[task_id], key=lambda item: item["case_id"])
        ],
    )
    write_jsonl(
        TARGET / "private" / "search_necessity.jsonl",
        [search_rows[task_id] for task_id in EXPECTED_TASK_IDS],
    )
    write_jsonl(TARGET / "private" / "evidence_node_omissions.jsonl", omissions)
    write_jsonl(TARGET / "private" / "multi_hardening_manifest.jsonl", hardening)
    write_jsonl(TARGET / "private" / "v151_case_repair_records.jsonl", repair_output_rows)
    write_json(TARGET / "private" / "decision_state_spec.json", build_state_spec())

    spec_text = SPEC_SOURCE.read_text(encoding="utf-8").replace(
        "# SearchWorthyOR V1.5.1 题目修复规范（Skill 文档草案）",
        "# SearchWorthyOR V1.5.1 题目修复规范（执行版）",
        1,
    )
    (TARGET / "V151_CASE_REPAIR_SPEC_zh.md").write_text(spec_text, encoding="utf-8")
    (TARGET / "MODEL_IO_CONTRACT_zh.md").write_text(build_io_contract(), encoding="utf-8")
    (TARGET / "README.md").write_text(build_readme(repairs), encoding="utf-8")
    (TARGET / "V151_REPAIR_RECORDS_zh.md").write_text(
        build_repair_markdown(repair_output_rows), encoding="utf-8"
    )
    write_json(
        TARGET / "validation_report.json",
        {
            "schema_version": "searchworthyor.v151.validation.v1",
            "status": "NOT_RUN_AFTER_BUILD",
            "dataset": "SearchWorthyOR-v1.5.1",
            "counts": {"tasks": 120, "cases": 240, "repair_records": 120},
            "note": "Run scripts/validate_searchworthyor_v151.py after the build.",
            "errors": [],
        },
    )
    print(
        json.dumps(
            {
                "target": str(TARGET),
                "tasks": len(tasks),
                "cases": len(cases),
                "repair_records": len(repair_output_rows),
                "r001_patched_objective": solve_results["SWOR-R001"]["patched_objective"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

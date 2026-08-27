from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

import build_searchworthyor_v151 as build


DATASET = build.TARGET
SOURCE = build.SOURCE
EXPECTED_IDS = build.EXPECTED_TASK_IDS
CASE_FIELDS = build.EXPECTED_CASE_FIELDS

TASK_KEYS = {"id", "problem_zh", "output_schema"}
CASE_KEYS = {
    "base_semantics_contract",
    "case_facts",
    "case_id",
    "output_schema",
    "pair_id",
    "problem_zh",
    "prompt_zh",
    "source_task_id",
}
IR_KEYS = {
    "schema_version",
    "id",
    "variant",
    "family",
    "source_candidate_id",
    "variables",
    "objective",
    "constraints",
    "action_projection",
}
VARIABLE_KEYS = {"name", "type", "lb", "ub", "meaning"}
OBJECTIVE_KEYS = {"sense", "coefficients", "constant", "unit", "meaning"}
CONSTRAINT_KEYS = {"name", "sense", "coefficients", "rhs", "meaning"}
SOLVE_KEYS = {
    "schema_version",
    "id",
    "solver",
    "base_status",
    "base_feasible_assignment_count",
    "base_objective",
    "base_incumbent",
    "base_optimal_actions",
    "patched_status",
    "patched_feasible_assignment_count",
    "patched_objective",
    "patched_incumbent",
    "patched_optimal_actions",
    "common_optimal_action_feasible",
    "common_optimal_actions",
    "optimal_action_changed",
    "objective_value_contract",
}
EVIDENCE_KEYS = {
    "node_id",
    "source_node_id",
    "publisher",
    "url",
    "quote",
    "role",
    "information_responsibility",
    "omission_effect",
    "supported_patch_slots",
    "support_target_type",
    "support_targets",
}
GOLD_KEYS = {
    "base_model_path",
    "base_optimal_action_set",
    "correct_patch_elements",
    "family",
    "id",
    "objective_value_contract",
    "patched_model_path",
    "patched_optimal_action_set",
    "public_to_private_action_map",
    "solve_result_path",
    "task_mode",
}
ASSET_KEYS = {
    "applicability_decision",
    "id",
    "official_evidence",
    "patch_elements",
    "search_intent",
    "task_mode",
    "why_search_is_necessary",
}
APP_NEGATIVE_KEYS = {
    "applicability",
    "case_id",
    "changed_factor",
    "changed_factors",
    "decision_state",
    "gold_action_set",
    "gold_objective",
    "gold_patch_elements",
    "negative_value",
    "non_applicability_reason",
    "official_support",
    "pair_id",
    "positive_value",
    "source_task_id",
}
APP_POSITIVE_KEYS = {
    "applicability",
    "case_id",
    "changed_factor",
    "decision_state",
    "gold_action_set",
    "gold_objective",
    "gold_patch_elements",
    "official_support",
    "pair_id",
    "source_task_id",
}
SEARCH_KEYS = {
    "base_model_from_problem",
    "corresponding_patch_elements",
    "gold_rule_conclusion_leaked",
    "nonempty_structural_patch",
    "patched_model_unique_without_web",
    "required_pages",
    "required_quotes",
    "search_object",
    "specific_official_rule_required",
    "structural_pass",
    "task_id",
}

# These patterns target conclusions/instructions, not objective facts such as a
# place, date, quantity or product attribute.  The full prompt legitimately
# contains the neutral evidence contract, so source and case facts are scanned
# separately.
SOURCE_LEAK_PATTERNS = {
    "search_instruction": re.compile(
        r"(?:(?:请|需要|须|应|必须).{0,4}(?:搜索|检索|查找|上网|联网|浏览)"
        r"|(?:搜索|检索|查找|上网)(?:官网|网页|外部|官方|法规|规则|资料|来源))"
    ),
    "external_rule_instruction": re.compile(
        r"(?:还|另|并|且)?(?:须|必须|应当|需要).{0,20}(?:现行|外部|题外|法规|法律|监管|官方).{0,20}(?:要求|规则|规定|标准|约束|规范)"
    ),
    "applicability_instruction": re.compile(
        r"(?:自行|据此|并据此|然后).{0,12}(?:判断|确定).{0,8}(?:适用|不适用|是否适用|监管范围)"
    ),
    "position_mapping_meta": re.compile(r"题面候选.{0,12}(?:首次出现顺序|对应output_schema行动)"),
}
FACT_CONCLUSION_PATTERNS = {
    "explicit_applicability": re.compile(
        r"(?:本|该|上述|相关)?(?:规则|法规|法律|条例|要求|监管框架).{0,12}(?:适用|不适用|覆盖|豁免|触发)"
    ),
    "explicit_conclusion": re.compile(
        r"(?:适用|不适用|已豁免|被豁免|无需遵守|须遵守|必须遵守|触发.{0,8}(?:规则|义务|要求)|不触发.{0,8}(?:规则|义务|要求))"
    ),
    "search_meta": re.compile(r"(?:需要|须|请|应).{0,8}(?:搜索|检索|查找|联网|浏览官网)"),
    "relative_legal_threshold": re.compile(
        r"(?:低于|高于|超过|达到|未达到|不超过).{0,18}(?:公布|规定|法定|报告|监管|规则|法规|source所述).{0,10}(?:门槛|阈值|要求)?"
        r"|(?:低于|高于|超过|达到|未达到).{0,8}(?:门槛|阈值)"
    ),
    "external_legal_status": re.compile(
        r"(?:法院|机构|委员会).{0,16}(?:撤销|废止).{0,16}(?:规则|法规|最终规则)"
        r"|(?:规则|法规|最终规则).{0,16}(?:已生效|已失效|已撤销|尚未完成|已经过去)"
    ),
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def index_exact(
    errors: list[str], label: str, rows: list[dict[str, Any]], key: str, expected: list[str]
) -> dict[str, dict[str, Any]]:
    values = [row.get(key) for row in rows]
    if len(values) != len(set(values)) or sorted(values) != expected:
        fail(errors, f"{label}: expected exactly {expected[0]} through {expected[-1]}")
    return {row[key]: row for row in rows if key in row}


def canonical_public_actions(rows: list[list[dict[str, Any]]]) -> list[tuple[tuple[str, Any], ...]]:
    return sorted(tuple(sorted((item["id"], item["value"]) for item in row)) for row in rows)


def validate_ir_schema(errors: list[str], task_id: str, variant: str, ir: dict[str, Any]) -> None:
    label = f"{task_id}/{variant}"
    if set(ir) != IR_KEYS:
        fail(errors, f"{label}: IR top-level keys differ: {sorted(set(ir) ^ IR_KEYS)}")
        return
    if ir.get("schema_version") != "searchworthyor.rapid_model_ir.v0":
        fail(errors, f"{label}: unexpected IR schema version")
    if ir.get("id") != task_id or ir.get("variant") != variant:
        fail(errors, f"{label}: id/variant mismatch")
    variables = ir.get("variables")
    if not isinstance(variables, list) or not variables:
        fail(errors, f"{label}: variables must be non-empty")
        return
    names = [row.get("name") for row in variables]
    if len(names) != len(set(names)):
        fail(errors, f"{label}: duplicate variable names")
    for row in variables:
        if set(row) != VARIABLE_KEYS:
            fail(errors, f"{label}/{row.get('name')}: variable keys differ")
            continue
        if row["type"] not in {"BINARY", "INTEGER"}:
            fail(errors, f"{label}/{row['name']}: unsupported variable type")
        if not isinstance(row["lb"], int) or not isinstance(row["ub"], int) or row["lb"] > row["ub"]:
            fail(errors, f"{label}/{row['name']}: invalid integer bounds")
        if row["type"] == "BINARY" and (row["lb"], row["ub"]) != (0, 1):
            fail(errors, f"{label}/{row['name']}: binary bounds must be 0..1")
        if not isinstance(row["meaning"], str) or not row["meaning"].strip():
            fail(errors, f"{label}/{row['name']}: empty variable meaning")
    objective = ir.get("objective", {})
    if set(objective) != OBJECTIVE_KEYS:
        fail(errors, f"{label}: objective keys differ")
    else:
        if objective["sense"] not in {"min", "max"}:
            fail(errors, f"{label}: invalid objective sense")
        if not set(objective["coefficients"]) <= set(names):
            fail(errors, f"{label}: objective references unknown variables")
    constraints = ir.get("constraints")
    if not isinstance(constraints, list):
        fail(errors, f"{label}: constraints must be a list")
        return
    constraint_names = [row.get("name") for row in constraints]
    if len(constraint_names) != len(set(constraint_names)):
        fail(errors, f"{label}: duplicate constraint names")
    for row in constraints:
        if set(row) != CONSTRAINT_KEYS:
            fail(errors, f"{label}/{row.get('name')}: constraint keys differ")
            continue
        if row["sense"] not in {"<=", "=", ">="}:
            fail(errors, f"{label}/{row['name']}: invalid constraint sense")
        if not set(row["coefficients"]) <= set(names):
            fail(errors, f"{label}/{row['name']}: constraint references unknown variables")
    projection = ir.get("action_projection")
    if not isinstance(projection, list) or len(projection) != len(set(projection)):
        fail(errors, f"{label}: action_projection must be a unique list")
    elif not set(projection) <= set(names):
        fail(errors, f"{label}: action_projection references unknown variables")


def reconstruct_patched(base: dict[str, Any], patches: list[dict[str, Any]], task_id: str) -> dict[str, Any]:
    candidate = deepcopy(base)
    candidate["variant"] = "patched"
    for patch in patches:
        op = patch.get("op")
        name = patch.get("name")
        if op == "add_variable":
            if set(patch) != {"op", "name", "after"} or patch["after"].get("name") != name:
                raise AssertionError(f"{task_id}/{name}: malformed add_variable")
            if name in {row["name"] for row in candidate["variables"]}:
                raise AssertionError(f"{task_id}/{name}: add_variable already exists")
            candidate["variables"].append(deepcopy(patch["after"]))
        elif op == "add_constraint":
            if set(patch) != {"op", "name", "after"} or patch["after"].get("name") != name:
                raise AssertionError(f"{task_id}/{name}: malformed add_constraint")
            if name in {row["name"] for row in candidate["constraints"]}:
                raise AssertionError(f"{task_id}/{name}: add_constraint already exists")
            candidate["constraints"].append(deepcopy(patch["after"]))
        elif op == "modify_constraint":
            if set(patch) != {"op", "name", "before", "after"}:
                raise AssertionError(f"{task_id}/{name}: malformed modify_constraint")
            indices = [index for index, row in enumerate(candidate["constraints"]) if row["name"] == name]
            if len(indices) != 1 or candidate["constraints"][indices[0]] != patch["before"]:
                raise AssertionError(f"{task_id}/{name}: modify_constraint before mismatch")
            candidate["constraints"][indices[0]] = deepcopy(patch["after"])
        elif op == "modify_objective":
            if set(patch) != {"op", "name", "before", "after"}:
                raise AssertionError(f"{task_id}/{name}: malformed modify_objective")
            if candidate["objective"] != patch["before"]:
                raise AssertionError(f"{task_id}/{name}: modify_objective before mismatch")
            candidate["objective"] = deepcopy(patch["after"])
        else:
            raise AssertionError(f"{task_id}/{name}: unsupported Patch op {op}")
    return candidate


def normalize_named_ir_collections(ir: dict[str, Any]) -> dict[str, Any]:
    """Normalize order-only differences in named IR collections."""
    normalized = deepcopy(ir)
    normalized["variables"] = sorted(normalized["variables"], key=lambda row: row["name"])
    normalized["constraints"] = sorted(normalized["constraints"], key=lambda row: row["name"])
    return normalized


def main() -> None:
    errors: list[str] = []
    required = [
        "README.md",
        "MODEL_IO_CONTRACT_zh.md",
        "V151_CASE_REPAIR_SPEC_zh.md",
        "V151_REPAIR_RECORDS_zh.md",
        "validation_report.json",
        "public/tasks_zh.jsonl",
        "public/applicability_cases_zh.jsonl",
        "private/gold.jsonl",
        "private/task_assets.jsonl",
        "private/applicability_gold.jsonl",
        "private/decision_state_spec.json",
        "private/evidence_node_omissions.jsonl",
        "private/multi_hardening_manifest.jsonl",
        "private/search_necessity.jsonl",
        "private/v151_case_repair_records.jsonl",
    ]
    for relative in required:
        if not (DATASET / relative).is_file():
            fail(errors, f"missing required file: {relative}")
    for stale in (
        "freeze_manifest.json",
        "base_feature_matching_report.json",
        "V143_REPAIR_AUDIT_zh.md",
        "V144_MANUAL_REVIEW_zh.md",
        "V151_CASE_REPAIR_SKILL_DRAFT_zh.md",
    ):
        if (DATASET / stale).exists():
            fail(errors, f"forbidden stale artifact: {stale}")
    if errors:
        raise SystemExit("\n".join(errors))

    expected_root = {
        "README.md",
        "MODEL_IO_CONTRACT_zh.md",
        "V151_CASE_REPAIR_SPEC_zh.md",
        "V151_REPAIR_RECORDS_zh.md",
        "validation_report.json",
        "public",
        "private",
        "models",
    }
    actual_root = {path.name for path in DATASET.iterdir()}
    if actual_root != expected_root:
        fail(errors, f"dataset root inventory differs: {sorted(actual_root ^ expected_root)}")
    expected_public = {"tasks_zh.jsonl", "applicability_cases_zh.jsonl"}
    actual_public = {path.name for path in (DATASET / "public").iterdir()}
    if actual_public != expected_public:
        fail(errors, f"public inventory differs: {sorted(actual_public ^ expected_public)}")
    expected_private = {
        "applicability_gold.jsonl",
        "decision_state_spec.json",
        "evidence_node_omissions.jsonl",
        "gold.jsonl",
        "multi_hardening_manifest.jsonl",
        "search_necessity.jsonl",
        "task_assets.jsonl",
        "v151_case_repair_records.jsonl",
    }
    actual_private = {path.name for path in (DATASET / "private").iterdir()}
    if actual_private != expected_private:
        fail(errors, f"private inventory differs: {sorted(actual_private ^ expected_private)}")
    model_dirs = sorted(path.name for path in (DATASET / "models").iterdir() if path.is_dir())
    if model_dirs != EXPECTED_IDS:
        fail(errors, "models directory does not exactly cover R001-R120")
    for task_id in model_dirs:
        names = {path.name for path in (DATASET / "models" / task_id).iterdir()}
        if names != {"base_ir.json", "patched_ir.json", "solve_result.json"}:
            fail(errors, f"{task_id}: model file inventory differs")
    utf8_file_count = 0
    for path in DATASET.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".json", ".jsonl", ".md"}:
            utf8_file_count += 1
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                fail(errors, f"{path.relative_to(DATASET)}: invalid UTF-8: {exc}")
                continue
            if "\ufffd" in text:
                fail(errors, f"{path.relative_to(DATASET)}: Unicode replacement character remains")

    repairs = build.load_repairs()
    expected_readme = build.build_readme(repairs)
    readme = (DATASET / "README.md").read_text(encoding="utf-8")
    if readme != expected_readme:
        fail(errors, "README differs from the deterministic V1.5.1 template plus repair table")
    if not readme.startswith("# SearchWorthyOR-v1.5.1"):
        fail(errors, "README title/version mismatch")
    repair_markdown = (DATASET / "V151_REPAIR_RECORDS_zh.md").read_text(encoding="utf-8")
    headings = re.findall(r"^## (SWOR-R\d{3})$", repair_markdown, flags=re.MULTILINE)
    if headings != EXPECTED_IDS:
        fail(errors, "repair Markdown does not contain exactly one ordered section for every R001-R120")
    spec = (DATASET / "V151_CASE_REPAIR_SPEC_zh.md").read_text(encoding="utf-8")
    if not spec.startswith("# SearchWorthyOR V1.5.1 题目修复规范（执行版）"):
        fail(errors, "executed repair specification title/version mismatch")
    io_contract = (DATASET / "MODEL_IO_CONTRACT_zh.md").read_text(encoding="utf-8")
    for token in ("id", "case_id", "prompt_zh", "RETAIN", "PATCH_CHANGES", "applicability", "patch", "actions", "objective"):
        if token not in io_contract:
            fail(errors, f"model I/O contract omits {token}")

    tasks = read_jsonl(DATASET / "public" / "tasks_zh.jsonl")
    cases = read_jsonl(DATASET / "public" / "applicability_cases_zh.jsonl")
    gold_rows = read_jsonl(DATASET / "private" / "gold.jsonl")
    asset_rows = read_jsonl(DATASET / "private" / "task_assets.jsonl")
    app_rows = read_jsonl(DATASET / "private" / "applicability_gold.jsonl")
    search_rows = read_jsonl(DATASET / "private" / "search_necessity.jsonl")
    omissions = read_jsonl(DATASET / "private" / "evidence_node_omissions.jsonl")
    hardening = read_jsonl(DATASET / "private" / "multi_hardening_manifest.jsonl")
    repair_rows = read_jsonl(DATASET / "private" / "v151_case_repair_records.jsonl")
    state_spec = read_json(DATASET / "private" / "decision_state_spec.json")

    task_by_id = index_exact(errors, "tasks", tasks, "id", EXPECTED_IDS)
    gold_by_id = index_exact(errors, "gold", gold_rows, "id", EXPECTED_IDS)
    asset_by_id = index_exact(errors, "assets", asset_rows, "id", EXPECTED_IDS)
    search_by_id = index_exact(errors, "search", search_rows, "task_id", EXPECTED_IDS)
    repair_by_id = index_exact(errors, "repair records", repair_rows, "source_task_id", EXPECTED_IDS)
    if len(cases) != 240 or len(app_rows) != 240:
        fail(errors, f"case cardinality mismatch: public={len(cases)}, private={len(app_rows)}")
    public_by_case = {row.get("case_id"): row for row in cases}
    private_by_case = {row.get("case_id"): row for row in app_rows}
    if len(public_by_case) != 240 or set(public_by_case) != set(private_by_case):
        fail(errors, "public/private case IDs are not one-to-one")

    if state_spec != build.build_state_spec():
        fail(errors, "decision-state specification differs from the V1.5.1 two-state contract")
    mode_counts = Counter(row.get("task_mode") for row in gold_rows)
    if mode_counts != Counter({"single_hop_control": 60, "multi_hop_revision": 60}):
        fail(errors, f"task-mode balance changed: {mode_counts}")
    for row in gold_rows:
        if set(row) != GOLD_KEYS:
            fail(errors, f"{row.get('id')}: private Gold keys differ")
    for row in asset_rows:
        if set(row) != ASSET_KEYS:
            fail(errors, f"{row.get('id')}: task asset keys differ")
    for row in app_rows:
        expected_keys = APP_POSITIVE_KEYS if row.get("applicability") is True else APP_NEGATIVE_KEYS
        if set(row) != expected_keys:
            fail(errors, f"{row.get('case_id')}: applicability Gold keys differ")
    for row in search_rows:
        if set(row) != SEARCH_KEYS:
            fail(errors, f"{row.get('task_id')}: search-necessity keys differ")

    source_tasks = {row["id"]: row for row in read_jsonl(SOURCE / "public" / "tasks_zh.jsonl")}
    for task_id in EXPECTED_IDS:
        task = task_by_id[task_id]
        if set(task) != TASK_KEYS:
            fail(errors, f"{task_id}: public task keys differ")
            continue
        expected_problem = build.apply_source_replacements(
            task_id, source_tasks[task_id]["problem_zh"], repairs[task_id]["source_replacements"]
        )
        if task["problem_zh"] != expected_problem:
            fail(errors, f"{task_id}: source text differs from exact recorded replacements")
        expected_schema = deepcopy(source_tasks[task_id]["output_schema"])
        expected_actions = {row["id"]: row for row in expected_schema["actions"]}
        for public_id, meaning in repairs[task_id]["output_schema_meaning_overrides"].items():
            expected_actions[public_id]["meaning"] = meaning
        if task["output_schema"] != expected_schema:
            fail(errors, f"{task_id}: output_schema differs beyond recorded meaning overrides")
        schema = task["output_schema"]
        if set(schema) != {"schema_version", "actions", "objective"} or schema.get("schema_version") != "searchworthyor.public_output.v1.1":
            fail(errors, f"{task_id}: public output schema contract changed")
        public_action_ids = [row.get("id") for row in schema.get("actions", [])]
        if len(public_action_ids) != len(set(public_action_ids)) or not public_action_ids:
            fail(errors, f"{task_id}: public action IDs are empty or duplicated")
        for action in schema.get("actions", []):
            if set(action) != {"id", "meaning", "type"} or action.get("type") not in {"BINARY", "INTEGER"}:
                fail(errors, f"{task_id}/{action.get('id')}: public action schema differs")
            if build.is_placeholder_action_meaning(action.get("meaning")):
                fail(errors, f"{task_id}/{action.get('id')}: position-only public action meaning remains")
        if set(schema.get("objective", {})) != {"canonical_unit", "accepted_units"}:
            fail(errors, f"{task_id}: public objective schema differs")
        source_text = task["problem_zh"]
        for label, pattern in SOURCE_LEAK_PATTERNS.items():
            if pattern.search(source_text):
                fail(errors, f"{task_id}: source leakage pattern {label}: {pattern.search(source_text).group(0)!r}")
        record = repair_by_id[task_id]
        for key, value in repairs[task_id].items():
            if record.get(key) != value:
                fail(errors, f"{task_id}: persisted repair record differs on {key}")
        if record.get("review_date") != "2026-08-26" or not record.get("reviewed_by"):
            fail(errors, f"{task_id}: persisted repair review metadata missing")

    state_counts = Counter(row.get("decision_state") for row in app_rows)
    if state_counts != Counter({"RETAIN": 120, "PATCH_CHANGES": 120}):
        fail(errors, f"decision-state balance mismatch: {state_counts}")
    pairs_public: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pairs_private: dict[str, list[dict[str, Any]]] = defaultdict(list)
    placeholder = re.compile(r"\b(?:MATCH|CLOSED_BY_PUBLIC_LOCAL_FACTS|UNKNOWN|TBD|TODO)\b")
    for case in cases:
        case_id = case.get("case_id", "<missing>")
        if set(case) != CASE_KEYS:
            fail(errors, f"{case_id}: public case keys differ")
            continue
        if set(case["case_facts"]) != CASE_FIELDS:
            fail(errors, f"{case_id}: case fact fields differ")
        if any(value is None or value == "" for value in case["case_facts"].values()):
            fail(errors, f"{case_id}: empty case fact")
        fact_text = json.dumps(case["case_facts"], ensure_ascii=False)
        if placeholder.search(fact_text):
            fail(errors, f"{case_id}: placeholder remains in case facts")
        for label, pattern in FACT_CONCLUSION_PATTERNS.items():
            match = pattern.search(fact_text)
            if match:
                fail(errors, f"{case_id}: case fact conclusion pattern {label}: {match.group(0)!r}")
        task_id = case["source_task_id"]
        expected_suffix = case_id.rsplit("-", 1)[-1]
        if expected_suffix not in {"C1", "C2"} or case["case_facts"] != repairs[task_id]["case_facts"].get(expected_suffix):
            fail(errors, f"{case_id}: facts differ from reviewed repair shard")
        if case["output_schema"] != task_by_id[task_id]["output_schema"]:
            fail(errors, f"{case_id}: output_schema differs from source task")
        expected_problem = build.render_case_problem_zh(task_by_id[task_id]["problem_zh"], case["case_facts"])
        if case["problem_zh"] != expected_problem:
            fail(errors, f"{case_id}: problem_zh order/content is non-canonical")
        if case["prompt_zh"] != build.render_prompt(case):
            fail(errors, f"{case_id}: prompt_zh serialization is non-canonical")
        if case["base_semantics_contract"] != build.CASE_BASE_SEMANTICS_CONTRACT:
            fail(errors, f"{case_id}: base semantics contract mismatch")
        if "历史描述冲突" in case["prompt_zh"] or "冲突文字作废" in case["prompt_zh"]:
            fail(errors, f"{case_id}: old conflict/deletion meta-language remains")
        if any(key in case for key in ("decision_state", "applicability", "gold_patch_elements", "official_support")):
            fail(errors, f"{case_id}: private Gold leaked into public record")
        pairs_public[case["pair_id"]].append(case)
    for row in app_rows:
        pairs_private[row["pair_id"]].append(row)

    if len(pairs_public) != 120 or set(pairs_public) != set(pairs_private):
        fail(errors, "expected 120 aligned public/private pairs")
    for pair_id in sorted(pairs_public):
        public_pair = pairs_public[pair_id]
        private_pair = pairs_private[pair_id]
        if len(public_pair) != 2 or len(private_pair) != 2:
            fail(errors, f"{pair_id}: expected two public and two private cases")
            continue
        negative = next((row for row in private_pair if row.get("applicability") is False), None)
        positive = next((row for row in private_pair if row.get("applicability") is True), None)
        if negative is None or positive is None:
            fail(errors, f"{pair_id}: expected one applicable and one non-applicable case")
            continue
        task_id = positive["source_task_id"]
        if negative["case_id"] != f"{task_id}-C1" or positive["case_id"] != f"{task_id}-C2":
            fail(errors, f"{pair_id}: C1/C2 polarity changed")
            continue
        c1 = public_by_case[negative["case_id"]]
        c2 = public_by_case[positive["case_id"]]
        diffs = sorted(key for key in CASE_FIELDS if c1["case_facts"][key] != c2["case_facts"][key])
        if diffs != sorted(negative.get("changed_factors", [])):
            fail(errors, f"{pair_id}: actual fact differences do not match private changed_factors")
        if negative.get("changed_factor") not in diffs or negative.get("changed_factor") != repairs[task_id]["changed_factor"]:
            fail(errors, f"{pair_id}: primary changed_factor mismatch")
        if negative.get("negative_value") != c1["case_facts"][negative["changed_factor"]]:
            fail(errors, f"{negative['case_id']}: negative_value mismatch")
        if negative.get("positive_value") != c2["case_facts"][negative["changed_factor"]]:
            fail(errors, f"{negative['case_id']}: positive_value mismatch")
        if negative.get("non_applicability_reason") != repairs[task_id]["non_applicability_reason"]:
            fail(errors, f"{negative['case_id']}: non-applicability reason mismatch")
        if negative.get("decision_state") != "RETAIN" or negative.get("gold_patch_elements") != []:
            fail(errors, f"{negative['case_id']}: RETAIN semantics violated")
        if positive.get("decision_state") != "PATCH_CHANGES" or not positive.get("gold_patch_elements"):
            fail(errors, f"{positive['case_id']}: PATCH_CHANGES semantics violated")
        if positive.get("changed_factor") is not None:
            fail(errors, f"{positive['case_id']}: positive row changed_factor must remain null")
        if negative.get("official_support") != positive.get("official_support"):
            fail(errors, f"{pair_id}: paired cases do not share official evidence")
        if build.render_prompt(c1) == build.render_prompt(c2):
            fail(errors, f"{pair_id}: paired actual prompts are identical")

    independent_ir_count = 0
    replay_count = 0
    action_changed_count = 0
    for task_id in EXPECTED_IDS:
        gold = gold_by_id[task_id]
        asset = asset_by_id[task_id]
        if gold.get("task_mode") != asset.get("task_mode"):
            fail(errors, f"{task_id}: Gold/asset task mode mismatch")
        if gold.get("correct_patch_elements") != asset.get("patch_elements"):
            fail(errors, f"{task_id}: Gold/asset Patch mismatch")
        expected_paths = {
            "base_model_path": f"models/{task_id}/base_ir.json",
            "patched_model_path": f"models/{task_id}/patched_ir.json",
            "solve_result_path": f"models/{task_id}/solve_result.json",
        }
        for key, value in expected_paths.items():
            if gold.get(key) != value:
                fail(errors, f"{task_id}: {key} path mismatch")
        base = read_json(DATASET / expected_paths["base_model_path"])
        patched = read_json(DATASET / expected_paths["patched_model_path"])
        result = read_json(DATASET / expected_paths["solve_result_path"])
        validate_ir_schema(errors, task_id, "base", base)
        validate_ir_schema(errors, task_id, "patched", patched)
        if set(result) != SOLVE_KEYS:
            fail(errors, f"{task_id}: solve_result keys differ")
        if result.get("schema_version") != "searchworthyor.rapid_solve_result.v0" or result.get("id") != task_id:
            fail(errors, f"{task_id}: solve_result schema/id mismatch")
        try:
            reconstructed = reconstruct_patched(base, gold["correct_patch_elements"], task_id)
            if normalize_named_ir_collections(reconstructed) != normalize_named_ir_collections(patched):
                fail(errors, f"{task_id}: typed Patch replay does not reconstruct patched IR by named elements")
            else:
                replay_count += 1
        except (AssertionError, KeyError, TypeError) as exc:
            fail(errors, str(exc))
        for variant, ir in (("base", base), ("patched", patched)):
            try:
                count, objective, actions = build.enumerate_ir(ir)
                independent_ir_count += 1
            except (AssertionError, KeyError, TypeError, ValueError) as exc:
                fail(errors, f"{task_id}/{variant}: enumeration failed: {exc}")
                continue
            if count != result.get(f"{variant}_feasible_assignment_count"):
                fail(errors, f"{task_id}/{variant}: feasible count mismatch")
            if abs(objective - float(result.get(f"{variant}_objective", float('nan')))) > 1e-9:
                fail(errors, f"{task_id}/{variant}: objective mismatch")
            if actions != result.get(f"{variant}_optimal_actions"):
                fail(errors, f"{task_id}/{variant}: optimal action set mismatch")
        if result.get("base_status") != "OPTIMAL" or result.get("patched_status") != "OPTIMAL":
            fail(errors, f"{task_id}: solve statuses must both be OPTIMAL")
        base_set = {tuple(sorted(row.items())) for row in result.get("base_optimal_actions", [])}
        patched_set = {tuple(sorted(row.items())) for row in result.get("patched_optimal_actions", [])}
        common = base_set & patched_set
        if common or result.get("common_optimal_action_feasible") is not False or result.get("common_optimal_actions"):
            fail(errors, f"{task_id}: Base/Patched optimal action sets are not disjoint")
        if result.get("optimal_action_changed") is not True:
            fail(errors, f"{task_id}: optimal_action_changed is not true")
        else:
            action_changed_count += 1
        if result.get("base_optimal_actions") != gold.get("base_optimal_action_set"):
            fail(errors, f"{task_id}: base solve/Gold action mismatch")
        if result.get("patched_optimal_actions") != gold.get("patched_optimal_action_set"):
            fail(errors, f"{task_id}: patched solve/Gold action mismatch")
        contract = gold.get("objective_value_contract", {})
        if contract != result.get("objective_value_contract") or abs(float(contract.get("canonical_value", float('nan'))) - float(result.get("patched_objective", float('nan')))) > 1e-9:
            fail(errors, f"{task_id}: objective contract mismatch")
        accepted_units = task_by_id[task_id]["output_schema"]["objective"]["accepted_units"]
        expected_patched_contract = build.objective_contract_with_value(
            contract, result["patched_objective"], accepted_units
        )
        if contract != expected_patched_contract:
            fail(errors, f"{task_id}: accepted objective units do not convert to the canonical value")
        public_actions = {row["id"]: row for row in task_by_id[task_id]["output_schema"]["actions"]}
        mapping = gold.get("public_to_private_action_map", {})
        if set(public_actions) != set(mapping) or len(set(mapping.values())) != len(mapping):
            fail(errors, f"{task_id}: public/private action map mismatch")
        for variant, ir in (("base", base), ("patched", patched)):
            source_ir = read_json(SOURCE / "models" / task_id / f"{variant}_ir.json")
            expected_objective_meaning = (
                repairs[task_id]["model_objective_meaning_override"]
                or source_ir["objective"]["meaning"]
            )
            if ir["objective"]["meaning"] != expected_objective_meaning:
                fail(errors, f"{task_id}/{variant}: objective meaning was not preserved or recorded")
        for public_id, private_name in mapping.items():
            for variant, ir in (("base", base), ("patched", patched)):
                matches = [row for row in ir["variables"] if row["name"] == private_name]
                source_ir = read_json(SOURCE / "models" / task_id / f"{variant}_ir.json")
                source_matches = [row for row in source_ir["variables"] if row["name"] == private_name]
                expected_meaning = repairs[task_id]["output_schema_meaning_overrides"].get(
                    public_id,
                    source_matches[0]["meaning"] if len(source_matches) == 1 else None,
                )
                if len(matches) != 1 or len(source_matches) != 1 or matches[0]["meaning"] != expected_meaning:
                    fail(errors, f"{task_id}/{variant}/{public_id}: private action meaning was not preserved or overridden")
                if public_id in repairs[task_id]["output_schema_meaning_overrides"] and matches[0]["meaning"] != public_actions[public_id]["meaning"]:
                    fail(errors, f"{task_id}/{variant}/{public_id}: recorded meaning override is not synchronized")

        negative = private_by_case[f"{task_id}-C1"]
        positive = private_by_case[f"{task_id}-C2"]
        reverse = {private: public for public, private in mapping.items()}
        expected_base_actions = [
            [{"id": reverse[name], "value": value} for name, value in sorted(row.items(), key=lambda item: reverse[item[0]])]
            for row in gold["base_optimal_action_set"]
        ]
        expected_patched_actions = [
            [{"id": reverse[name], "value": value} for name, value in sorted(row.items(), key=lambda item: reverse[item[0]])]
            for row in gold["patched_optimal_action_set"]
        ]
        if canonical_public_actions(negative["gold_action_set"]) != canonical_public_actions(expected_base_actions):
            fail(errors, f"{task_id}-C1: public Gold actions differ from base solve")
        if canonical_public_actions(positive["gold_action_set"]) != canonical_public_actions(expected_patched_actions):
            fail(errors, f"{task_id}-C2: public Gold actions differ from patched solve")
        if positive["gold_patch_elements"] != gold["correct_patch_elements"]:
            fail(errors, f"{task_id}-C2: case Patch differs from task Gold")
        if abs(float(negative["gold_objective"]["canonical_value"]) - float(result["base_objective"])) > 1e-9:
            fail(errors, f"{task_id}-C1: objective differs from base solve")
        if abs(float(positive["gold_objective"]["canonical_value"]) - float(result["patched_objective"])) > 1e-9:
            fail(errors, f"{task_id}-C2: objective differs from patched solve")
        expected_base_contract = build.objective_contract_with_value(
            contract, result["base_objective"], accepted_units
        )
        if negative["gold_objective"] != expected_base_contract:
            fail(errors, f"{task_id}-C1: accepted objective units are inconsistent")
        if positive["gold_objective"] != expected_patched_contract:
            fail(errors, f"{task_id}-C2: accepted objective units are inconsistent")

    positive_support = {
        row["source_task_id"]: row["official_support"] for row in app_rows if row.get("applicability") is True
    }
    omission_by_key = {(row.get("task_id"), row.get("omitted_node_id")): row for row in omissions}
    hardening_by_id = {row.get("id"): row for row in hardening}
    expected_omissions = 0
    evidence_nodes = 0
    for task_id in EXPECTED_IDS:
        asset = asset_by_id[task_id]
        evidence = asset.get("official_evidence")
        if not isinstance(evidence, list) or not evidence:
            fail(errors, f"{task_id}: official evidence must be non-empty")
            continue
        evidence_nodes += len(evidence)
        node_ids = [node.get("node_id") for node in evidence]
        source_ids = [node.get("source_node_id") for node in evidence]
        if len(node_ids) != len(set(node_ids)) or len(source_ids) != len(set(source_ids)):
            fail(errors, f"{task_id}: evidence node/source IDs must be unique")
        patch_names = {row["name"] for row in asset["patch_elements"]}
        covered: set[str] = set()
        support_by_source = {row["node_id"]: row for row in positive_support[task_id]}
        for node in evidence:
            label = f"{task_id}/{node.get('node_id')}"
            if set(node) != EVIDENCE_KEYS:
                fail(errors, f"{label}: official evidence keys differ")
                continue
            if not node["url"].startswith(("https://", "http://")) or not node["publisher"].strip() or len(node["quote"].strip()) < 20:
                fail(errors, f"{label}: incomplete official source metadata")
            if re.search(r"\.{3}|…", node["quote"]):
                fail(errors, f"{label}: official evidence quote contains an editorial ellipsis")
            slots = set(node["supported_patch_slots"])
            if not slots <= patch_names:
                fail(errors, f"{label}: evidence references nonexistent Patch slots")
            covered.update(slots)
            if node["support_target_type"] not in {"patch_slot", "applicability_gate", "retained_action", "exception_boundary"}:
                fail(errors, f"{label}: invalid support_target_type")
            if not isinstance(node["support_targets"], list) or not node["support_targets"]:
                fail(errors, f"{label}: support_targets must be non-empty")
            if slots and (node["support_target_type"] != "patch_slot" or set(node["support_targets"]) != slots):
                fail(errors, f"{label}: Patch target metadata mismatch")
            support = support_by_source.get(node["source_node_id"])
            if support is None or any(support.get(key) != node[key] for key in ("publisher", "url", "quote")):
                fail(errors, f"{label}: official support does not close to asset evidence")
        if covered != patch_names:
            fail(errors, f"{task_id}: official evidence does not cover every Patch slot")
        search = search_by_id[task_id]
        if search.get("corresponding_patch_elements") != asset["patch_elements"]:
            fail(errors, f"{task_id}: search/Patch mismatch")
        if search.get("required_pages") != list(dict.fromkeys(node["url"] for node in evidence)):
            fail(errors, f"{task_id}: search required_pages mismatch")
        if search.get("required_quotes") != list(dict.fromkeys(node["quote"] for node in evidence)):
            fail(errors, f"{task_id}: search required_quotes mismatch")
        if asset["task_mode"] == "multi_hop_revision":
            expected_omissions += len(evidence)
            hard = hardening_by_id.get(task_id)
            if hard is None or hard.get("empirical_omission_test_status") != "NOT_RUN":
                fail(errors, f"{task_id}: hardening metadata missing or overclaimed")
            for node in evidence:
                derivative = omission_by_key.get((task_id, node["node_id"]))
                if derivative is None:
                    fail(errors, f"{task_id}/{node['node_id']}: omission derivative missing")
                    continue
                for key in ("source_node_id", "supported_patch_slots", "support_target_type", "support_targets", "publisher", "url", "quote"):
                    if derivative.get(key) != node[key]:
                        fail(errors, f"{task_id}/{node['node_id']}: omission derivative differs on {key}")
                if derivative.get("empirical_omission_test_status") != "NOT_RUN" or derivative.get("remaining_evidence_uniquely_determines_gold_patch") is not None:
                    fail(errors, f"{task_id}/{node['node_id']}: unrun omission test is overclaimed")
    if len(omissions) != expected_omissions:
        fail(errors, f"omission cardinality {len(omissions)} != {expected_omissions}")
    expected_multi = {row["id"] for row in asset_rows if row["task_mode"] == "multi_hop_revision"}
    if set(hardening_by_id) != expected_multi:
        fail(errors, "hardening manifest does not exactly cover Multi tasks")

    # Regression for the one Gold correction identified during the full review.
    r001_patch = gold_by_id["SWOR-R001"]["correct_patch_elements"]
    expected_r001_constraint = {
        "coefficients": {
            "lot_a": 20,
            "lot_b": 18,
            "lot_c": 17,
            "lot_d": 16,
            "lot_e": 15,
            "lot_f": 14,
            "trade_support_p": -5,
        },
        "meaning": "同一进口人同一日历年所选CBAM货物总净重超过50吨时，运营方案P提供本题所列执行能力",
        "name": "annual_mass_branch",
        "rhs": 50,
        "sense": "<=",
    }
    r001_result = read_json(DATASET / "models" / "SWOR-R001" / "solve_result.json")
    expected_r001_action = {
        "lot_a": 0,
        "lot_b": 1,
        "lot_c": 1,
        "lot_d": 0,
        "lot_e": 1,
        "lot_f": 0,
        "trade_support_p": 0,
    }
    if len(r001_patch) != 1 or r001_patch[0].get("after") != expected_r001_constraint:
        fail(errors, "R001 strict-more-than-50-tonne Patch regression failed")
    if (r001_result.get("base_feasible_assignment_count"), r001_result.get("base_objective")) != (40, 69.0):
        fail(errors, "R001 Base regression must remain 40 feasible / objective 69")
    if (r001_result.get("patched_feasible_assignment_count"), r001_result.get("patched_objective")) != (31, 65.0):
        fail(errors, "R001 patched regression must be 31 feasible / objective 65")
    if r001_result.get("patched_optimal_actions") != [expected_r001_action]:
        fail(errors, "R001 patched action regression must be B+C+E with P=0")

    report = {
        "schema_version": "searchworthyor.v151.validation.v1",
        "status": "PASS" if not errors else "FAIL",
        "dataset": "SearchWorthyOR-v1.5.1",
        "counts": {
            "source_tasks_reviewed": len(tasks),
            "public_cases_reviewed": len(cases),
            "repair_records": len(repair_rows),
            "retain_cases": state_counts.get("RETAIN", 0),
            "patch_changes_cases": state_counts.get("PATCH_CHANGES", 0),
            "single_hop_tasks": mode_counts.get("single_hop_control", 0),
            "multi_hop_tasks": mode_counts.get("multi_hop_revision", 0),
            "official_evidence_nodes": evidence_nodes,
            "multi_evidence_omission_records": len(omissions),
            "utf8_text_files": utf8_file_count,
            "model_files": len(model_dirs) * 3,
        },
        "gates": {
            "canonical_public_prompts": len(cases),
            "public_private_pairs": len(pairs_public),
            "typed_patches_replayed": replay_count,
            "ir_files_independently_enumerated": independent_ir_count,
            "decision_changing_model_pairs": action_changed_count,
            "public_leakage_findings": sum("leakage pattern" in error or "conclusion pattern" in error for error in errors),
        },
        "targeted_regressions": {
            "R001_base_feasible": r001_result.get("base_feasible_assignment_count"),
            "R001_base_objective": r001_result.get("base_objective"),
            "R001_patched_feasible": r001_result.get("patched_feasible_assignment_count"),
            "R001_patched_objective": r001_result.get("patched_objective"),
            "R001_patched_actions": r001_result.get("patched_optimal_actions"),
        },
        "errors": errors,
    }
    (DATASET / "validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if errors:
        raise SystemExit("\n".join(errors))
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()

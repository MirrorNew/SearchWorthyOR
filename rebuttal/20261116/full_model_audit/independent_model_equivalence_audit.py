"""Independent exact finite-domain audit of saved C2 model artifacts.

Reads the frozen reference IR and the persisted Standard/SWAgent models directly.
No experiment, model API, solver, network access, or source-file modification.
JSON decimals are parsed as Decimal and duplicate object keys are rejected.
"""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
from collections import Counter
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
DATA = ROOT / "datasets" / "SearchWorthyOR-v1.6.3"
EXPERIMENTS = ROOT / "experiments" / "deepseek_20261107"
OLD_RECORDS = ROOT / "analysis" / "rebuttal_dqz1_evidence_20261114" / "model_full_equivalence_records.jsonl"
MAX_ASSIGNMENTS = 2**20
TOLERANCE = Fraction(1, 10**7)
METHODS = {
    "Standard-online": ("deepseek_standard_knowledge_20261107_v1", "standard_knowledge_on"),
    "SWAgent-online": ("deepseek_four_groups_20261107_v1", "swagent_on"),
}


class AuditError(ValueError):
    pass


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AuditError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"), parse_float=Decimal,
                      object_pairs_hook=reject_duplicate_keys)


def digest(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path):
    return path.relative_to(ROOT).as_posix()


def exact_number(value: Any) -> Fraction:
    if isinstance(value, bool) or value is None:
        raise AuditError("boolean or missing numeric value")
    try:
        if isinstance(value, Fraction):
            return value
        if isinstance(value, Decimal):
            if not value.is_finite():
                raise AuditError("non-finite numeric value")
            return Fraction(value)
        if isinstance(value, int):
            return Fraction(value)
        return Fraction(str(value))
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise AuditError(f"invalid numeric value: {value!r}") from exc


def ceil_fraction(value: Fraction):
    return -((-value.numerator) // value.denominator)


def floor_fraction(value: Fraction):
    return value.numerator // value.denominator


def normalize(raw: Any, public_to_private=None):
    if not isinstance(raw, dict):
        raise AuditError("missing model object")
    allowed = {"schema_version", "id", "variant", "family", "source_candidate_id", "variables",
               "objective", "constraints", "action_projection"}
    unknown = set(raw) - allowed
    if unknown:
        raise AuditError("unsupported model fields: " + str(sorted(unknown)))
    rename = {private: public for public, private in (public_to_private or {}).items()}
    if public_to_private is not None and len(rename) != len(public_to_private):
        raise AuditError("public/private mapping is not one-to-one")

    projection = raw.get("action_projection")
    if projection is not None and (not isinstance(projection, list) or
                                   any(not isinstance(x, str) for x in projection) or
                                   len(projection) != len(set(projection))):
        raise AuditError("malformed action_projection")
    variables = []
    for var in raw.get("variables", []):
        if not isinstance(var, dict):
            raise AuditError("variable is not an object")
        unknown = set(var) - {"id", "name", "type", "lb", "ub", "meaning"}
        if unknown or ("id" in var and "name" in var):
            raise AuditError("unsupported or ambiguous variable fields")
        name = var.get("id", var.get("name"))
        if not isinstance(name, str):
            raise AuditError("missing variable id")
        variables.append({"id": rename.get(name, name), "type": var.get("type"),
                          "lb": var.get("lb"), "ub": var.get("ub")})

    obj = raw.get("objective", {})
    if not isinstance(obj, dict):
        raise AuditError("objective is not an object")
    unknown = set(obj) - {"direction", "sense", "unit", "constant", "terms", "coefficients", "meaning", "citations"}
    if unknown or ("direction" in obj and "sense" in obj) or ("terms" in obj and "coefficients" in obj):
        raise AuditError("unsupported or ambiguous objective fields")
    terms = obj.get("terms", obj.get("coefficients"))
    if not isinstance(terms, dict):
        raise AuditError("nonlinear or missing objective terms")
    objective = {"direction": obj.get("direction", obj.get("sense")), "unit": obj.get("unit"),
                 "constant": obj.get("constant", 0),
                 "terms": {rename.get(k, k): v for k, v in terms.items()}}

    constraints = []
    for row in raw.get("constraints", []):
        if not isinstance(row, dict):
            raise AuditError("constraint is not an object")
        unknown = set(row) - {"name", "sense", "rhs", "terms", "coefficients", "citations", "meaning", "when"}
        if unknown:
            raise AuditError("unsupported constraint fields: " + str(sorted(unknown)))
        terms = row.get("terms", row.get("coefficients"))
        if not isinstance(terms, dict) or ("terms" in row and "coefficients" in row):
            raise AuditError("nonlinear or missing constraint terms")
        when = row.get("when")
        if when is not None:
            if not isinstance(when, dict) or set(when) != {"variable", "equals"}:
                raise AuditError("unsupported indicator condition")
            when = {"variable": rename.get(when["variable"], when["variable"]), "equals": when["equals"]}
        sense = "==" if row.get("sense") == "=" else row.get("sense")
        constraints.append({"name": row.get("name"), "sense": sense, "rhs": row.get("rhs"),
                            "terms": {rename.get(k, k): v for k, v in terms.items()}, "when": when})
    return {"variables": variables, "objective": objective, "constraints": constraints,
            "action_projection": projection}


def enumerate_model(model, public_ids):
    variables = model["variables"]
    names = [v["id"] for v in variables]
    if len(names) != len(set(names)) or not set(public_ids).issubset(names):
        raise AuditError("duplicate or missing public variables")
    index = {name: i for i, name in enumerate(names)}
    domains = []
    for var in variables:
        if var["type"] not in ("BINARY", "INTEGER"):
            raise AuditError("continuous or unsupported variable type")
        lo_value, hi_value = exact_number(var["lb"]), exact_number(var["ub"])
        lo, hi = ceil_fraction(lo_value), floor_fraction(hi_value)
        if var["type"] == "BINARY":
            lo, hi = max(0, lo), min(1, hi)
        # Unlike range(lo, max(lo, hi + 1)), this preserves an empty domain.
        domains.append(range(lo, hi + 1))
    combinations = math.prod(len(domain) for domain in domains)
    if combinations > MAX_ASSIGNMENTS:
        raise AuditError(f"enumeration cap exceeded: {combinations}")

    obj = model["objective"]
    if obj["direction"] not in ("min", "max") or not isinstance(obj["unit"], str):
        raise AuditError("unsupported objective direction/unit")
    if not set(obj["terms"]).issubset(index):
        raise AuditError("undefined variable in objective")
    auxiliary = set(names) - set(public_ids)
    if any(exact_number(obj["terms"].get(name, 0)) != 0 for name in auxiliary):
        raise AuditError("objective depends on auxiliary variables")
    objective_coeff = {name: exact_number(obj["terms"].get(name, 0)) for name in names}
    objective_constant = exact_number(obj["constant"])

    constraints = []
    for row in model["constraints"]:
        if row["sense"] not in ("<=", ">=", "==") or not set(row["terms"]).issubset(index):
            raise AuditError("unsupported constraint relation or undefined variable")
        terms = [(index[name], exact_number(coef)) for name, coef in row["terms"].items()]
        rhs = exact_number(row["rhs"])
        when = row["when"]
        trigger = None
        if when is not None:
            if (when["variable"] not in index or variables[index[when["variable"]]]["type"] != "BINARY" or
                    type(when["equals"]) is not int or when["equals"] not in (0, 1)):
                raise AuditError("indicator trigger must be a binary variable equal to 0/1")
            trigger = (index[when["variable"]], when["equals"])
        constraints.append((terms, row["sense"], rhs, trigger))

    public_indices = [index[name] for name in public_ids]
    feasible = {}
    feasible_assignments = 0
    for assignment in itertools.product(*domains):
        valid = True
        for terms, sense, rhs, trigger in constraints:
            if trigger is not None and assignment[trigger[0]] != trigger[1]:
                continue
            lhs = sum((coef * assignment[i] for i, coef in terms), Fraction(0))
            if ((sense == "<=" and lhs > rhs) or (sense == ">=" and lhs < rhs) or
                    (sense == "==" and lhs != rhs)):
                valid = False
                break
        if not valid:
            continue
        feasible_assignments += 1
        action = tuple(assignment[i] for i in public_indices)
        value = objective_constant + sum((objective_coeff[names[i]] * assignment[i]
                                          for i in range(len(names))), Fraction(0))
        if action in feasible and feasible[action] != value:
            raise AuditError("non-unique objective under auxiliary projection")
        feasible[action] = value
    return feasible, {"enumerated_assignments": combinations,
                      "feasible_assignments_before_projection": feasible_assignments,
                      "feasible_public_actions": len(feasible), "auxiliary_variables": len(auxiliary),
                      "empty_variable_domains": sum(len(domain) == 0 for domain in domains)}


def action_object(action, value, public_ids):
    return {"actions": dict(zip(public_ids, action)), "objective_exact": str(value)}


def compare(reference, generated, ref_map, gen_map, public_ids):
    missing = sorted(set(ref_map) - set(gen_map))
    extra = sorted(set(gen_map) - set(ref_map))
    shared = ref_map.keys() & gen_map.keys()
    objective_mismatch = sorted(a for a in shared if abs(ref_map[a] - gen_map[a]) > TOLERANCE)
    strict_mismatch = sum(ref_map[a] != gen_map[a] for a in shared)
    direction_equal = reference["objective"]["direction"] == generated["objective"]["direction"]
    unit_equal = reference["objective"]["unit"] == generated["objective"]["unit"]
    region_equal = not missing and not extra
    objective_equal = not objective_mismatch
    status = "PASS" if region_equal and objective_equal and direction_equal and unit_equal else "FAIL"
    return {
        "full_model_status": status,
        "feasible_region_equal": region_equal,
        "objective_equal_on_shared_feasible_actions": objective_equal,
        "objective_strict_rational_mismatches": strict_mismatch,
        "direction_equal": direction_equal,
        "unit_equal": unit_equal,
        "reference_feasible_missing_from_generated": len(missing),
        "generated_extra_feasible": len(extra),
        "shared_feasible_objective_mismatches": len(objective_mismatch),
        "counterexamples": {
            "overconstrained": [action_object(a, ref_map[a], public_ids) for a in missing[:3]],
            "underconstrained": [action_object(a, gen_map[a], public_ids) for a in extra[:3]],
            "objective": [{**action_object(a, gen_map[a], public_ids),
                           "reference_objective_exact": str(ref_map[a]),
                           "absolute_difference_exact": str(abs(ref_map[a] - gen_map[a]))}
                          for a in objective_mismatch[:3]],
        },
    }


def optimal_set_audit(generated, gen_feasible, gold, public_ids, reference):
    mapping = gold["public_to_private_action_map"]
    gold_optimal = {tuple(action[mapping[name]] for name in public_ids)
                    for action in gold["full_optimal_action_set"]}
    if not gen_feasible:
        return {"instance_optimal_set_status": "NO_FEASIBLE_GENERATED_ACTION",
                "gold_optimal_action_count": len(gold_optimal), "generated_optimal_action_count": 0,
                "gold_optimal_actions_missing_from_generated_optimum": len(gold_optimal),
                "non_gold_generated_optimal_actions": 0,
                "gold_optimal_set_is_subset_of_generated_optimal_set": False,
                "generated_optimal_set_is_subset_of_gold_optimal_set": True}
    if generated["objective"]["direction"] not in ("min", "max"):
        return {"instance_optimal_set_status": "NOT_COMPARABLE_DIRECTION"}
    best = (max if generated["objective"]["direction"] == "max" else min)(gen_feasible.values())
    generated_optimal = {action for action, value in gen_feasible.items() if abs(value - best) <= TOLERANCE}
    gold_missing = gold_optimal - generated_optimal
    generated_extra = generated_optimal - gold_optimal
    if generated_optimal == gold_optimal:
        relation = "EQUAL"
    elif gold_optimal <= generated_optimal:
        relation = "GOLD_SET_STRICT_SUBSET_GENERATED_OPTIMUM"
    elif generated_optimal <= gold_optimal:
        relation = "GENERATED_OPTIMUM_STRICT_SUBSET_GOLD_SET"
    elif gold_optimal & generated_optimal:
        relation = "PARTIAL_OVERLAP"
    else:
        relation = "DISJOINT"
    comparable = (generated["objective"]["direction"] == reference["objective"]["direction"] and
                  generated["objective"]["unit"] == gold["objective_value_contract"]["canonical_unit"])
    return {
        "instance_optimal_set_status": relation if comparable else "NOT_COMPARABLE_DIRECTION_OR_UNIT",
        "instance_optimal_set_relation_raw": relation,
        "instance_optimal_set_comparable": comparable,
        "gold_optimal_action_count": len(gold_optimal),
        "generated_optimal_action_count": len(generated_optimal),
        "gold_optimal_actions_missing_from_generated_optimum": len(gold_missing),
        "non_gold_generated_optimal_actions": len(generated_extra),
        "gold_optimal_set_is_subset_of_generated_optimal_set": gold_optimal <= generated_optimal,
        "generated_optimal_set_is_subset_of_gold_optimal_set": generated_optimal <= gold_optimal,
        "generated_optimal_objective_exact": str(best),
        "gold_optimal_actions_sample": [dict(zip(public_ids, action)) for action in sorted(gold_optimal)[:3]],
        "generated_optimal_actions_sample": [dict(zip(public_ids, action)) for action in sorted(generated_optimal)[:3]],
    }


def tag_counterexamples(counterexamples, gen_feasible, generated, gold, public_ids):
    mapping = gold["public_to_private_action_map"]
    gold_optimal = {tuple(action[mapping[name]] for name in public_ids)
                    for action in gold["full_optimal_action_set"]}
    generated_optimal = set()
    if gen_feasible:
        best = (max if generated["objective"]["direction"] == "max" else min)(gen_feasible.values())
        generated_optimal = {action for action, value in gen_feasible.items() if abs(value - best) <= TOLERANCE}
    for label in ("overconstrained", "underconstrained", "objective"):
        for sample in counterexamples.get(label, []):
            action = tuple(sample["actions"][name] for name in public_ids)
            sample["is_frozen_gold_optimal"] = action in gold_optimal
            sample["is_generated_model_optimal"] = action in generated_optimal
            sample["is_gold_optimal_but_excluded_from_generated_optimum"] = action in gold_optimal and action not in generated_optimal
            sample["is_non_gold_generated_optimum"] = action not in gold_optimal and action in generated_optimal
            sample["feasible_in_generated_model"] = action in gen_feasible


def primary_category(row):
    if row.get("full_model_status") == "UNRESOLVED":
        return "MISSING_DELIVERABLE" if not row.get("terminal_result_available") else "UNRESOLVED_OTHER"
    if not row.get("feasible_region_equal"):
        return "FEASIBLE_REGION_DIFFERENCE"
    if not row.get("objective_equal_on_shared_feasible_actions"):
        return "SAME_DOMAIN_OBJECTIVE_DIFFERENCE"
    if not row.get("direction_equal") or not row.get("unit_equal"):
        return "DIRECTION_UNIT_ONLY"
    return "PASS"


def initial_model(case: Path, reference, ref_feasible, public_ids):
    for path in sorted((case / "semantic").glob("*UPDATE*.json")):
        try:
            saved = read_json(path)
        except Exception as exc:
            return {"initial_full_model_status": "UNRESOLVED", "initial_reason": f"{type(exc).__name__}: {exc}",
                    "initial_model_file": rel(path), "initial_model_sha256": digest(path)}
        for message in saved.get("messages", []):
            if message.get("role") != "user":
                continue
            try:
                payload = json.loads(message.get("content", ""), parse_float=Decimal,
                                     object_pairs_hook=reject_duplicate_keys)
            except (TypeError, ValueError, json.JSONDecodeError, AuditError):
                continue
            if not isinstance(payload, dict) or not isinstance(payload.get("model"), dict):
                continue
            info = {"initial_model_file": rel(path), "initial_model_sha256": digest(path),
                    "initial_request_contains_external_sources": bool(payload.get("sources")),
                    "initial_full_model_status": "UNRESOLVED"}
            try:
                model = normalize(payload["model"])
                feasible, stats = enumerate_model(model, public_ids)
                cmp = compare(reference, model, ref_feasible, feasible, public_ids)
                info.update({"initial_full_model_status": cmp["full_model_status"],
                             "initial_feasible_public_actions": stats["feasible_public_actions"],
                             "initial_counterexamples": cmp["counterexamples"]})
            except (AuditError, KeyError, TypeError) as exc:
                info["initial_reason"] = f"{type(exc).__name__}: {exc}"
            return info
    return {"initial_full_model_status": "UNRESOLVED", "initial_reason": "no saved UPDATE request containing a model"}


def validate_reference(reference, feasible, gold, mapping, public_ids):
    result = {"source_task_id": gold["id"], "nonempty_feasible_set": bool(feasible),
              "mapping_one_to_one_and_matches_projection":
                  len(set(mapping.values())) == len(mapping) and set(mapping.values()) == set(reference["action_projection"]),
              "optimal_actions_match_frozen_gold": False, "optimal_value_matches_frozen_gold": False}
    if feasible:
        direction = reference["objective"]["direction"]
        opt = (max if direction == "max" else min)(feasible.values())
        optimal = {action for action, value in feasible.items() if abs(value - opt) <= TOLERANCE}
        expected = {tuple(action[mapping[name]] for name in public_ids)
                    for action in gold["full_optimal_action_set"]}
        result["optimal_actions_match_frozen_gold"] = optimal == expected
        result["optimal_value_matches_frozen_gold"] = (
            abs(opt - exact_number(gold["objective_value_contract"]["canonical_value"])) <= TOLERANCE)
        result["reference_feasible_actions"] = len(feasible)
        result["reference_optimal_value_exact"] = str(opt)
    return result


def main():
    source_index_path = DATA / "private" / "source_index.csv"
    gold_path = DATA / "private" / "gold.jsonl"
    source_rows = list(csv.DictReader(source_index_path.open(encoding="utf-8-sig", newline="")))
    golds = {row["id"]: row for row in
             (json.loads(line, parse_float=Decimal, object_pairs_hook=reject_duplicate_keys)
              for line in gold_path.read_text(encoding="utf-8-sig").splitlines() if line.strip())}
    scores = {}
    score_files = {}
    for method, (batch, group) in METHODS.items():
        path = EXPERIMENTS / batch / "scores.json"
        score_files[method] = path
        for row in read_json(path)["case_scores"]:
            if row["group"] == group and row["case_role"] == "C2":
                scores[(method, row["source_task_id"], str(row["run_id"]))] = row

    legacy = {}
    if OLD_RECORDS.exists():
        for line in OLD_RECORDS.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                row = json.loads(line)
                legacy[(row["method"], row["source_task_id"], str(row["run_id"]))] = row

    refs = {}
    ref_validation = []
    ref_validation_by_sid = {}
    result_rows = []
    all_witnesses = []
    for task in source_rows:
        sid, eid = task["source_task_id"], task["C2_eval_id"]
        gold = golds[sid]
        mapping = gold["public_to_private_action_map"]
        public_ids = sorted(mapping)
        ref_path = DATA / "models" / sid / "full_ir.json"
        ref_raw = read_json(ref_path)
        if len(set(mapping.values())) != len(mapping) or set(mapping.values()) != set(ref_raw["action_projection"]):
            raise AuditError(f"reference mapping mismatch: {sid}")
        reference = normalize(ref_raw, mapping)
        ref_feasible, ref_stats = enumerate_model(reference, public_ids)
        refs[sid] = (reference, ref_feasible, ref_stats, ref_path)
        reference_check = validate_reference(reference, ref_feasible, gold, mapping, public_ids)
        ref_validation.append(reference_check)
        ref_validation_by_sid[sid] = reference_check

        for method, (batch, group) in METHODS.items():
            for run in range(1, 4):
                case = (EXPERIMENTS / batch / group / f"run_{run}" / group / eid / "case")
                result_path = case / "result.json"
                model_path = result_path if method == "Standard-online" else case / "case_state.json"
                score = scores.get((method, sid, str(run)))
                if score is None:
                    raise AuditError(f"missing score: {method} {sid} run{run}")
                row = {
                    "source_task_id": sid, "eval_id": eid, "run_id": run, "method": method,
                    "case_role": "C2", "answer_correct_existing": score["answer_correct"],
                    "reference_contract_status": ("PASS" if ref_validation_by_sid[sid]["optimal_actions_match_frozen_gold"] and
                                                   ref_validation_by_sid[sid]["optimal_value_matches_frozen_gold"]
                                                   else "GOLD_CONFLICT"),
                    "terminal_result_available": result_path.exists(),
                    "full_model_status": "UNRESOLVED", "snapshot_full_model_status": "UNRESOLVED",
                    "reference_file": rel(ref_path), "reference_sha256": digest(ref_path),
                    "model_file": rel(model_path) if model_path.exists() else None,
                    "model_sha256": digest(model_path) if model_path.exists() else None,
                    "result_file": rel(result_path), "result_sha256": digest(result_path) if result_path.exists() else None,
                    "source_reference_has_model_action_projection": "action_projection" in ref_raw,
                    "generated_action_projection_present": False,
                }
                legacy_row = legacy.get((method, sid, str(run)))
                row["legacy_full_model_status"] = legacy_row.get("full_model_status") if legacy_row else None
                row["legacy_snapshot_status"] = legacy_row.get("snapshot_full_model_status") if legacy_row else None
                witness = None
                try:
                    state = read_json(model_path)
                    generated_raw = state.get("model") if isinstance(state, dict) else None
                    model = normalize(generated_raw)
                    row["generated_action_projection_present"] = model["action_projection"] is not None
                    if model["action_projection"] is not None and set(model["action_projection"]) != set(public_ids):
                        raise AuditError("generated action_projection differs from public action IDs")
                    gen_feasible, stats = enumerate_model(model, public_ids)
                    cmp = compare(reference, model, ref_feasible, gen_feasible, public_ids)
                    row.update(cmp)
                    row.update(optimal_set_audit(model, gen_feasible, gold, public_ids, reference))
                    tag_counterexamples(cmp["counterexamples"], gen_feasible, model, gold, public_ids)
                    row.update({"snapshot_full_model_status": cmp["full_model_status"], **stats,
                                "generated_variables": len(model["variables"]),
                                "generated_constraint_count": len(model["constraints"]),
                                "generated_direction": model["objective"]["direction"],
                                "reference_direction": reference["objective"]["direction"],
                                "generated_unit": model["objective"]["unit"],
                                "reference_unit": reference["objective"]["unit"]})
                    if not result_path.exists():
                        row["full_model_status"] = "UNRESOLVED"
                        row["unresolved_reason"] = "missing final result; saved model snapshot is not validated as terminal delivery"
                    witness = {"source_task_id": sid, "eval_id": eid, "run_id": run, "method": method,
                               "full_model_status": row["full_model_status"],
                               "snapshot_full_model_status": row["snapshot_full_model_status"],
                               "reference_model_file": rel(ref_path), "generated_model_file": rel(model_path),
                               "reference_sha256": digest(ref_path), "generated_sha256": digest(model_path),
                               "failure_category": primary_category(row),
                               "instance_optimal_set_status": row.get("instance_optimal_set_status"),
                               "instance_optimal_set_comparable": row.get("instance_optimal_set_comparable"),
                               "gold_optimal_action_count": row.get("gold_optimal_action_count"),
                               "generated_optimal_action_count": row.get("generated_optimal_action_count"),
                               "counterexamples": cmp["counterexamples"]}
                    # For Standard and saved SWAgent deliveries, verify the exposed decision against the same saved model.
                    decision = read_json(result_path).get("decision") if result_path.exists() else None
                    row["decision_available"] = isinstance(decision, dict)
                    row["decision_model_consistency"] = "UNRESOLVED"
                    if isinstance(decision, dict) and isinstance(decision.get("actions"), dict):
                        actions = decision["actions"]
                        action = tuple(actions.get(name) for name in public_ids)
                        if set(actions) != set(public_ids) or action not in gen_feasible:
                            row["decision_model_consistency"] = "FAIL"
                        else:
                            try:
                                obj = decision.get("objective", {})
                                chosen = gen_feasible[action]
                                optimum = (max if model["objective"]["direction"] == "max" else min)(gen_feasible.values())
                                matches = (obj.get("unit") == model["objective"]["unit"] and
                                           obj.get("direction") == model["objective"]["direction"] and
                                           abs(exact_number(obj.get("value")) - chosen) <= TOLERANCE and
                                           abs(chosen - optimum) <= TOLERANCE)
                                row["decision_model_consistency"] = "PASS" if matches else "FAIL"
                            except (AuditError, TypeError, AttributeError):
                                row["decision_model_consistency"] = "UNRESOLVED"
                    # A redundant copy in result.json, when present, must match the state snapshot.
                    result_obj = read_json(result_path) if result_path.exists() else {}
                    if isinstance(result_obj, dict) and isinstance(result_obj.get("model"), dict):
                        row["terminal_result_embeds_model"] = True
                        try:
                            terminal_model = normalize(result_obj["model"])
                            row["terminal_model_equals_snapshot"] = terminal_model == model
                        except AuditError:
                            row["terminal_model_equals_snapshot"] = False
                    else:
                        row["terminal_result_embeds_model"] = False
                        row["terminal_model_equals_snapshot"] = None
                except (OSError, json.JSONDecodeError, AuditError, KeyError, TypeError, ValueError) as exc:
                    row["full_model_status"] = "UNRESOLVED" if result_path.exists() else "UNRESOLVED"
                    row["snapshot_full_model_status"] = "UNRESOLVED"
                    row["unresolved_reason"] = f"{type(exc).__name__}: {exc}"
                    witness = {"source_task_id": sid, "eval_id": eid, "run_id": run, "method": method,
                               "full_model_status": "UNRESOLVED", "failure_category": primary_category(row),
                               "reference_model_file": rel(ref_path), "generated_model_file": rel(model_path),
                               "unresolved_reason": row["unresolved_reason"]}

                row["failure_category"] = primary_category(row)
                row["secondary_domain_mismatch"] = not row.get("feasible_region_equal", True)
                removed = row.get("reference_feasible_missing_from_generated", 0)
                added = row.get("generated_extra_feasible", 0)
                row["domain_difference_shape"] = (
                    "MIXED_OVER_AND_UNDER" if removed and added else
                    "OVERCONSTRAINED_ONLY" if removed else
                    "UNDERCONSTRAINED_ONLY" if added else "NO_DOMAIN_DIFFERENCE")
                row["secondary_objective_mismatch"] = not row.get("objective_equal_on_shared_feasible_actions", True)
                row["secondary_direction_mismatch"] = not row.get("direction_equal", True)
                row["secondary_unit_mismatch"] = not row.get("unit_equal", True)
                row["legacy_status_changed"] = (row["legacy_full_model_status"] is not None and
                                                 row["legacy_full_model_status"] != row["full_model_status"])
                row["is_R116_sensitivity_case"] = sid == "SWOR-R116"

                if method == "SWAgent-online":
                    init = initial_model(case, reference, ref_feasible, public_ids)
                    row.update(init)
                    initial_status = row.get("initial_full_model_status", "UNRESOLVED")
                    final_status = row["full_model_status"]
                    row["initial_to_final_transition"] = initial_status + " -> " + final_status
                    row["legacy_initial_status"] = legacy_row.get("initial_full_model_status") if legacy_row else None
                    row["legacy_initial_status_changed"] = (row["legacy_initial_status"] is not None and
                                                              row["legacy_initial_status"] != initial_status)
                    if witness is not None:
                        witness["initial_full_model_status"] = initial_status
                        witness["initial_to_final_transition"] = row["initial_to_final_transition"]
                        witness["initial_counterexamples"] = row.get("initial_counterexamples")
                result_rows.append(row)
                if witness is not None and (row["full_model_status"] != "PASS" or
                                            row["snapshot_full_model_status"] != "PASS"):
                    all_witnesses.append(witness)

    summary = summarize(result_rows, ref_validation, score_files, source_index_path, gold_path)
    write_csv(OUT / "independent_model_equivalence_records.csv", result_rows)
    write_jsonl(OUT / "independent_model_equivalence_witnesses.jsonl", all_witnesses)
    write_json(OUT / "independent_model_equivalence_summary.json", summary)
    write_text_report(OUT / "independent_model_equivalence_report_zh.md", summary)
    print(json.dumps({"summary": summary["by_method"],
                      "failure_categories": summary["failure_categories"],
                      "initial_to_final": summary["swagent_initial_to_final"],
                      "legacy_status_differences": summary["legacy_status_differences"]},
                     ensure_ascii=False, indent=2))


def summarize(rows, reference_validation, score_files, source_index_path, gold_path):
    by_method = {}
    for method in METHODS:
        method_rows = [r for r in rows if r["method"] == method]
        by_method[method] = {
            "n": len(method_rows),
            "status": dict(Counter(r["full_model_status"] for r in method_rows)),
            "answer_correct": sum(bool(r["answer_correct_existing"]) for r in method_rows),
            "answer_correct_model_fail": sum(bool(r["answer_correct_existing"]) and r["full_model_status"] == "FAIL" for r in method_rows),
            "per_run": {str(run): dict(Counter(r["full_model_status"] for r in method_rows if r["run_id"] == run))
                        for run in range(1, 4)},
            "r116_excluded": dict(Counter(r["full_model_status"] for r in method_rows if not r["is_R116_sensitivity_case"])),
        }
        by_method[method]["pass_percent_fixed_denominator"] = 100 * by_method[method]["status"].get("PASS", 0) / len(method_rows)
        by_method[method]["pass_percent_excluding_R116"] = 100 * by_method[method]["r116_excluded"].get("PASS", 0) / (len(method_rows) - 3)

    exclusive = Counter(r["failure_category"] for r in rows)
    domain_shapes = {method: dict(Counter(r["domain_difference_shape"] for r in rows
                                          if r["method"] == method and r["full_model_status"] == "FAIL"))
                     for method in METHODS}
    domain_shapes["ALL"] = dict(Counter(r["domain_difference_shape"] for r in rows
                                        if r["full_model_status"] == "FAIL"))
    overlap = {name: sum(bool(r.get(field)) for r in rows)
               for name, field in (("domain_mismatch", "secondary_domain_mismatch"),
                                   ("objective_mismatch", "secondary_objective_mismatch"),
                                   ("direction_mismatch", "secondary_direction_mismatch"),
                                   ("unit_mismatch", "secondary_unit_mismatch"))}
    transitions = Counter(r.get("initial_to_final_transition", "NO_INITIAL_RECORD")
                          for r in rows if r["method"] == "SWAgent-online")
    sw = [r for r in rows if r["method"] == "SWAgent-online"]
    without_r116 = [r for r in sw if not r["is_R116_sensitivity_case"]]
    initfinal = {
        "n": len(sw), "transition_counts": dict(transitions),
        "initial_pass": sum(r.get("initial_full_model_status") == "PASS" for r in sw),
        "final_pass": sum(r["full_model_status"] == "PASS" for r in sw),
        "initial_to_final_excluding_R116": dict(Counter(r["initial_to_final_transition"] for r in without_r116)),
        "initial_pass_to_final_fail_cases": [r["source_task_id"] + "/run" + str(r["run_id"])
                                               for r in sw if r.get("initial_full_model_status") == "PASS" and
                                               r["full_model_status"] == "FAIL"],
        "fail_to_pass_cases": [r["source_task_id"] + "/run" + str(r["run_id"])
                               for r in sw if r.get("initial_full_model_status") == "FAIL" and
                               r["full_model_status"] == "PASS"],
        "fail_to_fail_cases": [r["source_task_id"] + "/run" + str(r["run_id"])
                               for r in sw if r.get("initial_full_model_status") == "FAIL" and
                               r["full_model_status"] == "FAIL"],
    }
    legacy_diffs = [
        {"method": r["method"], "source_task_id": r["source_task_id"], "run_id": r["run_id"],
         "legacy": r["legacy_full_model_status"], "independent": r["full_model_status"],
         "legacy_initial": r.get("legacy_initial_status"), "independent_initial": r.get("initial_full_model_status"),
         "reason": r.get("unresolved_reason")}
        for r in rows if r["legacy_status_changed"] or r.get("legacy_initial_status_changed")]
    answer_correct_model_fails = [r for r in rows if bool(r["answer_correct_existing"]) and
                                  r["full_model_status"] == "FAIL"]
    return {
        "protocol": {
            "objective_tolerance_absolute": str(TOLERANCE),
            "full_model_criterion": "same projected public feasible-action set, same objective within absolute 1e-7 for every shared feasible action, identical objective direction and unit",
            "arithmetic": "JSON decimal numbers parsed as Decimal, converted to exact Fraction; feasibility exact",
            "projection": "enumerate all finite bounded BINARY/INTEGER assignments; existentially project auxiliaries; reject objectives depending on auxiliaries",
            "empty_domain_handling": "empty integer domain remains empty; it is not replaced by a singleton",
            "cap_assignments_per_model": MAX_ASSIGNMENTS,
            "classification_precedence": ["MISSING_DELIVERABLE", "FEASIBLE_REGION_DIFFERENCE", "SAME_DOMAIN_OBJECTIVE_DIFFERENCE", "DIRECTION_UNIT_ONLY", "PASS"],
            "reference_scope": "equivalence is relative to frozen v1.6.3 full_ir; R116 is separately flagged because prior semantic review raised a reference conflict",
            "independent_inputs": {
                rel(source_index_path): digest(source_index_path), rel(gold_path): digest(gold_path),
                **{rel(path): digest(path) for path in score_files.values()},
                rel(Path(__file__)): digest(Path(__file__)),
            },
        },
        "records": len(rows), "source_tasks": len({r["source_task_id"] for r in rows}),
        "by_method": by_method,
        "failure_categories": dict(exclusive),
        "domain_difference_shapes": domain_shapes,
        "secondary_mismatch_counts_not_mutually_exclusive": overlap,
        "swagent_initial_to_final": initfinal,
        "answer_correct_model_fail_optimal_set_relation": {
            method: dict(Counter(r.get("instance_optimal_set_status", "NOT_COMPUTED")
                                 for r in answer_correct_model_fails if r["method"] == method))
            for method in METHODS
        },
        "answer_correct_model_fail_optimal_set_rows": [
            {key: r.get(key) for key in ("method", "source_task_id", "run_id", "failure_category",
                                          "instance_optimal_set_status", "gold_optimal_action_count",
                                          "generated_optimal_action_count",
                                          "gold_optimal_actions_missing_from_generated_optimum",
                                          "non_gold_generated_optimal_actions",
                                          "gold_optimal_set_is_subset_of_generated_optimal_set",
                                          "generated_optimal_set_is_subset_of_gold_optimal_set")}
            for r in answer_correct_model_fails],
        "legacy_status_differences": legacy_diffs,
        "reference_gold_validation": {
            "sources": len(reference_validation),
            "all_mapping_checks_pass": all(r["mapping_one_to_one_and_matches_projection"] for r in reference_validation),
            "all_feasible_sets_nonempty": all(r["nonempty_feasible_set"] for r in reference_validation),
            "gold_contract_conflicts": [r for r in reference_validation
                                         if not r["optimal_actions_match_frozen_gold"] or
                                         not r["optimal_value_matches_frozen_gold"]],
            "R116_rows": [r for r in reference_validation if r["source_task_id"] == "SWOR-R116"],
        },
        "audit_checks": {
            "all_expected_rows": len(rows) == 600,
            "unique_method_source_run_keys": len({(r["method"], r["source_task_id"], r["run_id"]) for r in rows}) == 600,
            "legacy_final_status_differences_n": len(legacy_diffs),
            "rows_with_empty_variable_domains": sum(bool(r.get("empty_variable_domains")) for r in rows),
            "terminal_result_embeds_model_n": sum(bool(r.get("terminal_result_embeds_model")) for r in rows),
            "terminal_model_snapshot_disagreements_n": sum(r.get("terminal_model_equals_snapshot") is False for r in rows),
            "generated_action_projection_present_n": sum(bool(r.get("generated_action_projection_present")) for r in rows),
            "decision_model_consistency": {m: dict(Counter(r.get("decision_model_consistency", "NOT_CHECKED")
                                                              for r in rows if r["method"] == m)) for m in METHODS},
        },
    }


def write_csv(path: Path, rows):
    preferred = ["source_task_id", "eval_id", "run_id", "method", "case_role", "answer_correct_existing",
                 "full_model_status", "snapshot_full_model_status", "failure_category", "terminal_result_available",
                 "domain_difference_shape",
                 "reference_contract_status", "reference_feasible_missing_from_generated", "generated_extra_feasible",
                 "shared_feasible_objective_mismatches", "feasible_region_equal", "objective_equal_on_shared_feasible_actions",
                 "direction_equal", "unit_equal", "objective_strict_rational_mismatches",
                 "reference_feasible_actions", "feasible_public_actions", "enumerated_assignments", "auxiliary_variables",
                 "empty_variable_domains", "generated_variables", "generated_constraint_count", "generated_unit",
                 "reference_unit", "generated_direction", "reference_direction", "decision_available",
                 "decision_model_consistency", "terminal_result_embeds_model", "terminal_model_equals_snapshot",
                 "instance_optimal_set_status", "instance_optimal_set_relation_raw", "instance_optimal_set_comparable",
                 "gold_optimal_action_count", "generated_optimal_action_count",
                 "gold_optimal_actions_missing_from_generated_optimum", "non_gold_generated_optimal_actions",
                 "gold_optimal_set_is_subset_of_generated_optimal_set", "generated_optimal_set_is_subset_of_gold_optimal_set",
                 "legacy_full_model_status", "legacy_status_changed", "initial_full_model_status",
                 "initial_to_final_transition", "legacy_initial_status", "legacy_initial_status_changed",
                 "is_R116_sensitivity_case", "unresolved_reason", "reference_file", "reference_sha256",
                 "model_file", "model_sha256", "result_file", "result_sha256", "initial_model_file", "initial_model_sha256"]
    fields = list(preferred)
    fields.extend(sorted({k for row in rows for k in row} - set(fields)))
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def write_text_report(path: Path, summary):
    methods = summary["by_method"]
    cats = summary["failure_categories"]
    shapes = summary["domain_difference_shapes"]
    transitions = summary["swagent_initial_to_final"]["transition_counts"]
    r116 = summary["reference_gold_validation"]["gold_contract_conflicts"]
    lines = [
        "# dqz1 full-model equivalence 独立复算",
        "",
        "本审计直接读取冻结 v1.6.3 的参考 IR、100 个 C2 源任务、两种方法的 600 份已保存模型和终态记录；未调用模型、搜索、网络或求解器。数字字段按 UTF-8 JSON 中的十进制文本解析为 `Decimal` 后转精确有理数。原始记录、模型和分数文件保持只读。",
        "",
        "判据是：公开行动的完整可行集合相同；对每个共享可行动作，目标值在绝对 1e-7 内一致；方向和单位一致。有限 BINARY/INTEGER 变量全枚举，辅助变量按存在可行赋值投影；不检查现实规则本身是否正确，也不把最优值相同视为模型等价。",
        "",
        "## 终态统计",
        "",
        "| 方法 | PASS | FAIL | UNRESOLVED | PASS率（固定n=300） | 排除R116后 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method, label in (("Standard-online", "Standard-online"), ("SWAgent-online", "SWAgent-online")):
        row = methods[method]
        st = row["status"]
        lines.append(f"| {label} | {st.get('PASS', 0)} | {st.get('FAIL', 0)} | {st.get('UNRESOLVED', 0)} | {row['pass_percent_fixed_denominator']:.2f}% | {row['pass_percent_excluding_R116']:.2f}%（n=297） |")
    lines += [
        "",
        "互斥首要失败分类按“缺交付/未决 → 可行域差异 → 同域目标值差异 → 仅方向或单位差异”的顺序归类；次级重叠计数另存于 JSON，便于看出一个案例是否同时有多种差异。",
        "",
        "| 首要类别 | 数量 |",
        "|---|---:|",
    ]
    for key in ("PASS", "FEASIBLE_REGION_DIFFERENCE", "SAME_DOMAIN_OBJECTIVE_DIFFERENCE", "DIRECTION_UNIT_ONLY", "MISSING_DELIVERABLE", "UNRESOLVED_OTHER"):
        lines.append(f"| {key} | {cats.get(key, 0)} |")
    lines += ["", "可行域差异的方向（按case-run计数）：", "", "| 方法 | 仅过约束 | 仅漏约束 | 同时过约束和漏约束 |", "|---|---:|---:|---:|"]
    for method, label in (("Standard-online", "Standard-online"), ("SWAgent-online", "SWAgent-online"), ("ALL", "合计")):
        values = shapes[method]
        lines.append(f"| {label} | {values.get('OVERCONSTRAINED_ONLY', 0)} | {values.get('UNDERCONSTRAINED_ONLY', 0)} | {values.get('MIXED_OVER_AND_UNDER', 0)} |")
    lines += ["", "## 答案正确但完整模型失败的最优集关系", "", "| 方法 | answer-correct + model-FAIL | 最优公开动作集等于冻结gold | 缺少gold最优动作 | 产生额外最优动作 |", "|---|---:|---:|---:|---:|"]
    for method in METHODS:
        rows = [r for r in summary["answer_correct_model_fail_optimal_set_rows"] if r["method"] == method]
        equal = sum(r["instance_optimal_set_status"] == "EQUAL" for r in rows)
        missing = sum(r["gold_optimal_actions_missing_from_generated_optimum"] or 0 for r in rows)
        extra = sum(r["non_gold_generated_optimal_actions"] or 0 for r in rows)
        lines.append(f"| {method} | {len(rows)} | {equal} | {missing} | {extra} |")
    lines += ["", "这里仅称逐实例最优公开动作集一致。每条仍有非最优部分的可行域差异；该结果不证明模型的一般合法性或语义正确性。逐条action set计数见summary JSON/CSV。", ""]
    lines += ["", "## SWAgent 初始模型到终态模型", "", "| 转移 | 次数 |", "|---|---:|"]
    for key, value in sorted(transitions.items()):
        lines.append(f"| {key} | {value} |")
    lines += ["", "首要逐条复核名单见 CSV。初始 PASS→终态 FAIL 是已引入错误限制的直接反例；FAIL→FAIL 是未修复，FAIL→PASS 是按冻结模型定义完成修复。", ""]
    lines += ["## 参考契约敏感性", ""]
    if r116:
        lines.append(f"全100源的复算继续按冻结 full_ir 计算，但 {len(r116)} 个参考源与冻结 gold 最优行动/目标值契约有差异，详见 summary 中的 `reference_gold_validation.gold_contract_conflicts`。先前语义审阅还提出 SWOR-R116 参考版本争议；因此主结果报告保留冻结统计，同时另列去掉 R116 的敏感性值。它不表示已判定 R116 哪个来源正确。")
    else:
        lines.append("本次枚举未发现参考 IR 与冻结 gold 的最优行动或目标契约不一致；这只验证二者在数学数据上的内部一致。先前语义审阅对 SWOR-R116 的现实规则来源/版本提出争议，内部一致不能消解该问题。因此保留全100源冻结统计，并另列排除 R116 的敏感性值。")
    lines += ["", "## 复算与实现风险", "",
              "- 原始 600 条记录与旧记录逐条对比，独立状态差异列表见 summary；差异须逐行查明，不能用原报告统计覆盖。",
              "- 另拒绝重复 JSON 对象键，精确读入小数；空变量域保留为空集，避免错误将无界/矛盾整数域变成单点。",
              "- 变量上下界、方向/单位、公开行动映射、条件约束触发、目标/约束中未定义变量、辅助变量目标项及枚举上限均单独校验；不支持的模型作为 UNRESOLVED，而非FAIL或PASS。",
              "- 完整反例 witness（参考可行但生成不可行、生成额外可行以及共享行动目标冲突）按每条失败逐题保存。",
              "- 结论边界：该统计证明的是生成模型相对冻结参考 IR 的全行动空间一致性。若冻结规则解释或版本错误，匹配它仍可能在语义上错误；反过来，若任务语义正确但参考 IR 错，也会被判不等价。语义审阅需单独完成。",
              "", "复算入口：`independent_model_equivalence_audit.py`；逐行表：`independent_model_equivalence_records.csv`；反例：`independent_model_equivalence_witnesses.jsonl`；机器汇总及散列：`independent_model_equivalence_summary.json`。", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()

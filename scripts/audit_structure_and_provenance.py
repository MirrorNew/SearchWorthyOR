"""Independent structural-template and base-provenance release gate.

The structural fingerprint deliberately ignores identifiers and coefficient
magnitudes.  It retains the signed zero pattern, factor senses, variable
types, bound categories, and action/auxiliary roles.  Fingerprint collisions
are confirmed with an exact colored-graph isomorphism check before rejection.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from validate_dataset_schema import Issue, canonical_bytes, issue, load_jsonl


MAX_ENUM_BINARY_VARS = 20
CERTIFIED_BASE_STATUSES = {"unchanged_pass", "repaired_pass"}


@dataclasses.dataclass(frozen=True)
class _Graph:
    attributes: tuple[tuple[str, ...], ...]
    adjacency: tuple[Mapping[int, str], ...]


@dataclasses.dataclass
class StructuralReport:
    errors: list[Issue] = dataclasses.field(default_factory=list)
    warnings: list[Issue] = dataclasses.field(default_factory=list)
    stats: dict[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": [entry.as_dict() for entry in self.errors],
            "warnings": [entry.as_dict() for entry in self.warnings],
            "stats": self.stats,
        }


def _numeric_category(value: Any, *, missing: str) -> str:
    if value is None:
        return missing
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "invalid"
    numeric = float(value)
    if math.isnan(numeric):
        return "invalid"
    if math.isinf(numeric):
        return "positive_infinity" if numeric > 0 else "negative_infinity"
    if numeric == 0:
        return "zero"
    return "positive" if numeric > 0 else "negative"


def _coefficient_sign(value: Any) -> str | None:
    category = _numeric_category(value, missing="missing")
    if category == "positive":
        return "+"
    if category == "negative":
        return "-"
    if category == "zero":
        return None
    return f"!{category}"


def _bound_relation(lower: Any, upper: Any) -> str:
    if (
        isinstance(lower, (int, float))
        and not isinstance(lower, bool)
        and isinstance(upper, (int, float))
        and not isinstance(upper, bool)
        and math.isfinite(float(lower))
        and math.isfinite(float(upper))
    ):
        return "fixed" if float(lower) == float(upper) else "range"
    return "unknown"


def _ir_graph(ir: Mapping[str, Any]) -> _Graph:
    variables = ir.get("variables")
    constraints = ir.get("constraints")
    objective = ir.get("objective")
    projection = ir.get("action_projection")
    if not isinstance(variables, list):
        raise ValueError("variables must be a list")
    if not isinstance(constraints, list):
        raise ValueError("constraints must be a list")
    if not isinstance(objective, Mapping):
        raise ValueError("objective must be an object")
    if not isinstance(projection, list):
        raise ValueError("action_projection must be a list")

    projection_names = {str(name) for name in projection}
    names: list[str] = []
    attributes: list[tuple[str, ...]] = []
    for index, variable in enumerate(variables):
        if not isinstance(variable, Mapping):
            raise ValueError(f"variables[{index}] must be an object")
        name = variable.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"variables[{index}].name must be non-empty")
        if name in names:
            raise ValueError(f"duplicate variable name {name!r}")
        names.append(name)
        lower = variable.get("lb")
        upper = variable.get("ub")
        attributes.append(
            (
                "variable",
                str(variable.get("vartype", "<missing>")).upper(),
                f"lb:{_numeric_category(lower, missing='missing')}",
                f"ub:{_numeric_category(upper, missing='missing')}",
                f"bounds:{_bound_relation(lower, upper)}",
                "role:action" if name in projection_names else "role:auxiliary",
            )
        )

    name_to_node = {name: index for index, name in enumerate(names)}
    factor_specs: list[tuple[tuple[str, ...], Mapping[str, Any]]] = []
    for index, constraint in enumerate(constraints):
        if not isinstance(constraint, Mapping):
            raise ValueError(f"constraints[{index}] must be an object")
        terms = constraint.get("terms")
        if not isinstance(terms, Mapping):
            raise ValueError(f"constraints[{index}].terms must be an object")
        factor_specs.append(
            (
                (
                    "constraint",
                    f"sense:{constraint.get('sense', '<missing>')}",
                    f"rhs:{_numeric_category(constraint.get('rhs'), missing='missing')}",
                ),
                terms,
            )
        )
    objective_terms = objective.get("terms")
    if not isinstance(objective_terms, Mapping):
        raise ValueError("objective.terms must be an object")
    factor_specs.append(
        (
            (
                "objective",
                f"sense:{ir.get('sense', '<missing>')}",
                f"constant:{_numeric_category(objective.get('constant', 0), missing='zero')}",
            ),
            objective_terms,
        )
    )

    adjacency: list[dict[int, str]] = [dict() for _ in range(len(names))]
    for factor_attr, terms in factor_specs:
        factor_node = len(attributes)
        attributes.append(factor_attr)
        adjacency.append({})
        for raw_name, coefficient in terms.items():
            name = str(raw_name)
            if name not in name_to_node:
                raise ValueError(f"factor references unknown variable {name!r}")
            sign = _coefficient_sign(coefficient)
            if sign is None:
                continue
            variable_node = name_to_node[name]
            adjacency[variable_node][factor_node] = sign
            adjacency[factor_node][variable_node] = sign

    return _Graph(
        attributes=tuple(attributes),
        adjacency=tuple(adjacency),
    )


def _refined_colors(graph: _Graph) -> tuple[str, ...]:
    colors = tuple(
        hashlib.sha256(canonical_bytes(attribute)).hexdigest()
        for attribute in graph.attributes
    )
    for _ in range(len(graph.attributes) + 1):
        refined = tuple(
            hashlib.sha256(
                canonical_bytes(
                    [
                        colors[node],
                        sorted(
                            (edge_label, colors[neighbor])
                            for neighbor, edge_label in graph.adjacency[node].items()
                        ),
                    ]
                )
            ).hexdigest()
            for node in range(len(graph.attributes))
        )
        if refined == colors:
            return refined
        colors = refined
    return colors


def canonical_structural_fingerprint(ir: Mapping[str, Any]) -> str:
    """Return an isomorphism-invariant signed structural fingerprint."""

    graph = _ir_graph(ir)
    colors = _refined_colors(graph)
    node_histogram = sorted(collections.Counter(colors).items())
    edge_histogram: collections.Counter[tuple[str, str, str]] = collections.Counter()
    for left, neighbors in enumerate(graph.adjacency):
        for right, label in neighbors.items():
            if left >= right:
                continue
            left_color, right_color = sorted((colors[left], colors[right]))
            edge_histogram[(left_color, right_color, label)] += 1
    payload = {
        "schema": "signed-bipartite-wl-v1",
        "nodes": node_histogram,
        "edges": sorted(
            [list(key) + [count] for key, count in edge_histogram.items()]
        ),
    }
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _neighbor_profile(
    graph: _Graph,
    colors: Sequence[str],
    node: int,
    mapped_nodes: set[int],
) -> collections.Counter[tuple[str, str]]:
    return collections.Counter(
        (edge, colors[neighbor])
        for neighbor, edge in graph.adjacency[node].items()
        if neighbor not in mapped_nodes
    )


def structurally_isomorphic(
    left_ir: Mapping[str, Any],
    right_ir: Mapping[str, Any],
) -> bool:
    """Confirm exact isomorphism of two colored, signed bipartite graphs."""

    try:
        left = _ir_graph(left_ir)
        right = _ir_graph(right_ir)
    except ValueError:
        return False
    if len(left.attributes) != len(right.attributes):
        return False
    left_colors = _refined_colors(left)
    right_colors = _refined_colors(right)
    if collections.Counter(left_colors) != collections.Counter(right_colors):
        return False

    right_by_key: dict[tuple[tuple[str, ...], str, int], list[int]] = (
        collections.defaultdict(list)
    )
    for node, attribute in enumerate(right.attributes):
        right_by_key[(attribute, right_colors[node], len(right.adjacency[node]))].append(
            node
        )
    candidate_sets: dict[int, tuple[int, ...]] = {}
    for node, attribute in enumerate(left.attributes):
        key = (attribute, left_colors[node], len(left.adjacency[node]))
        candidates = tuple(right_by_key.get(key, ()))
        if not candidates:
            return False
        candidate_sets[node] = candidates

    mapping: dict[int, int] = {}
    used_right: set[int] = set()

    def compatible(left_node: int, right_node: int) -> bool:
        for mapped_left, mapped_right in mapping.items():
            if left.adjacency[left_node].get(mapped_left) != right.adjacency[
                right_node
            ].get(mapped_right):
                return False
        return _neighbor_profile(
            left, left_colors, left_node, set(mapping)
        ) == _neighbor_profile(right, right_colors, right_node, used_right)

    def search() -> bool:
        if len(mapping) == len(left.attributes):
            return True
        unmapped = [node for node in range(len(left.attributes)) if node not in mapping]
        left_node = min(
            unmapped,
            key=lambda node: (
                sum(candidate not in used_right for candidate in candidate_sets[node]),
                -sum(neighbor in mapping for neighbor in left.adjacency[node]),
                -len(left.adjacency[node]),
                node,
            ),
        )
        for right_node in candidate_sets[left_node]:
            if right_node in used_right or not compatible(left_node, right_node):
                continue
            mapping[left_node] = right_node
            used_right.add(right_node)
            if search():
                return True
            used_right.remove(right_node)
            del mapping[left_node]
        return False

    return search()


def _is_string_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(item, str) and item for item in value)
        and len(value) == len(set(value))
    )


def _gold_projection(gold: Mapping[str, Any]) -> list[str] | None:
    projection = gold.get("action_projection")
    if not isinstance(projection, Mapping):
        return None
    fields = projection.get("fields", projection.get("variables"))
    return list(fields) if _is_string_list(fields) else None


def _validate_projection_and_enum(
    task_id: str,
    gold: Mapping[str, Any],
    models: Mapping[str, Mapping[str, Any]],
) -> list[Issue]:
    errors: list[Issue] = []
    base = models.get("base")
    patched = models.get("patched")
    path = f"models/{task_id}"
    if not isinstance(base, Mapping) or not isinstance(patched, Mapping):
        return [
            issue(
                "structure.model_pair_missing",
                path,
                "both base and patched canonical IR are required",
            )
        ]
    base_projection = base.get("action_projection")
    patched_projection = patched.get("action_projection")
    gold_projection = _gold_projection(gold)
    if not _is_string_list(base_projection) or not _is_string_list(
        patched_projection
    ):
        errors.append(
            issue(
                "structure.projection_invalid",
                path,
                "base and patched projections must be unique non-empty string lists",
            )
        )
    elif base_projection != patched_projection:
        errors.append(
            issue(
                "structure.projection_changed",
                path,
                "base and patched action projections must be identical and ordered alike",
            )
        )
    if (
        _is_string_list(base_projection)
        and gold_projection is not None
        and base_projection != gold_projection
    ):
        errors.append(
            issue(
                "structure.projection_gold_mismatch",
                f"private/gold.jsonl[{task_id}].action_projection",
                "gold projection differs from the canonical base projection",
            )
        )

    variable_names: dict[str, set[str]] = {}
    for world_name, ir in (("base", base), ("patched", patched)):
        variables = ir.get("variables")
        world_path = f"{path}/{world_name}_ir.json"
        if not isinstance(variables, list):
            errors.append(
                issue(
                    "structure.variables_invalid",
                    world_path,
                    "variables must be a list",
                )
            )
            continue
        if len(variables) > MAX_ENUM_BINARY_VARS:
            errors.append(
                issue(
                    "structure.enum_limit_exceeded",
                    f"{world_path}.variables",
                    (
                        f"{len(variables)} variables exceed the frozen exact binary "
                        f"enumeration limit {MAX_ENUM_BINARY_VARS}"
                    ),
                )
            )
        names: list[str] = []
        for index, variable in enumerate(variables):
            if not isinstance(variable, Mapping):
                continue
            name = variable.get("name")
            if isinstance(name, str) and name:
                names.append(name)
            if variable.get("vartype") != "B":
                errors.append(
                    issue(
                        "structure.enum_nonbinary",
                        f"{world_path}.variables[{index}]",
                        "first release exact enumeration requires binary variables only",
                    )
                )
        variable_names[world_name] = set(names)
        projection_value = ir.get("action_projection")
        if _is_string_list(projection_value) and not set(projection_value).issubset(
            variable_names[world_name]
        ):
            errors.append(
                issue(
                    "structure.projection_unknown_variable",
                    f"{world_path}.action_projection",
                    "projection references a variable absent from its canonical IR",
                )
            )

    if {"base", "patched"} <= set(variable_names) and _is_string_list(
        patched_projection
    ):
        patch_only = variable_names["patched"] - variable_names["base"]
        leaked_aux = sorted(patch_only & set(patched_projection))
        if leaked_aux:
            errors.append(
                issue(
                    "structure.patch_aux_in_projection",
                    f"{path}/patched_ir.json.action_projection",
                    f"patch-only auxiliary variables enter the action projection: {leaked_aux}",
                )
            )
    return errors


def _partition_isomorphic_groups(
    rows: Sequence[tuple[str, str, Mapping[str, Any]]],
) -> list[list[tuple[str, str, Mapping[str, Any]]]]:
    groups: list[list[tuple[str, str, Mapping[str, Any]]]] = []
    for row in rows:
        for group in groups:
            if structurally_isomorphic(row[2], group[0][2]):
                group.append(row)
                break
        else:
            groups.append([row])
    return [group for group in groups if len(group) > 1]


def audit_structure_records(
    gold: Sequence[Mapping[str, Any]],
    staging: Sequence[Mapping[str, Any]],
    model_irs: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> StructuralReport:
    """Audit already-loaded records; exposed for narrow regression tests."""

    report = StructuralReport()
    staging_index: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in staging:
        source_dataset = row.get("source_dataset")
        source_id = row.get("source_id")
        if isinstance(source_dataset, str) and isinstance(source_id, str):
            staging_index[(source_dataset, source_id)] = row

    fingerprint_rows: dict[
        str, list[tuple[str, str, Mapping[str, Any]]]
    ] = collections.defaultdict(list)
    valid_model_pairs = 0
    for index, row in enumerate(gold, start=1):
        task_id = str(row.get("id", f"<row-{index}>"))
        row_path = f"private/gold.jsonl:{index}"
        base_audit = row.get("base_audit")
        if not isinstance(base_audit, Mapping):
            report.errors.append(
                issue(
                    "provenance.base_audit_missing",
                    f"{row_path}.base_audit",
                    "base audit is required",
                )
            )
        else:
            base_kind = base_audit.get("base_kind")
            status = base_audit.get("status")
            if status not in CERTIFIED_BASE_STATUSES:
                report.errors.append(
                    issue(
                        "provenance.base_not_certified",
                        f"{row_path}.base_audit.status",
                        f"base audit status {status!r} is not a certified pass state",
                    )
                )
            if base_kind == "new_compact_adaptation" and status == "unchanged_pass":
                report.errors.append(
                    issue(
                        "provenance.adaptation_cannot_be_unchanged",
                        f"{row_path}.base_audit.status",
                        "a new compact adaptation cannot be certified unchanged",
                    )
                )
            source_dataset = base_audit.get("source_dataset")
            source_id = base_audit.get("source_id")
            if (
                isinstance(source_dataset, str)
                and isinstance(source_id, str)
                and status in CERTIFIED_BASE_STATUSES
            ):
                staged = staging_index.get((source_dataset, source_id))
                if staged is None:
                    report.errors.append(
                        issue(
                            "provenance.staging_candidate_missing",
                            f"{row_path}.base_audit",
                            "certified source base has no matching staging candidate",
                        )
                    )
                else:
                    staged_status = staged.get("status")
                    if staged_status == "selected_for_manual_review":
                        report.errors.append(
                            issue(
                                "provenance.staging_still_manual_review",
                                f"staging/base_candidates.jsonl[{source_dataset}:{source_id}].status",
                                "gold claims source certification while staging remains selected_for_manual_review",
                            )
                        )
                    elif staged_status not in CERTIFIED_BASE_STATUSES:
                        report.errors.append(
                            issue(
                                "provenance.staging_not_certified",
                                f"staging/base_candidates.jsonl[{source_dataset}:{source_id}].status",
                                f"staging status {staged_status!r} is not a certified pass state",
                            )
                        )
                    staged_hash = staged.get("source_hash")
                    audited_hash = base_audit.get("source_problem_sha256")
                    if (
                        isinstance(staged_hash, str)
                        and isinstance(audited_hash, str)
                        and staged_hash.lower() != audited_hash.lower()
                    ):
                        report.errors.append(
                            issue(
                                "provenance.source_hash_mismatch",
                                f"{row_path}.base_audit.source_problem_sha256",
                                "gold source hash differs from the matching staging candidate",
                            )
                        )

        models = model_irs.get(task_id)
        if not isinstance(models, Mapping):
            report.errors.append(
                issue(
                    "structure.model_pair_missing",
                    f"models/{task_id}",
                    "canonical model pair is absent from structural audit input",
                )
            )
            continue
        report.errors.extend(_validate_projection_and_enum(task_id, row, models))
        base_ir = models.get("base")
        if not isinstance(base_ir, Mapping):
            continue
        try:
            fingerprint = canonical_structural_fingerprint(base_ir)
        except ValueError as exc:
            report.errors.append(
                issue(
                    "structure.fingerprint_invalid_ir",
                    f"models/{task_id}/base_ir.json",
                    str(exc),
                )
            )
            continue
        family = str(row.get("family", "<missing>"))
        fingerprint_rows[fingerprint].append((task_id, family, base_ir))
        valid_model_pairs += 1

    all_collision_groups: list[dict[str, Any]] = []
    family_collision_groups: dict[str, list[list[str]]] = collections.defaultdict(list)
    for fingerprint, rows in sorted(fingerprint_rows.items()):
        if len(rows) < 2:
            continue
        for group in _partition_isomorphic_groups(rows):
            task_ids = sorted(row[0] for row in group)
            families = sorted({row[1] for row in group})
            all_collision_groups.append(
                {
                    "fingerprint": fingerprint,
                    "task_ids": task_ids,
                    "families": families,
                }
            )
            report.errors.append(
                issue(
                    "structure.template_collision_all",
                    "models",
                    f"isomorphic base-model template reused by tasks {task_ids}",
                )
            )
            by_family: dict[str, list[str]] = collections.defaultdict(list)
            for task_id, family, _ in group:
                by_family[family].append(task_id)
            for family, member_ids in sorted(by_family.items()):
                if len(member_ids) < 2:
                    continue
                sorted_ids = sorted(member_ids)
                family_collision_groups[family].append(sorted_ids)
                report.errors.append(
                    issue(
                        "structure.template_collision_family",
                        f"models[{family}]",
                        f"family reuses an isomorphic base template: {sorted_ids}",
                    )
                )

    report.stats.update(
        {
            "gold_records": len(gold),
            "staging_records": len(staging),
            "valid_base_fingerprints": valid_model_pairs,
            "unique_structural_fingerprints": len(fingerprint_rows),
            "all_collision_groups": all_collision_groups,
            "family_collision_groups": dict(sorted(family_collision_groups.items())),
            "max_enum_binary_vars": MAX_ENUM_BINARY_VARS,
        }
    )
    return report


def _safe_model_path(root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = (root / value).resolve()
    models_root = (root / "models").resolve()
    try:
        candidate.relative_to(models_root)
    except ValueError:
        return None
    return candidate


def _load_model_pair(
    root: Path,
    gold: Mapping[str, Any],
) -> tuple[dict[str, Mapping[str, Any]], list[Issue]]:
    task_id = str(gold.get("id", "<missing>"))
    model_hashes = gold.get("model_hashes")
    pair: dict[str, Mapping[str, Any]] = {}
    errors: list[Issue] = []
    if not isinstance(model_hashes, Mapping):
        return pair, [
            issue(
                "structure.model_hashes_missing",
                f"private/gold.jsonl[{task_id}].model_hashes",
                "model hash/path entries are required",
            )
        ]
    for world in ("base", "patched"):
        entry = model_hashes.get(world)
        model_path = (
            _safe_model_path(root, entry.get("path"))
            if isinstance(entry, Mapping)
            else None
        )
        display = f"private/gold.jsonl[{task_id}].model_hashes.{world}.path"
        if model_path is None:
            errors.append(
                issue(
                    "structure.model_path_invalid",
                    display,
                    "model path must resolve under models/",
                )
            )
            continue
        try:
            value = json.loads(model_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(
                issue(
                    "structure.model_load_failed",
                    display,
                    f"cannot load canonical IR as UTF-8 JSON: {exc}",
                )
            )
            continue
        if not isinstance(value, Mapping):
            errors.append(
                issue(
                    "structure.model_not_object",
                    display,
                    "canonical IR must be a JSON object",
                )
            )
            continue
        pair[world] = value
    return pair, errors


def _format_number(value: Any) -> str:
    numeric = float(value)
    return f"{numeric:g}"


def audit_public_base_binding(
    public_rows: Sequence[Mapping[str, Any]],
    gold_rows: Sequence[Mapping[str, Any]],
    model_irs: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> list[Issue]:
    """Require every base coefficient scope to be recoverable from public text."""

    errors: list[Issue] = []
    public_by_id = {
        row.get("id"): row
        for row in public_rows
        if isinstance(row.get("id"), str)
    }
    for row_index, gold in enumerate(gold_rows, start=1):
        task_id = gold.get("id")
        if not isinstance(task_id, str):
            continue
        row_path = f"public/tasks_zh.jsonl[{task_id}]"
        public = public_by_id.get(task_id)
        if public is None:
            errors.append(
                issue(
                    "base_binding.public_task_missing",
                    row_path,
                    "gold task has no matching public problem",
                )
            )
            continue
        problem = public.get("problem_zh")
        if not isinstance(problem, str) or not problem.strip():
            errors.append(
                issue(
                    "base_binding.problem_missing",
                    f"{row_path}.problem_zh",
                    "public problem text is required",
                )
            )
            continue
        base_audit = gold.get("base_audit")
        if isinstance(base_audit, Mapping):
            declared_problem_hash = base_audit.get("public_problem_sha256")
            actual_problem_hash = hashlib.sha256(problem.encode("utf-8")).hexdigest()
            if declared_problem_hash != actual_problem_hash:
                errors.append(
                    issue(
                        "base_binding.problem_hash_mismatch",
                        f"private/gold.jsonl:{row_index}.base_audit.public_problem_sha256",
                        "declared public problem hash does not match current text",
                    )
                )
        base = model_irs.get(task_id, {}).get("base")
        if not isinstance(base, Mapping):
            continue
        variables = base.get("variables")
        objective = base.get("objective")
        constraints = base.get("constraints")
        projection = base.get("action_projection")
        if (
            not isinstance(variables, list)
            or not isinstance(objective, Mapping)
            or not isinstance(constraints, list)
            or not isinstance(projection, list)
        ):
            continue
        variable_by_name = {
            variable.get("name"): variable
            for variable in variables
            if isinstance(variable, Mapping)
            and isinstance(variable.get("name"), str)
        }
        projection_names = {
            str(name) for name in projection if isinstance(name, str)
        }
        objective_terms = objective.get("terms")
        if not isinstance(objective_terms, Mapping):
            objective_terms = {}
        for variable_name in projection_names:
            variable = variable_by_name.get(variable_name)
            semantic_name = (
                variable.get("semantic_name")
                if isinstance(variable, Mapping)
                else None
            )
            if not isinstance(semantic_name, str) or not semantic_name:
                errors.append(
                    issue(
                        "base_binding.semantic_name_missing",
                        f"models/{task_id}/base_ir.json#/variables/{variable_name}",
                        "every projected action needs a public semantic name",
                    )
                )
                continue
            if semantic_name not in problem:
                errors.append(
                    issue(
                        "base_binding.action_not_disclosed",
                        f"{row_path}.problem_zh",
                        f"projected action {semantic_name!r} is absent from public text",
                    )
                )
            coefficient = objective_terms.get(variable_name)
            if isinstance(coefficient, (int, float)) and not isinstance(
                coefficient, bool
            ):
                item_lines = [
                    line
                    for line in problem.splitlines()
                    if line.startswith(f"- {semantic_name}：")
                ]
                coefficient_text = _format_number(coefficient)
                if len(item_lines) != 1 or coefficient_text not in item_lines[0]:
                    errors.append(
                        issue(
                            "base_binding.objective_coefficient_missing",
                            f"{row_path}.problem_zh",
                            f"public text does not bind {semantic_name!r} to its objective coefficient",
                        )
                    )
        for constraint_index, constraint in enumerate(constraints):
            if not isinstance(constraint, Mapping):
                continue
            if constraint.get("source") != "public_problem":
                continue
            requirement = constraint.get("requirement_zh")
            constraint_path = (
                f"models/{task_id}/base_ir.json#/constraints/{constraint_index}"
            )
            if not isinstance(requirement, str) or not requirement:
                errors.append(
                    issue(
                        "base_binding.requirement_missing",
                        constraint_path,
                        "public-origin constraint lacks requirement_zh",
                    )
                )
                continue
            if requirement not in problem:
                errors.append(
                    issue(
                        "base_binding.requirement_not_public",
                        f"{row_path}.problem_zh",
                        f"constraint {constraint.get('name')!r} is not disclosed verbatim",
                    )
                )
            terms = constraint.get("terms")
            if not isinstance(terms, Mapping):
                continue
            action_terms = [
                name for name in terms if str(name) in projection_names
            ]
            if len(action_terms) < len(projection_names):
                for variable_name in action_terms:
                    variable = variable_by_name.get(variable_name)
                    semantic_name = (
                        variable.get("semantic_name")
                        if isinstance(variable, Mapping)
                        else None
                    )
                    if (
                        isinstance(semantic_name, str)
                        and semantic_name not in requirement
                    ):
                        errors.append(
                            issue(
                                "base_binding.constraint_scope_hidden",
                                constraint_path,
                                f"subset member {semantic_name!r} is absent from requirement_zh",
                            )
                        )
            numeric_coefficients = [
                float(value)
                for value in terms.values()
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            ]
            if any(abs(abs(value) - 1.0) > 1e-12 for value in numeric_coefficients):
                for variable_name in action_terms:
                    variable = variable_by_name.get(variable_name)
                    semantic_name = (
                        variable.get("semantic_name")
                        if isinstance(variable, Mapping)
                        else None
                    )
                    coefficient = terms.get(variable_name)
                    marker = (
                        f"{semantic_name}={_format_number(coefficient)}"
                        if isinstance(semantic_name, str)
                        and isinstance(coefficient, (int, float))
                        and not isinstance(coefficient, bool)
                        else None
                    )
                    if marker and marker not in requirement:
                        errors.append(
                            issue(
                                "base_binding.weight_hidden",
                                constraint_path,
                                f"weighted term {marker!r} is absent from requirement_zh",
                            )
                        )
    return errors


def audit_structure_and_provenance(root: Path) -> StructuralReport:
    root = root.resolve()
    public, public_errors = load_jsonl(
        root / "public" / "tasks_zh.jsonl", "public/tasks_zh.jsonl"
    )
    gold, gold_errors = load_jsonl(
        root / "private" / "gold.jsonl", "private/gold.jsonl"
    )
    staging, staging_errors = load_jsonl(
        root / "staging" / "base_candidates.jsonl",
        "staging/base_candidates.jsonl",
    )
    model_irs: dict[str, Mapping[str, Mapping[str, Any]]] = {}
    model_errors: list[Issue] = []
    for row in gold:
        task_id = row.get("id")
        if not isinstance(task_id, str):
            continue
        pair, pair_errors = _load_model_pair(root, row)
        model_irs[task_id] = pair
        model_errors.extend(pair_errors)
    report = audit_structure_records(gold, staging, model_irs)
    binding_errors = audit_public_base_binding(public, gold, model_irs)
    report.errors[:0] = [
        *public_errors,
        *gold_errors,
        *staging_errors,
        *model_errors,
        *binding_errors,
    ]
    report.stats["public_base_binding_errors"] = len(binding_errors)
    return report


def _format_human(report: StructuralReport) -> str:
    lines = [
        f"SearchWorthyOR-100 structure/provenance gate: {'PASS' if report.ok else 'FAIL'}",
        f"errors={len(report.errors)} warnings={len(report.warnings)}",
    ]
    for entry in report.errors:
        lines.append(f"ERROR [{entry.code}] {entry.path}: {entry.message}")
    for entry in report.warnings:
        lines.append(f"WARN  [{entry.code}] {entry.path}: {entry.message}")
    lines.append(f"stats={json.dumps(report.stats, ensure_ascii=False, sort_keys=True)}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="dataset root (default: parent of scripts/)",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    args = parser.parse_args(argv)
    report = audit_structure_and_provenance(args.root)
    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(_format_human(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())

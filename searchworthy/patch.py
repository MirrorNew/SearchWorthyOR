"""Evidence-bound PatchPlan expansion and transactional IR mutation.

Only families in ``PATCH_FAMILIES`` are reachable in V0.  Constraint branches
remain visible as inactive scaffolding but are rejected before expansion until
complete constraint semantics can be grounded.
"""

from __future__ import annotations

import copy
from typing import Any

from .contracts import DecisionCompleteORState, GapState, PatchBundle, PatchOperation, PatchPlan
from .or_model import ValidatedIR, split_target, target_value, validate_ir


class PatchValidationError(ValueError):
    pass


PATCH_FAMILIES = {
    "SET_VARIABLE_BOUNDS",
    "SET_OBJECTIVE_COEFFICIENT",
}


def _gap(state: DecisionCompleteORState, gap_id: str):
    match = next((gap for gap in state.gaps if gap.gap_id == gap_id), None)
    if match is None:
        raise PatchValidationError("Patch references an unknown gap")
    return match


def _admitted_evidence_ids(gap: Any) -> set[str]:
    evidence = gap.evidence if isinstance(gap.evidence, dict) else {}
    cards = evidence.get("evidence_cards") if isinstance(evidence.get("evidence_cards"), list) else []
    admitted: set[str] = set()
    for card in cards:
        if not isinstance(card, dict):
            continue
        if all(card.get(key) is True for key in ("supported", "applies", "bindable", "consistent")):
            evidence_id = card.get("evidence_id")
            if isinstance(evidence_id, str):
                admitted.add(evidence_id)
    return admitted


def required_patch_bindings(plan: PatchPlan) -> dict[str, Any]:
    """Return evidence-controlled Patch leaves that must be bound exactly."""
    parameters = plan.parameters
    if plan.patch_family == "SET_VARIABLE_BOUNDS" and set(parameters) == {"lb", "ub"}:
        return {"parameters.lb": parameters["lb"], "parameters.ub": parameters["ub"]}
    if plan.patch_family in {"UPSERT_CONSTRAINT", "REMOVE_CONSTRAINT"}:
        raise PatchValidationError(
            "constraint insertion/removal is disabled until the complete constraint semantics can be grounded"
        )
    if plan.patch_family == "SET_OBJECTIVE_COEFFICIENT" and set(parameters) == {"coefficient"}:
        return {"parameters.coefficient": parameters["coefficient"]}
    raise PatchValidationError("PatchPlan parameters cannot be mapped to required evidence bindings")


def cards_bind_patch_plan(cards: list[Any], plan: PatchPlan) -> bool:
    required = required_patch_bindings(plan)
    observed: dict[str, list[Any]] = {path: [] for path in required}
    for card in cards:
        path = card.get("binding_path") if isinstance(card, dict) else getattr(card, "binding_path", None)
        value = card.get("binding_value") if isinstance(card, dict) else getattr(card, "binding_value", None)
        if path in observed:
            observed[path].append(value)
    return all(values and all(value == required[path] for value in values) for path, values in observed.items())


def expand_patch_plan(
    state: DecisionCompleteORState,
    current_ir: ValidatedIR,
    gap_id: str,
    plan: PatchPlan,
) -> PatchBundle:
    """Bind one admitted semantic plan to one guarded executable operation."""

    gap = _gap(state, gap_id)
    if gap.state != GapState.PATCH_READY:
        raise PatchValidationError("PatchPlan requires a PATCH_READY gap")
    if plan.patch_family not in PATCH_FAMILIES or plan.target != gap.target:
        raise PatchValidationError("PatchPlan family or target is invalid")
    admitted_ids = _admitted_evidence_ids(gap)
    if not plan.evidence_ids or not set(plan.evidence_ids).issubset(admitted_ids):
        raise PatchValidationError("PatchPlan lacks admitted evidence lineage")
    evidence = gap.evidence if isinstance(gap.evidence, dict) else {}
    cards = evidence.get("evidence_cards") if isinstance(evidence.get("evidence_cards"), list) else []
    cited_cards = [card for card in cards if card.get("evidence_id") in set(plan.evidence_ids)]
    if not cards_bind_patch_plan(cited_cards, plan):
        raise PatchValidationError("PatchPlan parameters do not equal the cited evidence bindings")
    current = target_value(current_ir, plan.target)
    if plan.before_guard != current:
        raise PatchValidationError("PatchPlan before_guard does not match current canonical IR")
    family, slot = split_target(plan.target)
    parameters = plan.parameters

    if plan.patch_family == "SET_VARIABLE_BOUNDS":
        if family != "variable" or set(parameters) != {"lb", "ub"}:
            raise PatchValidationError("SET_VARIABLE_BOUNDS parameters are invalid")
        operation = PatchOperation("SET", plan.target, current, {"lb": parameters["lb"], "ub": parameters["ub"]})
    # The two constraint branches document the intended representation, but
    # PATCH_FAMILIES currently rejects them before this point.
    elif plan.patch_family == "UPSERT_CONSTRAINT":
        constraint = parameters.get("constraint") if set(parameters) == {"constraint"} else None
        if family != "constraint" or not isinstance(constraint, dict):
            raise PatchValidationError("UPSERT_CONSTRAINT parameters are invalid")
        after = copy.deepcopy(constraint)
        after["name"] = slot
        after.setdefault("meaning", gap.gap_claim)
        operation = PatchOperation("UPSERT", plan.target, current, after)
    elif plan.patch_family == "REMOVE_CONSTRAINT":
        if family != "constraint" or parameters or current is None:
            raise PatchValidationError("REMOVE_CONSTRAINT parameters or target are invalid")
        operation = PatchOperation("REMOVE", plan.target, current, None)
    elif plan.patch_family == "SET_OBJECTIVE_COEFFICIENT":
        if family != "objective" or set(parameters) != {"coefficient"}:
            raise PatchValidationError("SET_OBJECTIVE_COEFFICIENT parameters are invalid")
        operation = PatchOperation("SET", plan.target, current, parameters["coefficient"])
    else:
        raise PatchValidationError("parameter Patch is disabled until canonical IR expressions consume parameters")

    bundle = PatchBundle(gap_id=gap_id, evidence_ids=list(plan.evidence_ids), operations=[operation])
    validate_patch_bundle(current_ir, bundle)
    return bundle


def validate_patch_bundle(current_ir: ValidatedIR, bundle: PatchBundle) -> None:
    if not bundle.evidence_ids or not bundle.operations:
        raise PatchValidationError("PatchBundle must contain evidence and operations")
    seen: set[str] = set()
    for operation in bundle.operations:
        if operation.target in seen:
            raise PatchValidationError("PatchBundle modifies a target more than once")
        if operation.before != target_value(current_ir, operation.target):
            raise PatchValidationError("PatchBundle before guard does not match current IR")
        family, _ = split_target(operation.target)
        allowed = {
            "variable": {"SET"},
            "parameter": set(),
            "constraint": {"UPSERT", "REMOVE"},
            "objective": {"SET"},
        }
        if operation.op not in allowed[family]:
            raise PatchValidationError("Patch operation is incompatible with its target family")
        seen.add(operation.target)


def apply_patch_transactionally(
    current_ir: ValidatedIR,
    bundle: PatchBundle,
    output_schema: dict[str, Any] | None = None,
) -> ValidatedIR:
    """Apply all operations to a copy; validation failure leaves current_ir untouched."""
    validate_patch_bundle(current_ir, bundle)
    candidate = copy.deepcopy(current_ir)
    for operation in bundle.operations:
        family, slot = split_target(operation.target)
        if family == "variable":
            row = next((item for item in candidate["variables"] if item["id"] == slot), None)
            if row is None or not isinstance(operation.after, dict) or set(operation.after) != {"lb", "ub"}:
                raise PatchValidationError("variable Patch target or value is invalid")
            row["lb"], row["ub"] = operation.after["lb"], operation.after["ub"]
        elif family == "parameter":
            raise PatchValidationError("parameter Patch cannot be executed by the V0 compiler")
        elif family == "objective":
            if slot == "constant":
                candidate["objective"]["constant"] = operation.after
            else:
                term = next((item for item in candidate["objective"]["terms"] if item["var"] == slot), None)
                if term is None:
                    candidate["objective"]["terms"].append({"var": slot, "coef": operation.after})
                else:
                    term["coef"] = operation.after
        else:
            index = next((i for i, item in enumerate(candidate["constraints"]) if item["name"] == slot), None)
            if operation.op == "REMOVE":
                if index is None:
                    raise PatchValidationError("constraint removal target is absent")
                candidate["constraints"].pop(index)
            else:
                if not isinstance(operation.after, dict):
                    raise PatchValidationError("constraint Patch value must be an object")
                after = {key: copy.deepcopy(operation.after[key]) for key in ("name", "terms", "sense", "rhs") if key in operation.after}
                after["name"] = slot
                if index is None:
                    candidate["constraints"].append(after)
                else:
                    candidate["constraints"][index] = after
    try:
        return validate_ir(candidate, output_schema)
    except ValueError as exc:
        raise PatchValidationError(str(exc)) from exc


def semantic_patch_elements(bundle: PatchBundle) -> list[dict[str, Any]]:
    """Stable public semantic projection; internal evidence lineage remains in state."""
    rows: list[dict[str, Any]] = []
    for operation in bundle.operations:
        family, slot = split_target(operation.target)
        if family == "constraint":
            if operation.op == "REMOVE":
                rows.append({"op": "remove_constraint", "name": slot, "before": copy.deepcopy(operation.before)})
                continue
            after = operation.after
            semantic_after = {
                "name": slot,
                "coefficients": {term["var"]: term["coef"] for term in after["terms"]},
                "sense": after["sense"],
                "rhs": after["rhs"],
                "meaning": str(after.get("meaning") or "evidence-bound constraint"),
            }
            rows.append(
                {
                    "op": "add_constraint" if operation.before is None else "modify_constraint",
                    "name": slot,
                    "after": semantic_after,
                }
            )
        elif family == "objective":
            rows.append(
                {
                    "op": "modify_objective_term",
                    "name": slot,
                    "before": copy.deepcopy(operation.before),
                    "after": {"coefficient": copy.deepcopy(operation.after)},
                }
            )
        elif family == "variable":
            rows.append(
                {
                    "op": "modify_variable_bound",
                    "name": slot,
                    "before": copy.deepcopy(operation.before),
                    "after": copy.deepcopy(operation.after),
                }
            )
    return rows

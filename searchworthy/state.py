"""Legal transitions and closure checks for the information-effect state.

The controller never mutates gap closure directly.  It requests one typed
``StateUpdate``; this module copies the state, verifies the transition, and
updates linked FactCoverage rows.  That makes search and Patch decisions
replayable as OR-state transitions rather than hidden agent memory.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .contracts import (
    AuditDimension,
    AuditSummary,
    DecisionCompleteORState,
    FactUsageStatus,
    GapState,
    PotentialEffect,
    StateUpdate,
)


CLOSED_GAP_STATES = {
    GapState.CLOSED_NO_SEARCH,
    GapState.CLOSED_RETAIN,
    GapState.CLOSED_PATCH,
}
ACCOUNTED_FACT_STATES = {
    FactUsageStatus.MODELED,
    FactUsageStatus.APPLICABILITY_USED,
    FactUsageStatus.DERIVED,
    FactUsageStatus.IRRELEVANT_JUSTIFIED,
}
SIGNIFICANT_EFFECTS = {
    PotentialEffect.VALUE_CHANGE,
    PotentialEffect.DECISION_CHANGE,
    PotentialEffect.FEASIBILITY_CHANGE,
}
CANONICAL_FACT_TARGET_PREFIXES = ("variable.", "constraint.", "objective.")


def _is_canonical_fact_target(target: Any) -> bool:
    return isinstance(target, str) and any(
        target.startswith(prefix) and len(target) > len(prefix) for prefix in CANONICAL_FACT_TARGET_PREFIXES
    )


def _is_applicability_target(target: str) -> bool:
    prefix = "applicability."
    return target.startswith(prefix) and len(target) > len(prefix)


def _fact_mapping_contract_holds(fact: Any) -> bool:
    targets = fact.mapped_targets
    if fact.usage_status in {FactUsageStatus.MODELED, FactUsageStatus.DERIVED}:
        return bool(targets) and all(_is_canonical_fact_target(target) for target in targets)
    if fact.usage_status == FactUsageStatus.APPLICABILITY_USED:
        return (
            bool(targets)
            and any(_is_applicability_target(target) for target in targets)
            and all(_is_canonical_fact_target(target) or _is_applicability_target(target) for target in targets)
        )
    if fact.usage_status in {FactUsageStatus.UNACCOUNTED, FactUsageStatus.IRRELEVANT_JUSTIFIED}:
        return targets == []
    return False


def digest_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def audit_complete(summary: AuditSummary) -> bool:
    return (
        summary.prompt_fact_to_model_complete is True
        and summary.model_interface_to_grounding_complete is True
        and set(summary.negative_space_checked) == set(AuditDimension)
        and all(summary.negative_space_checked.values())
        and summary.prompt_fact_unit_total > 0
        and summary.prompt_fact_unit_covered == summary.prompt_fact_unit_total
        and summary.prompt_fact_coverage_ratio == 1.0
        and summary.overflow_detected is False
        and summary.overflow_count == 0
    )


def _gap(state: DecisionCompleteORState, gap_id: str):
    matches = [gap for gap in state.gaps if gap.gap_id == gap_id]
    if len(matches) != 1:
        raise ValueError(f"unknown or duplicated gap_id: {gap_id}")
    return matches[0]


def _close_facts(
    state: DecisionCompleteORState,
    gap_id: str,
    status: FactUsageStatus,
    reason: str,
) -> None:
    gap = _gap(state, gap_id)
    linked = [fact for fact in state.fact_coverage if fact.gap_id == gap_id]
    if not linked:
        raise ValueError(f"gap {gap_id} has no linked FactCoverageRow")
    if status in {FactUsageStatus.MODELED, FactUsageStatus.DERIVED}:
        if not _is_canonical_fact_target(gap.target):
            raise ValueError("closed MODELED/DERIVED fact requires a canonical OR target")
        mapped_targets = [gap.target]
    elif status == FactUsageStatus.APPLICABILITY_USED:
        mapped_targets = [f"applicability.{gap.target}"]
    elif status == FactUsageStatus.IRRELEVANT_JUSTIFIED:
        mapped_targets = []
    else:
        raise ValueError("unsupported terminal FactCoverage status")
    for fact in linked:
        fact.usage_status = status
        fact.mapped_targets = list(mapped_targets)
        fact.reason = reason


def apply_state_update(
    state: DecisionCompleteORState,
    update: StateUpdate,
) -> DecisionCompleteORState:
    """Apply one legal, program-owned transition and return a copied state."""
    result = copy.deepcopy(state)
    gap = _gap(result, update.gap_id)

    if update.kind == "PROBE":
        if gap.state != GapState.OPEN:
            raise ValueError("Impact Probe requires an OPEN gap")
        effect = update.payload.get("effect")
        coverage = update.payload.get("coverage")
        if not isinstance(effect, PotentialEffect) or not isinstance(coverage, bool):
            raise ValueError("invalid solver-owned probe result")
        gap.probe_coverage = coverage
        gap.potential_effect = effect if coverage or effect != PotentialEffect.NO_EFFECT else PotentialEffect.UNKNOWN
        # A finite sensitivity sample cannot prove no effect.  Closure requires
        # a separate program proof that a finite local domain was exhausted.
        if (
            effect == PotentialEffect.NO_EFFECT
            and coverage
            and update.payload.get("exhaustive_local") is True
        ):
            gap.state = GapState.CLOSED_NO_SEARCH
            _close_facts(
                result,
                gap.gap_id,
                FactUsageStatus.IRRELEVANT_JUSTIFIED,
                str(update.payload.get("reason") or "solver probe found no decision effect"),
            )
            if result.active_gap_id == gap.gap_id:
                result.active_gap_id = None
        return result

    if update.kind == "EVIDENCE_OBSERVED":
        if gap.state != GapState.NEED_SEARCH or result.active_gap_id != gap.gap_id:
            raise ValueError("evidence may only be recorded for the active NEED_SEARCH gap")
        cards = update.payload.get("cards")
        if not isinstance(cards, list) or any(not isinstance(card, dict) for card in cards):
            raise ValueError("evidence ledger cards must be objects")
        for card in cards:
            result.evidence_ledger.append(
                {
                    "gap_id": gap.gap_id,
                    "round": result.round,
                    **copy.deepcopy(card),
                }
            )
        return result

    if update.kind == "SEARCH_AUTHORIZED":
        if gap.state != GapState.OPEN or gap.potential_effect not in SIGNIFICANT_EFFECTS:
            raise ValueError("search can only be authorized for an OPEN decision-critical gap")
        if result.active_gap_id not in {None, gap.gap_id}:
            raise ValueError("another gap is already active")
        result.active_gap_id = gap.gap_id
        gap.state = GapState.NEED_SEARCH
        return result

    if update.kind == "SEARCH_AGAIN":
        query = update.payload.get("query")
        if gap.state != GapState.NEED_SEARCH or result.active_gap_id != gap.gap_id:
            raise ValueError("search continuation requires the active NEED_SEARCH gap")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("search continuation requires a non-empty query")
        gap.pending_query = query.strip()
        gap.state = GapState.OPEN
        return result

    if update.kind == "RETAIN":
        if gap.state != GapState.NEED_SEARCH or result.active_gap_id != gap.gap_id:
            raise ValueError("RETAIN requires the active NEED_SEARCH gap")
        already_modeled = update.payload.get("already_modeled") is True
        gap.evidence = copy.deepcopy(update.payload.get("evidence"))
        gap.state = GapState.CLOSED_RETAIN
        _close_facts(
            result,
            gap.gap_id,
            FactUsageStatus.MODELED if already_modeled else FactUsageStatus.IRRELEVANT_JUSTIFIED,
            "evidence confirms the rule is already modeled" if already_modeled else "evidence proves the rule does not apply",
        )
        result.active_gap_id = None
        return result

    if update.kind == "PATCH_READY":
        if gap.state != GapState.NEED_SEARCH or result.active_gap_id != gap.gap_id:
            raise ValueError("PATCH_READY requires the active NEED_SEARCH gap")
        gap.evidence = copy.deepcopy(update.payload.get("evidence"))
        gap.state = GapState.PATCH_READY
        return result

    if update.kind == "PATCH_CLOSED":
        if gap.state != GapState.PATCH_READY or result.active_gap_id != gap.gap_id:
            raise ValueError("CLOSED_PATCH requires the active PATCH_READY gap")
        gap.patch = copy.deepcopy(update.payload.get("patch"))
        gap.realized_effect = copy.deepcopy(update.payload.get("realized_effect"))
        gap.state = GapState.CLOSED_PATCH
        _close_facts(result, gap.gap_id, FactUsageStatus.MODELED, "evidence-bound Patch validated and re-solved")
        result.active_gap_id = None
        return result

    if update.kind == "ABSTAIN":
        if gap.state in CLOSED_GAP_STATES:
            raise ValueError("a legally closed gap cannot be changed to ABSTAIN")
        reason = str(update.payload.get("reason") or "unresolved gap")
        gap.state = GapState.UNRESOLVED_ABSTAIN
        gap.realized_effect = {"reason": reason}
        result.active_gap_id = None
        return result

    raise ValueError(f"unknown StateUpdate kind: {update.kind}")


def select_next_gap(state: DecisionCompleteORState) -> str | None:
    if state.active_gap_id is not None:
        gap = _gap(state, state.active_gap_id)
        if gap.state in {GapState.OPEN, GapState.NEED_SEARCH, GapState.PATCH_READY}:
            return gap.gap_id
    candidates = [gap for gap in state.gaps if gap.state == GapState.OPEN]
    if not candidates:
        return None
    priority = {
        PotentialEffect.FEASIBILITY_CHANGE: 4,
        PotentialEffect.DECISION_CHANGE: 3,
        PotentialEffect.VALUE_CHANGE: 2,
        PotentialEffect.UNKNOWN: 1,
        PotentialEffect.NO_EFFECT: 0,
    }
    chosen = sorted(candidates, key=lambda gap: (-priority[gap.potential_effect], gap.gap_id))[0]
    return chosen.gap_id


def is_decision_complete(state: DecisionCompleteORState) -> bool:
    if not audit_complete(state.audit_summary):
        return False
    if not state.fact_coverage or any(
        fact.usage_status not in ACCOUNTED_FACT_STATES or not _fact_mapping_contract_holds(fact)
        for fact in state.fact_coverage
    ):
        return False
    if state.base_solve.status != "OPTIMAL" or not state.base_solve.feasible:
        return False
    if state.current_solve.status != "OPTIMAL" or not state.current_solve.feasible:
        return False
    if not state.gaps:
        return state.self_contained
    return all(gap.state in CLOSED_GAP_STATES for gap in state.gaps)


def render_state_table(state: DecisionCompleteORState) -> str:
    header = "Gap | Claim | OR Target | Potential Effect | State"
    separator = "--- | --- | --- | --- | ---"
    rows = [header, separator]
    for gap in state.gaps:
        marker = "*" if gap.gap_id == state.active_gap_id else ""
        claim = gap.gap_claim.replace("|", "/").replace("\n", " ")
        rows.append(
            f"{marker}{gap.gap_id} | {claim} | {gap.target} | {gap.potential_effect.value} | {gap.state.value}"
        )
    return "\n".join(rows)

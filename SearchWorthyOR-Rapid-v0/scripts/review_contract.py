from __future__ import annotations

from typing import Any


def reviewer_assignment_errors(contract: dict[str, Any], batch: int, reviewer_id: Any) -> list[str]:
    expected = contract.get("reviewer_assignments", {}).get(str(batch))
    if not isinstance(expected, str) or not expected:
        return [f"batch_{batch:02d}:reviewer_assignment_missing"]
    if reviewer_id != expected:
        return [f"batch_{batch:02d}:unexpected_reviewer:{reviewer_id!r}:expected:{expected!r}"]
    return []

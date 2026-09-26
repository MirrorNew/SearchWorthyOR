from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from review_contract import reviewer_assignment_errors


def test_reviewer_must_match_canonical_batch_assignment() -> None:
    contract = {"reviewer_assignments": {"3": "reviewer-c"}}
    assert reviewer_assignment_errors(contract, 3, "reviewer-c") == []
    assert "unexpected_reviewer" in reviewer_assignment_errors(contract, 3, "generator-a")[0]
    assert "reviewer_assignment_missing" in reviewer_assignment_errors(contract, 4, "reviewer-c")[0]

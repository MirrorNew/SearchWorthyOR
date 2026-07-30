"""Regression tests for fail-closed final blind-review merging."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from merge_reviews import REQUIRED_REVIEW_CHECKS, validate_review  # noqa: E402


def review(label: str = "accept") -> dict:
    return {
        "id": "SWOR001",
        "reviewer_id": "blind-a",
        "blind_packet": True,
        "label": label,
        "issues": [] if label == "accept" else ["semantic mismatch"],
        "checks": {key: label == "accept" for key in REQUIRED_REVIEW_CHECKS},
    }


def test_accept_requires_all_checks_and_no_issues() -> None:
    validate_review(review(), expected_id="SWOR001", packet="review_a")

    failed = review()
    failed["checks"]["patch_semantics"] = False
    with pytest.raises(ValueError, match="inconsistent"):
        validate_review(failed, expected_id="SWOR001", packet="review_a")

    issue_bearing = review()
    issue_bearing["issues"] = ["unresolved"]
    with pytest.raises(ValueError, match="inconsistent"):
        validate_review(issue_bearing, expected_id="SWOR001", packet="review_a")


def test_reject_requires_a_reason() -> None:
    rejected = review("reject")
    validate_review(rejected, expected_id="SWOR001", packet="review_b")
    rejected["issues"] = []
    with pytest.raises(ValueError, match="at least one issue"):
        validate_review(rejected, expected_id="SWOR001", packet="review_b")

    inconsistent = review("reject")
    inconsistent["checks"] = {key: True for key in REQUIRED_REVIEW_CHECKS}
    with pytest.raises(ValueError, match="fail at least one check"):
        validate_review(inconsistent, expected_id="SWOR001", packet="review_b")


def test_review_contract_is_exact_and_blind() -> None:
    top_level_extra = review()
    top_level_extra["evidence_notes"] = "not part of the frozen contract"
    with pytest.raises(ValueError, match="review fields must exactly match"):
        validate_review(
            top_level_extra, expected_id="SWOR001", packet="review_a"
        )

    extra = review()
    extra["checks"]["unregistered_check"] = True
    with pytest.raises(ValueError, match="exactly match"):
        validate_review(extra, expected_id="SWOR001", packet="review_a")

    visible = review()
    visible["blind_packet"] = False
    with pytest.raises(ValueError, match="blind_packet"):
        validate_review(visible, expected_id="SWOR001", packet="review_a")

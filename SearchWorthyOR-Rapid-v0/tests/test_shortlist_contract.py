from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_shortlist_exact_100_plus_30_and_balanced() -> None:
    rows = [
        json.loads(line)
        for line in (ROOT / "private" / "source_shortlist_130.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    primary = [row for row in rows if row["shortlist_role"] == "PRIMARY"]
    backups = [row for row in rows if row["shortlist_role"] == "BACKUP"]
    assert len(primary) == 100
    assert len(backups) == 30
    assert len({row["source_candidate_id"] for row in rows}) == 130
    assert len({row["rapid_task_id"] for row in primary}) == 100
    assert all(row["rapid_task_id"] is None for row in backups)
    assert Counter(row["batch"] for row in primary) == {1: 20, 2: 20, 3: 20, 4: 20, 5: 20}
    assert set(Counter(row["assigned_family"] for row in primary).values()) == {10}
    assert set(Counter(row["assigned_patch_class"] for row in primary).values()) == {25}
    assert max(Counter(row["source_document_key"] for row in primary).values()) <= 3
    quarantined = {f"SRCV2-{number:04d}" for number in range(294, 304)}
    assert not ({row["source_candidate_id"] for row in rows} & quarantined)


def test_each_batch_has_exact_local_coverage() -> None:
    rows = [
        json.loads(line)
        for line in (ROOT / "private" / "source_shortlist_130.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    for batch in range(1, 6):
        primary = [row for row in rows if row["shortlist_role"] == "PRIMARY" and row["batch"] == batch]
        assert set(Counter(row["assigned_family"] for row in primary).values()) == {2}
        assert set(Counter(row["assigned_patch_class"] for row in primary).values()) == {5}

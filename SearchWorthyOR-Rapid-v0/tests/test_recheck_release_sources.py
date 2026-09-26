from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from recheck_release_sources import default_output_path


def test_batch_recheck_does_not_overwrite_global_release_receipt(tmp_path: Path) -> None:
    assert default_output_path(tmp_path, None) == tmp_path / "private" / "source_recheck.jsonl"
    assert default_output_path(tmp_path, 3) == (
        tmp_path / "batches" / "batch_03" / "private" / "source_recheck.jsonl"
    )

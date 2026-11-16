from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_release import canonical_url, release_critical_files, release_mode_errors


def test_canonical_url_keeps_query_that_identifies_official_document() -> None:
    first = "https://example.gov/statute?section=1#content"
    second = "https://example.gov/statute?section=2"

    assert canonical_url(first) == "https://example.gov/statute?section=1"
    assert canonical_url(first) != canonical_url(second)


def test_write_release_cannot_skip_batch_validation() -> None:
    assert release_mode_errors(True, True) == ["write_release_requires_batch_validation"]
    assert release_mode_errors(True, False) == []


def test_manifest_file_scan_includes_critical_trees_and_excludes_temp_cache(tmp_path: Path) -> None:
    included = [
        tmp_path / "public" / "tasks.jsonl",
        tmp_path / "private" / "audit.jsonl",
        tmp_path / "batches" / "batch_01" / "models" / "R001" / "base_ir.json",
        tmp_path / "schemas" / "model.json",
        tmp_path / "config" / "contract.json",
        tmp_path / "scripts" / "gate.py",
        tmp_path / "tests" / "test_gate.py",
        tmp_path / ".gitattributes",
        tmp_path / "README.md",
        tmp_path / "生成方法.md",
    ]
    excluded = [
        tmp_path / "private" / "_tmp_page.png",
        tmp_path / "private" / "_diagnostic.jsonl",
        tmp_path / "scripts" / "__pycache__" / "gate.pyc",
        tmp_path / ".pytest_cache" / "state",
    ]
    for path in [*included, *excluded]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")
    assert release_critical_files(tmp_path) == sorted(included, key=lambda path: str(path.relative_to(tmp_path)).replace("\\", "/"))

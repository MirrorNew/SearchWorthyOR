from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


MANIFEST_NAME = "PUBLIC_BUNDLE_MANIFEST.json"
IGNORED_NAMES = {".git", ".pytest_cache", "__pycache__"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    manifest_path = root / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    expected = {row["path"]: row for row in manifest["files"]}
    actual = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if (
            not path.is_file()
            or path.name == MANIFEST_NAME
            or IGNORED_NAMES.intersection(relative.parts)
            or path.suffix in IGNORED_SUFFIXES
        ):
            continue
        actual[relative.as_posix()] = path
    errors: list[str] = []
    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    if missing:
        errors.append(f"missing files: {missing}")
    if unexpected:
        errors.append(f"unexpected files: {unexpected}")
    for relative in sorted(set(expected) & set(actual)):
        path = actual[relative]
        row = expected[relative]
        if path.stat().st_size != row["bytes"]:
            errors.append(f"size mismatch: {relative}")
        if sha256_file(path) != row["sha256"]:
            errors.append(f"sha256 mismatch: {relative}")
    if manifest.get("file_count") != len(expected):
        errors.append("manifest file_count mismatch")
    if manifest.get("total_bytes") != sum(
        row["bytes"] for row in expected.values()
    ):
        errors.append("manifest total_bytes mismatch")
    result = {
        "ok": not errors,
        "file_count": len(actual),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

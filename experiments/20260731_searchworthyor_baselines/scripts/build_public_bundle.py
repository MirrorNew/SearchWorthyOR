from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


EXCLUDED_NAMES = {".git", ".pytest_cache", "__pycache__"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
TEXT_SUFFIXES = {
    ".jsonl",
    ".md",
    ".ps1",
    ".py",
    ".txt",
    ".yaml",
    ".yml",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scrub_json(value: Any, replacements: list[tuple[str, str]]) -> Any:
    if isinstance(value, dict):
        return {
            key: scrub_json(item, replacements)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [scrub_json(item, replacements) for item in value]
    if isinstance(value, str):
        for old, new in replacements:
            value = value.replace(old, new)
        return value
    return value


def copy_file(
    source: Path,
    target: Path,
    replacements: list[tuple[str, str]],
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() == ".json":
        value = json.loads(source.read_text(encoding="utf-8-sig"))
        target.write_text(
            json.dumps(
                scrub_json(value, replacements),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    elif source.suffix.lower() in TEXT_SUFFIXES:
        text = source.read_text(encoding="utf-8-sig")
        for old, new in replacements:
            text = text.replace(old, new)
        target.write_text(text, encoding="utf-8")
    else:
        shutil.copy2(source, target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--include", required=True, action="append", type=Path)
    parser.add_argument("--replace", action="append", default=[])
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    destination = args.destination.resolve()
    if destination.exists():
        raise FileExistsError(
            f"destination already exists; refusing overwrite: {destination}"
        )
    replacements = []
    for raw in args.replace:
        if "=" not in raw:
            raise ValueError("--replace must be OLD=NEW")
        old, new = raw.split("=", 1)
        if not old:
            raise ValueError("--replace OLD must not be empty")
        replacements.append((old, new))
        escaped_old = old.replace("\\", "\\\\")
        if escaped_old != old:
            replacements.append((escaped_old, new))

    selected: set[Path] = set()
    for include in args.include:
        candidate = (source_root / include).resolve()
        try:
            candidate.relative_to(source_root)
        except ValueError as exc:
            raise ValueError(f"include escapes source root: {include}") from exc
        if not candidate.exists():
            raise FileNotFoundError(candidate)
        if candidate.is_file():
            selected.add(candidate)
        else:
            selected.update(path for path in candidate.rglob("*") if path.is_file())

    selected = {
        path
        for path in selected
        if not EXCLUDED_NAMES.intersection(path.parts)
        and path.suffix not in EXCLUDED_SUFFIXES
    }
    destination.mkdir(parents=True)
    for source in sorted(
        selected, key=lambda path: path.relative_to(source_root).as_posix()
    ):
        relative = source.relative_to(source_root)
        copy_file(source, destination / relative, replacements)

    records = []
    for path in sorted(
        (path for path in destination.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(destination).as_posix(),
    ):
        records.append(
            {
                "path": path.relative_to(destination).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    manifest = {
        "schema_version": 1,
        "hash_algorithm": "sha256",
        "manifest_self_excluded": True,
        "file_count": len(records),
        "total_bytes": sum(row["bytes"] for row in records),
        "files": records,
    }
    (destination / "PUBLIC_BUNDLE_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "destination": str(destination),
                "file_count": len(records),
                "total_bytes": manifest["total_bytes"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

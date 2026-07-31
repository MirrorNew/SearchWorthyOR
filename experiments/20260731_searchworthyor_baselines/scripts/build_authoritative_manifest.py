from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_files(root: Path, includes: list[Path], output: Path) -> list[Path]:
    files: set[Path] = set()
    for include in includes:
        candidate = (root / include).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as error:
            raise ValueError(f"include escapes root: {include}") from error
        if not candidate.exists():
            raise FileNotFoundError(f"missing include: {include}")
        if candidate.is_file():
            files.add(candidate)
        else:
            files.update(path.resolve() for path in candidate.rglob("*") if path.is_file())
    files.discard(output)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--include", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    output = args.output.resolve()
    try:
        output.relative_to(root)
    except ValueError as error:
        raise ValueError("--output must be inside --root") from error

    files = collect_files(root, args.include, output)
    records = [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in files
    ]
    payload = {
        "schema_version": 1,
        "hash_algorithm": "sha256",
        "root": ".",
        "file_count": len(records),
        "total_bytes": sum(record["bytes"] for record in records),
        "files": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

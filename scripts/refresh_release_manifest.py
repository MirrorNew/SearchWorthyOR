from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXCLUDED_TOP_LEVEL = {".git", ".pytest_cache", "staging"}
RAW_HASH_PREFIXES = (
    "private/web_snapshots/raw/",
    "reports/rejected_snapshots/",
)
FILE_HASH_POLICY = {
    "utf8_text_eol": "lf",
    "raw_prefixes": list(RAW_HASH_PREFIXES),
}


def manifest_bytes(path: Path, root: Path) -> bytes:
    data = path.read_bytes()
    relative = path.relative_to(root).as_posix()
    if relative.startswith(RAW_HASH_PREFIXES) or b"\x00" in data:
        return data
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def is_released(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if relative.as_posix() == "manifest.json":
        return False
    if relative.parts[0] in EXCLUDED_TOP_LEVEL:
        return False
    if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
        return False
    if (
        relative.parts[0] == "reports"
        and (
            path.name == "release_gate.json"
            or path.name.endswith((".stdout.txt", ".stderr.txt"))
        )
    ):
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    manifest_path = root / "manifest.json"
    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8-sig")
    )
    files = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not is_released(path, root):
            continue
        relative = path.relative_to(root).as_posix()
        payload = manifest_bytes(path, root)
        files[relative] = {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
        }
    manifest["file_hash_policy"] = FILE_HASH_POLICY
    manifest["files"] = files
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "released_file_count": len(files),
                "released_bytes": sum(
                    row["bytes"] for row in files.values()
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    script = Path(__file__).with_name("refresh_release_manifest.py")
    with tempfile.TemporaryDirectory() as raw_tmp:
        root = Path(raw_tmp)
        (root / "manifest.json").write_text(
            json.dumps({"dataset": "test", "files": {}}),
            encoding="utf-8",
        )
        for relative in (
            "README.md",
            ".git/config",
            ".pytest_cache/state",
            "staging/private.json",
            "reports/run.stdout.txt",
            "reports/run.stderr.txt",
            "reports/release_gate.json",
            "scripts/tool.py",
            "scripts/__pycache__/tool.pyc",
        ):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(relative, encoding="utf-8")
        (root / "README.md").write_bytes(b"line1\r\nline2\r\n")
        raw_snapshot = (
            root / "private" / "web_snapshots" / "raw" / "sample.response"
        )
        raw_snapshot.parent.mkdir(parents=True, exist_ok=True)
        raw_snapshot.write_bytes(b"line1\r\nline2\r\n")

        completed = subprocess.run(
            [
                sys.executable,
                str(script),
                "--root",
                str(root),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr or completed.stdout)
        manifest = json.loads(
            (root / "manifest.json").read_text(encoding="utf-8")
        )
        assert set(manifest["files"]) == {
            "README.md",
            "private/web_snapshots/raw/sample.response",
            "scripts/tool.py",
        }
        canonical_readme = b"line1\nline2\n"
        assert manifest["files"]["README.md"] == {
            "sha256": hashlib.sha256(canonical_readme).hexdigest(),
            "bytes": len(canonical_readme),
        }
        raw_bytes = b"line1\r\nline2\r\n"
        assert manifest["files"][
            "private/web_snapshots/raw/sample.response"
        ] == {
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "bytes": len(raw_bytes),
        }

    print("refresh_release_manifest exclusions regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

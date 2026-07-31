from __future__ import annotations

import json
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
            "scripts/tool.py",
        }

    print("refresh_release_manifest exclusions regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    script = Path(__file__).with_name("build_public_bundle.py")
    verifier = Path(__file__).with_name("verify_public_bundle.py")
    with tempfile.TemporaryDirectory() as raw_tmp:
        root = Path(raw_tmp)
        source = root / "source"
        destination = root / "bundle"
        (source / "docs").mkdir(parents=True)
        (source / "docs" / "note.md").write_text(
            "local=C:\\secret\\experiment",
            encoding="utf-8",
        )
        (source / "result.json").write_text(
            json.dumps(
                {
                    "run_root": "C:\\secret\\experiment\\runs",
                    "repr_run_root": r"C:\\secret\\experiment\\runs",
                    "score": 1,
                }
            ),
            encoding="utf-8",
        )
        (source / "events.jsonl").write_text(
            '{"run_root":"C:\\\\secret\\\\experiment\\\\runs"}\n',
            encoding="utf-8",
        )
        (source / "launch.ps1").write_text(
            "$experimentRoot = 'C:\\secret\\experiment'\n",
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                sys.executable,
                str(script),
                "--source-root",
                str(source),
                "--destination",
                str(destination),
                "--include",
                "docs",
                "--include",
                "result.json",
                "--include",
                "events.jsonl",
                "--include",
                "launch.ps1",
                "--replace",
                r"C:\secret\experiment=.",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr or completed.stdout)
        assert (destination / "docs" / "note.md").read_text(
            encoding="utf-8"
        ) == "local=."
        payload = json.loads(
            (destination / "result.json").read_text(encoding="utf-8")
        )
        assert payload["run_root"] == ".\\runs"
        assert payload["repr_run_root"] == r".\\runs"
        assert "C:\\secret\\experiment" not in (
            destination / "events.jsonl"
        ).read_text(encoding="utf-8")
        assert "C:\\secret\\experiment" not in (
            destination / "launch.ps1"
        ).read_text(encoding="utf-8")
        manifest = json.loads(
            (destination / "PUBLIC_BUNDLE_MANIFEST.json").read_text(
                encoding="utf-8"
            )
        )
        assert manifest["file_count"] == 4
        verified = subprocess.run(
            [
                sys.executable,
                str(verifier),
                "--root",
                str(destination),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if verified.returncode != 0:
            raise AssertionError(verified.stderr or verified.stdout)
        cache = destination / "scripts" / "__pycache__" / "tool.pyc"
        cache.parent.mkdir(parents=True)
        cache.write_bytes(b"local cache")
        verified_with_cache = subprocess.run(
            [
                sys.executable,
                str(verifier),
                "--root",
                str(destination),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if verified_with_cache.returncode != 0:
            raise AssertionError(
                verified_with_cache.stderr or verified_with_cache.stdout
            )

        refused = subprocess.run(
            [
                sys.executable,
                str(script),
                "--source-root",
                str(source),
                "--destination",
                str(destination),
                "--include",
                "result.json",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert refused.returncode != 0
        assert "refusing overwrite" in refused.stderr

    print("build_public_bundle regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

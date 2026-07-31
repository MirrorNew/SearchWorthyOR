from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    script = Path(__file__).with_name("aggregate_event_usage.py")
    with tempfile.TemporaryDirectory() as raw_tmp:
        root = Path(raw_tmp)
        first = root / "shard0" / "SWOR001" / "codex_events.jsonl"
        second = (
            root / "shard0" / "SWOR002" / "controller_turn_1.events.jsonl"
        )
        empty = (
            root / "shard0" / "SWOR002" / "controller_turn_2.events.jsonl"
        )
        for path in (first, second, empty):
            path.parent.mkdir(parents=True, exist_ok=True)
        first.write_text(
            json.dumps(
                {
                    "type": "turn.completed",
                    "usage": {
                        "input_tokens": 10,
                        "cached_input_tokens": 3,
                        "output_tokens": 2,
                        "reasoning_output_tokens": 1,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        second.write_text(
            json.dumps(
                {
                    "type": "turn.completed",
                    "usage": {
                        "input_tokens": 20,
                        "cached_input_tokens": 5,
                        "output_tokens": 4,
                        "reasoning_output_tokens": 2,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        empty.write_text("", encoding="utf-8")
        output = root / "usage.json"
        completed = subprocess.run(
            [
                sys.executable,
                str(script),
                "--run-root",
                str(root),
                "--output",
                str(output),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr or completed.stdout)
        payload = json.loads(output.read_text(encoding="utf-8"))
        assert payload["event_file_count"] == 3
        assert payload["files_with_usage_count"] == 2
        assert payload["files_without_usage_count"] == 1
        assert payload["task_count_with_usage"] == 2
        assert payload["totals"]["model_calls"] == 2
        assert payload["totals"]["input_tokens"] == 30
        assert payload["totals"]["cached_input_tokens"] == 8
        assert payload["totals"]["output_tokens"] == 6
        assert payload["totals"]["reasoning_output_tokens"] == 3

    print("aggregate_event_usage regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

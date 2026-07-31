from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from run_codex_cli_prompt_adapter import (
    audit_stage_events,
    call_json_stage,
)


def main() -> int:
    multiple_messages = [
        {"type": "thread.started"},
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {"type": "agent_message"},
        },
        {
            "type": "item.completed",
            "item": {"type": "agent_message"},
        },
        {"type": "turn.completed"},
    ]
    accepted = audit_stage_events(multiple_messages, [])
    assert accepted["passed"], accepted
    assert accepted["completed_agent_messages"] == 2
    assert accepted["last_completed_non_error_item"] == "agent_message"

    trailing_todo = multiple_messages[:-1] + [
        {
            "type": "item.started",
            "item": {"type": "todo_list", "id": "todo_1"},
        },
        {
            "type": "item.completed",
            "item": {"type": "todo_list", "id": "todo_1"},
        },
        {"type": "turn.completed"},
    ]
    todo_accepted = audit_stage_events(trailing_todo, [])
    assert todo_accepted["passed"], todo_accepted
    assert todo_accepted["todo_list_event_count"] == 2
    assert todo_accepted["trailing_item_types"] == [
        "todo_list",
        "todo_list",
    ]

    forbidden_tool = multiple_messages[:-1] + [
        {
            "type": "item.completed",
            "item": {"type": "command_execution"},
        },
        {"type": "turn.completed"},
    ]
    rejected = audit_stage_events(forbidden_tool, [])
    assert not rejected["passed"], rejected
    assert any(
        violation.get("type")
        in {"forbidden_item", "post_final_agent_item"}
        for violation in rejected["violations"]
    )

    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        artifact_dir = root / "artifacts"
        artifact_dir.mkdir()
        (artifact_dir / "resume_gate.events.jsonl").write_text(
            "", encoding="utf-8"
        )
        (artifact_dir / "resume_gate.stderr.txt").write_text(
            "fatal CLI error", encoding="utf-8"
        )
        try:
            call_json_stage(
                prompt="test",
                stage="resume_gate",
                artifact_dir=artifact_dir,
                sterile_dir=root / "sterile",
                codex_executable="must-not-be-called",
                output_schema=root / "missing-schema.json",
                model="test-model",
                reasoning_effort="high",
                reuse_existing_response=True,
            )
        except RuntimeError as error:
            assert "events or stderr" in str(error), error
        else:
            raise AssertionError(
                "non-empty stderr without a response must block recall"
            )
    print(
        {
            "multiple_agent_messages_accepted": True,
            "trailing_todo_list_accepted": True,
            "forbidden_tool_item_rejected": True,
            "stderr_only_resume_rejected": True,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

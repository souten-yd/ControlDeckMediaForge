from __future__ import annotations

import importlib.util
from pathlib import Path


spec = importlib.util.spec_from_file_location("argument_probe", Path(__file__).parents[1] / "scripts/3ds_tool_argument_probe.py")
assert spec and spec.loader
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_sse_multiline_done_and_unterminated_last_event() -> None:
    assert list(probe.stream_events([": ping", 'data: {"a":', 'data: 1}', "", "data: [DONE]", "", 'data: {"ignored":1}'])) == [{"a": 1}]
    assert list(probe.stream_events(['data: {"a":1}'])) == [{"a": 1}]


def test_tool_deltas_and_error_do_not_become_success() -> None:
    calls, finishes, errors = {}, [], []
    for fragment in ('{"x":', '1}'):
        probe.collect_event({"choices": [{"delta": {"tool_calls": [{"index": 0,
            "function": {"arguments": fragment}}]}}]}, calls, finishes, errors)
    probe.collect_event({"error": {"code": 500, "message": "private generated data"}}, calls, finishes, errors)
    assert calls[0]["arguments"] == '{"x":1}'
    assert errors == ["500"] and not finishes


def test_planning_protocol_does_not_supply_coordinates_or_execute() -> None:
    direct, plan = probe.prompt_for("direct"), probe.prompt_for("plan")
    assert "Choose coordinates and faces yourself" in direct and "Choose coordinates and faces yourself" in plan
    assert "copying that identical request" in plan and "JSON code block" in plan
    assert "no executor" in plan and "require_closed=true" in plan


def test_plan_must_match_actual_complete_arguments() -> None:
    calls = {0: {"name": "record_probe", "arguments": '{"x":1}'}}
    assert probe.plan_matches('```json\n{"x":1}\n```', calls)
    assert not probe.plan_matches('```json\n{"x":2}\n```', calls)
    assert not probe.plan_matches('No data artifact', calls)
    assert not probe.plan_matches('```json\n{"x":\n```', calls)

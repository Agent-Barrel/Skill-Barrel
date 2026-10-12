"""Claude input policy can be exercised independently of a Windows console."""
from step2step.claude.attach import attach_runner


def test_prompt_clear_type_snapshot_and_submit_order(monkeypatch):
    events = []

    class Console:
        def backspace(self, count):
            events.append(("backspace", count))

        def type_text(self, text):
            events.append(("type", text))

        def text(self):
            events.append(("snapshot",))
            return "prompt before submission"

        def submit(self):
            events.append(("submit",))

    monkeypatch.setattr(attach_runner.time, "sleep", lambda seconds: events.append(("sleep", seconds)))
    logs = []
    runner = attach_runner.AttachRunner(Console(), ["one\r\ntwo\rthree"], logger=logs.append)
    assert runner._send(1, runner.prompts[0]) == "prompt before submission"
    assert events == [
        ("backspace", 200), ("sleep", 0.15), ("type", "one\ntwo\nthree"),
        ("sleep", 0.3), ("snapshot",), ("submit",),
    ]
    assert any("multi-line prompt" in line for line in logs)

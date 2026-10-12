from copy import deepcopy
import queue

import pytest
from step2step.codex import session


MODELS = [{"id": "model-a", "model": "model-a", "displayName": "Model A", "isDefault": True,
           "defaultReasoningEffort": "low", "supportedReasoningEfforts": [{"reasoningEffort": "low"}, {"reasoningEffort": "high"}]},
          {"id": "model-b", "model": "model-b", "displayName": "Model B", "isDefault": False,
           "defaultReasoningEffort": "low", "supportedReasoningEfforts": [{"reasoningEffort": "low"}]}]


class FakeTransport:
    instances = []
    account_type = "chatgpt"

    def __init__(self, **kwargs):
        self.events = queue.Queue()
        self.calls, self.answers = [], []
        self.alive = True
        self.turn_count = 0
        self.on_start = None
        self.model, self.effort = "model-a", "low"
        self.history = []
        self.instances.append(self)

    def emit(self, method, params=None, **extra):
        self.events.put({"method": method, "params": {"threadId": "thread-1", **(params or {})}, **extra})

    def complete(self, turn_id=None, *, text="DONE", status="completed", error=None, kind="agentMessage"):
        tid = turn_id or f"turn-{self.turn_count}"
        self.emit("turn/completed", {"turn": {"id": tid, "status": status, "error": error,
                                             "items": [{"id": tid+"-answer", "type": kind, "text": text}]}})

    def question(self, questions=None, rid=100):
        self.emit("item/tool/requestUserInput", {"turnId": f"turn-{self.turn_count}", "itemId": "q-item",
                  "questions": questions or [{"id": "color", "question": "Which color?", "header": "Color",
                                               "options": [{"label": "Red"}, {"label": "Blue"}]}]}, id=rid)

    def request(self, method, params=None, **kwargs):
        self.calls.append((method, deepcopy(params)))
        if method == "initialize": return {}
        if method == "account/read": return {"account": {"type": self.account_type}}
        if method == "account/rateLimits/read": return {"rateLimits": {"primary": {"usedPercent": 10, "resetsAt": 1234}}}
        if method == "model/list": return {"data": deepcopy(MODELS), "nextCursor": None}
        if method in ("thread/start", "thread/resume"):
            self.model = params.get("model", "model-a")
            self.effort = params.get("config", {}).get("model_reasoning_effort", "low")
            return {"thread": {"id": "thread-1", "status": {"type": "idle"}},
                    "model": self.model, "reasoningEffort": self.effort, "modelProvider": "openai"}
        if method == "thread/turns/list": return {"data": self.history, "nextCursor": None}
        if method == "thread/read": return {"thread": {"model": self.model, "reasoningEffort": self.effort}}
        if method == "turn/start":
            self.turn_count += 1
            self.model, self.effort = params["model"], params["effort"]
            turn = {"id": f"turn-{self.turn_count}", "status": "inProgress", "items": []}
            self.emit("turn/started", {"turn": turn})
            if self.on_start: self.on_start(self, params)
            return {"turn": turn}
        if method == "turn/interrupt":
            self.complete(params["turnId"], status="interrupted")
            return {}
        if method == "thread/backgroundTerminals/clean": return {}
        raise AssertionError(method)

    def notify(self, method, params=None): self.calls.append((method, params))
    def respond(self, rid, result=None, **kwargs): self.answers.append((rid, result, kwargs))
    def is_alive(self): return self.alive
    def close(self, **kwargs): self.alive = False


@pytest.fixture
def make_session(monkeypatch, tmp_path):
    FakeTransport.instances = []
    monkeypatch.setattr(session, "Transport", FakeTransport)
    handles = []
    def make(**kwargs):
        h = session.SessionHandle.start(workdir=tmp_path, **kwargs)
        handles.append(h)
        return h
    yield make
    for h in handles:
        h.stop(force=True)

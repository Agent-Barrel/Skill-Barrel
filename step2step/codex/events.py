"""Codex event reduction, independent of subprocess I/O and Claude screens."""
from __future__ import annotations

from collections import OrderedDict, deque
from copy import deepcopy
from dataclasses import dataclass, field
import time

from ..contracts import MenuOption, PendingInteraction


QUESTION = "item/tool/requestUserInput"
APPROVALS = {"item/commandExecution/requestApproval": "command_approval",
             "item/fileChange/requestApproval": "file_approval"}


@dataclass
class Turn:
    id: str
    prompt: str = ""
    status: str = "inProgress"
    items: dict = field(default_factory=dict)
    error: dict | None = None
    last_progress: float = field(default_factory=time.monotonic)

    def record(self, index=1):
        texts, final, commentary, plans, tools, prompts, calls = [], [], [], [], [], [], []
        for item in self.items.values():
            kind = item.get("type")
            if kind == "agentMessage":
                texts.append(item.get("text", ""))
                if item.get("phase") == "final_answer":
                    final.append(item.get("text", ""))
                elif item.get("phase") == "commentary":
                    commentary.append(item.get("text", ""))
            elif kind == "plan":
                plans.append(item.get("text", ""))
            elif kind == "userMessage":
                prompts.extend(v.get("text", "") for v in item.get("content", [])
                               if v.get("type") == "text")
            elif kind not in ("reasoning", "contextCompaction"):
                tools.append(kind)
                calls.append(deepcopy(item))
        return {"index": index, "turn_id": self.id,
                "prompt": self.prompt or "\n".join(prompts),
                "response": "\n".join(t for t in (final or texts) if t).strip(),
                "commentary": "\n".join(t for t in commentary if t).strip(),
                "plan": "\n".join(t for t in plans if t).strip(),
                "tools": tools, "tool_inputs": calls, "status": self.status,
                "error": deepcopy(self.error)}


class EventState:
    def __init__(self, thread_id):
        self.thread_id = thread_id
        self.turns: dict[str, Turn] = OrderedDict()
        self.requests: dict[str | int, dict] = OrderedDict()
        self.resolved: set[tuple[str, str | int]] = set()
        self.activity = deque(maxlen=2000)
        self.rate_limits = None
        self.token_usage = None
        self.disconnected = None
        self.unsupported = None

    def turn(self, turn_id) -> Turn:
        return self.turns.setdefault(turn_id, Turn(turn_id))

    def load_turn(self, data):
        turn = self.turn(data["id"])
        turn.status = data["status"]
        turn.error = (data.get("error") or turn.error) if turn.status == "failed" else data.get("error")
        for item in data.get("items", []):
            turn.items[item["id"]] = deepcopy(item)
        return turn

    def apply(self, msg):
        method, params = msg.get("method", ""), msg.get("params") or {}
        if method == "transport/closed":
            self.disconnected = params.get("message", "disconnected")
            return
        if method == "account/rateLimits/updated":
            self.rate_limits = deepcopy(params)
            return
        if params.get("threadId") != self.thread_id:
            return
        if method == "thread/tokenUsage/updated":
            self.token_usage = deepcopy(params.get("tokenUsage"))
            return
        if method == "serverRequest/resolved":
            rid = params.get("requestId")
            request = self.requests.pop(rid, None)
            if request:
                self.resolved.add((request["params"]["turnId"], rid))
            return
        turn_id = params.get("turnId") or (params.get("turn") or {}).get("id")
        if not turn_id:
            return
        turn = self.turn(turn_id)
        if "id" in msg:
            rid = msg["id"]
            if (turn_id, rid) not in self.resolved and turn.status == "inProgress":
                self.requests.setdefault(rid, deepcopy(msg))
            return
        if method == "turn/completed":
            self.load_turn(params["turn"])
            for rid, request in list(self.requests.items()):
                if request["params"].get("turnId") == turn_id:
                    self.resolved.add((turn_id, rid))
                    self.requests.pop(rid)
        elif turn.status != "inProgress":
            return  # Late/duplicate events cannot reopen a terminal turn.
        elif method == "turn/started":
            for item in params["turn"].get("items", []):
                turn.items[item["id"]] = deepcopy(item)
        elif method in ("item/started", "item/completed"):
            item = deepcopy(params["item"])
            turn.items[item["id"]] = item
            if method == "item/completed":
                turn.items[item["id"]]["_complete"] = True
        elif method in ("item/agentMessage/delta", "item/plan/delta"):
            item = turn.items.setdefault(params["itemId"], {
                "id": params["itemId"],
                "type": "plan" if method == "item/plan/delta" else "agentMessage", "text": ""})
            if not item.get("_complete"):
                item["text"] = item.get("text", "") + params.get("delta", "")
        elif method == "error" and not params.get("willRetry", False):
            turn.error = deepcopy(params.get("error"))
        # Actual new turn/item progress, not thread heartbeat, resets stall time.
        if method.startswith(("turn/", "item/")):
            turn.last_progress = time.monotonic()
            delta = params.get("delta", "")
            self.activity.append(f"[{turn_id}] {method}" + (f": {delta}" if delta else ""))

    def pending(self, turn_id):
        for rid, request in self.requests.items():
            p, method = request["params"], request["method"]
            if p.get("turnId") != turn_id:
                continue
            questions = deepcopy(p.get("questions", []))
            options = questions[0].get("options") or [] if questions else []
            kind = "ask_user_question" if method == QUESTION else APPROVALS.get(method, "unknown_dialog")
            return PendingInteraction(
                kind=kind, tool_use_id=p.get("itemId"), questions=questions, plan=None,
                menu=[MenuOption(i+1, option["label"], False) for i, option in enumerate(options)],
                screen_tail="", source="app-server", request_id=rid, raw=deepcopy(request))
        return None

    def transcript(self):
        return [turn.record(i) for i, turn in enumerate(self.turns.values(), 1)]

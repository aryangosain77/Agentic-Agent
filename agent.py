"""Agent core: plan -> act (tools) -> observe -> repeat, with guardrails."""
import json
import time
from dataclasses import dataclass, field

from .memory import Memory
from .tools import ToolRegistry, build_registry

SYSTEM_PROMPT = """You are an autonomous agent. Work toward the user's goal.
1. Start with a brief numbered plan.
2. Use tools to act; check each observation before the next step.
3. If a tool errors, adapt instead of repeating the same call.
4. Save durable facts with `remember` when useful.
5. When done, call `finish` with the final answer. Never invent tool results."""


@dataclass
class AgentConfig:
    model: str = "claude-sonnet-5-5"
    max_steps: int = 12
    max_tokens: int = 2000
    workspace: str = "workspace"
    memory_path: str = "memory.json"
    allowed_tools: list[str] | None = None
    trace_path: str | None = "trace.jsonl"


@dataclass
class RunResult:
    answer: str
    steps: int
    finished: bool
    trace: list[dict] = field(default_factory=list)


class Agent:
    def __init__(self, config: AgentConfig | None = None, client=None, registry: ToolRegistry | None = None):
        self.cfg = config or AgentConfig()
        self.memory = Memory(self.cfg.memory_path)
        self.registry = registry or build_registry(self.cfg.workspace, self.memory)
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        self.client = client

    def _log(self, trace: list, event: dict) -> None:
        event["ts"] = time.time()
        trace.append(event)
        if self.cfg.trace_path:
            with open(self.cfg.trace_path, "a") as f:
                f.write(json.dumps(event, default=str) + "\n")

    def run(self, goal: str) -> RunResult:
        trace: list[dict] = []
        recalled = self.memory.recall(goal)
        prompt = goal + ("\n\nRelevant notes from memory:\n- " + "\n- ".join(recalled) if recalled else "")
        messages = [{"role": "user", "content": prompt}]
        tools = self.registry.specs(self.cfg.allowed_tools)
        self._log(trace, {"type": "goal", "goal": goal})

        for step in range(1, self.cfg.max_steps + 1):
            resp = self.client.messages.create(
                model=self.cfg.model, max_tokens=self.cfg.max_tokens,
                system=SYSTEM_PROMPT, tools=tools, messages=messages,
            )
            messages.append({"role": "assistant", "content": resp.content})
            text = "".join(b.text for b in resp.content if b.type == "text")
            if text:
                self._log(trace, {"type": "thought", "step": step, "text": text})

            calls = [b for b in resp.content if b.type == "tool_use"]
            if not calls:  # model answered without tools
                return RunResult(text, step, True, trace)

            results, final = [], None
            for c in calls:
                out = self.registry.call(c.name, c.input, self.cfg.allowed_tools)
                self._log(trace, {"type": "action", "step": step, "tool": c.name, "input": c.input, "output": out})
                results.append({"type": "tool_result", "tool_use_id": c.id, "content": out})
                if c.name == "finish" and not out.startswith("ERROR"):
                    final = out
            if final is not None:
                return RunResult(final, step, True, trace)
            messages.append({"role": "user", "content": results})

        self._log(trace, {"type": "stopped", "reason": "max_steps"})
        return RunResult("Stopped: step limit reached before finishing.", self.cfg.max_steps, False, trace)

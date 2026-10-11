import json
import os
import sys
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agentic_agent import Agent, AgentConfig, Memory
from agentic_agent.tools import build_registry, calculator


def test_calculator():
    assert calculator("17*23 + 2**10") == 1415
    for bad in ["__import__('os')", "2**1000"]:
        try:
            calculator(bad)
            assert False
        except Exception:
            pass


def test_sandbox(tmp_path):
    r = build_registry(str(tmp_path / "ws"), Memory(str(tmp_path / "m.json")))
    assert "wrote" in r.call("write_file", {"path": "a/b.txt", "content": "hi"})
    assert r.call("read_file", {"path": "a/b.txt"}) == "hi"
    assert "escapes" in r.call("read_file", {"path": "../../etc/passwd"})
    assert "blocked" in r.call("http_get", {"url": "http://127.0.0.1/"})
    assert "not available" in r.call("calculator", {"expression": "1"}, allowed=["finish"])


def test_memory(tmp_path):
    p = str(tmp_path / "m.json")
    Memory(p).add("The user's favourite colour is teal")
    assert Memory(p).recall("favourite colour") == ["The user's favourite colour is teal"]


class FakeClient:
    """Scripted LLM: calculate -> write -> finish."""
    def __init__(self):
        self.i = 0
        self.messages = self

    def create(self, **kw):
        script = [
            [NS(type="text", text="Plan: 1) calc 2) write 3) finish"),
             NS(type="tool_use", id="1", name="calculator", input={"expression": "6*7"})],
            [NS(type="tool_use", id="2", name="write_file", input={"path": "r.txt", "content": "42"})],
            [NS(type="tool_use", id="3", name="finish", input={"answer": "42 saved"})],
        ]
        c = script[self.i]
        self.i += 1
        return NS(content=c, stop_reason="tool_use")


def test_agent_loop(tmp_path):
    cfg = AgentConfig(workspace=str(tmp_path / "ws"), memory_path=str(tmp_path / "m.json"),
                      trace_path=str(tmp_path / "t.jsonl"))
    res = Agent(cfg, client=FakeClient()).run("compute 6*7 and save it")
    assert res.finished and res.answer == "42 saved" and res.steps == 3
    assert open(tmp_path / "ws" / "r.txt").read() == "42"
    assert len(open(tmp_path / "t.jsonl").readlines()) == len(res.trace)


def test_step_limit(tmp_path):
    class Loop(FakeClient):
        def create(self, **kw):
            return NS(content=[NS(type="tool_use", id="x", name="calculator", input={"expression": "1+1"})],
                      stop_reason="tool_use")
    cfg = AgentConfig(max_steps=3, workspace=str(tmp_path / "ws"), memory_path=str(tmp_path / "m.json"), trace_path=None)
    res = Agent(cfg, client=Loop()).run("loop")
    assert not res.finished and res.steps == 3


def test_schema_valid():
    import jsonschema
    schema = json.load(open(os.path.join(os.path.dirname(__file__), "..", "schema", "agent_schema.json")))
    jsonschema.validate({"config": {"max_steps": 5}}, schema)

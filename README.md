# Agentic Agent

A small, readable autonomous AI agent: it takes a goal, **plans**, **acts** through tools, **observes** the results, and loops until it calls `finish` — with memory, a full trace log, and safety guardrails.

## Features
- Plan → Act → Observe loop on the Claude API (tool use)
- Tools: calculator, sandboxed file I/O, public `http_get`, `remember`/`recall`, `finish`
- Persistent long-term memory (`memory.json`)
- JSONL trace of every thought and action
- Guardrails: step cap, path sandbox, SSRF block, AST-only math, tool allow-list
- Offline tests with a scripted fake LLM (no API key needed)

## Quick start
```bash
git clone https://github.com/<your-username>/agentic-agent.git
cd agentic-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key
python main.py "Compute 17*23 + 2**10, write it to result.txt, then read it back."
pytest -q
```

## Schema & architecture
- `schema/agent_schema.json` – JSON Schema for config, tool specs, memory notes, trace events
- `schema/architecture.md` – Mermaid architecture diagram + guardrail table

## Use as a library
```python
from agentic_agent import Agent, AgentConfig
agent = Agent(AgentConfig(max_steps=8, allowed_tools=["calculator", "write_file", "finish"]))
print(agent.run("What is 12% of 8450? Save it to tax.txt").answer)
```

## Add a tool
```python
registry.register("shout", "Uppercase text.", {"text": {"type": "string"}}, ["text"], lambda text: text.upper())
```
Pass `registry=` to `Agent(...)`.

## Layout
```
agentic_agent/  agent.py  tools.py  memory.py
schema/         agent_schema.json  architecture.md
tests/          test_agent.py
main.py
```

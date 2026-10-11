import argparse
from agentic_agent import Agent, AgentConfig

p = argparse.ArgumentParser(description="Run the Agentic Agent")
p.add_argument("goal")
p.add_argument("--model", default="claude-sonnet-5-5")
p.add_argument("--max-steps", type=int, default=12)
a = p.parse_args()

result = Agent(AgentConfig(model=a.model, max_steps=a.max_steps)).run(a.goal)
print(f"\n[{'done' if result.finished else 'incomplete'} in {result.steps} steps]\n{result.answer}")

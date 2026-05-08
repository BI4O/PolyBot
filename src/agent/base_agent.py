"""Base agent using ChatOpenAI with DeepSeek."""

from deepagents import create_deep_agent

from src.conf.agent_backend import AGENT_BACKEND
from src.conf.agent_models import DEEPSEEK_V4_FLASH
from src.conf.agent_prompts import HELLO_SYSTEM_PROMPT
from src.conf.agent_skills import AGENT_SKILL_SOURCES
from src.conf.agent_tools import AGENT_TOOLS

agent = create_deep_agent(
    model=DEEPSEEK_V4_FLASH,
    tools=AGENT_TOOLS,
    system_prompt=HELLO_SYSTEM_PROMPT,
    backend=AGENT_BACKEND,
    skills=AGENT_SKILL_SOURCES,
)

if __name__ == "__main__":
    # uv run -m src.agent.base_agent
    state = agent.invoke({"messages": [{"role": "user", "content": "你有什么技能"}]})
    for m in state["messages"]:
        m.pretty_print()

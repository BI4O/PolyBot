"""DeepSeek-native agent using ChatDeepSeek instead of ChatOpenAI."""

from langchain_deepseek import ChatDeepSeek

from deepagents import create_deep_agent

from src.conf.agent_backend import AGENT_BACKEND
from src.conf.agent_prompts import HELLO_SYSTEM_PROMPT
from src.conf.agent_skills import AGENT_SKILL_SOURCES
from src.conf.agent_tools import AGENT_TOOLS

# Must import agent_models BEFORE any model is created, to apply monkey-patch
import src.conf.agent_models  # noqa: F401

model = ChatDeepSeek(
    model="deepseek-v4-flash",
    timeout=20,
    max_retries=2,
)

agent = create_deep_agent(
    model=model,
    tools=AGENT_TOOLS,
    system_prompt=HELLO_SYSTEM_PROMPT,
    backend=AGENT_BACKEND,
    skills=AGENT_SKILL_SOURCES,
)

if __name__ == "__main__":
    # uv run -m src.agent.ds_agent
    state = agent.invoke({"messages": [{"role": "user", "content": "你有什么技能"}]})
    for m in state["messages"]:
        m.pretty_print()

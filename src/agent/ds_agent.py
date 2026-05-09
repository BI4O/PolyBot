"""DeepSeek-native agent using ChatDeepSeek instead of ChatOpenAI."""

from deepagents import create_deep_agent

from src.conf.agent_backend import AGENT_BACKEND
from src.conf.agent_models import DEEPSEEK_V4_FLASH
from src.conf.agent_prompts import HELLO_SYSTEM_PROMPT
from src.conf.agent_skills import AGENT_SKILL_SOURCES
from src.conf.agent_tools import AGENT_TOOLS
from src.middlewares import POLYMARKET_RETRY

agent = create_deep_agent(
    model=DEEPSEEK_V4_FLASH,
    tools=AGENT_TOOLS,
    system_prompt=HELLO_SYSTEM_PROMPT,
    backend=AGENT_BACKEND,
    skills=AGENT_SKILL_SOURCES,
    middleware=[POLYMARKET_RETRY],
)

if __name__ == "__main__":
    # uv run -m src.agent.ds_agent
    state = agent.invoke(
        {"messages": [{"role": "user", "content": "有哪些热门的政治类的市场"}]}
    )
    for m in state["messages"]:
        m.pretty_print()

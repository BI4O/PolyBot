"""Test agent using ChatOpenAI with DeepSeek."""

from deepagents import create_deep_agent

from src.conf.agent_backend import agent_backend
from src.conf.agent_models import DEEPSEEK_V4_FLASH
from src.conf.agent_prompts import HELLO_SYSTEM_PROMPT
from src.conf.agent_tools import HELLO_TOOLS

agent = create_deep_agent(
    model=DEEPSEEK_V4_FLASH,
    tools=HELLO_TOOLS,
    system_prompt=HELLO_SYSTEM_PROMPT,
    backend=agent_backend,
)

if __name__ == "__main__":
    state = agent.invoke(
        {"messages": [{"role": "user", "content": "你有什么技能，你用ls看看"}]}
    )
    for m in state["messages"]:
        m.pretty_print()

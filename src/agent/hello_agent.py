from deepagents import create_deep_agent

from src.conf.agent_models import DEEPSEEK_V4_FLASH
from src.conf.agent_prompts import HELLO_SYSTEM_PROMPT
from src.conf.agent_tools import HELLO_TOOLS

agent = create_deep_agent(
    model=DEEPSEEK_V4_FLASH,
    tools=HELLO_TOOLS,
    system_prompt=HELLO_SYSTEM_PROMPT,
)

if __name__ == "__main__":
    state = agent.invoke(
        {"messages": [{"role": "user", "content": "hello, what model are u?"}]}
    )
    for m in state["messages"]:
        m.pretty_print()

"""TokenAge/OpenAI-compatible agent.

This keeps the existing DeepSeek agent untouched.
Controlled by:
- OPENAI_API_KEY
- OPENAI_BASE_URL
- OPENAI_MODEL
"""

import os

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from src.conf.agent_backend import AGENT_BACKEND
from src.conf.agent_prompts import HELLO_SYSTEM_PROMPT
from src.conf.agent_skills import AGENT_SKILL_SOURCES
from src.conf.agent_tools import AGENT_TOOLS
from src.middlewares import POLYMARKET_RETRY


_api_key = os.getenv("OPENAI_API_KEY")

TOKENAGE_MODEL = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
    api_key=SecretStr(_api_key) if _api_key else None,
    base_url=os.getenv("OPENAI_BASE_URL", "https://www.tokenage.ai/v1"),
    timeout=60,
    max_retries=2,
)

agent = create_deep_agent(
    model=TOKENAGE_MODEL,
    tools=AGENT_TOOLS,
    system_prompt=HELLO_SYSTEM_PROMPT,
    backend=AGENT_BACKEND,
    skills=AGENT_SKILL_SOURCES,
    middleware=[POLYMARKET_RETRY],
)

if __name__ == "__main__":
    import asyncio

    async def main():
        state = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "你是什么模型"}]}
        )
        for m in state["messages"]:
            m.pretty_print()

    asyncio.run(main())

# pip install -qU deepagents langchain-openai
import os

from deepagents import create_deep_agent
from dotenv import load_dotenv
from typing import Literal

from langchain_core.messages import AIMessage, BaseMessage
from langchain_deepseek import ChatDeepSeek
from langchain_openai.chat_models import base as openai_base

load_dotenv()

# Monkey patch: pass through reasoning_content when serializing AIMessage
# (DeepSeek reasoning models require it on multi-turn)
_original_convert = openai_base._convert_message_to_dict


def _patched_convert(message: BaseMessage, api: Literal["chat/completions", "responses"] = "chat/completions") -> dict:
    result = _original_convert(message, api)
    if isinstance(message, AIMessage) and "reasoning_content" in message.additional_kwargs:
        result["reasoning_content"] = message.additional_kwargs["reasoning_content"]
    return result


openai_base._convert_message_to_dict = _patched_convert


def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"


agent = create_deep_agent(
    model=ChatDeepSeek(model="deepseek-v4-flash"),
    tools=[get_weather],
    system_prompt="You are a helpful assistant",
)

# Run the agent
state = agent.invoke({"messages": [{"role": "user", "content": "sf天气咋样"}]})

for m in state["messages"]:
    m.pretty_print()

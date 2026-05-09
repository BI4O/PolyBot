"""Model definitions for Deep Agent.

Monkey-patches langchain_openai to preserve `reasoning_content`
(required by DeepSeek reasoning models on multi-turn calls).
"""

import typing

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage
from langchain_deepseek import ChatDeepSeek
from langchain_openai.chat_models import base as _lc_openai_base  # monkey-patch target

load_dotenv()

# ---------------------------------------------------------------------------
# Monkey-patch: extract reasoning_content from API response into
# additional_kwargs (inbound), then forward it on subsequent API calls
# (outbound). DeepSeek requires reasoning_content to be passed back.
# ---------------------------------------------------------------------------

# --- inbound: _convert_dict_to_message -----------------------------------
_orig_convert_dict = _lc_openai_base._convert_dict_to_message


def _patched_convert_dict_to_message(
    _dict: typing.Mapping[str, typing.Any],
) -> typing.Any:
    msg = _orig_convert_dict(_dict)
    if isinstance(msg, AIMessage) and (rc := _dict.get("reasoning_content")):
        msg.additional_kwargs["reasoning_content"] = rc
    return msg


_lc_openai_base._convert_dict_to_message = _patched_convert_dict_to_message

# --- outbound: _convert_message_to_dict ----------------------------------
_orig_convert_msg = _lc_openai_base._convert_message_to_dict


def _patched_convert_message_to_dict(
    message: typing.Any,
    api: typing.Literal["chat/completions", "responses"] = "chat/completions",
) -> dict:
    msg_dict = _orig_convert_msg(message, api)
    if (
        hasattr(message, "additional_kwargs")
        and "reasoning_content" in message.additional_kwargs
    ):
        msg_dict["reasoning_content"] = message.additional_kwargs["reasoning_content"]
    return msg_dict


_lc_openai_base._convert_message_to_dict = _patched_convert_message_to_dict

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

# ChatOpenAI-based (openai: prefix via OPENAI_BASE_URL / .env)
OPENAI_DEEPSEEK_V4_FLASH = init_chat_model(
    model="openai:deepseek-v4-flash",
    timeout=20,
    max_retries=2,
)

# ChatDeepSeek native adapter (reads DEEPSEEK_API_KEY from env)
DEEPSEEK_V4_FLASH = ChatDeepSeek(
    model="deepseek-v4-flash",
    timeout=20,
    max_retries=2,
)

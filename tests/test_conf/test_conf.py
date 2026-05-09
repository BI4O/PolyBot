"""Tests for config modules under src/conf/."""


class TestAgentBackend:
    def test_backend_imports(self):
        from src.conf.agent_backend import AGENT_BACKEND

        assert AGENT_BACKEND is not None

    def test_composite_backend_has_skills_route(self):
        from src.conf.agent_backend import AGENT_BACKEND

        routes = AGENT_BACKEND.routes
        assert "/skills/" in routes

    def test_skills_backend_is_filesystem(self):
        from src.conf.agent_backend import AGENT_BACKEND
        from deepagents.backends import FilesystemBackend

        assert isinstance(AGENT_BACKEND.routes["/skills/"], FilesystemBackend)

    def test_skills_backend_virtual_mode(self):
        from src.conf.agent_backend import AGENT_BACKEND

        fb = AGENT_BACKEND.routes["/skills/"]
        assert fb.virtual_mode is True


class TestAgentModels:
    def test_model_config(self):
        from src.conf.agent_models import OPENAI_DEEPSEEK_V4_FLASH

        assert OPENAI_DEEPSEEK_V4_FLASH.model == "deepseek-v4-flash"
        assert OPENAI_DEEPSEEK_V4_FLASH.request_timeout == 20.0
        assert OPENAI_DEEPSEEK_V4_FLASH.max_retries == 2

    def test_inbound_patch_applied(self):
        """_convert_dict_to_message should be our patched version."""
        from langchain_openai.chat_models import base as lc_base
        import src.conf.agent_models  # noqa: F401 — ensures patch is applied

        from langchain_core.messages import AIMessage

        msg = lc_base._convert_dict_to_message(
            {"content": "hi", "role": "assistant", "reasoning_content": "thinking"}
        )
        assert isinstance(msg, AIMessage)
        assert msg.additional_kwargs.get("reasoning_content") == "thinking"

    def test_outbound_patch_applied(self):
        """_convert_message_to_dict should forward reasoning_content."""
        from langchain_openai.chat_models import base as lc_base
        import src.conf.agent_models  # noqa: F401

        from langchain_core.messages import AIMessage

        msg = AIMessage(content="hi", additional_kwargs={"reasoning_content": "thinking"})
        d = lc_base._convert_message_to_dict(msg)
        assert d.get("reasoning_content") == "thinking"


class TestAgentPrompts:
    def test_system_prompt_exists(self):
        from src.conf.agent_prompts import HELLO_SYSTEM_PROMPT

        assert isinstance(HELLO_SYSTEM_PROMPT, str)
        assert len(HELLO_SYSTEM_PROMPT) > 0


class TestAgentTools:
    def test_tool_list_is_list(self):
        from src.conf.agent_tools import AGENT_TOOLS

        assert isinstance(AGENT_TOOLS, list)

    def test_agent_tools_has_coin_tools(self):
        from src.conf.agent_tools import AGENT_TOOLS

        names = {t.name for t in AGENT_TOOLS}
        assert "search_coins" in names
        assert "search_events" in names
        assert "fetch_latest_news" in names

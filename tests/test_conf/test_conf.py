"""Tests for config modules under src/conf/."""


class TestAgentBackend:
    def test_backend_imports(self):
        from src.conf.agent_backend import agent_backend

        assert agent_backend is not None

    def test_composite_backend_has_skills_route(self):
        from src.conf.agent_backend import agent_backend

        routes = agent_backend.routes
        assert "/skills/" in routes

    def test_skills_backend_is_filesystem(self):
        from src.conf.agent_backend import agent_backend
        from deepagents.backends import FilesystemBackend

        assert isinstance(agent_backend.routes["/skills/"], FilesystemBackend)

    def test_skills_backend_virtual_mode(self):
        from src.conf.agent_backend import agent_backend

        fb = agent_backend.routes["/skills/"]
        assert fb.virtual_mode is True


class TestAgentModels:
    def test_model_config(self):
        from src.conf.agent_models import DEEPSEEK_V4_FLASH

        assert DEEPSEEK_V4_FLASH.model == "deepseek-v4-flash"
        assert DEEPSEEK_V4_FLASH.request_timeout == 20.0
        assert DEEPSEEK_V4_FLASH.max_retries == 2

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
        from src.conf.agent_tools import HELLO_TOOLS

        assert isinstance(HELLO_TOOLS, list)

    def test_hello_tools_contains_get_weather(self):
        from src.conf.agent_tools import HELLO_TOOLS

        names = {t.name for t in HELLO_TOOLS}
        assert "get_weather" in names

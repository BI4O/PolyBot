"""Tests for hello_agent configuration and invocation."""


def test_agent_imports():
    """Agent module loads without errors."""
    import src.agent.hello_agent  # noqa: F401


def test_agent_model_config():
    """Model has expected configuration."""
    from src.conf.agent_models import DEEPSEEK_V4_FLASH

    assert DEEPSEEK_V4_FLASH.model == "deepseek-v4-flash"
    assert DEEPSEEK_V4_FLASH.default_request_timeout == 20
    assert DEEPSEEK_V4_FLASH.max_retries == 2


def test_tools_are_registered():
    """Tool list contains expected tools."""
    from src.conf.agent_tools import HELLO_TOOLS

    assert len(HELLO_TOOLS) == 1
    assert HELLO_TOOLS[0].name == "get_weather"
    assert "weather" in HELLO_TOOLS[0].description.lower()

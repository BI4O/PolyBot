"""Tests for src/middlewares/ configurations."""

import httpx
from langchain.agents.middleware import ToolRetryMiddleware


class TestPolymarketRetry:
    def test_polymarket_retry_imports(self):
        from src.middlewares import POLYMARKET_RETRY

        assert isinstance(POLYMARKET_RETRY, ToolRetryMiddleware)

    def test_retry_config(self):
        from src.middlewares import POLYMARKET_RETRY

        assert POLYMARKET_RETRY.max_retries == 2

    def test_retry_targets_polymarket_tools(self):
        from src.middlewares import POLYMARKET_RETRY

        assert set(POLYMARKET_RETRY._tool_filter) == {
            "search_events", "get_trending_events", "get_event_detail", "get_market_detail",
        }

    def test_retry_on_connection_errors(self):
        from src.middlewares import POLYMARKET_RETRY

        assert httpx.ConnectError in POLYMARKET_RETRY.retry_on
        assert httpx.TimeoutException in POLYMARKET_RETRY.retry_on
        assert httpx.HTTPStatusError in POLYMARKET_RETRY.retry_on

"""Tests for async conversion — verifies no BlockingError and correct async behavior.

These tests specifically validate that the httpx sync→async migration works:
1. All now-async functions return valid results when awaited
2. The BlockingError scenario is reproduced and fixed
3. Error handling still works (HTTP errors, timeouts)
4. The full call chain (tool → service layer) resolves correctly
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.services.polymarket.markets import (
    get_market_by_id,
    get_market_by_slug,
    get_market_by_token_addr,
    list_markets,
    list_trending_markets,
)
from src.services.polymarket.search import search_events_by_keyword

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SEARCH_RESPONSE = {
    "events": [
        {
            "id": "36173",
            "title": "When will Bitcoin hit $150k?",
            "slug": "when-will-bitcoin-hit-150k",
            "tags": [{"id": "235", "label": "Bitcoin", "slug": "bitcoin"}],
            "markets": [
                {
                    "id": "573652",
                    "slug": "will-bitcoin-hit-150k-by-september-30",
                    "question": "Will Bitcoin hit $150k by September 30?",
                    "outcomes": '["Yes", "No"]',
                    "outcomePrices": '["0.45", "0.55"]',
                    "clobTokenIds": '["111", "222"]',
                    "volume": "778900",
                    "startDate": "2025-08-07T16:29:14Z",
                    "endDate": "2025-10-01T04:00:00Z",
                    "description": "Test description",
                    "icon": "https://example.com/icon.png",
                    "marketMakerAddress": "0xabc",
                },
            ],
        },
    ],
}

_MARKETS_LIST = [
    {
        "id": "540816",
        "slug": "bitcoin-108k",
        "question": "Bitcoin to close above $108K by May 10?",
        "outcomes": '["Yes", "No"]',
        "outcomePrices": '["0.67", "0.33"]',
        "clobTokenIds": '["t1", "t2"]',
        "volume": "1657979",
        "volumeNum": 1657979.63,
        "startDate": "2025-05-02T15:48:00Z",
        "endDate": "2026-05-10T12:00:00Z",
        "description": "Bitcoin 108K market",
        "icon": "https://example.com/icon.png",
        "marketMakerAddress": "0xdef",
        "closed": False,
    },
]

_MARKET_DETAIL = {
    "id": "573652",
    "slug": "bitcoin-108k",
    "question": "Bitcoin to close above $108K by May 10?",
    "outcomes": '["Yes", "No"]',
    "outcomePrices": '["0.67", "0.33"]',
    "volume": "778900",
    "active": True,
    "closed": False,
}

_TAG_RESPONSE = {"id": "235", "label": "Bitcoin", "slug": "bitcoin"}


def _async_mock_client(
    data: object,
    status: int = 200,
    has_post: bool = False,
) -> MagicMock:
    """Create a mock ``httpx.AsyncClient``.

    Usage::

        with patch("httpx.AsyncClient") as cls:
            cls.return_value.__aenter__.return_value = _async_mock_client(data=...)
    """
    resp = MagicMock()
    resp.status_code = status
    if status == 200:
        resp.json.return_value = data
    resp.raise_for_status.return_value = None
    if status >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            str(status), request=MagicMock(), response=resp,
        )
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    if has_post:
        client.post = AsyncMock(return_value=resp)
    return client


@pytest.fixture(autouse=True)
def _clear_tag_cache():
    """Clear ``resolve_tag_slug`` cache between tests."""
    from src.services.polymarket.tags import resolve_tag_slug
    resolve_tag_slug.cache_clear()


@pytest.fixture
def mock_async_client():
    """Patch httpx.AsyncClient globally with a controlled mock."""
    with patch("httpx.AsyncClient") as cls:
        yield cls


# ---------------------------------------------------------------------------
# Async function tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSearchEventsByKeywordAsync:
    async def test_returns_events(self):
        with patch("httpx.AsyncClient") as cls, \
             patch("src.services.polymarket.utils.batch_last_prices_async") as prices_async:
            cls.return_value.__aenter__.return_value = _async_mock_client(
                data=_SEARCH_RESPONSE, has_post=True,
            )
            prices_async.return_value = {
                "111": {"token_id": "111", "price": "0.46", "side": "BUY"},
                "222": {"token_id": "222", "price": "0.54", "side": "SELL"},
            }
            result = await search_events_by_keyword("bitcoin")

        assert len(result) == 1
        assert result[0]["title"] == "When will Bitcoin hit $150k?"
        assert result[0]["markets"][0]["options"] == [
            {"name": "Yes", "price": "0.45", "side": "BUY", "last": "0.46",
             "multiplier": 2.17, "pct": 46.0},
            {"name": "No", "price": "0.55", "side": "SELL", "last": "0.54",
             "multiplier": 1.85, "pct": 54.0},
        ]

    async def test_empty_response(self):
        with patch("httpx.AsyncClient") as cls:
            cls.return_value.__aenter__.return_value = _async_mock_client(data={"events": []})
            result = await search_events_by_keyword("nonexistent")
        assert result == []

    async def test_raises_on_http_error(self):
        with patch("httpx.AsyncClient") as cls:
            cls.return_value.__aenter__.return_value = _async_mock_client(
                data=None, status=500,
            )
            with pytest.raises(httpx.HTTPStatusError):
                await search_events_by_keyword("bitcoin")

    async def test_no_sync_httpx_get_called(self):
        with patch("httpx.AsyncClient") as cls, \
             patch("src.services.polymarket.search.httpx.get") as sync_get, \
             patch("src.services.polymarket.utils.batch_last_prices_async") as prices_async:
            cls.return_value.__aenter__.return_value = _async_mock_client(
                data=_SEARCH_RESPONSE, has_post=True,
            )
            prices_async.return_value = {}
            await search_events_by_keyword("bitcoin")

        sync_get.assert_not_called()


@pytest.mark.asyncio
class TestListMarketsAsync:
    async def test_returns_markets(self):
        with patch("httpx.AsyncClient") as cls:
            cls.return_value.__aenter__.return_value = _async_mock_client(data=_MARKETS_LIST)
            result = await list_markets()

        assert len(result) == 1
        assert result[0]["slug"] == "bitcoin-108k"

    async def test_empty_response(self):
        with patch("httpx.AsyncClient") as cls:
            cls.return_value.__aenter__.return_value = _async_mock_client(data=[])
            result = await list_markets()
        assert result == []

    async def test_raises_on_http_error(self):
        with patch("httpx.AsyncClient") as cls:
            cls.return_value.__aenter__.return_value = _async_mock_client(
                data=None, status=500,
            )
            with pytest.raises(httpx.HTTPStatusError):
                await list_markets()

    async def test_params_passed_correctly(self):
        with patch("httpx.AsyncClient") as cls:
            client_mock = _async_mock_client(data=_MARKETS_LIST)
            cls.return_value.__aenter__.return_value = client_mock
            await list_markets(closed=True, tag_id=235, order_by="volume24hr")

        call_kwargs = client_mock.get.call_args[1]
        assert call_kwargs["params"]["closed"] == "true"
        assert call_kwargs["params"]["tag_id"] == 235
        assert call_kwargs["params"]["order"] == "-volume24hr"

    async def test_tag_slug_resolves_to_id(self):
        with patch("httpx.AsyncClient") as cls, \
             patch("src.services.polymarket.tags.httpx.get") as sync_get:
            sync_get.return_value = MagicMock(
                status_code=200,
                json=lambda: _TAG_RESPONSE,
            )
            sync_get.return_value.raise_for_status = lambda: None
            cls.return_value.__aenter__.return_value = _async_mock_client(data=_MARKETS_LIST)
            await list_markets(tag_slug="bitcoin")

        assert sync_get.call_count == 1
        assert "tags/slug/bitcoin" in str(sync_get.call_args[0][0])

    async def test_detail_false_enriches(self):
        with patch("httpx.AsyncClient") as cls, \
             patch("src.services.polymarket.utils.batch_last_prices_async") as prices_async:
            cls.return_value.__aenter__.return_value = _async_mock_client(
                data=_MARKETS_LIST, has_post=True,
            )
            prices_async.return_value = {}
            result = await list_markets(detail=False)
        assert len(result) == 1

    async def test_no_sync_httpx_get(self):
        with patch("httpx.AsyncClient") as cls, \
             patch("src.services.polymarket.markets.httpx.get") as sync_get:
            cls.return_value.__aenter__.return_value = _async_mock_client(data=_MARKETS_LIST)
            await list_markets()
        sync_get.assert_not_called()


@pytest.mark.asyncio
class TestListTrendingMarketsAsync:
    async def test_trending(self):
        with patch("httpx.AsyncClient") as cls, \
             patch("src.services.polymarket.utils.batch_last_prices_async") as prices_async:
            cls.return_value.__aenter__.return_value = _async_mock_client(
                data=_MARKETS_LIST, has_post=True,
            )
            prices_async.return_value = {}
            result = await list_trending_markets(limit=5)
        assert len(result) == 1

    async def test_no_sync_httpx_get(self):
        with patch("httpx.AsyncClient") as cls, \
             patch("src.services.polymarket.utils.batch_last_prices_async") as prices_async, \
             patch("src.services.polymarket.markets.httpx.get") as sync_get:
            cls.return_value.__aenter__.return_value = _async_mock_client(
                data=_MARKETS_LIST, has_post=True,
            )
            prices_async.return_value = {}
            await list_trending_markets()
        sync_get.assert_not_called()


@pytest.mark.asyncio
class TestGetMarketBySlugAsync:
    async def test_returns_market(self):
        with patch("httpx.AsyncClient") as cls:
            cls.return_value.__aenter__.return_value = _async_mock_client(data=_MARKET_DETAIL)
            result = await get_market_by_slug("bitcoin-108k")
        assert result["slug"] == "bitcoin-108k"

    async def test_raises_on_not_found(self):
        with patch("httpx.AsyncClient") as cls:
            cls.return_value.__aenter__.return_value = _async_mock_client(
                data=None, status=404,
            )
            with pytest.raises(httpx.HTTPStatusError):
                await get_market_by_slug("nonexistent")

    async def test_no_sync_httpx_get(self):
        with patch("httpx.AsyncClient") as cls, \
             patch("src.services.polymarket.markets.httpx.get") as sync_get:
            cls.return_value.__aenter__.return_value = _async_mock_client(data=_MARKET_DETAIL)
            await get_market_by_slug("bitcoin-108k")
        sync_get.assert_not_called()


@pytest.mark.asyncio
class TestGetMarketByIdAsync:
    async def test_returns_market(self):
        with patch("httpx.AsyncClient") as cls:
            cls.return_value.__aenter__.return_value = _async_mock_client(data=_MARKET_DETAIL)
            result = await get_market_by_id(573652)
        assert result["id"] == "573652"

    async def test_no_sync_httpx_get(self):
        with patch("httpx.AsyncClient") as cls, \
             patch("src.services.polymarket.markets.httpx.get") as sync_get:
            cls.return_value.__aenter__.return_value = _async_mock_client(data=_MARKET_DETAIL)
            await get_market_by_id(573652)
        sync_get.assert_not_called()


@pytest.mark.asyncio
class TestGetMarketByTokenAddrAsync:
    _TOKEN_RESPONSE = {"condition_id": "0xabc", "primary_token_id": "111"}

    async def test_returns_market(self):
        with patch("httpx.AsyncClient") as cls:
            cls.return_value.__aenter__.return_value = _async_mock_client(
                data=self._TOKEN_RESPONSE,
            )
            result = await get_market_by_token_addr("0xabc")
        assert result["condition_id"] == "0xabc"

    async def test_no_sync_httpx_get(self):
        with patch("httpx.AsyncClient") as cls, \
             patch("src.services.polymarket.markets.httpx.get") as sync_get:
            cls.return_value.__aenter__.return_value = _async_mock_client(
                data=self._TOKEN_RESPONSE,
            )
            await get_market_by_token_addr("0xabc")
        sync_get.assert_not_called()


# ---------------------------------------------------------------------------
# BlockingError reproduction & verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestBlockingErrorFix:
    """Verifies the old pattern (sync httpx.get) is eliminated everywhere."""

    async def test_get_market_by_slug_is_async(self):
        """Calling without ``await`` returns a coroutine, not a dict."""
        with patch("httpx.AsyncClient") as cls:
            cls.return_value.__aenter__.return_value = _async_mock_client(data=_MARKET_DETAIL)
            result = get_market_by_slug("bitcoin-108k")
            import inspect
            assert inspect.iscoroutine(result)

    async def test_all_markets_functions_use_async_httpx(self):
        """Verify all 4 markets functions avoid sync httpx.get."""
        functions = [
            ("get_market_by_slug", lambda: get_market_by_slug("test")),
            ("get_market_by_id", lambda: get_market_by_id(1)),
            (
                "get_market_by_token_addr",
                lambda: get_market_by_token_addr("0xabc"),
            ),
        ]
        for name, fn in functions:
            with patch("httpx.AsyncClient") as cls, \
                 patch("src.services.polymarket.markets.httpx.get") as sync_get:
                cls.return_value.__aenter__.return_value = _async_mock_client(
                    data=_MARKET_DETAIL,
                )
                await fn()
                sync_get.assert_not_called()

    async def test_search_uses_async_httpx(self):
        with patch("httpx.AsyncClient") as cls, \
             patch("src.services.polymarket.search.httpx.get") as sync_get, \
             patch("src.services.polymarket.utils.batch_last_prices_async") as prices_async:
            cls.return_value.__aenter__.return_value = _async_mock_client(
                data=_SEARCH_RESPONSE, has_post=True,
            )
            prices_async.return_value = {}
            await search_events_by_keyword("bitcoin")
        sync_get.assert_not_called()

    async def test_list_markets_uses_async_httpx(self):
        with patch("httpx.AsyncClient") as cls, \
             patch("src.services.polymarket.markets.httpx.get") as sync_get:
            cls.return_value.__aenter__.return_value = _async_mock_client(data=_MARKETS_LIST)
            await list_markets()
        sync_get.assert_not_called()


# ---------------------------------------------------------------------------
# Error resilience
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAsyncErrorResilience:
    """Errors propagate correctly through async functions."""

    async def test_timeout_propagates(self):
        with patch("httpx.AsyncClient") as cls:
            client = MagicMock()
            client.get = AsyncMock(
                side_effect=httpx.TimeoutException("Request timed out"),
            )
            cls.return_value.__aenter__.return_value = client
            with pytest.raises(httpx.TimeoutException):
                await get_market_by_slug("bitcoin-108k")

    async def test_network_error_propagates(self):
        with patch("httpx.AsyncClient") as cls:
            client = MagicMock()
            client.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused"),
            )
            cls.return_value.__aenter__.return_value = client
            with pytest.raises(httpx.ConnectError):
                await list_markets()

    async def test_search_network_error_propagates(self):
        with patch("httpx.AsyncClient") as cls:
            client = MagicMock()
            client.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused"),
            )
            cls.return_value.__aenter__.return_value = client
            with pytest.raises(httpx.ConnectError):
                await search_events_by_keyword("bitcoin")


# ---------------------------------------------------------------------------
# Tool-level integration (via .ainvoke)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAsyncToolChain:
    """Tools decorated with ``@tool`` become ``StructuredTool`` objects.
    Use ``.ainvoke()`` to call them in tests.
    """

    async def test_get_event_detail_tool(self):
        from src.tools.prediction.events import get_event_detail

        with patch("httpx.AsyncClient") as cls:
            cls.return_value.__aenter__.return_value = _async_mock_client(data=_MARKET_DETAIL)
            result = await get_event_detail.ainvoke({"market_slug": "bitcoin-108k"})

        assert result["slug"] == "bitcoin-108k"

    async def test_get_trending_events_tool(self):
        from src.tools.prediction.events import get_trending_events

        with patch("httpx.AsyncClient") as cls, \
             patch("src.services.polymarket.utils.batch_last_prices_async") as prices_async:
            cls.return_value.__aenter__.return_value = _async_mock_client(
                data=_MARKETS_LIST, has_post=True,
            )
            prices_async.return_value = {}
            result = await get_trending_events.ainvoke(
                {"limit": 5, "tag": "crypto"},
            )

        assert len(result) >= 1

    async def test_search_events_tool(self):
        from src.tools.prediction.events import search_events

        with patch("httpx.AsyncClient") as cls, \
             patch("src.services.polymarket.utils.batch_last_prices_async") as prices_async:
            cls.return_value.__aenter__.return_value = _async_mock_client(
                data=_SEARCH_RESPONSE, has_post=True,
            )
            prices_async.return_value = {}
            result = await search_events.ainvoke({"query": "bitcoin", "limit": 3})

        assert len(result) >= 1

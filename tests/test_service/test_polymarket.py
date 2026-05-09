"""Tests for Polymarket search service."""

import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.services.polymarket.search import search_events_by_keyword
from src.services.polymarket.markets import (
    get_market_by_id,
    get_market_by_slug,
    get_market_by_token_addr,
    list_markets,
    list_trending_markets,
)
from src.services.polymarket.events import list_trending_events
from src.services.polymarket.tags import get_tag_by_slug, list_tags, resolve_tag_slug
from src.services.polymarket.utils import (
    batch_last_prices as _batch_last_prices,
    enrich_markets as _enrich_markets,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SEARCH_RESPONSE = {
    "events": [
        {
            "id": "36173",
            "title": "When will Bitcoin hit $150k?",
            "slug": "when-will-bitcoin-hit-150k",
            "tags": [
                {"id": "235", "label": "Bitcoin", "slug": "bitcoin"},
                {"id": "21", "label": "Crypto", "slug": "crypto"},
            ],
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

_SEARCH_SINGLE_EVENT = {
    "events": [
        {
            "id": "1",
            "title": "Single Event",
            "slug": "single",
            "tags": [],
            "markets": [
                {
                    "id": "100",
                    "slug": "market-100",
                    "question": "Market 100?",
                    "outcomes": '["Yes", "No"]',
                    "outcomePrices": '["0.5", "0.5"]',
                    "clobTokenIds": '["a1", "b1"]',
                    "volume": "1000",
                    "marketMakerAddress": "0x1",
                },
            ],
        },
    ],
}

_MARKETS_LIST = [
    {
        "id": "540816",
        "slug": "russia-ukraine-ceasefire-before-gta-vi",
        "question": "Russia-Ukraine Ceasefire before GTA VI?",
        "outcomes": '["Yes", "No"]',
        "outcomePrices": '["0.555", "0.445"]',
        "clobTokenIds": '["t1", "t2"]',
        "volume": "1657979",
        "volumeNum": 1657979.63,
        "startDate": "2025-05-02T15:48:00Z",
        "endDate": "2026-07-31T12:00:00Z",
        "description": "Some description",
        "icon": "https://example.com/icon.png",
        "marketMakerAddress": "0xdef",
        "closed": False,
        "active": True,
    },
    {
        "id": "540817",
        "slug": "new-rihanna-album-before-gta-vi",
        "question": "New Rihanna Album before GTA VI?",
        "outcomes": '["Yes", "No"]',
        "outcomePrices": '["0.525", "0.475"]',
        "clobTokenIds": '["t3", "t4"]',
        "volume": "706069",
        "volumeNum": 706069.17,
        "startDate": "2025-05-02T15:48:00Z",
        "endDate": "2026-07-31T12:00:00Z",
        "description": "Rihanna description",
        "icon": "https://example.com/rihanna.png",
        "marketMakerAddress": "0xdef",
        "closed": False,
        "active": True,
    },
]

_TAG_RESPONSE = {
    "id": "235",
    "label": "Bitcoin",
    "slug": "bitcoin",
}

_BATCH_PRICES = [
    {"token_id": "111", "price": "0.46", "side": "BUY"},
    {"token_id": "222", "price": "0.54", "side": "SELL"},
    {"token_id": "t1", "price": "0.56", "side": "BUY"},
    {"token_id": "t2", "price": "0.44", "side": "SELL"},
    {"token_id": "t3", "price": "0.52", "side": "SELL"},
    {"token_id": "t4", "price": "0.48", "side": "BUY"},
    {"token_id": "e1", "price": "0.0108", "side": "BUY"},
    {"token_id": "e2", "price": "0.9892", "side": "SELL"},
    {"token_id": "e3", "price": "0.0130", "side": "BUY"},
    {"token_id": "e4", "price": "0.9870", "side": "SELL"},
    {"token_id": "e5", "price": "0.12", "side": "BUY"},
    {"token_id": "e6", "price": "0.88", "side": "SELL"},
]

_BATCH_PRICE_MAP = {item["token_id"]: item for item in _BATCH_PRICES}

_MARKET_DETAIL = {
    "id": "573652",
    "slug": "will-bitcoin-hit-150k-by-september-30",
    "question": "Will Bitcoin hit $150k by September 30?",
    "outcomes": '["Yes", "No"]',
    "outcomePrices": '["0.45", "0.55"]',
    "volume": "778900",
    "active": True,
    "closed": False,
}

_MARKET_BY_TOKEN = {
    "condition_id": "0xabc123",
    "primary_token_id": "111",
    "secondary_token_id": "222",
}


@pytest.fixture(autouse=True)
def _clear_resolve_cache():
    """每个测试前清理 _resolve_tag_slug 缓存，避免跨测试干扰。"""
    resolve_tag_slug.cache_clear()


def _mock_http(status: int = 200, data: object = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    if status == 200:
        resp.json.return_value = data
    resp.raise_for_status.return_value = None
    if status >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            str(status), request=MagicMock(), response=resp,
        )
    return resp


# ---------------------------------------------------------------------------
# search_events_by_keyword
# ---------------------------------------------------------------------------


class TestSearchEventsByKeyword:
    def test_returns_events_with_nested_markets(self):
        """返回事件列表，每个事件内嵌 enriched markets。"""
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.utils.batch_last_prices") as mock_post:
            mock_get.return_value = _mock_http(data=_SEARCH_RESPONSE)
            mock_post.return_value = _BATCH_PRICE_MAP
            result = search_events_by_keyword("bitcoin")

        assert len(result) == 1
        ev = result[0]
        assert ev["id"] == "36173"
        assert ev["title"] == "When will Bitcoin hit $150k?"
        assert ev["slug"] == "when-will-bitcoin-hit-150k"
        assert len(ev["markets"]) == 1

        m = ev["markets"][0]
        assert m["id"] == "573652"
        assert m["question"] == "Will Bitcoin hit $150k by September 30?"
        assert m["volume"] == "778900"
        # options 已配对含实时价格
        assert m["options"] == [
            {"name": "Yes", "price": "0.45", "side": "BUY", "last": "0.46",
             "multiplier": 2.17, "pct": 46.0},
            {"name": "No", "price": "0.55", "side": "SELL", "last": "0.54",
             "multiplier": 1.85, "pct": 54.0},
        ]
        # tags 在 event 级别
        assert ev["tags"] == [
            {"id": "235", "label": "Bitcoin", "slug": "bitcoin"},
            {"id": "21", "label": "Crypto", "slug": "crypto"},
        ]
        assert "outcomes" not in m
        assert "clobTokenIds" not in m

    def test_limit_truncates_events(self):
        """limit 控制返回事件数量。"""
        data = {
            "events": [
                {"id": str(i), "title": f"E{i}", "slug": f"e{i}", "volume": 100,
                 "markets": [{"id": str(100 + i), "question": f"Q{i}",
                              "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]',
                              "clobTokenIds": '["x","y"]', "volume": "1"}]}
                for i in range(5)
            ],
        }
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.utils.batch_last_prices") as mock_post:
            mock_get.return_value = _mock_http(data=data)
            mock_post.return_value = {}
            result = search_events_by_keyword("test", limit=2)

        assert len(result) == 2

    def test_empty_search_returns_empty_list(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data={"events": []})
            result = search_events_by_keyword("nonexistent")
        assert result == []

    def test_missing_markets_field_does_not_crash(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(
                data={"events": [{"id": "1", "title": "E1", "slug": "e1"}]}
            )
            result = search_events_by_keyword("test")
        assert len(result) == 1
        assert result[0]["markets"] == []

    def test_no_events_key_returns_empty(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data={})
            result = search_events_by_keyword("test")
        assert result == []

    def test_raises_on_http_error(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(status=500, data=None)
            with pytest.raises(httpx.HTTPStatusError):
                search_events_by_keyword("bitcoin")

    def test_multiple_events_preserved_in_order(self):
        """多个 event 各自独立返回，不拍平。"""
        data = {
            "events": [
                {"id": "1", "title": "E1", "slug": "e1", "volume": 200, "tags": [], "markets": [
                    {"id": "10", "question": "Q10", "slug": "m10",
                     "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]',
                     "clobTokenIds": '["a","b"]', "volume": "1"},
                ]},
                {"id": "2", "title": "E2", "slug": "e2", "volume": 100, "tags": [], "markets": [
                    {"id": "20", "question": "Q20", "slug": "m20",
                     "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]',
                     "clobTokenIds": '["c","d"]', "volume": "2"},
                ]},
            ],
        }
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.utils.batch_last_prices") as mock_post:
            mock_get.return_value = _mock_http(data=data)
            mock_post.return_value = {}
            result = search_events_by_keyword("test")

        assert len(result) == 2
        assert result[0]["title"] == "E1"
        assert result[0]["markets"][0]["question"] == "Q10"

    def test_null_tags_does_not_crash(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data={
                "events": [{"id": "1", "title": "E1", "slug": "e1", "tags": None,
                            "volume": 0, "markets": []}],
            })
            result = search_events_by_keyword("test")
        assert result[0]["tags"] == []

    def test_partial_price_data_graceful(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.utils.batch_last_prices") as mock_post:
            mock_get.return_value = _mock_http(data=_SEARCH_RESPONSE)
            mock_post.return_value = {"111": {"token_id": "111", "price": "0.46", "side": "BUY"}}
            result = search_events_by_keyword("bitcoin")

        opts = result[0]["markets"][0]["options"]
        assert opts[0]["name"] == "Yes"
        assert opts[0]["last"] == "0.46"
        assert opts[1] == {"name": "No", "price": "0.55"}

    def test_markets_sorted_by_volume(self):
        """event 内的 markets 按 volume 降序排列。"""
        data = {
            "events": [{
                "id": "1", "title": "E1", "slug": "e1", "volume": 1000, "tags": [], "markets": [
                    {"id": "1a", "question": "Low", "slug": "m1",
                     "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]',
                     "clobTokenIds": '["a","b"]', "volume": "10"},
                    {"id": "1b", "question": "High", "slug": "m2",
                     "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]',
                     "clobTokenIds": '["c","d"]', "volume": "100"},
                    {"id": "1c", "question": "Mid", "slug": "m3",
                     "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]',
                     "clobTokenIds": '["e","f"]', "volume": "50"},
                ],
            }],
        }
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.utils.batch_last_prices") as mock_post:
            mock_get.return_value = _mock_http(data=data)
            mock_post.return_value = {}
            result = search_events_by_keyword("test")

        volumes = [float(m["volume"]) for m in result[0]["markets"]]
        assert volumes == sorted(volumes, reverse=True)


# ---------------------------------------------------------------------------
# _batch_last_prices
# ---------------------------------------------------------------------------


class TestBatchLastPrices:
    def test_empty_token_ids_returns_empty(self):
        assert _batch_last_prices([]) == {}

    def test_success_returns_mapped_dict(self):
        prices = [
            {"token_id": "111", "price": "0.46", "side": "BUY"},
            {"token_id": "222", "price": "0.54", "side": "SELL"},
        ]
        mock_resp = _mock_http(data=prices)
        mock_resp.status_code = 200

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = _batch_last_prices(["111", "222"])

        assert result == {
            "111": {"token_id": "111", "price": "0.46", "side": "BUY"},
            "222": {"token_id": "222", "price": "0.54", "side": "SELL"},
        }

    def test_http_error_returns_empty(self):
        mock_resp = _mock_http(status=500, data=None)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = _batch_last_prices(["111"])
        assert result == {}

    def test_exception_during_request_returns_empty(self):
        """httpx.post 抛出异常时返回 {}，不冒泡。"""
        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.TimeoutException("timeout")
            )
            result = _batch_last_prices(["111"])
        assert result == {}


# ---------------------------------------------------------------------------
# _enrich_markets
# ---------------------------------------------------------------------------


class TestEnrichMarkets:
    def test_enriches_with_prices(self):
        markets = [
            {
                "id": "100",
                "slug": "m100",
                "question": "Q?",
                "outcomes": '["Yes","No"]',
                "outcomePrices": '["0.5","0.5"]',
                "clobTokenIds": '["a","b"]',
                "volume": "500",
                "marketMakerAddress": "0x1",
            },
        ]
        with patch(
            "src.services.polymarket.utils.batch_last_prices",
            return_value={
                "a": {"token_id": "a", "price": "0.55", "side": "BUY"},
                "b": {"token_id": "b", "price": "0.45", "side": "SELL"},
            },
        ):
            result = _enrich_markets(markets, limit=10)

        assert len(result) == 1
        opts = result[0]["options"]
        assert opts[0]["name"] == "Yes"
        assert opts[0]["last"] == "0.55"
        assert opts[0]["multiplier"] == 1.82  # 1/0.55
        assert opts[0]["pct"] == 55.0

    def test_limit_truncates(self):
        markets = [
            {"id": str(i), "slug": f"m{i}", "question": f"Q{i}",
             "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]',
             "clobTokenIds": "[]", "volume": "0", "marketMakerAddress": "0x"}
            for i in range(5)
        ]
        with patch(
            "src.services.polymarket.utils.batch_last_prices",
            return_value={},
        ):
            result = _enrich_markets(markets, limit=2)
        assert len(result) == 2

    def test_missing_fields_do_not_crash(self):
        markets = [
            {"id": "1", "slug": "m1", "question": "Q?"},
        ]
        with patch(
            "src.services.polymarket.utils.batch_last_prices",
            return_value={},
        ):
            result = _enrich_markets(markets, limit=10)

        assert len(result) == 1
        assert result[0]["options"] == []

    def test_batch_price_failure_still_returns_trimmed(self):
        """批量价格接口失败时，仍返回裁剪后的数据，只是 options 不含 last/multiplier。"""
        markets = [
            {
                "id": "1", "slug": "m1", "question": "Q?",
                "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]',
                "clobTokenIds": '["a","b"]', "volume": "100",
                "marketMakerAddress": "0x",
            },
        ]
        with patch(
            "src.services.polymarket.utils.batch_last_prices",
            return_value={},
        ):
            result = _enrich_markets(markets, limit=10)

        opts = result[0]["options"]
        assert opts[0] == {"name": "Yes", "price": "0.5"}
        assert opts[1] == {"name": "No", "price": "0.5"}


# ---------------------------------------------------------------------------
# list_markets
# ---------------------------------------------------------------------------


class TestListMarkets:
    def test_default_params(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data=_MARKETS_LIST)
            result = list_markets()

        assert len(result) == 2
        assert result[0]["id"] == "540816"

    def test_order_by_descending(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data=_MARKETS_LIST)
            list_markets(order_by="volume_num", ascending=False)

        params = mock_get.call_args[1]["params"]
        assert params["order"] == "-volume_num"

    def test_order_by_ascending(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data=_MARKETS_LIST)
            list_markets(order_by="volume_num", ascending=True)

        params = mock_get.call_args[1]["params"]
        assert params["order"] == "volume_num"

    def test_closed_filter(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data=_MARKETS_LIST)
            list_markets(closed=True)

        assert mock_get.call_args[1]["params"]["closed"] == "true"

    def test_tag_id_filter(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data=_MARKETS_LIST)
            list_markets(tag_id=235)

        assert mock_get.call_args[1]["params"]["tag_id"] == 235

    def test_tag_slug_resolves_to_id(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.side_effect = [
                _mock_http(data=_TAG_RESPONSE),
                _mock_http(data=_MARKETS_LIST),
            ]
            list_markets(tag_slug="bitcoin")

        assert mock_get.call_count == 2
        # 第一次调用: tags/slug/bitcoin（无 query params）
        assert "tags/slug/bitcoin" in str(mock_get.call_args_list[0][0][0])
        # 第二次调用: /markets?tag_id=235
        params = mock_get.call_args_list[1][1]["params"]
        assert params["tag_id"] == 235

    def test_volume_range_filter(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data=_MARKETS_LIST)
            list_markets(volume_num_min=1000, volume_num_max=50000)

        params = mock_get.call_args[1]["params"]
        assert params["volume_num_min"] == 1000
        assert params["volume_num_max"] == 50000

    def test_date_range_filter(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data=_MARKETS_LIST)
            list_markets(
                start_date_min="2025-01-01",
                end_date_max="2025-12-31",
            )

        params = mock_get.call_args[1]["params"]
        assert params["start_date_min"] == "2025-01-01"
        assert params["end_date_max"] == "2025-12-31"

    def test_include_tag(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data=_MARKETS_LIST)
            list_markets(include_tag=True)

        assert mock_get.call_args[1]["params"]["include_tag"] == "true"

    def test_liquidity_range(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data=_MARKETS_LIST)
            list_markets(liquidity_num_min=100)

        assert mock_get.call_args[1]["params"]["liquidity_num_min"] == 100

    def test_closed_none_omits_param(self):
        """closed=None 时 params 中不应包含 closed。"""
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data=_MARKETS_LIST)
            list_markets(closed=None)

        assert "closed" not in mock_get.call_args[1]["params"]

    def test_empty_response(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data=[])
            result = list_markets()

        assert result == []

    def test_detail_false_enriches(self):
        """detail=False 时裁剪字段并附上实时价格。"""
        stack = ExitStack()
        mock_get = stack.enter_context(
            patch("src.services.polymarket.search.httpx.get")
        )
        mock_post = stack.enter_context(
            patch("src.services.polymarket.utils.batch_last_prices")
        )
        mock_get.return_value = _mock_http(data=_MARKETS_LIST)
        mock_post.return_value = _BATCH_PRICE_MAP

        with stack:
            result = list_markets(detail=False)

        assert len(result) == 2
        assert "options" in result[0]
        assert result[0]["options"][0]["last"] == "0.56"
        assert "outcomes" not in result[0]

    def test_detail_true_returns_raw(self):
        """detail=True 返回 API 原始字段（默认行为）。"""
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data=_MARKETS_LIST)
            result = list_markets(detail=True)

        assert len(result) == 2
        assert "outcomes" in result[0]
        assert "clobTokenIds" in result[0]


# ---------------------------------------------------------------------------
# list_trending_markets
# ---------------------------------------------------------------------------


class TestListTrendingMarkets:
    def test_returns_enriched_markets(self):
        stack = ExitStack()
        mock_get = stack.enter_context(
            patch("src.services.polymarket.search.httpx.get")
        )
        mock_post = stack.enter_context(
            patch("src.services.polymarket.utils.batch_last_prices")
        )
        mock_get.return_value = _mock_http(data=_MARKETS_LIST)
        mock_post.return_value = _BATCH_PRICE_MAP

        with stack:
            result = list_trending_markets(limit=2)

        assert len(result) == 2
        assert "options" in result[0]
        assert result[0]["options"][0]["last"] == "0.56"

    def test_with_tag_slug(self):
        stack = ExitStack()
        mock_get = stack.enter_context(
            patch("src.services.polymarket.search.httpx.get")
        )
        mock_post = stack.enter_context(
            patch("src.services.polymarket.utils.batch_last_prices")
        )
        # 三次调用: tag slug 解析 → markets → 已由 _enrich_markets 触发
        mock_get.side_effect = [
            _mock_http(data=_TAG_RESPONSE),
            _mock_http(data=_MARKETS_LIST),
        ]
        mock_post.return_value = _BATCH_PRICE_MAP

        with stack:
            result = list_trending_markets(limit=2, tag_slug="bitcoin")

        assert len(result) == 2

    def test_empty_list(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.utils.batch_last_prices") as mock_post:
            mock_get.return_value = _mock_http(data=[])
            mock_post.return_value = {}
            result = list_trending_markets()

        assert result == []


# ---------------------------------------------------------------------------
# list_trending_events — 基于官网真实数据验证
# ---------------------------------------------------------------------------


_FIXTURE_DIR = Path(__file__).parent / "fixtures"


class TestListTrendingEvents:
    """使用 Polymarket 官网首页真实数据验证 list_trending_events。"""

    @pytest.fixture(autouse=True)
    def _load_fixtures(self):
        with open(_FIXTURE_DIR / "events_keyset_response.json") as f:
            self.events_data = json.load(f)
        with open(_FIXTURE_DIR / "batch_prices_response.json") as f:
            raw_prices = json.load(f)
            self.prices_data = {item["token_id"]: item for item in raw_prices}

    def test_returns_events_matching_homepage(self):
        """返回事件列表，每个事件包含 enriched markets。"""
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.utils.batch_last_prices") as mock_post:
            mock_get.return_value = _mock_http(data=self.events_data)
            mock_post.return_value = self.prices_data

            result = list_trending_events(limit=3)

        assert len(result) == 3

        for ev in result:
            # Event 级别字段
            assert "id" in ev and "title" in ev and "slug" in ev
            assert isinstance(ev["volume"], float)
            assert isinstance(ev["closed"], bool)
            assert isinstance(ev["tags"], list)
            assert isinstance(ev["markets"], list)

            # Markets 内嵌 enrichment
            for m in ev["markets"]:
                assert "id" in m and "question" in m
                assert isinstance(m["options"], list)
                for opt in m["options"]:
                    assert "name" in opt and "price" in opt

    def test_sorted_by_event_volume(self):
        """Event 按总成交量降序排列（与官网一致）。"""
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.utils.batch_last_prices") as mock_post:
            mock_get.return_value = _mock_http(data=self.events_data)
            mock_post.return_value = self.prices_data

            result = list_trending_events(limit=10)

        volumes = [ev["volume"] for ev in result]
        assert volumes == sorted(volumes, reverse=True), \
            "Event 成交量未按降序排列"

    def test_default_excludes_closed_markets(self):
        """默认 closed=False 过滤掉已结算的 market。"""
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.utils.batch_last_prices") as mock_post:
            mock_get.return_value = _mock_http(data=self.events_data)
            mock_post.return_value = self.prices_data

            result = list_trending_events(limit=50)

        # 每个 event 内的 market 都不应该已结算
        for ev in result:
            for m in ev["markets"]:
                for opt in m["options"]:
                    p = float(opt["price"])
                    assert 0 < p < 1, f"包含已结算 market: {m['question']} price={p}"

    def test_tag_slug_filters_by_category(self):
        """指定 tag_slug 时，API 请求参数应包含它。"""
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.utils.batch_last_prices") as mock_post:
            mock_get.return_value = _mock_http(data=self.events_data)
            mock_post.return_value = self.prices_data

            list_trending_events(limit=3, tag_slug="sports")

            # 验证请求参数
            call_kwargs = mock_get.call_args[1]
            params = call_kwargs.get("params", {})
            assert params.get("tag_slug") == "sports"

    def test_empty_events_returns_empty_list(self):
        """events/keyset 返回空时，函数应返回空列表。"""
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.utils.batch_last_prices") as mock_post:
            mock_get.return_value = _mock_http(data={"events": []})
            mock_post.return_value = {}
            result = list_trending_events(limit=5)

    def test_default_excludes_closed_markets(self):
        """默认 closed=False 应过滤掉已结算的市场。"""
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.utils.batch_last_prices") as mock_post:
            mock_get.return_value = _mock_http(data=self.events_data)
            mock_post.return_value = self.prices_data

            result = list_trending_events(limit=50)

        # 所有返回的 markets 都不应该是已结算的（price 为 0 或 1）
        for ev in result:
            for m in ev["markets"]:
                for opt in m["options"]:
                    p = float(opt["price"])
                    assert 0 < p < 1, f"包含已结算市场: {m['question']} price={p}"

    def test_tag_slug_filters_by_category(self):
        """指定 tag_slug 时，API 请求参数应包含它。"""
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.utils.batch_last_prices") as mock_post:
            mock_get.return_value = _mock_http(data=self.events_data)
            mock_post.return_value = self.prices_data

            list_trending_events(limit=3, tag_slug="sports")

            # 验证请求参数
            call_kwargs = mock_get.call_args[1]
            assert "sports" in str(call_kwargs.get("params", {}))

    def test_empty_events_returns_empty_list(self):
        """events/keyset 返回空时，函数应返回空列表。"""
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.utils.batch_last_prices") as mock_post:
            mock_get.return_value = _mock_http(data={"events": []})
            mock_post.return_value = {}
            result = list_trending_events(limit=5)

        assert result == []


# ---------------------------------------------------------------------------
# is_market_closed
# ---------------------------------------------------------------------------


class TestIsMarketClosed:
    """is_market_closed 辅助函数的单元测试（不涉及 HTTP 请求）。"""

    def test_closed_field_true(self):
        from src.services.polymarket.utils import is_market_closed
        assert is_market_closed({"closed": True}) is True
        assert is_market_closed({"closed": "true"}) is True

    def test_closed_field_false(self):
        from src.services.polymarket.utils import is_market_closed
        assert is_market_closed({"closed": False}) is False
        assert is_market_closed({"closed": "false"}) is False

    def test_closed_field_missing_enddate_past(self):
        """closed 字段缺失，endDate 在过去 → True"""
        from src.services.polymarket.utils import is_market_closed
        assert is_market_closed({"endDate": "2020-01-01T00:00:00Z"}) is True

    def test_closed_field_missing_enddate_future(self):
        """closed 字段缺失，endDate 在未来 → False"""
        from src.services.polymarket.utils import is_market_closed
        assert is_market_closed({"endDate": "2099-01-01T00:00:00Z"}) is False

    def test_no_closed_no_enddate(self):
        """两个字段都不存在 → None"""
        from src.services.polymarket.utils import is_market_closed
        assert is_market_closed({}) is None


# ---------------------------------------------------------------------------
# search_events_by_keyword — closed 参数
# ---------------------------------------------------------------------------


class TestSearchEventsClosedFilter:
    """search_events_by_keyword closed 过滤测试。"""

    def test_closed_true_keeps_only_closed(self):
        """closed=True 只保留已结束的市场。"""
        data = {
            "events": [{
                "id": "1", "title": "E1", "slug": "e1", "volume": 0, "tags": [], "markets": [
                    {"id": "10", "question": "Q1", "closed": True,
                     "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]',
                     "clobTokenIds": '["a","b"]', "volume": "1"},
                ],
            }],
        }
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.utils.batch_last_prices") as mock_post:
            mock_get.return_value = _mock_http(data=data)
            mock_post.return_value = {}
            result = search_events_by_keyword("test", closed=True)
        assert len(result[0]["markets"]) == 1
        assert result[0]["markets"][0]["id"] == "10"

    def test_closed_false_keeps_only_open(self):
        """closed=False 只保留未结束的 market。"""
        data = {
            "events": [{
                "id": "1", "title": "E1", "slug": "e1", "volume": 0, "tags": [], "markets": [
                    {"id": "10", "question": "Q1", "closed": True,
                     "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]',
                     "clobTokenIds": '["a","b"]', "volume": "1"},
                    {"id": "11", "question": "Q2", "closed": False,
                     "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]',
                     "clobTokenIds": '["c","d"]', "volume": "2"},
                ],
            }],
        }
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.utils.batch_last_prices") as mock_post:
            mock_get.return_value = _mock_http(data=data)
            mock_post.return_value = {}
            result = search_events_by_keyword("test", closed=False)
        assert len(result[0]["markets"]) == 1
        assert result[0]["markets"][0]["id"] == "11"

    def test_closed_default_none_no_filter(self):
        """closed=None 不过滤。"""
        data = {
            "events": [{
                "id": "1", "title": "E1", "slug": "e1", "volume": 0, "tags": [], "markets": [
                    {"id": "10", "question": "Q1", "closed": True,
                     "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]',
                     "clobTokenIds": '["a","b"]', "volume": "1"},
                    {"id": "11", "question": "Q2", "closed": False,
                     "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]',
                     "clobTokenIds": '["c","d"]', "volume": "2"},
                ],
            }],
        }
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.utils.batch_last_prices") as mock_post:
            mock_get.return_value = _mock_http(data=data)
            mock_post.return_value = {}
            result = search_events_by_keyword("test")
        assert len(result[0]["markets"]) == 2

    def test_closed_filter_with_enrich(self):
        """closed 过滤后 enrichment 仍正常。"""
        data = {
            "events": [{
                "id": "1", "title": "E1", "slug": "e1", "volume": 0, "tags": [], "markets": [
                    {"id": "10", "question": "Q1", "closed": False,
                     "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]',
                     "clobTokenIds": '["x","y"]', "volume": "1"},
                ],
            }],
        }
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.utils.batch_last_prices") as mock_post:
            mock_get.return_value = _mock_http(data=data)
            mock_post.return_value = {}
            result = search_events_by_keyword("test", closed=False)
        assert len(result[0]["markets"]) == 1
        assert "options" in result[0]["markets"][0]


# ---------------------------------------------------------------------------
# list_trending_markets — closed 参数透传
# ---------------------------------------------------------------------------


class TestListTrendingMarketsClosed:
    """list_trending_markets 的 closed 参数透传到 list_markets。"""

    def test_closed_false_sends_param(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.utils.batch_last_prices") as mock_post:
            mock_get.return_value = _mock_http(data=[])
            mock_post.return_value = {}
            list_trending_markets(limit=1, closed=False)
        _, kwargs = mock_get.call_args
        assert kwargs["params"].get("closed") == "false"

    def test_closed_true_sends_param(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.utils.batch_last_prices") as mock_post:
            mock_get.return_value = _mock_http(data=[])
            mock_post.return_value = {}
            list_trending_markets(limit=1, closed=True)
        _, kwargs = mock_get.call_args
        assert kwargs["params"].get("closed") == "true"

    def test_closed_none_omits_param(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.utils.batch_last_prices") as mock_post:
            mock_get.return_value = _mock_http(data=[])
            mock_post.return_value = {}
            list_trending_markets(limit=1)
        _, kwargs = mock_get.call_args
        assert "closed" not in kwargs["params"]
# ---------------------------------------------------------------------------


class TestListTags:
    def test_returns_tag_list(self):
        tags_data = [
            {"id": "1", "label": "Politics", "slug": "politics"},
            {"id": "2", "label": "Crypto", "slug": "crypto"},
        ]
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data=tags_data)
            result = list_tags(limit=50)

        assert result == tags_data
        assert mock_get.call_args[1]["params"]["limit"] == 50

    def test_default_limit(self):
        """limit 默认值为 100。"""
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data=[])
            list_tags()

        assert mock_get.call_args[1]["params"]["limit"] == 100


# ---------------------------------------------------------------------------
# get_tag_by_slug
# ---------------------------------------------------------------------------


class TestGetTagBySlug:
    def test_returns_tag(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data=_TAG_RESPONSE)
            result = get_tag_by_slug("bitcoin")

        assert result == _TAG_RESPONSE
        assert "tags/slug/bitcoin" in str(mock_get.call_args[0][0])


    def test_raises_on_not_found(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(status=404, data=None)
            with pytest.raises(httpx.HTTPStatusError):
                get_tag_by_slug("nonexistent")


# ---------------------------------------------------------------------------
# _resolve_tag_slug
# ---------------------------------------------------------------------------


class TestResolveTagSlug:
    def test_returns_int_id(self):
        with patch(
            "src.services.polymarket.tags.get_tag_by_slug",
            return_value=_TAG_RESPONSE,
        ):
            result = resolve_tag_slug("bitcoin")

        assert result == 235
        assert isinstance(result, int)

    def test_cache_hits(self):
        """同 slug 第二次调用不触发 HTTP 请求。"""
        with patch(
            "src.services.polymarket.tags.get_tag_by_slug",
            return_value=_TAG_RESPONSE,
        ) as mock_get:
            resolve_tag_slug("bitcoin")
            resolve_tag_slug("bitcoin")

        assert mock_get.call_count == 1

    def test_tag_not_found_propagates(self):
        """tag slug 不存在时透传 404 异常。"""
        with patch(
            "src.services.polymarket.tags.get_tag_by_slug",
            side_effect=httpx.HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock(),
            ),
        ):
            with pytest.raises(httpx.HTTPStatusError):
                resolve_tag_slug("nonexistent")


# ---------------------------------------------------------------------------
# get_market_by_slug
# ---------------------------------------------------------------------------


class TestGetMarketBySlug:
    def test_returns_market(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data=_MARKET_DETAIL)
            result = get_market_by_slug("will-bitcoin-hit-150k-by-september-30")

        assert result["id"] == "573652"
        assert "markets/slug/" in str(mock_get.call_args[0][0])

    def test_raises_on_not_found(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(status=404, data=None)
            with pytest.raises(httpx.HTTPStatusError):
                get_market_by_slug("nonexistent")


# ---------------------------------------------------------------------------
# get_market_by_id
# ---------------------------------------------------------------------------


class TestGetMarketById:
    def test_returns_market(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data=_MARKET_DETAIL)
            result = get_market_by_id(573652)

        assert result["id"] == "573652"
        assert str(mock_get.call_args[0][0]).endswith("/markets/573652")

    def test_raises_on_not_found(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(status=404, data=None)
            with pytest.raises(httpx.HTTPStatusError):
                get_market_by_id(999999)


# ---------------------------------------------------------------------------
# get_market_by_token_addr
# ---------------------------------------------------------------------------


class TestGetMarketByTokenAddr:
    def test_returns_market_info(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data=_MARKET_BY_TOKEN)
            result = get_market_by_token_addr("0xabc123")

        assert result["condition_id"] == "0xabc123"
        assert "markets-by-token/" in str(mock_get.call_args[0][0])

    def test_raises_on_not_found(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(status=404, data=None)
            with pytest.raises(httpx.HTTPStatusError):
                get_market_by_token_addr("0xdead")

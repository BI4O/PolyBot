"""Tests for Polymarket search service."""

import json
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.services.polymarket.search import (
    _batch_last_prices,
    _enrich_markets,
    _resolve_tag_slug,
    get_market_by_id,
    get_market_by_slug,
    get_market_by_token_addr,
    get_tag_by_slug,
    list_markets,
    list_tags,
    list_trending_markets,
    search_markets_by_keyword,
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
]

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
# search_markets_by_keyword
# ---------------------------------------------------------------------------


class TestSearchMarketsByKeyword:
    def test_detail_returns_raw_data(self):
        """detail=True 返回原始数据 + 附加 event/tags，不截取字段。"""
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data=_SEARCH_RESPONSE)
            result = search_markets_by_keyword("bitcoin", detail=True)

        assert len(result) == 1
        m = result[0]
        assert m["id"] == "573652"
        assert m["question"] == "Will Bitcoin hit $150k by September 30?"
        assert m["event"] == {"id": "36173", "title": "When will Bitcoin hit $150k?"}
        assert m["_tags"] == [
            {"id": "235", "label": "Bitcoin", "slug": "bitcoin"},
            {"id": "21", "label": "Crypto", "slug": "crypto"},
        ]
        # 保留所有原始字段
        assert "startDate" in m
        assert "volume" in m

    def test_detail_false_trims_and_enriches(self):
        """detail=False 时裁剪字段并附上实时价格。"""
        stack = ExitStack()
        mock_get = stack.enter_context(
            patch("src.services.polymarket.search.httpx.get")
        )
        mock_post = stack.enter_context(
            patch("src.services.polymarket.search.httpx.post")
        )
        mock_get.return_value = _mock_http(data=_SEARCH_RESPONSE)
        mock_post.return_value = _mock_http(data=_BATCH_PRICES)

        with stack:
            result = search_markets_by_keyword("bitcoin")

        assert len(result) == 1
        item = result[0]
        # 核心字段
        assert item["id"] == "573652"
        assert item["slug"] == "will-bitcoin-hit-150k-by-september-30"
        assert item["question"] == "Will Bitcoin hit $150k by September 30?"
        assert item["event"] == {"id": "36173", "title": "When will Bitcoin hit $150k?"}
        assert item["volume"] == "778900"
        # 没有原始 API 赘余字段
        assert "outcomes" not in item
        assert "clobTokenIds" not in item
        # options 已配对
        assert item["options"] == [
            {
                "name": "Yes", "price": "0.45",
                "side": "BUY", "last": "0.46",
                "multiplier": 2.17, "pct": 46.0,
            },
            {
                "name": "No", "price": "0.55",
                "side": "SELL", "last": "0.54",
                "multiplier": 1.85, "pct": 54.0,
            },
        ]

    def test_limit_truncates_results(self):
        """limit 参数控制返回条数。"""
        data = {
            "events": [
                {"id": str(i), "title": f"Event {i}", "slug": f"e{i}", "markets": [
                    {"id": str(100 + i), "slug": f"m-{100+i}", "question": f"Q {i}",
                     "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]',
                     "clobTokenIds": '["x","y"]', "volume": "100", "marketMakerAddress": "0x"},
                ]}
                for i in range(5)
            ],
        }
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.search.httpx.post") as mock_post:
            mock_get.return_value = _mock_http(data=data)
            mock_post.return_value = _mock_http(data=[])

            result_full = search_markets_by_keyword("test", limit=10, detail=True)
            result_limited = search_markets_by_keyword("test", limit=2, detail=True)

        assert len(result_full) == 5
        assert len(result_limited) == 2

    def test_empty_search_returns_empty_list(self):
        """搜索结果为空时返回 []. """
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data={"events": []})
            result = search_markets_by_keyword("nonexistent")
        assert result == []

    def test_missing_markets_field_does_not_crash(self):
        """event 没有 markets 字段时不崩溃。"""
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(
                data={"events": [{"id": "1", "title": "E1", "slug": "e1"}]}
            )
            result = search_markets_by_keyword("test")
        assert result == []

    def test_no_events_key_returns_empty(self):
        """响应缺少 events 键时返回 []。"""
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data={})
            result = search_markets_by_keyword("test")
        assert result == []

    def test_raises_on_http_error(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(status=500, data=None)
            with pytest.raises(httpx.HTTPStatusError):
                search_markets_by_keyword("bitcoin")

    def test_multiple_events_are_flattened(self):
        """多个 event 下的 market 全部拍平到一个列表。"""
        data = {
            "events": [
                {"id": "1", "title": "E1", "slug": "e1", "tags": [], "markets": [
                    {"id": "10", "slug": "m10", "question": "Q10",
                     "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]',
                     "clobTokenIds": '["a","b"]', "volume": "1", "marketMakerAddress": "0x"},
                ]},
                {"id": "2", "title": "E2", "slug": "e2", "tags": [], "markets": [
                    {"id": "20", "slug": "m20", "question": "Q20",
                     "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]',
                     "clobTokenIds": '["c","d"]', "volume": "2", "marketMakerAddress": "0x"},
                ]},
            ],
        }
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data=data)
            result = search_markets_by_keyword("test", detail=True)

        assert len(result) == 2
        assert result[0]["event"]["title"] == "E1"
        assert result[1]["event"]["title"] == "E2"

    def test_null_tags_does_not_crash(self):
        """event.tags 为 None 时 _tags 应留空列表。"""
        data = {
            "events": [
                {"id": "1", "title": "E1", "slug": "e1", "tags": None, "markets": [
                    {"id": "10", "slug": "m10", "question": "Q10",
                     "outcomes": '["Yes","No"]', "outcomePrices": '["0.5","0.5"]',
                     "clobTokenIds": '["a","b"]', "volume": "1", "marketMakerAddress": "0x"},
                ]},
            ],
        }
        with patch("src.services.polymarket.search.httpx.get") as mock_get:
            mock_get.return_value = _mock_http(data=data)
            result = search_markets_by_keyword("test", detail=True)

        assert result[0]["_tags"] == []

    def test_partial_price_data_graceful(self):
        """部分 token 没有实时价格时，对应 option 只保留 name/price。"""
        stack = ExitStack()
        mock_get = stack.enter_context(patch("src.services.polymarket.search.httpx.get"))
        mock_post = stack.enter_context(patch("src.services.polymarket.search.httpx.post"))
        mock_get.return_value = _mock_http(data=_SEARCH_RESPONSE)
        # price_map 只包含 Yes token（111），不包含 No token（222）
        mock_post.return_value = _mock_http(data=[
            {"token_id": "111", "price": "0.46", "side": "BUY"},
        ])
        with stack:
            result = search_markets_by_keyword("bitcoin")

        opts = result[0]["options"]
        # Yes：有实时价格
        assert opts[0]["name"] == "Yes"
        assert opts[0]["last"] == "0.46"
        # No：price_map 中不存在，不能有 last/multiplier/pct
        assert opts[1] == {"name": "No", "price": "0.55"}

    def test_price_zero_handling(self):
        """价格为 0 时 multiplier 应为 None，避免除零错误。"""
        markets = [
            {
                "id": "1", "slug": "m1", "question": "Q?",
                "outcomes": '["Yes","No"]', "outcomePrices": '["0","1"]',
                "clobTokenIds": '["a","b"]', "volume": "100",
                "marketMakerAddress": "0x",
            },
        ]
        with patch(
            "src.services.polymarket.search._batch_last_prices",
            return_value={"a": {"token_id": "a", "price": "0", "side": "BUY"}},
        ):
            result = _enrich_markets(markets, limit=10)

        opt = result[0]["options"][0]
        assert opt["price"] == "0"
        assert opt["multiplier"] is None  # 1/0 没有意义


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
        with patch("src.services.polymarket.search.httpx.post") as mock_post:
            mock_post.return_value = _mock_http(data=prices)
            result = _batch_last_prices(["111", "222"])

        assert result == {
            "111": {"token_id": "111", "price": "0.46", "side": "BUY"},
            "222": {"token_id": "222", "price": "0.54", "side": "SELL"},
        }

    def test_http_error_returns_empty(self):
        with patch("src.services.polymarket.search.httpx.post") as mock_post:
            mock_post.return_value = _mock_http(status=500, data=None)
            result = _batch_last_prices(["111"])
        assert result == {}

    def test_exception_during_request_returns_empty(self):
        """httpx.post 抛出异常时返回 {}，不冒泡。"""
        with patch(
            "src.services.polymarket.search.httpx.post",
            side_effect=httpx.TimeoutException("timeout"),
        ):
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
            "src.services.polymarket.search._batch_last_prices",
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
            "src.services.polymarket.search._batch_last_prices",
            return_value={},
        ):
            result = _enrich_markets(markets, limit=2)
        assert len(result) == 2

    def test_missing_fields_do_not_crash(self):
        markets = [
            {"id": "1", "slug": "m1", "question": "Q?"},
        ]
        with patch(
            "src.services.polymarket.search._batch_last_prices",
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
            "src.services.polymarket.search._batch_last_prices",
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
            patch("src.services.polymarket.search.httpx.post")
        )
        mock_get.return_value = _mock_http(data=_MARKETS_LIST)
        mock_post.return_value = _mock_http(data=_BATCH_PRICES)

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
            patch("src.services.polymarket.search.httpx.post")
        )
        # 三次调用: tag slug 解析 → markets → 已由 _enrich_markets 触发
        mock_get.side_effect = [
            _mock_http(data=_TAG_RESPONSE),
            _mock_http(data=_MARKETS_LIST),
        ]
        mock_post.return_value = _mock_http(data=_BATCH_PRICES)

        with stack:
            result = list_trending_markets(limit=2, tag_slug="bitcoin")

        assert len(result) == 2

    def test_empty_list(self):
        with patch("src.services.polymarket.search.httpx.get") as mock_get, \
             patch("src.services.polymarket.search.httpx.post") as mock_post:
            mock_get.return_value = _mock_http(data=[])
            mock_post.return_value = _mock_http(data=[])
            result = list_trending_markets()

        assert result == []


# ---------------------------------------------------------------------------
# list_tags
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
            "src.services.polymarket.search.get_tag_by_slug",
            return_value=_TAG_RESPONSE,
        ):
            result = _resolve_tag_slug("bitcoin")

        assert result == 235
        assert isinstance(result, int)

    def test_tag_not_found_propagates(self):
        """tag slug 不存在时透传 404 异常。"""
        with patch(
            "src.services.polymarket.search.get_tag_by_slug",
            side_effect=httpx.HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock(),
            ),
        ):
            with pytest.raises(httpx.HTTPStatusError):
                _resolve_tag_slug("nonexistent")


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

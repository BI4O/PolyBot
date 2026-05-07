"""Tests for Coingecko service."""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import httpx

from src.services.coingecko.client import get_token_info, get_token_price

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_COINS_ORDI = [
    {
        "thumb": "https://assets.coingecko.com/coins/images/30162/standard/ordi.png",
        "name": "ORDI",
        "symbol": "ORDI",
        "market_cap_rank": 282,
        "id": "ordinals",
        "coin_id": 30162,
        "data": {
            "price": "$5.17",
            "market_cap": "$108,685,246",
            "sparkline": "https://www.coingecko.com/coins/30162/sparkline.svg",
        },
    },
    {
        "thumb": "https://assets.coingecko.com/coins/images/30666/standard/sats.png",
        "name": "SATS (Ordinals)",
        "symbol": "SATS",
        "market_cap_rank": 682,
        "id": "sats-ordinals",
        "coin_id": 30666,
        "data": {
            "price": "$0.0<sub>7</sub>1480",
            "market_cap": "$31,114,368",
            "sparkline": "https://www.coingecko.com/coins/30666/sparkline.svg",
        },
    },
]

_COINS_MULTI = [
    {
        "thumb": "https://assets.coingecko.com/coins/images/1/standard/bitcoin.png",
        "name": "Bitcoin",
        "symbol": "BTC",
        "market_cap_rank": 1,
        "id": "bitcoin",
        "data": {
            "price": "$78,628",
            "market_cap": "$1,577,075,214,512",
            "sparkline": "https://www.coingecko.com/coins/1/sparkline.svg",
        },
    },
    {
        "thumb": "https://assets.coingecko.com/coins/images/2/standard/bitcoin-cash.png",
        "name": "Bitcoin Cash",
        "symbol": "BCH",
        "market_cap_rank": 16,
        "id": "bitcoin-cash",
        "data": {
            "price": "$443",
            "market_cap": "$8,893,209,590",
            "sparkline": "https://www.coingecko.com/coins/2/sparkline.svg",
        },
    },
    {
        "thumb": "https://assets.coingecko.com/coins/images/3/standard/dog-bitcoin.png",
        "name": "Dog (Bitcoin)",
        "symbol": "DOG",
        "market_cap_rank": 352,
        "id": "dog-go-to-the-moon-rune",
        "data": {
            "price": "$0.000791",
            "market_cap": "$79,099,246",
            "sparkline": "https://www.coingecko.com/coins/3/sparkline.svg",
        },
    },
    {
        "thumb": "https://assets.coingecko.com/coins/images/4/standard/ethereum.png",
        "name": "Ethereum",
        "symbol": "ETH",
        "market_cap_rank": 2,
        "id": "ethereum",
        "data": {
            "price": "$2,100",
            "market_cap": "$252,000,000,000",
            "sparkline": "https://www.coingecko.com/coins/4/sparkline.svg",
        },
    },
    {
        "name": "NoDataCoin",
        "symbol": "NDC",
        "market_cap_rank": 999,
        "id": "no-data-coin",
    },
]


def _mock_search_response(data: list[dict]) -> MagicMock:
    """Mock the search_v2 endpoint response."""
    resp = MagicMock(spec=httpx.Response)
    resp.json.return_value = {"coins": data}
    resp.raise_for_status.return_value = None
    return resp


def _mock_coins_list(coin_ids: set[str]) -> MagicMock:
    """Mock /coins/list?include_platform=true — all coins get empty platforms."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = [
        {"id": cid, "symbol": "", "name": "", "platforms": {}}
        for cid in coin_ids
    ]
    return resp


def _patch_httpx(search_data: list[dict], coin_ids: set[str]) -> ExitStack:
    """Return a context manager that patches both httpx.get and httpx.Client."""
    mock_get = MagicMock()
    mock_get.return_value = _mock_search_response(search_data)

    mock_client = MagicMock()
    mock_client.get.return_value = _mock_coins_list(coin_ids)
    mock_client_cls = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client

    stack = ExitStack()
    stack.enter_context(patch("src.services.coingecko.client.httpx.get", mock_get))
    stack.enter_context(patch("src.services.coingecko.client.httpx.Client", mock_client_cls))
    return stack


# ---------------------------------------------------------------------------
# Tests: get_token_info
# ---------------------------------------------------------------------------


class TestGetTokenInfo:
    def test_substring_match_includes_all(self):
        """'ordi' matches ORDI (exact name) and SATS (Ordinals) — substring on name."""
        with _patch_httpx(_COINS_ORDI, {"ordinals", "sats-ordinals"}):
            result = get_token_info("ordi")

        assert [r["name"] for r in result] == ["ORDI", "SATS (Ordinals)"]

    def test_exact_match_sorted_first(self):
        """Exact name match (Bitcoin) before substring matches (Bitcoin Cash, etc.)."""
        coin_ids = {"bitcoin", "bitcoin-cash", "dog-go-to-the-moon-rune"}
        with _patch_httpx(_COINS_MULTI, coin_ids):
            result = get_token_info("bitcoin")

        assert [r["name"] for r in result] == [
            "Bitcoin",
            "Bitcoin Cash",
            "Dog (Bitcoin)",
        ]

    def test_symbol_exact_match_first(self):
        """Exact symbol match beats partial word match."""
        coins = [
            {"name": "Bitcoin", "symbol": "BTC", "market_cap_rank": 1, "id": "bitcoin"},
            {
                "name": "Bitget Wrapped BTC",
                "symbol": "BGBTC",
                "market_cap_rank": 552,
                "id": "bgbtc",
            },
        ]
        with _patch_httpx(coins, {"bitcoin", "bgbtc"}):
            result = get_token_info("btc")

        assert [r["id"] for r in result] == ["bitcoin", "bgbtc"]

    def test_returns_empty_for_no_match(self):
        with _patch_httpx(_COINS_MULTI, set()):
            result = get_token_info("xyzzy")

        assert result == []

    def test_topn_limits_results(self):
        coin_ids = {"bitcoin", "bitcoin-cash", "dog-go-to-the-moon-rune"}
        with _patch_httpx(_COINS_MULTI, coin_ids):
            result = get_token_info("bitcoin", topn=2)

        assert len(result) == 2

    def test_networks_field_present(self):
        with _patch_httpx(_COINS_ORDI[:1], {"ordinals"}):
            result = get_token_info("ordi")

        assert "networks" in result[0]
        assert isinstance(result[0]["networks"], dict)


# ---------------------------------------------------------------------------
# Tests: get_token_price
# ---------------------------------------------------------------------------


class TestGetTokenPrice:
    def test_returns_same_format_as_get_token_info(self):
        with _patch_httpx(_COINS_ORDI, {"ordinals", "sats-ordinals"}):
            info_result = get_token_info("ordi")
            price_result = get_token_price("ordi")

        assert info_result == price_result

    def test_required_fields_present(self):
        required = {
            "id", "name", "symbol", "icon",
            "price", "market_cap", "market_cap_rank",
            "sparkline", "networks",
        }
        with _patch_httpx(_COINS_ORDI, {"ordinals", "sats-ordinals"}):
            result = get_token_price("ordi")

        for item in result:
            assert required.issubset(item.keys())


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------


class TestApiError:
    def test_raises_on_http_error(self):
        with patch("src.services.coingecko.client.httpx.get") as mock_get:
            resp = MagicMock(spec=httpx.Response)
            resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock()
            )
            mock_get.return_value = resp

            import pytest

            with pytest.raises(httpx.HTTPStatusError):
                get_token_info("ordi")

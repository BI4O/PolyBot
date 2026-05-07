"""Tests for news analyzer."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.news.analyzer import extract_keywords, _fallback_keywords, analyze_market, analyze_trending_markets


def _make_ainvoke(content: str):
    """返回一个 async 函数，模拟 DEEPSEEK_V4_FLASH.ainvoke() 返回带 content 的对象。"""
    async def _ainvoke(*args, **kwargs):
        msg = MagicMock()
        msg.content = content
        return msg
    return _ainvoke


class TestExtractKeywords:
    @pytest.mark.asyncio
    async def test_ai_extracts_keywords(self):
        """AI 正常返回逗号分隔的关键词。"""
        with patch("src.services.news.analyzer.DEEPSEEK_V4_FLASH") as mock_model:
            mock_model.ainvoke = _make_ainvoke("Bitcoin, BTC, 150000, September")
            result = await extract_keywords("Will Bitcoin hit $150K?")
        assert result == ["Bitcoin", "BTC", "150000", "September"]

    @pytest.mark.asyncio
    async def test_ai_failure_falls_back(self):
        """AI 抛出异常时走兜底分词。"""
        with patch("src.services.news.analyzer.DEEPSEEK_V4_FLASH") as mock_model:
            mock_model.ainvoke.side_effect = Exception("API error")
            result = await extract_keywords("Will Bitcoin hit $150K?")
        assert "Bitcoin" in result
        assert "150K" in result
        assert "Will" not in result


class TestFallbackKeywords:
    def test_removes_stop_words(self):
        result = _fallback_keywords("Will Bitcoin hit 150K?")
        assert result == ["Bitcoin", "150K"]

    def test_deduplicates(self):
        result = _fallback_keywords("Bitcoin and Bitcoin price")
        assert result == ["Bitcoin", "price"]

    def test_empty_for_all_stop_words(self):
        result = _fallback_keywords("Will the a an")
        assert result == []


class TestAnalyzeMarket:
    @pytest.mark.asyncio
    async def test_returns_market_with_keywords_and_news(self):
        market = {"slug": "bitcoin-test", "question": "Will Bitcoin hit 150K?"}

        with (
            patch("src.services.news.analyzer.DEEPSEEK_V4_FLASH") as mock_model,
            patch("src.services.news.analyzer.search_news", return_value=[{"title": "Bitcoin rally"}]) as mock_search,
        ):
            mock_model.ainvoke = _make_ainvoke("Bitcoin, BTC")
            result = await analyze_market(market)

        assert result["market"]["slug"] == "bitcoin-test"
        assert result["keywords"] == ["Bitcoin", "BTC"]
        assert len(result["news"]) == 1


class TestAnalyzeTrendingMarkets:
    @pytest.mark.asyncio
    async def test_analyzes_multiple_markets(self):
        mock_markets = [
            {"slug": "m1", "question": "Bitcoin 150K?"},
            {"slug": "m2", "question": "Ethereum upgrade?"},
        ]
        with (
            patch("src.services.polymarket.list_trending_markets", return_value=mock_markets),
            patch("src.services.news.analyzer.DEEPSEEK_V4_FLASH") as mock_model,
            patch("src.services.news.analyzer.search_news", return_value=[]),
        ):
            mock_model.ainvoke = _make_ainvoke("Bitcoin")
            results = await analyze_trending_markets(limit=2)

        assert len(results) == 2
        assert results[0]["market"]["slug"] == "m1"
        assert results[1]["market"]["slug"] == "m2"


class TestExtractKeywordsEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_question_with_ai(self):
        """空字符串传给 AI。"""
        with patch("src.services.news.analyzer.DEEPSEEK_V4_FLASH") as mock_model:
            mock_model.ainvoke = _make_ainvoke("")
            result = await extract_keywords("")
        assert result == []

    @pytest.mark.asyncio
    async def test_ai_returns_single_word_no_commas(self):
        """没有逗号，只有一个词。"""
        with patch("src.services.news.analyzer.DEEPSEEK_V4_FLASH") as mock_model:
            mock_model.ainvoke = _make_ainvoke("  Bitcoin  ")
            result = await extract_keywords("Bitcoin?")
        assert result == ["Bitcoin"]

    @pytest.mark.asyncio
    async def test_ai_returns_extra_whitespace_around_commas(self):
        with patch("src.services.news.analyzer.DEEPSEEK_V4_FLASH") as mock_model:
            mock_model.ainvoke = _make_ainvoke("  Bitcoin  ,  ETH  ,  SOL  ")
            result = await extract_keywords("test")
        assert result == ["Bitcoin", "ETH", "SOL"]

    @pytest.mark.asyncio
    async def test_ai_failure_empty_question_fallback(self):
        """AI 失败且问题为空，兜底返回空。"""
        with patch("src.services.news.analyzer.DEEPSEEK_V4_FLASH") as mock_model:
            mock_model.ainvoke.side_effect = Exception("error")
            result = await extract_keywords("")
        assert result == []


class TestFallbackKeywordsEdgeCases:
    def test_empty_string(self):
        assert _fallback_keywords("") == []

    def test_only_symbols(self):
        assert _fallback_keywords("???,,,!$$") == []

    def test_only_numbers(self):
        """数字保留。"""
        result = _fallback_keywords("100 200 300")
        assert result == ["100", "200", "300"]

    def test_mixed_case_deduplication(self):
        """大小写不同的相同词只保留第一个。"""
        result = _fallback_keywords("BITCOIN Bitcoin bitcoin BTC")
        assert result == ["BITCOIN", "BTC"]

    def test_single_character_filtered(self):
        result = _fallback_keywords("a b c Bitcoin")
        assert result == ["Bitcoin"]

    def test_non_english_characters(self):
        """中文等非英文字符不被过滤。"""
        result = _fallback_keywords("Bitcoin 以太坊 Solana")
        assert result == ["Bitcoin", "以太坊", "Solana"]


class TestAnalyzeMarketEdgeCases:
    @pytest.mark.asyncio
    async def test_missing_question_field(self):
        """market 没有 question 字段不崩溃。"""
        with (
            patch("src.services.news.analyzer.DEEPSEEK_V4_FLASH") as mock_model,
            patch("src.services.news.analyzer.search_news", return_value=[]),
        ):
            mock_model.ainvoke = _make_ainvoke("")
            result = await analyze_market({"slug": "no-question"})

        assert result["market"]["slug"] == "no-question"
        assert result["keywords"] == []

    @pytest.mark.asyncio
    async def test_since_hours_passed_to_search(self):
        """since_hours 透传到 search_news。"""
        with (
            patch("src.services.news.analyzer.DEEPSEEK_V4_FLASH") as mock_model,
            patch("src.services.news.analyzer.search_news", return_value=[]) as mock_search,
        ):
            mock_model.ainvoke = _make_ainvoke("Bitcoin")
            await analyze_market({"slug": "s", "question": "Bitcoin?"}, since_hours=12)

        mock_search.assert_called_once()
        assert mock_search.call_args[1]["since_hours"] == 12

    @pytest.mark.asyncio
    async def test_keywords_empty_skips_search(self):
        """关键词为空时跳过 search_news。"""
        with (
            patch("src.services.news.analyzer.DEEPSEEK_V4_FLASH") as mock_model,
            patch("src.services.news.analyzer.search_news") as mock_search,
        ):
            mock_model.ainvoke = _make_ainvoke("")
            await analyze_market({"slug": "s", "question": ""})

        mock_search.assert_not_called()

    @pytest.mark.asyncio
    async def test_ai_failure_still_returns_result(self):
        """AI 失败走兜底后仍返回 market 结构。"""
        with (
            patch("src.services.news.analyzer.DEEPSEEK_V4_FLASH") as mock_model,
            patch("src.services.news.analyzer.search_news", return_value=[]),
        ):
            mock_model.ainvoke.side_effect = Exception("API error")
            result = await analyze_market({"slug": "s", "question": "Bitcoin price?"})

        assert result["market"]["slug"] == "s"
        assert "Bitcoin" in result["keywords"]


class TestAnalyzeTrendingMarketsEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_market_list(self):
        """API 返回空列表时不报错。"""
        with patch("src.services.polymarket.list_trending_markets", return_value=[]):
            results = await analyze_trending_markets(limit=10)
        assert results == []

    @pytest.mark.asyncio
    async def test_polymarket_api_failure_propagates(self):
        """Polymarket API 异常时透传。"""
        with patch(
            "src.services.polymarket.list_trending_markets",
            side_effect=Exception("Connection refused"),
        ):
            with pytest.raises(Exception, match="Connection refused"):
                await analyze_trending_markets(limit=10)

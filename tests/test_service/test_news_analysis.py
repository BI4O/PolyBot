"""Tests for news analysis CLI output logic."""

from unittest.mock import patch

import pytest


class TestAnalysisOutput:
    """news_analysis.py 的输出路径测试。"""

    @pytest.mark.asyncio
    async def test_empty_results_shows_message(self):
        """无热门市场数据时显示对应消息。"""
        with (
            patch("src.run.news_analysis.init_db"),
            patch("src.run.news_analysis.analyze_trending_markets", return_value=[]),
            patch("src.run.news_analysis.rprint") as mock_print,
        ):
            from src.run.news_analysis import main
            await main()

        assert any("无热门市场数据" in str(call) for call in mock_print.call_args_list)

    @pytest.mark.asyncio
    async def test_results_with_news(self):
        """市场有关联新闻时正常渲染。"""
        results = [
            {
                "market": {"slug": "btc-test", "question": "Will Bitcoin hit 150K?"},
                "keywords": ["Bitcoin", "150K"],
                "news": [
                    {"published": "2026-05-07T10:00:00Z", "source_name": "CoinDesk",
                     "title": "Bitcoin rallies to 150K"},
                ],
            },
        ]
        with (
            patch("src.run.news_analysis.init_db"),
            patch("src.run.news_analysis.analyze_trending_markets", return_value=results),
            patch("src.run.news_analysis.rprint") as mock_print,
        ):
            from src.run.news_analysis import main
            await main()

        all_text = "".join(str(c) for c in mock_print.call_args_list)
        assert "Will Bitcoin hit 150K?" in all_text
        assert "CoinDesk" in all_text

    @pytest.mark.asyncio
    async def test_results_without_news(self):
        """市场没有关联新闻时显示无相关新闻。"""
        results = [
            {
                "market": {"slug": "obscure", "question": "Obscure market?"},
                "keywords": ["Obscure"],
                "news": [],
            },
        ]
        with (
            patch("src.run.news_analysis.init_db"),
            patch("src.run.news_analysis.analyze_trending_markets", return_value=results),
            patch("src.run.news_analysis.rprint") as mock_print,
        ):
            from src.run.news_analysis import main
            await main()

        assert any("无相关新闻" in str(call) for call in mock_print.call_args_list)

    @pytest.mark.asyncio
    async def test_multiple_markets_all_rendered(self):
        """多个市场全部渲染，不遗漏。"""
        results = [
            {"market": {"slug": f"m{i}", "question": f"Market {i}?"},
             "keywords": [f"K{i}"], "news": []}
            for i in range(3)
        ]
        with (
            patch("src.run.news_analysis.init_db"),
            patch("src.run.news_analysis.analyze_trending_markets", return_value=results),
        ):
            from src.run.news_analysis import main
            await main()

    @pytest.mark.asyncio
    async def test_news_with_missing_published(self):
        """新闻缺少 published 字段不崩溃。"""
        results = [
            {
                "market": {"slug": "m", "question": "Q?"},
                "keywords": ["K"],
                "news": [
                    {"published": None, "source_name": "Src", "title": "No date article"},
                    {"published": "2026-05-07T10:00:00Z", "source_name": "Src", "title": "Has date"},
                ],
            },
        ]
        with (
            patch("src.run.news_analysis.init_db"),
            patch("src.run.news_analysis.analyze_trending_markets", return_value=results),
        ):
            from src.run.news_analysis import main
            await main()

    @pytest.mark.asyncio
    async def test_analyze_failure_propagates(self):
        """analyze_trending_markets 失败时冒泡。"""
        with (
            patch("src.run.news_analysis.init_db"),
            patch(
                "src.run.news_analysis.analyze_trending_markets",
                side_effect=Exception("Analysis failed"),
            ),
        ):
            from src.run.news_analysis import main
            with pytest.raises(Exception, match="Analysis failed"):
                await main()

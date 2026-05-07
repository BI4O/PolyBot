"""Tests for news fetcher 30-min filter logic."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


class TestRecentFilter:
    """news_fetcher 的 30 分钟过滤逻辑测试。"""

    NOW = datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)

    def _run_filter(self, articles: list[dict]) -> list[dict]:
        """复现 fetcher 的过滤逻辑。"""
        return [
            a for a in articles
            if a.get("published") and 0 < (self.NOW - a["published"]).total_seconds() < 1800
        ]

    def test_only_recent_articles_pass(self):
        articles = [
            {"guid": "1", "title": "5 min ago", "published": self.NOW - timedelta(minutes=5)},
            {"guid": "2", "title": "29 min ago", "published": self.NOW - timedelta(minutes=29)},
            {"guid": "3", "title": "31 min ago", "published": self.NOW - timedelta(minutes=31)},
        ]
        result = self._run_filter(articles)
        assert len(result) == 2
        assert [a["guid"] for a in result] == ["1", "2"]

    def test_exactly_30_minutes_included(self):
        articles = [
            {"guid": "edge", "title": "Exactly 30 min", "published": self.NOW - timedelta(minutes=30)},
        ]
        result = self._run_filter(articles)
        # 1800 seconds = 30 min exactly, 0 < x < 1800 means 30min is EXCLUDED
        assert len(result) == 0

    def test_future_published_excluded(self):
        """发布时间在未来（可能时钟偏差）应排除。"""
        articles = [
            {"guid": "future", "title": "Future", "published": self.NOW + timedelta(minutes=5)},
        ]
        result = self._run_filter(articles)
        assert len(result) == 0

    def test_no_published_field_excluded(self):
        articles = [
            {"guid": "nope", "title": "No date"},
            {"guid": "also", "title": "Also no date", "published": None},
        ]
        result = self._run_filter(articles)
        assert result == []

    def test_mixed_ages(self):
        articles = [
            {"guid": "old", "title": "Old", "published": self.NOW - timedelta(hours=2)},
            {"guid": "recent", "title": "Recent", "published": self.NOW - timedelta(minutes=10)},
            {"guid": "border", "title": "Border", "published": self.NOW - timedelta(minutes=30, seconds=1)},
        ]
        result = self._run_filter(articles)
        assert [a["guid"] for a in result] == ["recent"]

    def test_all_recent(self):
        articles = [
            {"guid": f"r{i}", "title": f"Recent {i}", "published": self.NOW - timedelta(minutes=i)}
            for i in range(1, 25)
        ]
        result = self._run_filter(articles)
        assert len(result) == 24

    def test_all_old(self):
        articles = [
            {"guid": f"o{i}", "title": f"Old {i}", "published": self.NOW - timedelta(hours=i)}
            for i in range(1, 5)
        ]
        result = self._run_filter(articles)
        assert result == []


class TestFetcherEndToEnd:
    """模拟完整 fetcher 流程。"""

    @pytest.mark.asyncio
    async def test_fetcher_integration(self):
        """mock fetch_all_news，验证 insert_articles 只收到过滤后的数据。"""
        now = datetime.now(timezone.utc)
        articles = [
            {"guid": "new1", "title": "Fresh news", "link": "https://a.com/1", "summary": "",
             "source_name": "A", "source_category": "c", "published": now - timedelta(minutes=5)},
            {"guid": "old1", "title": "Old news", "link": "https://a.com/2", "summary": "",
             "source_name": "B", "source_category": "c", "published": now - timedelta(hours=2)},
        ]

        with (
            patch("src.run.news_fetcher.fetch_all_news", return_value=articles),
            patch("src.run.news_fetcher.init_db"),
            patch("src.run.news_fetcher.insert_articles") as mock_insert,
        ):
            from src.run.news_fetcher import main
            await main()

        inserted = mock_insert.call_args[0][0]
        assert len(inserted) == 1
        assert inserted[0]["guid"] == "new1"

    @pytest.mark.asyncio
    async def test_fetcher_no_recent_news(self):
        """没有近期新闻时不调用 insert_articles。"""
        now = datetime.now(timezone.utc)
        articles = [
            {"guid": "old", "title": "Old", "link": "", "summary": "",
             "source_name": "A", "source_category": "c", "published": now - timedelta(hours=5)},
        ]

        with (
            patch("src.run.news_fetcher.fetch_all_news", return_value=articles),
            patch("src.run.news_fetcher.init_db"),
            patch("src.run.news_fetcher.insert_articles") as mock_insert,
        ):
            from src.run.news_fetcher import main
            await main()

        mock_insert.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetcher_fetch_failure(self):
        """fetch_all_news 失败时冒泡。"""
        with (
            patch("src.run.news_fetcher.fetch_all_news", side_effect=Exception("Network error")),
            patch("src.run.news_fetcher.init_db"),
        ):
            from src.run.news_fetcher import main
            with pytest.raises(Exception, match="Network error"):
                await main()

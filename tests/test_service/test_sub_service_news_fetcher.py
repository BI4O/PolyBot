"""Tests for sub_service_news_fetcher."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


class TestFetchOnce:
    """测试 fetch_once 单次拉取逻辑。"""

    @pytest.mark.asyncio
    async def test_all_articles_passed(self):
        """所有 RSS 文章都传给 insert_articles，不按时间过滤。"""
        now = datetime.now(timezone.utc)
        articles = [
            {"guid": "new1", "title": "Fresh", "link": "https://a.com/1", "summary": "",
             "source_name": "A", "source_category": "c", "published": now - timedelta(minutes=5)},
            {"guid": "old1", "title": "Old", "link": "https://a.com/2", "summary": "",
             "source_name": "B", "source_category": "c", "published": now - timedelta(hours=2)},
        ]

        with (
            patch("src.run.sub_service_news_fetcher.fetch_all_news", return_value=articles),
            patch("src.run.sub_service_news_fetcher.insert_articles") as mock_insert,
        ):
            from src.run.sub_service_news_fetcher import fetch_once
            await fetch_once()

        inserted = mock_insert.call_args[0][0]
        assert len(inserted) == 2
        assert {a["guid"] for a in inserted} == {"new1", "old1"}

    @pytest.mark.asyncio
    async def test_no_articles(self):
        """没有文章时不调用 insert_articles。"""
        with (
            patch("src.run.sub_service_news_fetcher.fetch_all_news", return_value=[]),
            patch("src.run.sub_service_news_fetcher.insert_articles") as mock_insert,
        ):
            from src.run.sub_service_news_fetcher import fetch_once
            result = await fetch_once()

        assert result == 0
        mock_insert.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_failure(self):
        """fetch_all_news 失败时冒泡。"""
        with patch("src.run.sub_service_news_fetcher.fetch_all_news", side_effect=Exception("Network error")):
            from src.run.sub_service_news_fetcher import fetch_once
            with pytest.raises(Exception, match="Network error"):
                await fetch_once()

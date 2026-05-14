"""Tests for RSS news service."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.services.news.client import (
    fetch_all_news,
    fetch_feed,
    fetch_news_by_category,
    load_config,
)

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Test Feed</title>
<item>
<title>Article 1</title>
<link>https://example.com/1</link>
<description>Summary 1</description>
<pubDate>Mon, 06 May 2026 10:00:00 +0000</pubDate>
<guid>https://example.com/1</guid>
</item>
<item>
<title>Article 2</title>
<link>https://example.com/2</link>
<description>Summary 2</description>
<pubDate>Sun, 05 May 2026 10:00:00 +0000</pubDate>
<guid>https://example.com/2</guid>
</item>
</channel>
</rss>"""

_RSS_EMPTY = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Empty Feed</title></channel></rss>"""

_ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>Atom Feed</title>
<entry>
<title>Atom Article</title>
<link href="https://example.com/atom1"/>
<summary>Atom summary</summary>
<published>2026-05-06T10:00:00Z</published>
<id>https://example.com/atom1</id>
</entry>
</feed>"""

_CONFIG_DATA = {
    "sources": [
        {"name": "SourceA", "url": "https://a.com/feed", "category": "crypto", "enabled": True},
        {"name": "SourceB", "url": "https://b.com/feed", "category": "ai", "enabled": True},
        {"name": "SourceC", "url": "https://c.com/feed", "category": "crypto", "enabled": False},
    ],
}


def _mock_http(text: str = "", status: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.text = text
    if status >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            str(status), request=MagicMock(), response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


@pytest.fixture(autouse=True)
def _mock_asyncio_loop():
    """确保异步测试在同一次循环中运行。"""
    yield


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_returns_only_enabled(self):
        with patch("src.services.news.client.yaml.safe_load", return_value=_CONFIG_DATA):
            result = load_config()

        assert len(result) == 2
        assert result[0]["name"] == "SourceA"
        assert result[1]["name"] == "SourceB"

    def test_empty_yaml_returns_empty(self):
        with patch("src.services.news.client.yaml.safe_load", return_value={}):
            result = load_config()
        assert result == []

    def test_no_sources_key_returns_empty(self):
        with patch("src.services.news.client.yaml.safe_load", return_value={"other": []}):
            result = load_config()
        assert result == []

    def test_all_disabled_returns_empty(self):
        data = {"sources": [
            {"name": "A", "url": "https://a.com", "category": "c", "enabled": False},
        ]}
        with patch("src.services.news.client.yaml.safe_load", return_value=data):
            result = load_config()
        assert result == []


# ---------------------------------------------------------------------------
# fetch_feed
# ---------------------------------------------------------------------------


class TestFetchFeed:
    @pytest.mark.asyncio
    async def test_parses_rss(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _mock_http(text=_RSS_XML)
        result = await fetch_feed("https://test.com/feed", client)

        assert len(result) == 2
        assert result[0]["title"] == "Article 1"
        assert result[0]["link"] == "https://example.com/1"
        assert result[0]["summary"] == "Summary 1"
        assert result[0]["published"] is not None
        assert result[0]["guid"] == "https://example.com/1"

    @pytest.mark.asyncio
    async def test_parses_atom(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _mock_http(text=_ATOM_XML)
        result = await fetch_feed("https://test.com/atom", client)

        assert len(result) == 1
        assert result[0]["title"] == "Atom Article"
        assert result[0]["link"] == "https://example.com/atom1"
        assert result[0]["summary"] == "Atom summary"
        assert result[0]["published"] is not None

    @pytest.mark.asyncio
    async def test_http_error_returns_empty(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _mock_http(status=500, text="")
        result = await fetch_feed("https://test.com/feed", client)
        assert result == []

    @pytest.mark.asyncio
    async def test_connection_error_returns_empty(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.side_effect = httpx.ConnectError("connection refused")
        result = await fetch_feed("https://test.com/feed", client)
        assert result == []

    @pytest.mark.asyncio
    async def test_invalid_xml_returns_empty(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _mock_http(text="not xml at all")
        result = await fetch_feed("https://test.com/feed", client)
        assert result == []

    @pytest.mark.asyncio
    async def test_unsupported_format_returns_empty(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _mock_http(
            text="<html><body>not a feed</body></html>"
        )
        result = await fetch_feed("https://test.com/feed", client)
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_feed_returns_empty_list(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get.return_value = _mock_http(text=_RSS_EMPTY)
        result = await fetch_feed("https://test.com/empty", client)
        assert result == []


# ---------------------------------------------------------------------------
# fetch_all_news
# ---------------------------------------------------------------------------


class TestFetchAllNews:
    @pytest.mark.asyncio
    async def test_aggregates_multiple_sources(self):
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = _mock_http(text=_RSS_XML)

        with patch("src.services.news.client.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_all_news(sources=[
                {"name": "A", "url": "https://a.com/feed", "category": "crypto"},
                {"name": "B", "url": "https://b.com/feed", "category": "ai"},
            ])

        assert len(result) == 4  # 2 items × 2 sources

    @pytest.mark.asyncio
    async def test_sorts_by_date_descending(self):
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = _mock_http(text=_RSS_XML)

        with patch("src.services.news.client.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_all_news(sources=[
                {"name": "A", "url": "https://a.com/feed", "category": "crypto"},
            ])

        # Article 1: May 6 → Article 2: May 5
        assert result[0]["title"] == "Article 1"
        assert result[1]["title"] == "Article 2"

    @pytest.mark.asyncio
    async def test_annotates_source_info(self):
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = _mock_http(text=_RSS_XML)

        with patch("src.services.news.client.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_all_news(sources=[
                {"name": "MyFeed", "url": "https://my.com/feed", "category": "defi"},
            ])

        assert result[0]["source_name"] == "MyFeed"
        assert result[0]["source_category"] == "defi"

    @pytest.mark.asyncio
    async def test_empty_sources_returns_empty(self):
        result = await fetch_all_news(sources=[])
        assert result == []

    @pytest.mark.asyncio
    async def test_timeout_skips_slow_source(self):
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        # First call times out, second succeeds
        mock_client.get.side_effect = [
            asyncio.TimeoutError(),
            _mock_http(text=_RSS_XML),
        ]

        with patch("src.services.news.client.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_all_news(sources=[
                {"name": "Slow", "url": "https://slow.com/feed", "category": "crypto"},
                {"name": "Fast", "url": "https://fast.com/feed", "category": "crypto"},
            ])

        assert len(result) == 2  # Slow source skipped
        assert result[0]["source_name"] == "Fast"

    @pytest.mark.asyncio
    async def test_max_per_source_limits_items(self):
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = _mock_http(text=_RSS_XML)

        with patch("src.services.news.client.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_all_news(
                sources=[{"name": "A", "url": "https://a.com", "category": "c"}],
                max_per_source=1,
            )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_all_sources_timeout_returns_empty(self):
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.side_effect = asyncio.TimeoutError()

        with patch("src.services.news.client.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_all_news(sources=[
                {"name": "A", "url": "https://a.com", "category": "c"},
            ])

        assert result == []


# ---------------------------------------------------------------------------
# fetch_news_by_category
# ---------------------------------------------------------------------------


class TestFetchNewsByCategory:
    @pytest.mark.asyncio
    async def test_filters_by_category(self):
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = _mock_http(text=_RSS_XML)

        with (
            patch("src.services.news.client.httpx.AsyncClient", return_value=mock_client),
            patch("src.services.news.client.yaml.safe_load", return_value=_CONFIG_DATA),
        ):
            result = await fetch_news_by_category("ai")

        assert len(result) == 2
        assert result[0]["source_category"] == "ai"
        assert result[0]["source_name"] == "SourceB"


# ---------------------------------------------------------------------------
# fetch_all_news — per-source timeout
# ---------------------------------------------------------------------------


class TestFetchAllNewsTimeout:
    @pytest.mark.asyncio
    async def test_per_source_timeout_is_6_seconds(self):
        """每个源的 asyncio.wait_for 超时为 6 秒。"""
        from src.services.news.client import fetch_all_news as _fn
        import asyncio
        import inspect
        source = inspect.getsource(_fn)

        # 验证 wait_for 调用中的 timeout 参数
        assert "timeout=6.0" in source, (
            f"Expected timeout=6.0 in fetch_all_news, got:\n{source}"
        )

    @pytest.mark.asyncio
    async def test_per_source_timeout_uses_6s(self):
        """验证 6s 超时：超过 6s 的源被跳过，正常的源仍返回数据。"""
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client

        # 第一个源超时（6s），第二个正常
        async def _side_effect(url, **kw):
            if "slow" in str(url):
                await asyncio.sleep(10)  # 超过 6s 会触发 TimeoutError
                raise AssertionError("should not reach")
            return _mock_http(text=_RSS_XML)

        mock_client.get.side_effect = _side_effect

        with patch("src.services.news.client.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_all_news(sources=[
                {"name": "Slow", "url": "https://slow.com/feed", "category": "crypto"},
                {"name": "Fast", "url": "https://fast.com/feed", "category": "crypto"},
            ])

        # 慢源被跳过，快源正常
        assert len(result) == 2
        assert result[0]["source_name"] == "Fast"


# ---------------------------------------------------------------------------
# fetch_latest_news tool — auto-save to DB
# ---------------------------------------------------------------------------


class TestFetchLatestNewsTool:
    """fetch_latest_news 工具抓取后自动写入 DB 的行为。"""

    _ARTICLES = [
        {"guid": "1", "title": "BTC News", "link": "https://a.com/1",
         "summary": "Bitcoin summary", "published": datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc),
         "source_name": "SourceA", "source_category": "crypto"},
        {"guid": "2", "title": "ETH News", "link": "https://a.com/2",
         "summary": "Ethereum summary", "published": datetime(2026, 5, 11, 11, 0, 0, tzinfo=timezone.utc),
         "source_name": "SourceB", "source_category": "crypto"},
    ]

    @pytest.mark.asyncio
    async def test_fetch_saves_to_db(self):
        """抓取后自动调用 init_db + insert_articles 写入 DB。"""
        with (
            patch("src.tools.news.articles.fetch_all_news", return_value=self._ARTICLES),
            patch("src.tools.news.articles._init_db") as mock_init,
            patch("src.tools.news.articles._insert_articles") as mock_insert,
        ):
            from src.tools.news.articles import fetch_latest_news
            result = await fetch_latest_news.ainvoke({})

        # 写入 DB
        mock_init.assert_called_once()
        mock_insert.assert_called_once_with(self._ARTICLES)
        # 仍返回文章
        assert len(result) == 2
        assert result[0]["title"] == "BTC News"

    @pytest.mark.asyncio
    async def test_category_still_saves_to_db(self):
        """按分类抓取也写入 DB。"""
        with (
            patch("src.tools.news.articles.fetch_news_by_category", return_value=self._ARTICLES),
            patch("src.tools.news.articles._init_db") as mock_init,
            patch("src.tools.news.articles._insert_articles") as mock_insert,
        ):
            from src.tools.news.articles import fetch_latest_news
            result = await fetch_latest_news.ainvoke({"category": "crypto"})

        mock_init.assert_called_once()
        mock_insert.assert_called_once_with(self._ARTICLES)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_empty_fetch_does_not_write_db(self):
        """没有抓到文章时，不调用 insert_articles。"""
        with (
            patch("src.tools.news.articles.fetch_all_news", return_value=[]),
            patch("src.tools.news.articles._init_db") as mock_init,
            patch("src.tools.news.articles._insert_articles") as mock_insert,
        ):
            from src.tools.news.articles import fetch_latest_news
            result = await fetch_latest_news.ainvoke({})

        mock_init.assert_not_called()
        mock_insert.assert_not_called()
        assert result == []

    @pytest.mark.asyncio
    async def test_db_failure_still_returns_articles(self):
        """DB 写入失败不应阻塞返回文章。"""
        with (
            patch("src.tools.news.articles.fetch_all_news", return_value=self._ARTICLES),
            patch("src.tools.news.articles._init_db", side_effect=Exception("DB error")),
            patch("src.tools.news.articles._insert_articles"),
        ):
            from src.tools.news.articles import fetch_latest_news
            result = await fetch_latest_news.ainvoke({})

        # 即使 DB 失败，文章仍然返回
        assert len(result) == 2

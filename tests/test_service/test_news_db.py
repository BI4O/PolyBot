"""Tests for news SQLite storage."""
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from src.services.news.db import init_db, get_stats, insert_articles, search_news, close_db

_NOW = datetime.now(timezone.utc)
_RECENT = _NOW - timedelta(hours=1)
_OLD = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _db_fresh():
    """每个测试使用独立临时数据库。"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    os.environ["NEWS_DB_PATH"] = db_path
    init_db()
    yield
    close_db()
    os.unlink(db_path)
    del os.environ["NEWS_DB_PATH"]


class TestInitDB:
    def test_tables_exist_after_init(self):
        conn = sqlite3.connect(os.environ["NEWS_DB_PATH"])
        try:
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        finally:
            conn.close()
        assert "articles" in tables
        assert "articles_fts" in tables


class TestInsertArticles:
    def test_insert_and_query(self):
        articles = [
            {
                "guid": "1", "title": "Bitcoin Rally", "link": "https://a.com/1",
                "summary": "Bitcoin price goes up", "source_name": "A", "source_category": "crypto",
                "published": _RECENT,
            },
        ]
        count = insert_articles(articles)
        assert count == 1
        stats = get_stats()
        assert stats["total"] == 1
        assert stats["sources"][0]["source_name"] == "A"

    def test_duplicate_guid_ignored(self):
        articles = [
            {
                "guid": "dup", "title": "Original", "link": "https://a.com/1",
                "summary": "", "source_name": "A", "source_category": "c",
                "published": _RECENT,
            },
        ]
        insert_articles(articles)
        count = insert_articles(articles)  # same guid again
        assert count == 0
        assert get_stats()["total"] == 1

    def test_missing_published_skipped(self):
        articles = [{"guid": "x", "title": "No date", "link": "", "summary": "", "source_name": "A", "source_category": "c"}]
        count = insert_articles(articles)
        assert count == 0

    def test_cleanup_old_data(self):
        """published 超过 24h 的应被清理。"""
        old = {
            "guid": "old", "title": "Old", "link": "", "summary": "",
            "source_name": "A", "source_category": "c",
            "published": _OLD,
        }
        fresh = {
            "guid": "new", "title": "Fresh", "link": "", "summary": "",
            "source_name": "B", "source_category": "c",
            "published": _RECENT,
        }
        insert_articles([old, fresh])
        stats = get_stats()
        assert stats["total"] == 1
        assert stats["sources"][0]["source_name"] == "B"


class TestSearchNews:
    @staticmethod
    def _make(title: str, guid: str, published=None):
        return {
            "guid": guid, "title": title, "link": f"https://a.com/{guid}",
            "summary": f"About {title}", "source_name": "T", "source_category": "c",
            "published": published or _RECENT,
        }

    def test_fts_finds_by_keyword(self):
        insert_articles([self._make("Bitcoin hits new high", "b1")])
        insert_articles([self._make("Ethereum upgrade live", "e1")])
        results = search_news(["Bitcoin"], since_hours=24)
        assert len(results) == 1
        assert results[0]["title"] == "Bitcoin hits new high"

    def test_or_search_returns_both(self):
        insert_articles([self._make("Bitcoin rally", "b1")])
        insert_articles([self._make("Ethereum rally", "e1")])
        results = search_news(["Bitcoin", "Ethereum"], since_hours=24)
        assert len(results) == 2

    def test_empty_keywords_returns_empty(self):
        assert search_news([]) == []

    def test_time_filter(self):
        insert_articles([self._make("Old news", "o1", published=_OLD)])
        results = search_news(["Old"], since_hours=6)
        assert results == []

    def test_no_match_returns_empty(self):
        insert_articles([self._make("Bitcoin", "b1")])
        results = search_news(["XYZNotFound"], since_hours=24)
        assert results == []

    def test_search_by_summary(self):
        """summary 也同样被 FTS 索引。"""
        insert_articles([{
            "guid": "s1", "title": "Title only", "link": "https://a.com/s1",
            "summary": "Deep dive into blockchain tech", "source_name": "T",
            "source_category": "c",
            "published": _RECENT,
        }])
        results = search_news(["blockchain"], since_hours=24)
        assert len(results) == 1

    def test_fts_syntax_error_returns_empty(self):
        """FTS5 语法错误（如未闭合的引号）不冒泡，返回空。"""
        results = search_news(['"unclosed quote'], since_hours=24)
        assert results == []

    def test_fts_query_reserved_words(self):
        """FTS5 保留字作为关键词不报错（语法错误优雅降级）。"""
        insert_articles([self._make("OR and AND are words", "rw1")])
        # "AND" 是 FTS5 运算符，裸查询会触法语法错误，被捕获后返回空
        results = search_news(["AND"], since_hours=24)
        assert results == []


class TestInsertArticlesEdgeCases:
    def test_empty_list(self):
        """空列表返回 0。"""
        assert insert_articles([]) == 0

    def test_mixed_valid_and_invalid(self):
        """有效和无 published 的混在一起，只算有效的。"""
        articles = [
            {
                "guid": "v1", "title": "Valid", "link": "", "summary": "",
                "source_name": "A", "source_category": "c",
                "published": _RECENT,
            },
            {"guid": "i1", "title": "No date", "link": "", "summary": "", "source_name": "A", "source_category": "c"},
            {"guid": "i2", "title": "Also no date", "link": "", "summary": "", "source_name": "B", "source_category": "c"},
        ]
        assert insert_articles(articles) == 1
        assert get_stats()["total"] == 1

    def test_guid_falls_back_to_link(self):
        """guid 为空时用 link 做唯一键。"""
        a = {
            "guid": "", "title": "No GUID", "link": "https://example.com/1",
            "summary": "", "source_name": "A", "source_category": "c",
            "published": _RECENT,
        }
        assert insert_articles([a]) == 1
        a["title"] = "Duplicate by link"
        assert insert_articles([a]) == 0

    def test_fts_trigger_syncs_on_insert(self):
        """INSERT 后 FTS 自动同步，能从标题里搜到词。"""
        insert_articles([{
            "guid": "tr1", "title": "NVIDIA Partners with Crypto Mining Firm",
            "link": "", "summary": "", "source_name": "A", "source_category": "c",
            "published": _RECENT,
        }])
        assert len(search_news(["NVIDIA"], since_hours=24)) == 1
        assert len(search_news(["Crypto"], since_hours=24)) == 1


class TestInitDBEdgeCases:
    def test_init_db_idempotent(self):
        """多次调用 init_db 不报错。"""
        init_db()  # 第二次调用
        init_db()  # 第三次调用
        conn = sqlite3.connect(os.environ["NEWS_DB_PATH"])
        try:
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        finally:
            conn.close()
        assert "articles" in tables


class TestGetStatsEdgeCases:
    def test_empty_db(self):
        """没有任何数据时 get_stats 返回零。"""
        stats = get_stats()
        assert stats["total"] == 0
        assert stats["sources"] == []

    def test_multiple_sources(self):
        """多个源时按条数降序排列。"""
        articles = [
            {"guid": f"s{i}", "title": f"A{i}", "link": "", "summary": "", "source_name": src, "source_category": "c",
             "published": _RECENT}
            for i, src in enumerate(["B", "A", "B", "A", "A"])
        ]
        insert_articles(articles)
        stats = get_stats()
        assert stats["total"] == 5
        assert stats["sources"][0]["source_name"] == "A"
        assert stats["sources"][0]["cnt"] == 3
        assert stats["sources"][1]["source_name"] == "B"
        assert stats["sources"][1]["cnt"] == 2


class TestCloseDB:
    def test_close_db_idempotent(self):
        """连续调用 close_db 不报错。"""
        close_db()
        close_db()

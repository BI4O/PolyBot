"""RSS 新闻获取服务

用法示例:

    import asyncio
    from src.services.news import fetch_all_news, fetch_news_by_category

    # ── 全量获取 ──
    news = await fetch_all_news()
    for n in news[:5]:
        print(f"[{n['source_name']}] {n['title']}")

    # ── 按分类 ──
    ai_news = await fetch_news_by_category("ai")
    eth_news = await fetch_news_by_category("eth")

    # ── 控制每源数量和超时（内部参数） ──
    # fetch_all_news(max_per_source=5)  → 每源最多取 5 条
    # fetch_all_news(sources=[...])     → 只抓指定的源列表

    # ── 单源调试 ──
    from src.services.news import fetch_feed
    items = await fetch_feed("https://decrypt.co/feed", httpx_client)
    for item in items:
        print(item["title"], item["published"])

    # ── 查看配置 ──
    from src.services.news import load_config
    for src in load_config():
        print(f"[{src['category']}] {src['name']} -> {src['url']}")

    # ── SQLite 缓存与搜索 ──
    from src.services.news import init_db, insert_articles, search_news, get_stats, close_db
    init_db()
    count = insert_articles(await fetch_all_news())
    results = search_news(["Bitcoin", "BTC"], since_hours=6)

    # ── AI 关键词分析 ──
    from src.services.news import extract_keywords, analyze_trending_markets
    kw = await extract_keywords("Will Bitcoin hit $150K?")
    analysis = await analyze_trending_markets(limit=5)
"""

from src.services.news.analyzer import (
    analyze_market,
    analyze_trending_markets,
    extract_keywords,
)
from src.services.news.client import fetch_all_news, fetch_feed, fetch_news_by_category, load_config
from src.services.news.db import close_db, get_stats, init_db, insert_articles, search_news

__all__ = [
    "analyze_market",
    "analyze_trending_markets",
    "close_db",
    "extract_keywords",
    "fetch_all_news",
    "fetch_feed",
    "fetch_news_by_category",
    "get_stats",
    "init_db",
    "insert_articles",
    "load_config",
    "search_news",
]

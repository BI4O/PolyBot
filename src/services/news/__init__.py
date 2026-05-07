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
"""

from src.services.news.client import fetch_all_news, fetch_feed, fetch_news_by_category, load_config

__all__ = [
    "fetch_all_news",
    "fetch_news_by_category",
    "fetch_feed",
    "load_config",
]

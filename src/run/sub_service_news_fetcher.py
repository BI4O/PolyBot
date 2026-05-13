"""RSS 新闻摄入子服务：开机初始化 → 循环拉取 → 存入 SQLite。

用法:
    uv run python -m src.run.sub_service_news_fetcher
"""

import asyncio
import os
from datetime import datetime, timezone

from src.services.news.client import fetch_all_news
from src.services.news.db import init_db, insert_articles


async def fetch_once() -> int:
    """拉取一次 RSS 并落库，返回新增条数。"""
    articles = await fetch_all_news()
    if not articles:
        return 0
    return insert_articles(articles)


async def main() -> None:
    init_db()
    interval = int(os.environ.get("NEWS_FETCH_INTERVAL", "900"))

    while True:
        try:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            print(f"[fetcher] {ts} Fetching...")
            count = await fetch_once()
            print(f"[fetcher] {count} new")
        except Exception as e:
            print(f"[fetcher] Error: {e}")

        await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(main())

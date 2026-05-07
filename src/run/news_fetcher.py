"""每 30 分钟执行：抓取 RSS → 过滤 30min → 存入 SQLite。

用法:
    uv run python -m src.run.news_fetcher
"""

import asyncio
from datetime import datetime, timezone

from src.services.news.client import fetch_all_news
from src.services.news.db import init_db, insert_articles


async def main() -> None:
    init_db()
    articles = await fetch_all_news()
    now = datetime.now(timezone.utc)
    recent = [
        a for a in articles
        if a.get("published") and 0 < (now - a["published"]).total_seconds() < 1800
    ]
    if recent:
        count = insert_articles(recent)
        print(f"[fetcher] 存入 {count}/{len(recent)} 条新闻 (新增 {count})")
    else:
        print("[fetcher] 无近期新闻")


if __name__ == "__main__":
    asyncio.run(main())

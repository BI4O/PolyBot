"""分析热门市场的关联新闻。

用法:
    uv run python -m src.run.news_analysis
"""

import asyncio

from rich import print as rprint

from src.services.news.analyzer import analyze_trending_markets
from src.services.news.db import init_db


async def main() -> None:
    init_db()
    results = await analyze_trending_markets(limit=10)

    if not results:
        rprint("[yellow]无热门市场数据[/yellow]")
        return

    for r in results:
        market = r["market"]
        rprint(f"\n[bold cyan]{market['question']}[/bold cyan]")
        rprint(f"  [yellow]关键词: {', '.join(r['keywords'])}[/yellow]")
        if r["news"]:
            for n in r["news"]:
                ts = (n.get("published") or "?")[:16]
                rprint(f"  [dim]{ts}[/dim] [{n['source_name']}] {n['title']}")
        else:
            rprint("  [dim]无相关新闻[/dim]")


if __name__ == "__main__":
    asyncio.run(main())

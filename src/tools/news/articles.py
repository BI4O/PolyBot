"""Crypto news tools.

Wraps News RSS + SQLite services with langchain tool decorators.
"""

from langchain.tools import tool
from src.services.news import fetch_all_news, fetch_news_by_category
from src.services.news.db import search_news as _search_news_db
from src.services.news.analyzer import analyze_market as _analyze_market


@tool
def search_news(keywords: list[str], since_hours: int = 6, limit: int = 20) -> list[dict]:
    """Search cached news articles by keywords using full-text search.

    Args:
        keywords: List of search terms (e.g. ["Bitcoin", "ETF"])
        since_hours: Only return articles from this many hours ago (default 6)
        limit: Max results (default 20)

    Returns:
        Matching news articles with title, summary, source, and publish date.
    """
    return _search_news_db(keywords, since_hours=since_hours, limit=limit)


@tool
async def fetch_latest_news(category: str | None = None, max_per_source: int = 5) -> list[dict]:
    """Fetch the latest crypto news from RSS feeds.

    Args:
        category: Optional category filter ("ai", "eth", "general", etc.)
        max_per_source: Max articles per RSS source (default 5)

    Returns:
        Fresh news articles sorted by publish time (newest first).
    """
    if category:
        return await fetch_news_by_category(category, max_per_source=max_per_source)
    return await fetch_all_news(max_per_source=max_per_source)


@tool
async def analyze_market_news(market_slug: str) -> dict:
    """Analyze news related to a prediction market.

    Extracts keywords from the market question and searches recent news.

    Args:
        market_slug: Slug of the Polymarket event (e.g. "will-bitcoin-hit-150k-by-september-30")

    Returns:
        Market info, extracted keywords, and matching news articles.
    """
    from src.services.polymarket import get_market_by_slug
    market = get_market_by_slug(market_slug)
    return await _analyze_market(market, since_hours=6)

"""Database query tools.

Provides read-only access to the local news SQLite database.
"""

from langchain.tools import tool
from src.services.news.db import get_stats as _get_db_stats
from src.services.news.db import search_news


@tool
def get_news_stats() -> dict:
    """Get statistics from the news database.

    Returns:
        Total article count and breakdown by source.
    """
    return _get_db_stats()


@tool
def search_news_db(keywords: list[str], since_hours: int = 24, limit: int = 20) -> list[dict]:
    """Search the news database directly.

    Args:
        keywords: Search terms (OR logic between terms)
        since_hours: Lookback window (default 24)
        limit: Max results (default 20)

    Returns:
        Articles matching the query.
    """
    return search_news(keywords, since_hours=since_hours, limit=limit)

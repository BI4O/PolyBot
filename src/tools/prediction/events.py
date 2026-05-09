"""Prediction market tools.

Wraps Polymarket service with langchain tool decorators.
"""

from langchain.tools import tool
from src.services.polymarket import (
    get_market_by_slug,
    list_trending_markets,
    search_events_by_keyword,
)


@tool
def search_events(query: str, limit: int = 5, closed: bool = False) -> list[dict]:
    """Search prediction events by keyword. Returns events containing their markets.

    Args:
        query: Search term (e.g. "bitcoin", "election", "Fed rate")
        limit: Max events to return (default 5)
        closed: Include closed/settled markets (default False, only open markets)

    Returns:
        Events with title, volume, and nested markets with question, odds, and outcome probabilities.
    """
    service_closed = closed if closed else None
    return search_events_by_keyword(query, limit=limit, closed=service_closed)


@tool
def get_trending_events(
    limit: int = 5,
    tag: str | None = None,
    closed: bool = False,
) -> list[dict]:
    """Get the hottest prediction markets by 24h trading volume.

    Args:
        limit: Number of markets to return (default 5)
        tag: Optional category filter (e.g. "crypto", "politics")
        closed: Include closed/settled markets (default False, only open markets)

    Returns:
        Trending markets with question, volume, odds, and outcomes.
    """
    # API 默认返回未结束市场，只在请求已结束市场时才传 closed=True
    service_closed = closed if closed else None
    return list_trending_markets(limit=limit, tag_slug=tag, closed=service_closed)


@tool
def get_event_detail(market_slug: str) -> dict:
    """Get full details for a specific prediction market.

    Args:
        market_slug: URL slug of the market (e.g. "will-bitcoin-hit-150k-by-september-30")

    Returns:
        Full market data including question, outcomes, probabilities, volume, and description.
    """
    return get_market_by_slug(market_slug)

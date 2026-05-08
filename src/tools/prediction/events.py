"""Prediction market tools.

Wraps Polymarket service with langchain tool decorators.
"""

from langchain.tools import tool
from src.services.polymarket import (
    get_market_by_slug,
    list_trending_markets,
    search_markets_by_keyword,
)


@tool
def search_events(query: str, limit: int = 5) -> list[dict]:
    """Search prediction markets by keyword.

    Args:
        query: Search term (e.g. "bitcoin", "election", "Fed rate")
        limit: Max results (default 5)

    Returns:
        Markets with question, volume, odds, and outcome probabilities.
    """
    return search_markets_by_keyword(query, limit=limit, detail=False)


@tool
def get_trending_events(limit: int = 5, tag: str | None = None) -> list[dict]:
    """Get the hottest prediction markets by 24h trading volume.

    Args:
        limit: Number of markets to return (default 5)
        tag: Optional category filter (e.g. "crypto", "politics")

    Returns:
        Trending markets with question, volume, odds, and outcomes.
    """
    return list_trending_markets(limit=limit, tag_slug=tag)


@tool
def get_event_detail(market_slug: str) -> dict:
    """Get full details for a specific prediction market.

    Args:
        market_slug: URL slug of the market (e.g. "will-bitcoin-hit-150k-by-september-30")

    Returns:
        Full market data including question, outcomes, probabilities, volume, and description.
    """
    return get_market_by_slug(market_slug)

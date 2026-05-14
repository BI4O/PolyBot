"""Prediction market tools.

Wraps Polymarket service with langchain tool decorators.
"""

from langchain.tools import tool
from src.services.polymarket import (
    get_event_by_slug,
    list_trending_events,
    search_events_by_keyword,
)
from src.services.polymarket.markets import get_market_by_slug


@tool
async def search_events(query: str, limit: int = 5, closed: bool = False) -> list[dict]:
    """Search prediction events by keyword. Returns events containing their markets.

    Args:
        query: Search term (e.g. "bitcoin", "election", "Fed rate")
        limit: Max events to return (default 5)
        closed: Include closed/settled markets (default False, only open markets)

    Returns:
        Events with title, volume, and nested markets with question, odds, and outcome probabilities.
    """
    service_closed = closed if closed else None
    return await search_events_by_keyword(query, limit=limit, closed=service_closed)


@tool
async def get_trending_events(
    limit: int = 5,
    tag: str | None = None,
    closed: bool = False,
) -> list[dict]:
    """Get the hottest prediction events by total volume.

    Args:
        limit: Number of events to return (default 5)
        tag: Optional category filter (e.g. "crypto", "politics")
        closed: Include closed/settled events (default False, only open events)

    Returns:
        Events with title, volume, and nested markets with question, odds, and outcome probabilities.
    """
    return await list_trending_events(limit=limit, tag_slug=tag, closed=closed)


@tool
async def get_market_detail(market_slug: str) -> dict:
    """Get full details for a specific prediction market.

    Args:
        market_slug: URL slug of the market (e.g. "will-bitcoin-hit-150k-by-september-30")

    Returns:
        Full market data including question, outcomes, probabilities, volume, and description.
    """
    return await get_market_by_slug(market_slug)


@tool
async def get_event_detail(event_slug: str) -> dict | None:
    """Get full details for a prediction event, including all its nested markets.

    Args:
        event_slug: URL slug of the event (e.g. "when-will-bitcoin-hit-150k")

    Returns:
        Event data with title, volume, nested markets, each with question and odds.
        Returns None if no event found with that slug.
    """
    return await get_event_by_slug(event_slug)

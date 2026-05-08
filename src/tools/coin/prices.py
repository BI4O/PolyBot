"""Coin price and market data tools.

Wraps CoinGecko service with langchain tool decorators.
"""

from langchain.tools import tool
from src.services.coingecko import get_token_info


@tool
def search_coins(query: str, topn: int = 5) -> list[dict]:
    """Search for cryptocurrencies by name or symbol.

    Args:
        query: Coin name or symbol (e.g. "bitcoin", "BTC", "ethereum")
        topn: Max results to return (default 5)

    Returns:
        List of coins with id, name, symbol, price, market_cap, and network addresses.
    """
    return get_token_info(query, topn=topn)


@tool
def get_coin_price(query: str, topn: int = 5) -> list[dict]:
    """Get current price and market data for one or more cryptocurrencies.

    Args:
        query: Coin name or symbol (e.g. "bitcoin", "ETH")
        topn: Max results to return (default 5)

    Returns:
        List of coins with price, market_cap_rank, and 7d sparkline data.
    """
    return get_token_info(query, topn=topn)

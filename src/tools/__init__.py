from .coin import search_coins, get_coin_price
from .database import get_news_stats, search_news_db
from .news import analyze_market_news, fetch_latest_news, search_news
from .prediction import get_event_detail, get_market_detail, get_trending_events, search_events

# 所有工具合并列表，供 agent 使用
# hello 工具已归档到 tools/hello/，不再加入主列表
AGENT_TOOLS = [
    # coin
    search_coins,
    get_coin_price,
    # prediction
    search_events,
    get_trending_events,
    get_event_detail,
    get_market_detail,
    # news
    search_news,
    fetch_latest_news,
    analyze_market_news,
    # database
    get_news_stats,
    search_news_db,
]

__all__ = ["AGENT_TOOLS"]

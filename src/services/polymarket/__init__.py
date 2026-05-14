"""Polymarket 市场搜索与查询服务

用法示例:

    from src.services.polymarket import (
        search_events_by_keyword,
        list_markets,
        list_trending_markets,
        list_trending_events,
        list_tags,
        get_tag_by_slug,
        get_market_by_slug,
        get_market_by_id,
        get_market_by_token_addr,
    )

    # ── 关键词搜索（返回 Events，内嵌 Markets）──
    results = search_events("bitcoin", limit=5)
    for ev in results:
        print(ev["title"], ev["volume"])
        for m in ev["markets"]:
            print("  ", m["question"], m["options"][0]["pct"], "%")

    # ── 按条件筛选 ──
    markets = list_markets(
        limit=10,
        detail=False,                # False=精简+实时价格; True=API 原始字段
        tag_slug="crypto",           # 按标签分类
        closed=False,                # 只开未结束的
        order_by="volume24hr",       # 排序字段
        ascending=False,
        volume_num_min=100_000,      # 成交量下限
        liquidity_num_min=50_000,    # 流动性下限
    )
    # order_by 可选: volume_num | liquidity_num | start_date | end_date
    #               | volume24hr | competitive | spread | last_trade_price

    # ── 热门市场（24h 成交量降序）──
    trending = list_trending_markets(limit=5, tag_slug="politics")

    # ── 首页推荐（按总成交量降序，与官网一致）──
    homepage = list_trending_events(limit=5)
    for ev in homepage:
        print(ev["title"], ev["volume"], f'{len(ev["markets"])} markets')

    # ── 标签查询 ──
    tags = list_tags()
    for t in tags:
        print(t["id"], t["slug"])   # 如 7 "crypto", 13 "politics"

    tag_info = get_tag_by_slug("crypto")
    print(tag_info["id"])            # → 7

    # ── 单市场查询 ──
    market = get_market_by_slug("will-bitcoin-hit-150k-by-september-30")
    print(market["question"], market["volume"])

    market = get_market_by_id(12345)
    market = get_market_by_token_addr("0xabc...")
"""

from src.services.polymarket.search import search_events_by_keyword
from src.services.polymarket.markets import (
    get_market_by_id,
    get_market_by_slug,
    get_market_by_token_addr,
    list_markets,
    list_trending_markets,
)
from src.services.polymarket.events import get_event_by_slug, list_trending_events
from src.services.polymarket.tags import get_tag_by_slug, list_tags

__all__ = [
    "search_events_by_keyword",
    "list_markets",
    "list_trending_markets",
    "list_trending_events",
    "list_tags",
    "get_tag_by_slug",
    "get_market_by_slug",
    "get_market_by_id",
    "get_market_by_token_addr",
    "get_event_by_slug",
]

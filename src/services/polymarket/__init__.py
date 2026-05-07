"""Polymarket 市场搜索与查询服务

用法示例:

    from src.services.polymarket import (
        search_markets_by_keyword,
        list_markets,
        list_trending_markets,
        list_tags,
        get_tag_by_slug,
        get_market_by_slug,
        get_market_by_id,
        get_market_by_token_addr,
    )

    # ── 关键词搜索 ──
    results = search_markets_by_keyword("bitcoin", limit=5)
    for m in results:
        print(m["question"], m["volume"])

    # detail=True 返回 API 原始全量字段
    results = search_markets_by_keyword("eth", detail=True)

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

from src.services.polymarket.search import (
    get_market_by_id,
    get_market_by_slug,
    get_market_by_token_addr,
    get_tag_by_slug,
    list_markets,
    list_tags,
    list_trending_markets,
    search_markets_by_keyword,
)

__all__ = [
    "search_markets_by_keyword",
    "list_markets",
    "list_trending_markets",
    "list_tags",
    "get_tag_by_slug",
    "get_market_by_slug",
    "get_market_by_id",
    "get_market_by_token_addr",
]

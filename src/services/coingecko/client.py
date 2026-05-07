import re

import httpx

_SEARCH_URL = "https://www.coingecko.com/en/search_v2"
_API_URL = "https://api.coingecko.com/api/v3"
_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def get_token_info(query: str, topn: int = 5) -> list[dict]:
    """Search tokens by keyword, filtered + sorted, returned as flat items."""
    q = query.lower()

    # 请求 CoinGecko 搜索接口，返回原始 coin 列表
    resp = httpx.get(
        _SEARCH_URL,
        params={"query": query, "vs_currency": "usd"},
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    coins = resp.json().get("coins", [])

    # 过滤：name 或 symbol 包含 query（子串匹配），因为有精确匹配优先排序，误配不会干扰前排结果
    matched = [
        c
        for c in coins
        if re.search(re.escape(query), c.get("name", ""), re.IGNORECASE)
        or re.search(re.escape(query), c.get("symbol", ""), re.IGNORECASE)
    ]

    # 排序：精确匹配（name/symbol 与 query 完全一致）排最前，其余按市值排名升序
    matched.sort(
        key=lambda c: (
            0
            if q == c.get("name", "").lower() or q == c.get("symbol", "").lower()
            else 1,
            c.get("market_cap_rank") or 99999,
        )
    )

    # 只返回 topn 个结果
    matched = matched[:topn]

    # 展平嵌套的 data 字段，只保留前端/下游需要的标准字段
    items = [
        {
            "id": c["id"],
            "name": c["name"],
            "symbol": c["symbol"],
            "icon": c.get("thumb"),
            "price": (c.get("data") or {}).get("price"),
            "market_cap": (c.get("data") or {}).get("market_cap"),
            "market_cap_rank": c.get("market_cap_rank"),
            "sparkline": (c.get("data") or {}).get("sparkline"),
        }
        for c in matched
    ]

    # 一次请求获取所有匹配币种的网络合约地址
    with httpx.Client(headers=_HEADERS) as client:
        coin_ids = {c["id"] for c in matched}
        resp_list = client.get(
            f"{_API_URL}/coins/list",
            params={"include_platform": "true"},
        )
        platform_map = {}
        if resp_list.status_code == 200:
            all_coins = resp_list.json()
            # 构建 {coin_id: {network: address}} 的映射
            for coin in all_coins:
                if coin["id"] in coin_ids and coin.get("platforms"):
                    platform_map[coin["id"]] = {
                        k: v for k, v in coin["platforms"].items() if v
                    }

    for item in items:
        item["networks"] = platform_map.get(item["id"], {})

    return items


def get_token_price(query: str, topn: int = 5) -> list[dict]:
    """Alias for get_token_info — returns flat items with price data."""
    return get_token_info(query, topn=topn)


if __name__ == "__main__":
    from rich import print

    print(get_token_info("BTC"))

"""Polymarket 市场搜索与查询服务."""

import functools
import json
from typing import Literal

import httpx

_GAMMA_URL = "https://gamma-api.polymarket.com"
_CLOB_URL = "https://clob.polymarket.com"
_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def search_markets_by_keyword(q: str, limit: int = 10, detail: bool = False) -> list[dict]:
    """按关键词搜索，返回拍平的市场列表。

    detail=True 时返回 API 原始全量字段；False 时只保留核心字段，
    且 options 中附带实时成交价、赔率倍数和隐含概率。
    """
    resp = httpx.get(
        f"{_GAMMA_URL}/public-search",
        params={"q": q, "limit_per_type": limit},
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    raw = resp.json()
    markets = []
    for event in raw.get("events") or []:
        tags = [
            {k: t[k] for k in ("id", "label", "slug") if k in t}
            for t in (event.get("tags") or [])
        ]
        for m in event.get("markets") or []:
            m = dict(m)
            m["event"] = {"id": event.get("id"), "title": event.get("title")}
            m["_tags"] = tags
            markets.append(m)

    if detail:
        return markets[:limit]

    return _enrich_markets(markets, limit)


def _batch_last_prices(token_ids: list[str]) -> dict[str, dict]:
    """批量拉取多个 token 的最新成交价，一次请求返回全部（最多 500 个）。"""
    if not token_ids:
        return {}
    try:
        resp = httpx.post(
            f"{_CLOB_URL}/last-trades-prices",
            json=[{"token_id": tid} for tid in token_ids],
            headers=_HEADERS,
            timeout=10,
        )
        if resp.status_code == 200:
            return {item["token_id"]: item for item in resp.json()}
    except httpx.HTTPError as e:
        print(f"[polymarket] 批量拉取价格失败: {e}")
    return {}


def _enrich_markets(markets: list[dict], limit: int) -> list[dict]:
    """裁剪市场列表为核心字段，并附上实时成交价和赔率倍数。"""
    # 一次解析 clobTokenIds，避免循环内重复 json.loads
    all_token_ids = set()
    for m in markets:
        tids = json.loads(m.get("clobTokenIds") or "[]")
        m["_tids"] = tids
        all_token_ids.update(tids)
    price_map = _batch_last_prices(list(all_token_ids)) if all_token_ids else {}

    _ORDER = (
        "id", "slug", "question", "event", "options",
        "volume", "startDate", "endDate", "description", "icon",
        "marketMakerAddress", "_tags",
    )
    trimmed = []
    for m in markets[:limit]:
        item = {}
        for k in _ORDER:
            if k == "options":
                outcomes = json.loads(m.get("outcomes") or "[]")
                prices = json.loads(m.get("outcomePrices") or "[]")
                tids = m["_tids"]
                opts = []
                for i in range(min(len(outcomes), len(prices))):
                    opt = {"name": outcomes[i], "price": prices[i]}
                    tid = tids[i] if i < len(tids) else None
                    if tid and tid in price_map and price_map[tid].get("price"):
                        lp = price_map[tid]
                        opt["side"] = lp["side"]
                        opt["last"] = lp["price"]
                        p = float(lp["price"])
                        opt["multiplier"] = round(1 / p, 2) if p > 0 else None
                        opt["pct"] = round(p * 100, 1)
                    opts.append(opt)
                item[k] = opts
            elif k in m:
                item[k] = m[k]
        trimmed.append(item)
    return trimmed


_ORDER_FIELDS = Literal[
    "volume_num", "liquidity_num", "start_date", "end_date",
    "volume24hr", "competitive", "spread", "last_trade_price",
]


def list_markets(
    limit: int = 20,
    offset: int = 0,
    detail: bool = True,
    order_by: _ORDER_FIELDS | None = None,
    ascending: bool = False,
    closed: bool | None = None,
    tag_id: int | None = None,
    tag_slug: str | None = None,
    volume_num_min: float | None = None,
    volume_num_max: float | None = None,
    liquidity_num_min: float | None = None,
    liquidity_num_max: float | None = None,
    start_date_min: str | None = None,
    start_date_max: str | None = None,
    end_date_min: str | None = None,
    end_date_max: str | None = None,
    include_tag: bool | None = None,
) -> list[dict]:
    """按条件筛选市场列表。默认按 id 升序（即创建时间先后）。

    detail=True 返回 API 原始全量字段；False 时只保留核心字段，
    且 options 中附带实时成交价、赔率倍数和隐含概率。

    按标签筛选时，可用 tag_slug（如 "politics"、"crypto"）或 tag_id（数字 ID）。

    参数说明见 https://docs.polymarket.com/api-reference/markets/list-markets
    """
    params: dict = {"limit": limit, "offset": offset}
    if order_by is not None:
        sign = "" if ascending else "-"
        params["order"] = f"{sign}{order_by}"
    if closed is not None:
        params["closed"] = str(closed).lower()
    if tag_slug is not None:
        params["tag_id"] = _resolve_tag_slug(tag_slug)
    elif tag_id is not None:
        params["tag_id"] = tag_id
    if volume_num_min is not None:
        params["volume_num_min"] = volume_num_min
    if volume_num_max is not None:
        params["volume_num_max"] = volume_num_max
    if liquidity_num_min is not None:
        params["liquidity_num_min"] = liquidity_num_min
    if liquidity_num_max is not None:
        params["liquidity_num_max"] = liquidity_num_max
    if start_date_min is not None:
        params["start_date_min"] = start_date_min
    if start_date_max is not None:
        params["start_date_max"] = start_date_max
    if end_date_min is not None:
        params["end_date_min"] = end_date_min
    if end_date_max is not None:
        params["end_date_max"] = end_date_max
    if include_tag is not None:
        params["include_tag"] = str(include_tag).lower()

    resp = httpx.get(
        f"{_GAMMA_URL}/markets",
        params=params,
        headers=_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    raw = resp.json()
    if not detail:
        return _enrich_markets(raw, limit)
    return raw


def list_trending_markets(limit: int = 10, tag_slug: str | None = None) -> list[dict]:
    """按 24h 成交量降序返回热门市场，可指定 tag_slug 限定分类。"""
    return list_markets(
        limit=limit, detail=False, order_by="volume24hr", ascending=False,
        tag_slug=tag_slug,
    )


def list_tags(limit: int = 100) -> list[dict]:
    """获取所有可用标签，每个标签含 id、label、slug。"""
    resp = httpx.get(
        f"{_GAMMA_URL}/tags",
        params={"limit": limit},
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_tag_by_slug(slug: str) -> dict:
    """通过 slug 获取标签信息（含 id、label 等）。"""
    resp = httpx.get(
        f"{_GAMMA_URL}/tags/slug/{slug}",
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


@functools.cache
def _resolve_tag_slug(slug: str) -> int:
    """将 tag slug 解析为数字 ID，供 list_markets 使用。结果缓存避免重复 HTTP 请求。"""
    return int(get_tag_by_slug(slug)["id"])


def get_market_by_slug(slug: str) -> dict:
    """通过 slug 获取单个市场的完整信息。"""
    resp = httpx.get(
        f"{_GAMMA_URL}/markets/slug/{slug}",
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_market_by_id(market_id: int) -> dict:
    """通过数字 ID 获取单个市场的完整信息。"""
    resp = httpx.get(
        f"{_GAMMA_URL}/markets/{market_id}",
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_market_by_token_addr(token_addr: str) -> dict:
    """通过 token 地址（token ID）获取所属市场信息。"""
    resp = httpx.get(
        f"{_CLOB_URL}/markets-by-token/{token_addr}",
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    from rich import print as rprint

    rprint("=== search_markets_by_keyword('bitcoin', limit=3) ===")
    rprint(search_markets_by_keyword("bitcoin", limit=3))

    rprint("\n=== list_trending_markets(limit=3) ===")
    rprint(list_trending_markets(limit=3))

    rprint("\n=== get_market_by_slug('will-bitcoin-hit-150k-by-september-30') ===")
    rprint(get_market_by_slug("will-bitcoin-hit-150k-by-september-30"))

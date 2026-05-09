"""Polymarket 市场查询服务（列表、筛选、单个查询）。"""

from typing import Literal

import httpx

from src.services.polymarket import utils
from src.services.polymarket.tags import resolve_tag_slug

_ORDER_FIELDS = Literal[
    "volume_num",
    "liquidity_num",
    "start_date",
    "end_date",
    "volume24hr",
    "competitive",
    "spread",
    "last_trade_price",
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
        params["tag_id"] = resolve_tag_slug(tag_slug)
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
        f"{utils._GAMMA_URL}/markets",
        params=params,
        headers=utils._HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    raw = resp.json()
    if not detail:
        return utils.enrich_markets(raw, limit)
    return raw


def list_trending_markets(
    limit: int = 10,
    tag_slug: str | None = None,
    closed: bool | None = None,
) -> list[dict]:
    """按 24h 成交量降序返回热门市场，可指定 tag_slug 限定分类。"""
    return list_markets(
        limit=limit,
        detail=False,
        order_by="volume24hr",
        ascending=False,
        tag_slug=tag_slug,
        closed=closed,
    )


def get_market_by_slug(slug: str) -> dict:
    """通过 slug 获取单个市场的完整信息。"""
    resp = httpx.get(
        f"{utils._GAMMA_URL}/markets/slug/{slug}",
        headers=utils._HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_market_by_id(market_id: int) -> dict:
    """通过数字 ID 获取单个市场的完整信息。"""
    resp = httpx.get(
        f"{utils._GAMMA_URL}/markets/{market_id}",
        headers=utils._HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_market_by_token_addr(token_addr: str) -> dict:
    """通过 token 地址（token ID）获取所属市场信息。"""
    resp = httpx.get(
        f"{utils._CLOB_URL}/markets-by-token/{token_addr}",
        headers=utils._HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()

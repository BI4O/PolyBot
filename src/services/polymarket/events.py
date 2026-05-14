"""Polymarket 热门事件（对齐官网首页推荐）。"""

import json

import httpx

from src.services.polymarket import utils


async def list_trending_events(
    limit: int = 10,
    tag_slug: str | None = None,
    closed: bool = False,
) -> list[dict]:
    """按总成交量降序返回热门事件列表，与 Polymarket 官网首页推荐一致。

    底层使用 ``events/keyset`` 接口（首页实际使用的端点），排序方式与官网一致。
    每个事件包含其下所有活跃市场，市场附带实时成交价和赔率倍数。

    Args:
        limit: 返回事件数量上限（默认 10）。
        tag_slug: 按标签分类过滤，如 "politics"、"sports"、"crypto"。
        closed: 是否包含已结束的事件（默认 False，只返回未结束的）。

    Returns:
        按总成交量降序排列的事件列表，每个事件结构::

            {
                "id": "30829",
                "title": "2028年民主党总统候选人",
                "slug": "democratic-presidential-nominee-2028",
                "volume": 1132399886.79,
                "image": "https://...",
                "closed": False,
                "tags": [{"id": "2", "label": "政治", "slug": "politics"}, ...],
                "markets": [
                    {
                        "id": "559657",
                        "question": "斯蒂芬·A·史密斯会赢得2028年民主党总统提名吗？",
                        "volume": "12345000",
                        "options": [
                            {"name": "是", "price": "0.0105",
                             "last": "0.0108", "side": "BUY",
                             "multiplier": 92.59, "pct": 1.1},
                            {"name": "否", "price": "0.9895",
                             "last": "0.9892", "side": "SELL",
                             "multiplier": 1.01, "pct": 98.9},
                        ],
                    },
                ],
            }
    """
    params: dict = {
        "limit": 50,
        "order": "volume",
        "ascending": "false",
        "closed": str(closed).lower(),
        "locale": "zh",
    }
    if tag_slug is not None:
        params["tag_slug"] = tag_slug

    async with httpx.AsyncClient(headers=utils._HEADERS) as client:
        resp = await client.get(
            f"{utils._GAMMA_URL}/events/keyset",
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json()
    events = raw.get("events") or raw.get("data") or []

    _TAG_FIELDS = ("id", "label", "slug")

    result: list[dict] = []
    for ev in events:
        if len(result) >= limit:
            break

        enriched = []
        for m in ev.get("markets") or []:
            if utils.is_market_closed(m) != closed:
                continue
            item = {k: m[k] for k in _MK_BROWSE if k in m}
            enriched.append(item)

        enriched.sort(key=lambda m: float(m.get("volume", 0) or 0), reverse=True)

        result.append(
            {
                "id": ev.get("id"),
                "title": ev.get("title"),
                "slug": ev.get("slug"),
                "volume": float(ev.get("volume", 0)),
                "image": ev.get("image"),
                "closed": ev.get("closed", False),
                "tags": [
                    {k: t[k] for k in _TAG_FIELDS if k in t}
                    for t in (ev.get("tags") or [])
                ],
                "markets": enriched,
            }
        )

    return result


async def get_event_by_slug(slug: str) -> dict | None:
    """通过 event slug 获取单个事件的完整信息。

    GET /events?slug={slug} 返回数组，取首项。
    返回结构与 ``list_trending_events`` 一致（含 nested enriched markets）。
    查不到返回 None。

    Args:
        slug: 事件的 URL slug，如 "when-will-bitcoin-hit-150k"。

    Returns:
        Enriched event dict，或 None（未找到）。
    """
    params: dict = {"slug": slug}
    async with httpx.AsyncClient(headers=utils._HEADERS) as client:
        resp = await client.get(
            f"{utils._GAMMA_URL}/events",
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json()
    if isinstance(raw, list):
        events = raw
    else:
        events = raw.get("events") or raw.get("data") or []
    if not events:
        return None

    ev = events[0]

    # 收集 clobTokenIds 拉取实时价格
    all_token_ids: set[str] = set()
    for m in ev.get("markets") or []:
        tids = json.loads(m.get("clobTokenIds") or "[]")
        m["_tids"] = tids
        all_token_ids.update(tids)
    price_map = await utils.batch_last_prices_async(list(all_token_ids)) if all_token_ids else {}

    _MK_ORDER = (
        "id", "slug", "question", "options", "volume",
        "startDate", "endDate", "description", "icon",
    )
    _TAG_FIELDS = ("id", "label", "slug")

    enriched_markets = []
    for m in ev.get("markets") or []:
        item = {}
        for k in _MK_ORDER:
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
        enriched_markets.append(item)

    enriched_markets.sort(key=lambda x: float(x.get("volume", 0) or 0), reverse=True)

    return {
        "id": ev.get("id"),
        "title": ev.get("title"),
        "slug": ev.get("slug"),
        "volume": float(ev.get("volume", 0)),
        "image": ev.get("image"),
        "closed": ev.get("closed", False),
        "tags": [
            {k: t[k] for k in _TAG_FIELDS if k in t}
            for t in (ev.get("tags") or [])
        ],
        "markets": enriched_markets,
    }


if __name__ == "__main__":
    import asyncio
    from rich import print as rprint

    # uv run -m src.services.polymarket.events

    async def _main():
        rprint("=== list_trending_events(limit=5) ===")
        result = await list_trending_events(limit=5)
        for ev in result:
            ev_vol = ev["volume"]
            print(
                f"\n[Event] {ev['title']}  (volume={ev_vol:,.0f}, total markets={len(ev['markets'])})"
            )
            for m in ev["markets"][:5]:
                mv = float(m.get("volume", 0) or 0)
                pct = (mv / ev_vol * 100) if ev_vol > 0 else 0
                outcome = ", ".join(
                    f"{o.get('name', '')}={o.get('pct', '?')}%"
                    for o in m.get("options", [])[:2]
                )
                print(f"  [{pct:4.1f}%] {m['question']}  | {outcome}")
            if len(ev["markets"]) > 5:
                print(f"  ... 共 {len(ev['markets'])} 个市场")

    asyncio.run(_main())

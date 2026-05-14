"""Polymarket 关键词搜索服务（返回 Events 级别）。"""

import httpx

from src.services.polymarket import utils


async def search_events_by_keyword(
    q: str,
    limit: int = 10,
    closed: bool | None = None,
) -> list[dict]:
    """按关键词搜索事件，返回 Event 列表（内嵌 enriched Markets）。

    与官网搜索行为一致：输入关键词，返回匹配的事件，每个事件包含其下的市场。
    市场附带实时成交价、赔率倍数和隐含概率。

    Args:
        q: 搜索关键词，如 "bitcoin"、"election"、"UFO"。
        limit: 返回事件数量上限（默认 10）。
        closed: 是否包含已结束的市场。None=不过滤，False=只开未结束的，True=只已结束。

    Returns:
        事件列表，结构同 ``list_trending_events``。每个事件含 ``markets`` 列表。
    """
    async with httpx.AsyncClient(headers=utils._HEADERS) as client:
        resp = await client.get(
            f"{utils._GAMMA_URL}/public-search",
            params={"q": q, "limit_per_type": limit},
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json()
    events = raw.get("events") or []

    _MK_BROWSE = ("id", "slug", "question", "volume")
    _TAG_FIELDS = ("id", "label", "slug")

    result: list[dict] = []
    for ev in events:
        if len(result) >= limit:
            break

        enriched = []
        for m in ev.get("markets") or []:
            if closed is not None and utils.is_market_closed(m) != closed:
                continue
            item = {k: m[k] for k in _MK_BROWSE if k in m}
            enriched.append(item)

        enriched.sort(key=lambda x: float(x.get("volume", 0) or 0), reverse=True)

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


if __name__ == "__main__":
    import asyncio
    from rich import print as rprint

    # uv run -m src.services.polymarket.search

    async def _main():
        for keyword in ("taiwan",):
            rprint(f"\n=== search_events_by_keyword('{keyword}', limit=2) ===")
            result = await search_events_by_keyword(keyword, limit=10)
            for ev in result:
                ev_vol = ev["volume"]
                print(
                    f"[Event] {ev['title']}  (volume={ev_vol:,.0f}, markets={len(ev['markets'])})"
                )
                for m in ev["markets"][:3]:
                    mv = float(m.get("volume", 0) or 0)
                    pct = (mv / ev_vol * 100) if ev_vol > 0 else 0
                    outcomes = ", ".join(
                        f"{o.get('name', '')}={o.get('pct', '?')}%"
                        for o in m.get("options", [])[:2]
                    )
                    print(f"  [{pct:4.1f}%] {m['question']}  | {outcomes}")
                if len(ev["markets"]) > 3:
                    print(f"  ... 共 {len(ev['markets'])} 个市场")

    asyncio.run(_main())

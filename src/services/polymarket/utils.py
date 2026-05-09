"""Polymarket 服务共享工具（常量、辅助函数）。"""

import asyncio
import json
from datetime import datetime, timezone

import httpx

_GAMMA_URL = "https://gamma-api.polymarket.com"
_CLOB_URL = "https://clob.polymarket.com"
_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def is_market_closed(market: dict) -> bool | None:
    """判断市场是否已关闭/结算。

    优先读取 API 原生的 ``closed`` 字段，回退到 ``endDate`` 与当前时间比较。
    两个字段都不存在时返回 ``None``（不确定）。
    """
    closed = market.get("closed")
    if closed is not None:
        if isinstance(closed, str):
            return closed.lower() == "true"
        return bool(closed)
    end = market.get("endDate")
    if end:
        try:
            dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            return dt < datetime.now(timezone.utc)
        except (ValueError, AttributeError):
            pass
    return None


def batch_last_prices(token_ids: list[str]) -> dict[str, dict]:
    """批量拉取多个 token 的最新成交价，自动按 500 个一组并发请求。"""
    if not token_ids:
        return {}

    _MAX = 500
    chunks = [token_ids[i : i + _MAX] for i in range(0, len(token_ids), _MAX)]

    async def _fetch(
        client: httpx.AsyncClient, batch: list[str]
    ) -> dict[str, dict]:
        try:
            resp = await client.post(
                f"{_CLOB_URL}/last-trades-prices",
                json=[{"token_id": tid} for tid in batch],
                timeout=10,
            )
            if resp.status_code == 200:
                return {item["token_id"]: item for item in resp.json()}
        except httpx.HTTPError as e:
            print(f"[polymarket] 拉取价格失败: {e}")
        return {}

    async def _run() -> dict[str, dict]:
        async with httpx.AsyncClient(headers=_HEADERS) as client:
            results = await asyncio.gather(*[_fetch(client, c) for c in chunks])
            merged: dict[str, dict] = {}
            for r in results:
                merged.update(r)
            return merged

    return asyncio.run(_run())


_MARKET_ORDER = (
    "id",
    "slug",
    "question",
    "event",
    "options",
    "volume",
    "startDate",
    "endDate",
    "description",
    "icon",
    "marketMakerAddress",
    "_tags",
)


def enrich_markets(markets: list[dict], limit: int) -> list[dict]:
    """裁剪市场列表为核心字段，并附上实时成交价和赔率倍数。"""
    all_token_ids = set()
    for m in markets:
        tids = json.loads(m.get("clobTokenIds") or "[]")
        m["_tids"] = tids
        all_token_ids.update(tids)
    price_map = batch_last_prices(list(all_token_ids)) if all_token_ids else {}

    trimmed = []
    for m in markets[:limit]:
        item = {}
        for k in _MARKET_ORDER:
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

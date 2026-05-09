"""Polymarket 标签查询服务。"""

import functools

import httpx

from src.services.polymarket import utils


def list_tags(limit: int = 100) -> list[dict]:
    """获取所有可用标签，每个标签含 id、label、slug。"""
    resp = httpx.get(
        f"{utils._GAMMA_URL}/tags",
        params={"limit": limit},
        headers=utils._HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_tag_by_slug(slug: str) -> dict:
    """通过 slug 获取标签信息（含 id、label 等）。"""
    resp = httpx.get(
        f"{utils._GAMMA_URL}/tags/slug/{slug}",
        headers=utils._HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


@functools.cache
def resolve_tag_slug(slug: str) -> int:
    """将 tag slug 解析为数字 ID，供 list_markets 使用。结果缓存避免重复 HTTP 请求。"""
    return int(get_tag_by_slug(slug)["id"])

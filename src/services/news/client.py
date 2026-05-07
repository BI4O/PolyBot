"""RSS 新闻获取服务"""

from __future__ import annotations

import asyncio
import email.utils
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import httpx
import yaml

_CONFIG_PATH = Path(__file__).parent / "rss_config.yaml"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}
_TIMEOUT = 15.0
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


def load_config() -> list[dict[str, Any]]:
    """从 YAML 加载启用的 RSS 源列表"""
    raw = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    return [s for s in raw.get("sources", []) if s.get("enabled", True)]


def _parse_date(date_str: str | None) -> datetime | None:
    """尝试多种格式解析 RSS 日期"""
    if not date_str:
        return None
    # RFC 2822 (RSS 2.0)
    try:
        return email.utils.parsedate_to_datetime(date_str)
    except (ValueError, TypeError):
        pass
    # ISO 8601 (Atom)
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt
    except (ValueError, TypeError):
        pass
    return None


def _parse_rss_items(root: ElementTree.Element) -> list[dict[str, Any]]:
    """解析 RSS 2.0 格式"""
    items = []
    for item in root.findall(".//channel/item"):
        title = item.findtext("title")
        link = item.findtext("link")
        desc = item.findtext("description")
        pub_date = item.findtext("pubDate")
        items.append({
            "title": title.strip() if title else "",
            "link": link.strip() if link else "",
            "summary": desc.strip() if desc else "",
            "published": _parse_date(pub_date),
            "guid": item.findtext("guid") or link or "",
        })
    return items


def _parse_atom_items(root: ElementTree.Element) -> list[dict[str, Any]]:
    """解析 Atom 格式"""
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = []
    for entry in root.findall("atom:entry", ns):
        title = entry.findtext("atom:title", "", ns)
        link_el = entry.find("atom:link", ns)
        link = link_el.get("href") if link_el is not None else ""
        summary_el = entry.find("atom:summary", ns)
        if summary_el is None:
            summary_el = entry.find("atom:content", ns)
        summary = (summary_el.text or "") if summary_el is not None else ""
        updated = entry.findtext("atom:updated", "", ns)
        published = entry.findtext("atom:published", updated, ns)
        items.append({
            "title": title.strip() if title else "",
            "link": link.strip() if link else "",
            "summary": summary.strip() if summary else "",
            "published": _parse_date(published),
            "guid": entry.findtext("atom:id", "", ns) or link,
        })
    return items


def _parse_feed_xml(xml_text: str, url: str) -> list[dict[str, Any]]:
    """解析 XML 为 feed 条目（纯 CPU 操作，保持同步）"""
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as e:
        print(f"[news] XML 解析失败: {url} — {e}")
        return []

    if root.tag == "rss":
        return _parse_rss_items(root)
    if root.tag == "{http://www.w3.org/2005/Atom}feed":
        return _parse_atom_items(root)

    if root.find(".//item") is not None:
        return _parse_rss_items(root)
    if root.find("{http://www.w3.org/2005/Atom}entry") is not None:
        return _parse_atom_items(root)

    print(f"[news] 不支持的 feed 格式: {url} (root: {root.tag})")
    return []


async def fetch_feed(url: str, client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """异步获取并解析单个 RSS/Atom feed"""
    try:
        resp = await client.get(url)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f"[news] 请求失败: {url} — {e}")
        return []

    return _parse_feed_xml(resp.text, url)


async def fetch_all_news(
    sources: list[dict[str, Any]] | None = None,
    max_per_source: int = 10,
) -> list[dict[str, Any]]:
    """并发获取所有启用 RSS 源的最新新闻，按时间降序排列"""
    if sources is None:
        sources = load_config()

    limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
    async with httpx.AsyncClient(
        headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True, limits=limits
    ) as client:

        async def fetch_one(source: dict[str, Any]) -> list[dict[str, Any]] | None:
            try:
                items = await asyncio.wait_for(
                    fetch_feed(source["url"], client), timeout=4.0
                )
            except asyncio.TimeoutError:
                print(f"[news] 超时: {source['name']}")
                return None
            for item in items:
                item["source_name"] = source["name"]
                item["source_category"] = source.get("category", "")
            return items[:max_per_source]

        tasks = [asyncio.create_task(fetch_one(s)) for s in sources]
        results = await asyncio.gather(*tasks)

    all_news = []
    for items in results:
        if items is not None:
            all_news.extend(items)

    all_news.sort(
        key=lambda x: x.get("published") or _EPOCH,
        reverse=True,
    )
    return all_news


async def fetch_news_by_category(
    category: str,
    max_per_source: int = 10,
) -> list[dict[str, Any]]:
    """按分类获取新闻"""
    sources = [s for s in load_config() if s.get("category") == category]
    return await fetch_all_news(sources=sources, max_per_source=max_per_source)


if __name__ == "__main__":
    from rich import print as rprint

    async def main():
        news = await fetch_all_news()
        rprint(f"共获取 {len(news)} 条新闻")
        for n in news[:15]:
            published = n.get("published")
            rprint(f"[dim]{published}[/dim] [cyan]{n['source_name']}[/cyan] {n['title']}")

    asyncio.run(main())

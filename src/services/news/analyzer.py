"""Polymarket 市场关键词提取与新闻搜索。"""

from langchain_core.messages import HumanMessage
from src.conf.agent_models import DEEPSEEK_V4_FLASH
from src.services.news.db import search_news

_EXTRACT_PROMPT = """\
从以下 Polymarket 市场标题中提取 3-6 个关键词，用于搜索相关新闻。
考虑常见同义词和简写（如 Bitcoin->BTC, $150K->150000）。
只返回关键词，逗号分隔，不要序号和解释。

标题: {question}
关键词:"""

_STOP_WORDS = {
    "will", "the", "a", "an", "by", "to", "of", "in", "for", "on", "and", "or",
    "be", "is", "are", "this", "that", "before", "after", "hit", "reach", "what",
    "who", "where", "when", "how", "does", "do", "have", "has", "not", "at",
    "with", "from", "it", "its", "up", "down", "out", "off", "over", "into",
}


async def extract_keywords(question: str) -> list[str]:
    """调用 DeepSeek 从市场标题提取关键词列表。"""
    try:
        msg = await DEEPSEEK_V4_FLASH.ainvoke(
            [HumanMessage(content=_EXTRACT_PROMPT.format(question=question))]
        )
        raw = msg.content.strip() if isinstance(msg.content, str) else ""
        return [k.strip() for k in raw.split(",") if k.strip()]
    except Exception as e:
        print(f"[analyzer] AI 关键词提取失败 ({question[:40]}...): {e}")
        return _fallback_keywords(question)


def _fallback_keywords(question: str) -> list[str]:
    """AI 失败时的兜底：去掉停用词和标点，取剩余单词。"""
    for ch in "?.,!$%":
        question = question.replace(ch, "")
    words = question.split()
    seen = set()
    result = []
    for w in words:
        if w.lower() not in _STOP_WORDS and len(w) > 1 and w.lower() not in seen:
            seen.add(w.lower())
            result.append(w)
    return result


async def analyze_market(market: dict, since_hours: int = 6) -> dict:
    """分析单个市场：提取关键词 + 搜索新闻。"""
    question = market.get("question", "")
    keywords = await extract_keywords(question)
    news = search_news(keywords, since_hours=since_hours) if keywords else []
    return {"market": {"slug": market.get("slug"), "question": question}, "keywords": keywords, "news": news}


async def analyze_trending_markets(limit: int = 10, since_hours: int = 6) -> list[dict]:
    """获取热门市场，逐个分析关键词并搜索相关新闻。"""
    from src.services.polymarket import list_trending_markets
    markets = list_trending_markets(limit=limit)
    results = []
    for m in markets:
        result = await analyze_market(m, since_hours=since_hours)
        results.append(result)
    return results

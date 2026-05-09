import httpx
from langchain.agents.middleware import ToolRetryMiddleware

# 指数退避重试：对 Polymarket API 工具的网络错误进行重试
# 首次失败等 1s，后续 3 倍递增，最多重试 2 次
POLYMARKET_RETRY = ToolRetryMiddleware(
    max_retries=2,
    initial_delay=1.0,
    backoff_factor=3.0,
    tools=["search_events", "get_trending_events", "get_event_detail"],
    retry_on=(httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError),
)

__all__ = ["POLYMARKET_RETRY"]

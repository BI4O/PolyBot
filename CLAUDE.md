# Deep Agent Project

## 包管理

本项目使用 **uv** 管理依赖。**禁止使用 `pip`**。

```bash
uv add <package>          # 安装依赖并写入 pyproject.toml
uv add --dev <package>    # 安装开发依赖
uv remove <package>       # 移除依赖
uv sync                   # 同步环境
uv run <script>           # 运行脚本
```

## 项目结构

```
src/
├── agent/     # AI 分析决策
├── service/   # 第三方服务对接（新闻、交易等）
└── run/       # 启动入口（如 uv run -m src.run.fastapi）
tests/
├── test_agent/
└── test_service/
```

## DeepSeek reasoning_content 兼容性

`ChatOpenAI` 使用 OpenAI 标准 schema，不识别 DeepSeek 返回的 `reasoning_content`（非标准字段），导致多轮对话报错 400：

```
The `reasoning_content` in the thinking mode must be passed back to the API.
```

**根因：** `langchain_openai` 的 `_convert_dict_to_message`（入站）不提取 `reasoning_content` 到 `additional_kwargs`；`_convert_message_to_dict`（出站）也不从 `additional_kwargs` 写回请求 dict。DeepSeek 在第二轮 API 调用时发现缺少 `reasoning_content` 就拒绝。

**修复位置：** `src/conf/agent_models.py` — 两个 monkey patch：

- **inbound** — 拦截 `_convert_dict_to_message`，用 `isinstance(msg, AIMessage)` 判断后提取 `reasoning_content` 到 `additional_kwargs`（注意不能用 `msg.type == "assistant"`，因为 `AIMessage.type` 返回 `"ai"`）。
- **outbound** — 拦截 `_convert_message_to_dict`，检查 `additional_kwargs` 中的 `reasoning_content` 并写回请求 dict。

只要 `agent_models` 在模型实例化前被 import，patch 即可生效。当前 `AGENT_BACKEND` 和 `base_agent` 的 import 链已经保证这个顺序。

## Git 提交流程

**禁止直接 add 和 commit。** 所有改动完成后：
1. 先让我检查一遍改动
2. 我确认没问题后，由我提议 `git add` 哪些文件
3. 等我确认 **"好，提交吧"** 之后再执行 commit

## langgraph dev 注意事项

**Windows 上 `langgraph dev` 的 Ctrl+C 是假的**——它用 `os.killpg`（Unix only）杀子进程，Windows 无效。必须手动杀端口。

### 杀僵尸进程

```bash
# 1. 查出占用 2024 端口的进程 PID
netstat -ano | findstr :2024

# 2. 强制杀掉每个 LISTENING 的 PID
taskkill /F /PID <PID> /T

# 3. 确认端口已释放
netstat -ano | findstr :2024
```

⚠️ 如果 `taskkill` 无效（进程已死但端口不释放），重启终端即可。

### 正确的启动方式（推荐）

```bash
# 自动杀僵尸 + 启动，端口被占则自增
uv run -m src.run.langgraph

# 指定端口
uv run -m src.run.langgraph 2025
```

支持在 `src/run/langgraph.py` 顶部修改默认 `PORT`。

## Polymarket API 概念

### Gamma vs CLOB

| API | 用途 | 需认证？ |
|-----|------|----------|
| **Gamma** (`gamma-api.polymarket.com`) | 浏览市场/事件/标签/搜索 | 不需要 |
| **CLOB** (`clob.polymarket.com`) | 订单簿、价格、下单/撤单 | 读公开，写需要 |

### Event 与 Market

- **Event** = 容器，组织一个或多个相关 Market，**本身不可交易**
- **Market** = 最小可交易单元，一个 Yes/No 二元问题
- 每个 Market 有 Yes/No 两种 **Token**（ERC1155 代币），CLOB 上实际交易的是 Token

### 三种获取市场数据策略

1. **By Slug** — 知道 URL slug 直接取
2. **By Tags** — `tag_id` / `tag_slug` 按分类过滤
3. **Via Events** — 拿活跃事件（`active=true&closed=false`），响应自带 markets

### 分页

| 方式 | 适用端点 |
|------|----------|
| `limit + offset` | `/markets`、`/tags` 等 |
| **keyset cursor** | `/events/keyset` — 响应带 `next_cursor`，传 `after_cursor` 翻页，**不接收 offset** |

### 频率限制（关键）

| 端点 | 限制 |
|------|------|
| Gamma `/markets` | 300 / 10s |
| Gamma `/events` | 500 / 10s |
| Gamma `/public-search` | 350 / 10s |
| Gamma `/tags` | 200 / 10s |
| CLOB `/last-trades-prices` | 9000 / 10s（通用层） |
| 全局 | 15000 / 10s |

超出后排队延迟，不拒绝。`last-trades-prices` 一次最多查 **500 个 token**。

### 模块结构

```
src/services/polymarket/
├── __init__.py     # 统一导出
├── utils.py        # 常量 + 工具 (is_market_closed, batch_last_prices, enrich_markets)
├── search.py       # 关键词搜索
├── markets.py      # 市场查询 (list_markets, list_trending_markets, get_market_by_*)
├── events.py       # 首页热门 (list_trending_events)
└── tags.py         # 标签 (list_tags, get_tag_by_slug, resolve_tag_slug)
```

## Async HTTP × LangGraph：BlockingError

LangGraph 把所有 tools（包括 sync tools）都通过 `asyncio.gather` 在事件循环中执行。这时任何**同步阻塞网络调用**都会被 blockbuster 拦截并抛 `BlockingError`：

```
blockbuster.blockbuster.BlockingError: Blocking call to socket.socket.connect
```

### 根因

用同步 `httpx.get()` / `requests.get()` 等做 HTTP 请求。在 ASGI/LangGraph 环境下，它们阻塞了事件循环。

### 修复原则：一律 async

**所有** HTTP 调用都必须用 `httpx.AsyncClient`，不能用 `httpx.get()`：

```python
# ❌ 会触发 BlockingError
resp = httpx.get(url, headers=headers)
data = resp.json()

# ✅ 正确
async with httpx.AsyncClient(headers=headers) as client:
    resp = await client.get(url)
    data = resp.json()
```

关键点：
- 从工具（`@tool`）到 service 层的**整条调用链**都必须 async，不能 sync → async 混搭
- 测试 mock 也要跟着改：`patch("httpx.AsyncClient")` 而非 `patch("httpx...get")`
- `@tool` 装饰后的函数变成 `StructuredTool` 对象，测试时用 `.ainvoke()` 而非直接调用

### 连锁反应：asyncio.run() 在事件循环内失效

`batch_last_prices` 原来用 `asyncio.run(_run())` 封装异步逻辑。当它被 async 函数调用时，`asyncio.run()` 会抛：
```
RuntimeError: asyncio.run() cannot be called from a running event loop
```

修复方案：
- 提供显式 async 版本 `batch_last_prices_async()`，内部用 `async with httpx.AsyncClient` 而不调用 `asyncio.run()`
- sync 版保留 `asyncio.run()` 给 sync 调用者，加上 try/except 检测运行中事件循环时给 warning
- 在 async 调用链中，一律使用 `batch_last_prices_async()`

## SSH：云服务器部署

本机通过 Clash Verge (verge-mih) 代理上网，端口 `127.0.0.1:7897`。

### 服务器

```
Host rwa.ltd
  HostName 45.77.245.137
  User bi4o
  IdentityFile ~/.ssh/id_ed25519
```

- `ssh rwa.ltd` → `45.77.245.137` — **此服务器**，PolyBot 后端在 `/opt/agents/PolyBot`
- 部署流程：先传 `.env.docker`，再拉代码重启：

  ```bash
  scp .env.docker rwa.ltd:/opt/agents/PolyBot/.env.docker
  ssh rwa.ltd "cd /opt/agents/PolyBot && git pull && docker compose down && docker compose up -d --build"
  ```

### SSH 连接失败排查

**现象：** 用未定义的主机别名（如 `openclaw-prod`）SSH 时连到 `127.0.0.1:7897` 然后断开

**原因：** 主机别名在 SSH config 中不存在 → SSH 尝试 DNS 解析 → Clash 全局代理接管 → 代理不认识 SSH 协议

**解决：**
1. `cat ~/.ssh/config` 确认别名存在
2. 用已定义的别名或 IP 直连
3. 检查 Clash Verge 是否开了全局代理；需 SSH 时可暂时关掉或切规则模式

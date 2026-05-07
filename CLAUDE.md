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

只要 `agent_models` 在模型实例化前被 import，patch 即可生效。当前 `agent_backend` 和 `hello_agent` 的 import 链已经保证这个顺序。

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

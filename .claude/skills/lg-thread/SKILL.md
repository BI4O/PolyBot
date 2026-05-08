---
name: lg-thread
description: 查看 langgraph dev 服务中的聊天会话（thread）和消息记录。启动 langgraph dev 后使用。
---

# LangGraph Thread Viewer

## 前提

`langgraph dev` 已在运行（`Alt+Shift+T` → `Langgraph Dev`）。

## API 基础

```
BASE = http://127.0.0.1:2024
```

## 列出所有会话

```bash
curl -s -X POST $BASE/threads/search \
  -H "Content-Type: application/json" \
  -d '{"limit": 20}'
```

返回包含 `thread_id`、`created_at`、首条消息的列表。

## 查看指定会话的消息

```bash
curl -s $BASE/threads/{thread_id}/state
```

返回包含完整 `messages` 数组的状态，每条消息有 `role`、`content`、`additional_kwargs`（含 `reasoning_content`）。

## 浏览器快速查看

- 列出所有线程: `$BASE/threads`
- 查看线程状态: `$BASE/threads/{thread_id}/state`
- 查看线程历史: `$BASE/threads/{thread_id}/history`
- Swagger UI: `$BASE/docs`
- Studio UI: `https://smith.langchain.com/studio/?baseUrl=$BASE`

## 用法

在 Claude Code 中：

```
/lg-thread 列出所有会话
/lg-thread 查看 thread xxx 的消息
```

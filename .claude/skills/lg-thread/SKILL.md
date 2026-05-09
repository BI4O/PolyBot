---
name: lg-thread
description: 查看 langgraph dev 服务中的聊天会话（thread）和消息记录。自动检测运行中的服务端口。
---

# LangGraph Thread Viewer

## 前提

`langgraph dev` 已在运行（`Alt+Shift+T` → `Langgraph Dev`）。

## 检测端口

```bash
curl -s http://127.0.0.1:2024/ok && PORT=2024 || curl -s http://127.0.0.1:2025/ok && PORT=2025 || echo "NOT_RUNNING"
```

后续命令用 `$PORT` 替代。

## 列出所有会话（含预览）

```bash
curl -s -X POST http://127.0.0.1:$PORT/threads/search \
  -H "Content-Type: application/json" \
  -d '{"limit": 10}' | python -c "
import sys, json, re
raw = sys.stdin.read()
try:
    data = json.loads(raw)
    for t in data:
        tid = t.get('thread_id','?')
        created = t.get('created_at','')[:19]
        values = t.get('values', {}) or {}
        msgs = values.get('messages', [])
        first = ''
        for m in msgs:
            c = m.get('content', m.get('content','')) or ''
            if isinstance(c, str) and c.strip():
                first = c[:60]
                break
        print(f'{tid[:36]}  [{created}] {first}')
except:
    # fallback: raw regex
    tids = re.findall(r'\"thread_id\": \"([^\"]+)\"', raw)
    dates = re.findall(r'\"created_at\": \"([^\"]+)\"', raw)
    for i, t in enumerate(tids):
        d = dates[i][:19] if i < len(dates) else ''
        print(f'{t}  [{d}]')
    print(f'(共 {len(tids)} 个)')
"

```

## 查看指定会话的消息

```bash
curl -s http://127.0.0.1:$PORT/threads/{thread_id}/state | python -c "
import sys, json
raw = sys.stdin.read()
try:
    data = json.loads(raw)
except:
    # JSON too large or escaped, fallback to scanning
    import re
    data = {'values': {'messages': []}}
    # extract message-like objects
    for m in re.finditer(r'\{\"content\":.*?(?=\}\}?,\s*\{|\}\]\})', raw):
        try:
            msg = json.loads(m.group())
            data['values']['messages'].append(msg)
        except:
            pass

msgs = data['values']['messages']
for m in msgs:
    role = m.get('role') or m.get('type', '?')
    content = m.get('content', '') or ''
    tc = m.get('tool_calls', [])
    
    if isinstance(content, list):
        content = ' '.join(c.get('text','') for c in content if isinstance(c, dict))
    
    if tc:
        names = [t['name'] for t in tc]
        args = [str(t.get('args',{}))[:80] for t in tc]
        pairs = [f'{n}({a})' for n, a in zip(names, args)]
        print(f'[{role}] → {"; ".join(pairs)}')
    elif content:
        content = str(content)[:250]
        has_link = 'polymarket.com' in content
        print(f'[{role}]{\"🔗\" if has_link else \"\"} {content}')
    else:
        print(f'[{role}] (no content)')
    print()
"
```

## 快速链接

- 列出所有: `http://127.0.0.1:2024/threads`
- API 文档: `http://127.0.0.1:2024/docs`
- Studio UI: `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`

## 用法

```
/lg-thread 列出所有会话
/lg-thread 查看 thread xxx
```

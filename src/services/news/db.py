"""SQLite 存储与 FTS5 全文搜索。"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

_DEFAULT_PATH = os.fspath(Path(__file__).resolve().parents[3] / "data" / "news.db")

_conn: sqlite3.Connection | None = None
_conn_path: str | None = None


def _resolve_db_path() -> str:
    return os.environ.get("NEWS_DB_PATH", _DEFAULT_PATH)


def _get_conn() -> sqlite3.Connection:
    """每次调用创建独立 connection，避免 LangGraph worker 跨线程复用。

    WAL 模式允许多线程并发读，写入不阻塞读取。
    """
    global _conn, _conn_path
    path = _resolve_db_path()
    if _conn is not None and _conn_path == path:
        try:
            # 快速验证连接是否有效
            _conn.execute("SELECT 1")
            return _conn
        except sqlite3.ProgrammingError:
            pass
    # 连接无效或路径变了 → 重建
    close_db()
    _conn = sqlite3.connect(path, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn_path = path
    return _conn


def close_db() -> None:
    global _conn
    if _conn is not None:
        try:
            _conn.close()
        except Exception:
            pass
        _conn = None


def init_db() -> None:
    """建表、建 FTS5 索引、注册触发器。"""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            guid            TEXT PRIMARY KEY,
            title           TEXT NOT NULL,
            link            TEXT,
            summary         TEXT,
            published       TEXT,
            source_name     TEXT,
            source_category TEXT,
            fetched_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
            title, summary,
            content='articles',
            content_rowid='rowid'
        );

        CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
            INSERT INTO articles_fts(rowid, title, summary)
            VALUES (new.rowid, new.title, new.summary);
        END;
    """)
    conn.commit()


def _fmt_published(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def insert_articles(articles: list[dict]) -> int:
    """批量写入新闻（INSERT OR IGNORE 按 guid 去重），写入后清理 24h+ 旧数据。返回新增条数。"""
    conn = _get_conn()
    count = 0
    for a in articles:
        published = _fmt_published(a.get("published"))
        if not published:
            continue
        cur = conn.execute(
            """INSERT OR IGNORE INTO articles
               (guid, title, link, summary, published, source_name, source_category)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                a.get("guid") or a.get("link", ""),
                a.get("title", ""),
                a.get("link", ""),
                a.get("summary", ""),
                published,
                a.get("source_name"),
                a.get("source_category"),
            ),
        )
        count += cur.rowcount
    # 清理 24 小时前的数据
    conn.execute("DELETE FROM articles WHERE published < datetime('now', '-24 hours')")
    conn.commit()
    return count


def search_news(
    keywords: list[str],
    since_hours: int = 6,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """FTS5 全文搜索，keywords 之间 OR 关系，按 rank 排序。"""
    if not keywords:
        return []
    conn = _get_conn()
    # 对每个关键词做 FTS5 安全转义：包裹双引号防止特殊字符（-、"、AND/OR 等）被解析为语法
    def _escape_fts5(term: str) -> str:
        escaped = term.replace('"', '""')
        return f'"{escaped}"'

    query = " OR ".join(_escape_fts5(k) for k in keywords if k.strip())
    sql = """
        SELECT a.* FROM articles a
        JOIN articles_fts f ON a.rowid = f.rowid
        WHERE articles_fts MATCH ?
          AND a.published >= datetime('now', ?)
        ORDER BY rank
        LIMIT ?
    """
    try:
        cur = conn.execute(sql, (query, f"-{since_hours} hours", limit))
        return [dict(row) for row in cur.fetchall()]
    except (sqlite3.OperationalError, sqlite3.InterfaceError) as e:
        print(f"[news] FTS 搜索错误 ({type(e).__name__}): {e}")
        return []


def get_stats() -> dict[str, Any]:
    """返回库中新闻统计信息。"""
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    sources = conn.execute(
        "SELECT source_name, COUNT(*) as cnt FROM articles GROUP BY source_name ORDER BY cnt DESC"
    ).fetchall()
    return {"total": total, "sources": [dict(s) for s in sources]}

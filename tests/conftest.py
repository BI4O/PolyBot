"""Ensure DB tests use a temp file."""
import os
import tempfile
from pathlib import Path

# Force temp DB path for all tests
_tmp_dir = tempfile.mkdtemp()
_db_path = os.path.join(_tmp_dir, "test_news.db")
os.environ["NEWS_DB_PATH"] = _db_path
Path(_tmp_dir).mkdir(parents=True, exist_ok=True)

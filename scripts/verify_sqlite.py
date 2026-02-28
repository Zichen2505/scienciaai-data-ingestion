from __future__ import annotations

import sqlite3
from urllib.parse import urlparse
from pathlib import Path

def load_db_path() -> Path:
    env = Path(".env").read_text(encoding="utf-8").splitlines()
    db_url = None
    for line in env:
        if line.startswith("DB_URL="):
            db_url = line.split("=", 1)[1].strip()
            break
    if not db_url:
        raise RuntimeError("DB_URL not found in .env")

    p = urlparse(db_url)
    if p.scheme != "sqlite":
        raise RuntimeError(f"Only sqlite DB_URL supported, got: {db_url}")

    path = p.path
    if path.startswith("/") and len(path) >= 3 and path[2] == ":":
        path = path[1:]  # /D:/... -> D:/...
    return Path(path)

def q(cur: sqlite3.Cursor, sql: str):
    rows = cur.execute(sql).fetchall()
    print(f"--- {sql}")
    print(rows)
    return rows

def main() -> int:
    db_path = load_db_path()
    print("db_path =", db_path)
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()

    tables = q(cur, "select name from sqlite_master where type='table' order by name")
    required = {"apps","reviews","ingestion_runs","review_runs","app_runs","failures","raw_samples"}
    existing = {t[0] for t in tables}
    missing = sorted(required - existing)
    if missing:
        raise SystemExit(f"Missing tables: {missing}")

    q(cur, "select count(*) from apps")
    q(cur, "select count(*) from reviews")
    q(cur, "select count(*) from ingestion_runs")
    q(cur, "select app_id, count(*) from reviews group by app_id order by count(*) desc limit 5")

    print("VERIFY_OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# Minimal duplicate-upsert smoke test
from pathlib import Path
import sqlite3
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sciencia_ingestion.sources.google_play.normalize import normalize_review
from sciencia_ingestion.storage.sqlite_store import upsert_review

SCHEMA_PATH = PROJECT_ROOT / "schema" / "reviews_schema.sql"

def main():
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys=ON;")
    con.executescript(schema_sql)
    con.commit()

    # Insert minimal parent app row to satisfy FK (only required fields)
    now = "2024-01-01T00:00:00Z"
    con.execute(
        "INSERT INTO apps(app_id, source, first_seen_at, last_seen_at) VALUES(?, ?, ?, ?)",
        ("com.openai.chatgpt", "google_play", now, now),
    )
    con.commit()

    # Fixed raw review (stable timestamp)
    raw = {
        "reviewId": "r-dup-1",
        "userName": "tester",
        "score": 5,
        "content": "duplicate test",
        "thumbsUpCount": 10,
        "at": "2024-01-01T00:00:00Z",
        "replyContent": None,
        "repliedAt": None,
        "appVersion": "1.0.0",
    }

    nr = normalize_review("com.openai.chatgpt", "en", "us", raw)

    # Upsert the same normalized record twice
    upsert_review(con, nr)
    upsert_review(con, nr)
    con.commit()

    # Query count and data
    cnt = con.execute("SELECT COUNT(*) FROM reviews WHERE review_id=?", (nr["review_id"],)).fetchone()[0]
    row = con.execute(
        "SELECT review_id, content_hash, content, rating FROM reviews WHERE review_id=?",
        (nr["review_id"],),
    ).fetchone()

    print("RESULTS")
    print("-------")
    print("review_id:", nr["review_id"])
    print("count in table:", cnt)
    print("row:", row)

if __name__ == "__main__":
    main()
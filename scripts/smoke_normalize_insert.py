# English-only test script to verify normalize -> insert -> sqlite field mapping
from pathlib import Path
import sqlite3
import json
from sciencia_ingestion.sources.google_play.normalize import normalize_review
from sciencia_ingestion.storage.sqlite_store import upsert_review, connect_sqlite
from datetime import datetime, UTC

# load canonical schema
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schema" / "reviews_schema.sql"
schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

# create in-memory DB and apply schema
con = sqlite3.connect(":memory:")
con.executescript(schema_sql)
con.commit()

# simulated raw review (fields similar to client output)
raw = {
    "reviewId": "r-123",
    "userName": "Alice",
    "score": 4,
    "content": "This is a test review.",
    "thumbsUpCount": 2,
    "at": datetime.now(UTC),
    "replyContent": None,
    "repliedAt": None,
    "appVersion": "1.2.3",
}

# normalize
nr = normalize_review("com.openai.chatgpt", "en", "us", raw)

# use upsert_review from storage module (it uses utc timestamps internally)
upsert_review(con, nr)
con.commit()

# read back
cur = con.execute("SELECT review_id, app_id, user_name, rating, content, thumbs_up_count, at, content_hash FROM reviews WHERE review_id=?", (nr["review_id"],))
row = cur.fetchone()
print("Inserted row:", row)
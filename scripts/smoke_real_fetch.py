
#!/usr/bin/env python3
# Minimal real-data smoke fetch: fetch ~15 reviews, normalize, insert into sqlite
from pathlib import Path
import sys
import json
import uuid

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sciencia_ingestion.sources.google_play.client import fetch_app, fetch_reviews_page
from sciencia_ingestion.sources.google_play.normalize import normalize_app, normalize_review
from sciencia_ingestion.storage.sqlite_store import (
    connect_sqlite,
    ensure_schema,
    upsert_run,
    upsert_app,
    upsert_review,
    link_review_run,
)

APP_ID = "com.openai.chatgpt"
LANG = "en"
COUNTRY = "us"
FETCH_COUNT = 20  # request up to 20; will insert ≤ that many

def main():
    db_path = PROJECT_ROOT / "data" / "smoke_reviews.db"
    con = connect_sqlite(db_path)
    ensure_schema(con)

    run_id = "smoke-" + uuid.uuid4().hex[:8]
    upsert_run(con, run_id, "google_play", "running", params_json=json.dumps({
        "app_id": APP_ID, "count": FETCH_COUNT, "lang": LANG, "country": COUNTRY
    }))

    # fetch app metadata and upsert app
    app_detail = fetch_app(APP_ID, LANG, COUNTRY)
    upsert_app(con, normalize_app(APP_ID, app_detail))
    
    # fetch one page of reviews
    items, token = fetch_reviews_page(APP_ID, LANG, COUNTRY, FETCH_COUNT, None)
    inserted = 0
    for it in items:
        nr = normalize_review(APP_ID, LANG, COUNTRY, it)
        is_new = 0 if con.execute("SELECT 1 FROM reviews WHERE review_id=? LIMIT 1", (nr["review_id"],)).fetchone() else 1
        upsert_review(con, nr)
        link_review_run(con, run_id, nr["review_id"], is_new)
        inserted += 1
    con.commit()
    upsert_run(con, run_id, "google_play", "success")

    print("DB file:", str(db_path))
    print("Requested reviews:", FETCH_COUNT)
    print("Fetched/processed:", len(items))
    print("Inserted (attempted):", inserted)

if __name__ == "__main__":
    main()
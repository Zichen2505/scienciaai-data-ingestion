#!/usr/bin/env python3
import sys
import sqlite3
from pathlib import Path

db = Path(sys.argv[1] if len(sys.argv) > 1 else "data/smoke_reviews.db")
if not db.exists():
    print("DB not found:", db); sys.exit(2)

con = sqlite3.connect(str(db))
cur = con.cursor()

def q(sql, params=()):
    return cur.execute(sql, params)

print("DB:", db)
print("--- Total reviews ---")
print(q("SELECT COUNT(*) FROM reviews").fetchone()[0])

print("\n--- Failures count ---")
print(q("SELECT COUNT(*) FROM failures").fetchone()[0])
print("\n--- Recent failures (up to 10) ---")
for row in q("SELECT id, run_id, error_type, message, created_at FROM failures ORDER BY created_at DESC LIMIT 10"):
    print(row)

print("\n--- Sample reviews (up to 5) ---")
for row in q("SELECT review_id, content, at, content_hash FROM reviews LIMIT 5"):
    print(row)

print("\n--- Duplicates (review_id with count>1) ---")
dups = list(q("SELECT review_id, COUNT(*) AS c FROM reviews GROUP BY review_id HAVING c>1"))
print(dups or "none")

print("\n--- Time range ---")
print(q("SELECT MIN(at), MAX(at) FROM reviews").fetchone())

print("\n--- Rating distribution ---")
for r in q("SELECT rating, COUNT(*) FROM reviews GROUP BY rating ORDER BY rating DESC"):
    print(r)

con.close()
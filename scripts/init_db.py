from pathlib import Path
import sqlite3

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schema" / "reviews_schema.sql"
DB_PATH = PROJECT_ROOT / "data" / "reviews.db"

def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(schema_sql)
        conn.commit()
        print(f"Database initialized successfully: {DB_PATH}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
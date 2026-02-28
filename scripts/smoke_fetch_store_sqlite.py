import os
import hashlib
from datetime import datetime, timezone

import truststore
truststore.inject_into_ssl()

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from tenacity import retry, stop_after_attempt, wait_exponential
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env", override=True)

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    raise RuntimeError(f"DB_URL missing. Expected in {REPO_ROOT / '.env'}")

USER_AGENT = os.getenv("USER_AGENT", "ScienciaAIIngestion/0.1")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "20"))

URL = "https://example.com/"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def fetch(url: str) -> requests.Response:
    r = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()
    return r


def main() -> None:
    resp = fetch(URL)
    soup = BeautifulSoup(resp.text, "lxml")

    title = (soup.title.text or "").strip() if soup.title else ""
    content_hash = hashlib.sha256(resp.text.encode("utf-8", errors="ignore")).hexdigest()
    fetched_at = datetime.now(timezone.utc).isoformat()

    engine = create_engine(DB_URL, future=True)

    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            status_code INTEGER NOT NULL,
            title TEXT,
            content_hash TEXT,
            fetched_at TEXT NOT NULL
        )
        """))

        conn.execute(
            text("""
            INSERT INTO pages (url, status_code, title, content_hash, fetched_at)
            VALUES (:url, :status_code, :title, :content_hash, :fetched_at)
            """),
            {
                "url": URL,
                "status_code": int(resp.status_code),
                "title": title,
                "content_hash": content_hash,
                "fetched_at": fetched_at,
            },
        )

        rows = conn.execute(
            text("SELECT id, url, status_code, title, fetched_at FROM pages ORDER BY id DESC LIMIT 5")
        ).fetchall()

    print("DB_URL =", DB_URL)
    print("Latest rows:")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()

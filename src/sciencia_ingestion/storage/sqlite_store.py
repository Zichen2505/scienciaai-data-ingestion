from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def connect_sqlite(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path), timeout=30)
    con.execute("PRAGMA foreign_keys=ON;")
    return con

def ensure_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        '''
        CREATE TABLE IF NOT EXISTS ingestion_runs (
          run_id TEXT PRIMARY KEY,
          source TEXT NOT NULL,
          started_at TEXT NOT NULL,
          ended_at TEXT,
          status TEXT NOT NULL,
          params_json TEXT,
          error TEXT
        );

        CREATE TABLE IF NOT EXISTS apps (
          app_id TEXT PRIMARY KEY,
          source TEXT NOT NULL,
          url TEXT,
          title TEXT,
          developer TEXT,
          genre TEXT,
          score REAL,
          ratings INTEGER,
          reviews INTEGER,
          installs TEXT,
          updated_unix INTEGER,
          first_seen_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL
        );

        -- run association + is_new for rollback safety
        CREATE TABLE IF NOT EXISTS app_runs (
          run_id TEXT NOT NULL,
          app_id TEXT NOT NULL,
          scraped_at TEXT NOT NULL,
          is_new INTEGER NOT NULL,
          raw_sample_path TEXT,
          PRIMARY KEY(run_id, app_id),
          FOREIGN KEY(run_id) REFERENCES ingestion_runs(run_id) ON DELETE CASCADE,
          FOREIGN KEY(app_id) REFERENCES apps(app_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS reviews (
          review_id TEXT PRIMARY KEY,
          app_id TEXT NOT NULL,
          source TEXT NOT NULL,
          user_name TEXT,
          rating INTEGER,
          content TEXT,
          thumbs_up_count INTEGER,
          at TEXT,
          reply_content TEXT,
          replied_at TEXT,
          app_version TEXT,
          lang TEXT,
          country TEXT,
          content_hash TEXT NOT NULL,
          first_seen_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          FOREIGN KEY(app_id) REFERENCES apps(app_id) ON DELETE CASCADE
        );

        -- run association + is_new for rollback safety
        CREATE TABLE IF NOT EXISTS review_runs (
          run_id TEXT NOT NULL,
          review_id TEXT NOT NULL,
          fetched_at TEXT NOT NULL,
          is_new INTEGER NOT NULL,
          PRIMARY KEY(run_id, review_id),
          FOREIGN KEY(run_id) REFERENCES ingestion_runs(run_id) ON DELETE CASCADE,
          FOREIGN KEY(review_id) REFERENCES reviews(review_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS raw_samples (
          sample_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          source TEXT NOT NULL,
          app_id TEXT,
          kind TEXT NOT NULL,
          file_path TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(run_id) REFERENCES ingestion_runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS failures (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          run_id TEXT NOT NULL,
          source TEXT NOT NULL,
          app_id TEXT,
          stage TEXT NOT NULL,
          status_code INTEGER,
          error_type TEXT NOT NULL,
          message TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(run_id) REFERENCES ingestion_runs(run_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_reviews_app ON reviews(app_id);
        '''
    )
    con.commit()

def upsert_run(con: sqlite3.Connection, run_id: str, source: str, status: str, params_json: str | None = None, error: str | None = None, ended_at: str | None = None) -> None:
    started_at = utc_now_iso()
    con.execute(
        '''
        INSERT INTO ingestion_runs(run_id, source, started_at, ended_at, status, params_json, error)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
          ended_at=COALESCE(excluded.ended_at, ingestion_runs.ended_at),
          status=excluded.status,
          params_json=COALESCE(excluded.params_json, ingestion_runs.params_json),
          error=COALESCE(excluded.error, ingestion_runs.error)
        ''',
        (run_id, source, started_at, ended_at, status, params_json, error),
    )
    con.commit()

def app_exists(con: sqlite3.Connection, app_id: str) -> bool:
    cur = con.execute("SELECT 1 FROM apps WHERE app_id=? LIMIT 1", (app_id,))
    return cur.fetchone() is not None

def upsert_app(con: sqlite3.Connection, row: dict[str, Any]) -> None:
    now = utc_now_iso()
    con.execute(
        '''
        INSERT INTO apps(app_id, source, url, title, developer, genre, score, ratings, reviews, installs, updated_unix, first_seen_at, last_seen_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(app_id) DO UPDATE SET
          url=COALESCE(excluded.url, apps.url),
          title=COALESCE(excluded.title, apps.title),
          developer=COALESCE(excluded.developer, apps.developer),
          genre=COALESCE(excluded.genre, apps.genre),
          score=COALESCE(excluded.score, apps.score),
          ratings=COALESCE(excluded.ratings, apps.ratings),
          reviews=COALESCE(excluded.reviews, apps.reviews),
          installs=COALESCE(excluded.installs, apps.installs),
          updated_unix=COALESCE(excluded.updated_unix, apps.updated_unix),
          last_seen_at=excluded.last_seen_at
        ''',
        (
            row["app_id"], row["source"], row.get("url"), row.get("title"), row.get("developer"),
            row.get("genre"), row.get("score"), row.get("ratings"), row.get("reviews"),
            row.get("installs"), row.get("updated_unix"), now, now
        ),
    )
    con.commit()

def link_app_run(con: sqlite3.Connection, run_id: str, app_id: str, is_new: int, raw_sample_path: str | None) -> None:
    con.execute(
        '''
        INSERT OR REPLACE INTO app_runs(run_id, app_id, scraped_at, is_new, raw_sample_path)
        VALUES(?, ?, ?, ?, ?)
        ''',
        (run_id, app_id, utc_now_iso(), is_new, raw_sample_path),
    )
    con.commit()

def review_exists(con: sqlite3.Connection, review_id: str) -> bool:
    cur = con.execute("SELECT 1 FROM reviews WHERE review_id=? LIMIT 1", (review_id,))
    return cur.fetchone() is not None

def upsert_review(con: sqlite3.Connection, r: dict[str, Any]) -> None:
    now = utc_now_iso()
    con.execute(
        '''
        INSERT INTO reviews(
          review_id, app_id, source, user_name, rating, content, thumbs_up_count, at,
          reply_content, replied_at, app_version, lang, country, content_hash, first_seen_at, last_seen_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(review_id) DO UPDATE SET
          thumbs_up_count=COALESCE(excluded.thumbs_up_count, reviews.thumbs_up_count),
          reply_content=COALESCE(excluded.reply_content, reviews.reply_content),
          replied_at=COALESCE(excluded.replied_at, reviews.replied_at),
          last_seen_at=excluded.last_seen_at
        ''',
        (
            r["review_id"], r["app_id"], r["source"], r.get("user_name"), r.get("rating"),
            r.get("content"), r.get("thumbs_up_count"), r.get("at"),
            r.get("reply_content"), r.get("replied_at"), r.get("app_version"),
            r.get("lang"), r.get("country"), r["content_hash"], now, now
        ),
    )

def link_review_run(con: sqlite3.Connection, run_id: str, review_id: str, is_new: int) -> None:
    con.execute(
        '''
        INSERT OR REPLACE INTO review_runs(run_id, review_id, fetched_at, is_new)
        VALUES(?, ?, ?, ?)
        ''',
        (run_id, review_id, utc_now_iso(), is_new),
    )

def commit(con: sqlite3.Connection) -> None:
    con.commit()

def record_raw_sample(con: sqlite3.Connection, sample_id: str, run_id: str, source: str, app_id: str | None, kind: str, file_path: str) -> None:
    con.execute(
        '''
        INSERT INTO raw_samples(sample_id, run_id, source, app_id, kind, file_path, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        ''',
        (sample_id, run_id, source, app_id, kind, file_path, utc_now_iso()),
    )
    con.commit()

def record_failure(con: sqlite3.Connection, run_id: str, source: str, app_id: str | None, stage: str, status_code: int | None, error_type: str, message: str) -> None:
    con.execute(
        '''
        INSERT INTO failures(run_id, source, app_id, stage, status_code, error_type, message, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (run_id, source, app_id, stage, status_code, error_type, message, utc_now_iso()),
    )
    con.commit()

def rollback_run(con: sqlite3.Connection, run_id: str) -> None:
    # Delete run metadata and run-links; delete only rows inserted newly in this run (is_new=1)
    # reviews
    cur = con.execute("SELECT review_id FROM review_runs WHERE run_id=? AND is_new=1", (run_id,))
    new_review_ids = [r[0] for r in cur.fetchall()]
    con.execute("DELETE FROM review_runs WHERE run_id=?", (run_id,))
    for rid in new_review_ids:
        con.execute("DELETE FROM reviews WHERE review_id=?", (rid,))

    # apps
    cur = con.execute("SELECT app_id FROM app_runs WHERE run_id=? AND is_new=1", (run_id,))
    new_app_ids = [r[0] for r in cur.fetchall()]
    con.execute("DELETE FROM app_runs WHERE run_id=?", (run_id,))
    for aid in new_app_ids:
        con.execute("DELETE FROM apps WHERE app_id=?", (aid,))

    con.execute("DELETE FROM raw_samples WHERE run_id=?", (run_id,))
    con.execute("DELETE FROM failures WHERE run_id=?", (run_id,))
    con.execute("DELETE FROM ingestion_runs WHERE run_id=?", (run_id,))
    con.commit()

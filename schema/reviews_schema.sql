-- Canonical ingestion schema matching src/sciencia_ingestion/storage/sqlite_store.py

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
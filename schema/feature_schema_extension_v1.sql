-- =========================================================
-- Feature Engineering Schema Extension v1
--
-- Purpose:
-- Additive extension on top of the canonical ingestion schema.
-- Source review entity remains: reviews(review_id, content, ...)
--
-- This file defines storage structures for:
--   1) feature_runs
--   2) review_features
--   3) review_aspects
--
-- It does NOT populate feature data.
-- It only defines where future feature-engineering outputs will live.
-- =========================================================

PRAGMA foreign_keys = ON;

-- =========================================================
-- 1) FEATURE RUNS
-- =========================================================
-- Tracks each feature-engineering execution.
-- Necessary for reproducibility and versioned feature outputs.
-- =========================================================

CREATE TABLE IF NOT EXISTS feature_runs (
    feature_run_id        TEXT PRIMARY KEY,
    created_at            TEXT NOT NULL,
    status                TEXT NOT NULL CHECK (status IN ('started', 'completed', 'failed')),
    upstream_run_id       TEXT,
    feature_version       TEXT NOT NULL,
    text_prep_version     TEXT NOT NULL,
    extractor_config_json TEXT,
    notes                 TEXT,
    FOREIGN KEY (upstream_run_id) REFERENCES ingestion_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_feature_runs_created_at
    ON feature_runs(created_at);

CREATE INDEX IF NOT EXISTS idx_feature_runs_upstream_run_id
    ON feature_runs(upstream_run_id);

CREATE INDEX IF NOT EXISTS idx_feature_runs_feature_version
    ON feature_runs(feature_version);

-- =========================================================
-- 2) REVIEW FEATURES
-- =========================================================
-- Document-level engineered features.
-- Grain: one row per (feature_run_id, review_id)
-- Derived primarily from reviews.content
-- =========================================================

CREATE TABLE IF NOT EXISTS review_features (
    feature_run_id                 TEXT NOT NULL,
    review_id                      TEXT NOT NULL,

    char_count                     INTEGER NOT NULL CHECK (char_count >= 0),
    word_count                     INTEGER NOT NULL CHECK (word_count >= 0),
    sentence_count                 INTEGER NOT NULL CHECK (sentence_count >= 0),

    sentiment_compound             REAL,
    sentiment_label                TEXT CHECK (
        sentiment_label IN ('positive', 'neutral', 'negative', 'mixed')
    ),

    keyword_topk_json              TEXT,

    aspect_count                   INTEGER NOT NULL DEFAULT 0 CHECK (aspect_count >= 0),

    quality_flag_short_text        INTEGER NOT NULL DEFAULT 0 CHECK (quality_flag_short_text IN (0, 1)),
    quality_flag_empty_after_prep  INTEGER NOT NULL DEFAULT 0 CHECK (quality_flag_empty_after_prep IN (0, 1)),

    PRIMARY KEY (feature_run_id, review_id),

    FOREIGN KEY (feature_run_id) REFERENCES feature_runs(feature_run_id),
    FOREIGN KEY (review_id) REFERENCES reviews(review_id)
);

CREATE INDEX IF NOT EXISTS idx_review_features_review_id
    ON review_features(review_id);

CREATE INDEX IF NOT EXISTS idx_review_features_sentiment_label
    ON review_features(sentiment_label);

CREATE INDEX IF NOT EXISTS idx_review_features_sentiment_compound
    ON review_features(sentiment_compound);

CREATE INDEX IF NOT EXISTS idx_review_features_aspect_count
    ON review_features(aspect_count);

-- =========================================================
-- 3) REVIEW ASPECTS
-- =========================================================
-- Aspect-level extracted records.
-- Grain: one row per extracted aspect mention for a given
--        (feature_run_id, review_id)
-- =========================================================

CREATE TABLE IF NOT EXISTS review_aspects (
    aspect_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_run_id         TEXT NOT NULL,
    review_id              TEXT NOT NULL,

    aspect_rank            INTEGER NOT NULL CHECK (aspect_rank >= 1),
    aspect_text            TEXT NOT NULL,
    aspect_lemma           TEXT,
    extraction_method      TEXT NOT NULL,
    aspect_category        TEXT,
    is_primary_aspect      INTEGER CHECK (is_primary_aspect IN (0, 1)),

    FOREIGN KEY (feature_run_id) REFERENCES feature_runs(feature_run_id),
    FOREIGN KEY (review_id) REFERENCES reviews(review_id),

    UNIQUE (feature_run_id, review_id, aspect_rank)
);

CREATE INDEX IF NOT EXISTS idx_review_aspects_review_id
    ON review_aspects(review_id);

CREATE INDEX IF NOT EXISTS idx_review_aspects_feature_run_id
    ON review_aspects(feature_run_id);

CREATE INDEX IF NOT EXISTS idx_review_aspects_aspect_lemma
    ON review_aspects(aspect_lemma);

CREATE INDEX IF NOT EXISTS idx_review_aspects_aspect_category
    ON review_aspects(aspect_category);

CREATE INDEX IF NOT EXISTS idx_review_aspects_extraction_method
    ON review_aspects(extraction_method);

-- =========================================================
-- OPTIONAL REVIEW-FRIENDLY VIEW
-- =========================================================
-- This view is for inspection/demo convenience only.
-- It does not replace the canonical normalized tables.
-- =========================================================

CREATE VIEW IF NOT EXISTS review_feature_summary_v1 AS
SELECT
    rf.feature_run_id,
    r.review_id,
    r.app_id,
    r.rating,
    r.at,
    r.lang,
    r.country,
    r.content,
    rf.char_count,
    rf.word_count,
    rf.sentence_count,
    rf.sentiment_compound,
    rf.sentiment_label,
    rf.keyword_topk_json,
    rf.aspect_count,
    rf.quality_flag_short_text,
    rf.quality_flag_empty_after_prep
FROM review_features rf
JOIN reviews r
  ON rf.review_id = r.review_id;
from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from typing import Any

def _iso(dt: Any) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(dt)

def content_hash(app_id: str, r: dict[str, Any]) -> str:
    s = "|".join([
        app_id,
        str(r.get("reviewId") or ""),
        str(r.get("userName") or ""),
        str(r.get("score") or ""),
        str(_iso(r.get("at")) or ""),
        (r.get("content") or "").strip(),
    ])
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def review_id(app_id: str, r: dict[str, Any]) -> str:
    rid = r.get("reviewId")
    if rid:
        return str(rid)
    return "hash:" + content_hash(app_id, r)

def normalize_app(app_id: str, d: dict[str, Any]) -> dict[str, Any]:
    return {
        "app_id": app_id,
        "source": "google_play",
        "url": d.get("url"),
        "title": d.get("title"),
        "developer": d.get("developer"),
        "genre": d.get("genre"),
        "score": d.get("score"),
        "ratings": d.get("ratings"),
        "reviews": d.get("reviews"),
        "installs": d.get("installs"),
        "updated_unix": d.get("updated"),
    }

def normalize_review(app_id: str, lang: str, country: str, r: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_id": review_id(app_id, r),
        "app_id": app_id,
        "source": "google_play",
        "user_name": r.get("userName"),
        "rating": r.get("score"),
        "content": r.get("content"),
        "thumbs_up_count": r.get("thumbsUpCount"),
        "at": _iso(r.get("at")),
        "reply_content": r.get("replyContent"),
        "replied_at": _iso(r.get("repliedAt")),
        "app_version": r.get("appVersion"),
        "lang": lang,
        "country": country,
        "content_hash": content_hash(app_id, r),
    }

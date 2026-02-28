from __future__ import annotations
from typing import Any, Optional, Tuple
from google_play_scraper import Sort, app as gp_app, reviews as gp_reviews  # type: ignore

def fetch_app(app_id: str, lang: str, country: str) -> dict[str, Any]:
    return gp_app(app_id, lang=lang, country=country)

def fetch_reviews_page(
    app_id: str,
    lang: str,
    country: str,
    count: int,
    continuation_token: Optional[dict[str, Any]] = None
) -> Tuple[list[dict[str, Any]], Optional[dict[str, Any]]]:
    items, token = gp_reviews(
        app_id,
        lang=lang,
        country=country,
        sort=Sort.NEWEST,
        count=count,
        continuation_token=continuation_token,
    )
    return items, token

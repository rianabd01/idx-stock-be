from fastapi import APIRouter, Query

from app.core.db import get_connection
from app.repositories.news_repository import latest_articles

router = APIRouter()


@router.get("/news/latest")
def get_latest_news(limit: int = Query(default=20, ge=1, le=100)):
    with get_connection() as conn:
        return latest_articles(conn, limit)

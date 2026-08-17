from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.core.db import get_connection
from app.repositories.analytics_repository import track_source_visit

router = APIRouter()


class SourceTrackingPayload(BaseModel):
    source: str = Field(min_length=1, max_length=80)
    visitor_id: str = Field(min_length=16, max_length=80)
    path: str = Field(default="/", max_length=300)


def normalize_source(value: str) -> str:
    return "".join(char for char in value.lower().strip() if char.isalnum() or char in "_-. ").replace(" ", "")[:80]


@router.post("/analytics/source")
def track_source(payload: SourceTrackingPayload, request: Request):
    source = normalize_source(payload.source)
    if not source:
        return {"tracked": False, "reason": "empty_source"}

    with get_connection() as conn:
        inserted = track_source_visit(conn, source, payload.visitor_id, payload.path, request.headers.get("user-agent"))
    return {"tracked": inserted, "source": source}

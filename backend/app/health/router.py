from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.health.service import check_database

router = APIRouter(prefix="/health", tags=["health"])


class LivenessResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    database: str
    migrations: str


@router.get("", response_model=LivenessResponse, summary="Liveness check (no database access)")
def liveness() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get(
    "/db",
    response_model=ReadinessResponse,
    summary="Database readiness: reachable and fully migrated",
    responses={503: {"model": ReadinessResponse, "description": "Database not ready"}},
)
def readiness(request: Request) -> JSONResponse:
    result = check_database(request.app.state.engine)
    body = ReadinessResponse(
        status="ok" if result.healthy else "unavailable",
        database=result.database,
        migrations=result.migrations,
    )
    return JSONResponse(status_code=200 if result.healthy else 503, content=body.model_dump())

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bikeshare.api.contracts import (
    PredictionRequest,
    ReadinessResponse,
    RecommendationRequest,
    RecommendationResponse,
    StationCatalogue,
    StationLocation,
    StationStatusResponse,
)
from bikeshare.api.dashboard import DashboardResponse, DayType, build_dashboard
from bikeshare.api.service import RecommendationService, StaleDataError
from bikeshare.api.store import DatabaseStationStore, FixtureStationStore, StationStore
from bikeshare.config import AppMode, get_settings
from bikeshare.db.repository import IngestionRepository
from bikeshare.db.session import get_engine
from bikeshare.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Bike Share Dock Availability Predictor",
    version="0.2.0",
    description=(
        "Return-station recommendations using straight-line distance and current availability. "
        "Forecast probabilities are exposed only after an approved held-out evaluation."
    ),
)
app.mount('/assets', StaticFiles(directory=Path(__file__).parent / 'static'), name='assets')


@lru_cache(maxsize=1)
def station_store() -> StationStore:
    if settings.app_mode is AppMode.FIXTURE_DEMO:
        return FixtureStationStore(settings.fixture_path)
    return DatabaseStationStore(IngestionRepository(get_engine()), cache_seconds=2)


@app.middleware("http")
async def request_context(request: Request, call_next: Any) -> Response:
    requested_id = request.headers.get("X-Request-ID", "")
    try:
        request_id = str(uuid.UUID(requested_id)) if requested_id else str(uuid.uuid4())
    except ValueError:
        request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = round((time.perf_counter() - started) * 1000)
    response.headers["X-Request-ID"] = request_id
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    logger.info(
        "%s %s %s",
        request.method,
        request.url.path,
        response.status_code,
        extra={
            "service": "api",
            "event_code": "request_complete",
            "request_id": request_id,
            "duration_ms": duration_ms,
        },
    )
    return response


@app.get("/livez", tags=["health"])
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get(
    "/readyz",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
    tags=["health"],
)
def readiness(response: Response) -> ReadinessResponse:
    now = datetime.now(tz=UTC)
    if settings.app_mode is AppMode.FIXTURE_DEMO:
        return ReadinessResponse(
            ready=True,
            mode=AppMode.FIXTURE_DEMO.value,
            database="not_required",
            latest_complete_poll=None,
            latest_poll=None,
            stale=False,
            partial_feed=False,
            active_model_run_id=None,
            feature_version="v1",
            reason="deterministic fixture data; no real-world performance claim",
        )
    try:
        health = station_store().health()
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            ready=False,
            mode=AppMode.LIVE_BASELINE.value,
            database="unavailable",
            latest_complete_poll=None,
            latest_poll=None,
            stale=True,
            partial_feed=False,
            active_model_run_id=settings.active_model_run_id,
            feature_version="v1",
            reason="database unavailable",
        )
    latest = health.get("ended_at") or health.get("scheduled_at")
    latest_datetime = latest if isinstance(latest, datetime) else None
    latest_complete_value = health.get("latest_complete_at")
    latest_complete = latest_complete_value if isinstance(latest_complete_value, datetime) else None
    stale = latest_complete is None or not (
        -30 <= (now - latest_complete).total_seconds() <= settings.complete_batch_max_age_seconds
    )
    partial = health.get("status") == "partial"
    ready = not stale
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        ready=ready,
        mode=AppMode.LIVE_BASELINE.value,
        database="healthy",
        latest_complete_poll=latest_complete,
        latest_poll=latest_datetime,
        stale=stale,
        partial_feed=partial,
        active_model_run_id=None,
        feature_version="v1",
        reason=None if ready else "no sufficiently recent usable status batch",
    )


@app.get('/v1/stations', response_model=StationCatalogue, tags=['stations'])
def station_catalogue(q: str = Query(default='', max_length=100)) -> StationCatalogue:
    try:
        stations = station_store().all(decision_time=datetime.now(tz=UTC))
    except Exception as error:
        raise HTTPException(status_code=503, detail={
            'code': 'data_store_unavailable',
            'message': 'Station data is temporarily unavailable. Please retry shortly.',
        }) from error
    query = q.casefold().strip()
    return StationCatalogue(
        mode='fixture_demo' if settings.app_mode is AppMode.FIXTURE_DEMO else 'live_baseline',
        stations=[StationLocation(station_id=item.station_id, name=item.name or item.station_id,
                                  lat=item.lat, lon=item.lon)
                  for item in stations if item.lifecycle_state == 'active'
                  and (not query or query in (item.name or '').casefold() or query in item.station_id)][:2000],
    )


@app.get(
    "/v1/stations/{station_id}",
    response_model=StationStatusResponse,
    responses={404: {"description": "Unknown station"}, 503: {"description": "Data store unavailable"}},
    tags=["stations"],
)
def station_status(station_id: str) -> StationStatusResponse:
    try:
        result = RecommendationService(settings, station_store()).station_status(station_id)
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail={"code": "data_store_unavailable", "message": "Station data is temporarily unavailable. Please retry shortly."},
        ) from error
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "station_not_found", "message": f"station {station_id!r} is unknown"},
        )
    return result


@app.post(
    "/v1/predictions/stations/{station_id}",
    responses={
        404: {"description": "Unknown station"},
        409: {"description": "Station currently ineligible"},
        503: {"description": "Validated model unavailable"},
    },
    tags=["predictions"],
)
def station_prediction(station_id: str, prediction: PredictionRequest) -> dict[str, Any]:
    station = station_status(station_id)
    if station is None:
        raise HTTPException(status_code=404, detail={"code": "station_not_found"})
    raise HTTPException(
        status_code=503,
        detail={
            "code": "model_unavailable",
            "message": "No approved validated model is active; forecast probability is unavailable.",
            "station_id": station_id,
            "horizon_minutes": prediction.horizon_minutes,
        },
    )


@app.post(
    "/v1/recommendations",
    response_model=RecommendationResponse,
    responses={503: {"description": "All candidate data stale or unavailable"}},
    tags=["recommendations"],
)
def recommendations(
    request: Request,
    payload: RecommendationRequest,
    x_request_id: Annotated[str | None, Header()] = None,
) -> RecommendationResponse:
    del x_request_id  # middleware owns the validated response identifier
    request_id = uuid.UUID(request.state.request_id)
    partial = False
    if settings.app_mode is not AppMode.FIXTURE_DEMO:
        health = readiness(Response())
        if not health.ready:
            raise HTTPException(status_code=503, detail={
                'code': 'stale_data' if health.database == 'healthy' else 'data_store_unavailable',
                'message': 'Live station updates are temporarily unavailable. Wait a minute, then retry.',
            })
        partial = health.partial_feed
    try:
        return RecommendationService(settings, station_store()).recommend(
            payload,
            request_id=request_id,
            partial_feed=partial,
        )
    except StaleDataError as error:
        raise HTTPException(
            status_code=503,
            detail={"code": "stale_data", "message": str(error)},
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail={"code": "data_store_unavailable", "message": "Recommendations are temporarily unavailable. Please retry shortly."},
        ) from error


@app.get("/demo", include_in_schema=False)
def demo() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get('/', include_in_schema=False)
@app.get('/dashboard', include_in_schema=False)
def dashboard_page() -> FileResponse:
    return FileResponse(Path(__file__).parent / 'static' / 'dashboard.html')


@app.get('/v1/dashboard', response_model=DashboardResponse, tags=['dashboard'])
def dashboard_data(
    start_date: date | None = None, end_date: date | None = None,
    station_id: str | None = Query(default=None, min_length=1, max_length=100),
    day_type: DayType = 'all', hour: int | None = Query(default=None, ge=0, le=23),
) -> DashboardResponse:
    try:
        return build_dashboard(settings, station_store(),
            None if settings.app_mode is AppMode.FIXTURE_DEMO else get_engine(),
            start_date=start_date, end_date=end_date, station_id=station_id, day_type=day_type, hour=hour)
    except ValueError as error:
        raise HTTPException(status_code=422, detail={'code': 'invalid_range', 'message': str(error)}) from error
    except LookupError as error:
        raise HTTPException(status_code=404, detail={'code': 'station_not_found', 'message': str(error)}) from error
    except Exception as error:
        logger.exception('Dashboard data unavailable')
        raise HTTPException(status_code=503, detail={
            'code': 'dashboard_unavailable',
            'message': 'Dashboard data is temporarily unavailable. Start the local services and apply migrations, then retry.'}) from error


def run() -> None:
    uvicorn.run(app, host=settings.bind_host, port=settings.bind_port)

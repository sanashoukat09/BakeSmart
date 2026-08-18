from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import router as api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.schemas.design import HealthResponse
from app.services.recommendation import recommendation_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging(settings.log_level)
    yield


app = FastAPI(
    title=settings.service_name,
    version=__version__,
    description=(
        "Local API contract for BakeSmart event-decoration recommendations "
        "and 3D scene specifications."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=__version__,
        model_status=recommendation_service.status,
    )

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from loguru import logger

from app.api.ai.router import router as ai_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        logger.info(
            "Starting Frigate AI Proxy",
            log_level=settings.LOG_LEVEL,
            max_sampled_images=settings.MAX_SAMPLED_IMAGES,
            vlm_model=settings.ELORIAN_MODEL,
        )
        app.state.client = client
        yield


app = FastAPI(
    title="Frigate AI Proxy",
    description="Cost-efficient AI proxy and threat intelligence gateway for Frigate NVR Generative AI",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(ai_router)


@app.get("/health", response_model=bool)
async def health() -> bool:
    """Service health check endpoint."""
    return True

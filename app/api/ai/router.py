from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Request
from httpx import AsyncClient
from loguru import logger

from app.api.ai.models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    JevEvaluationResponse,
    JevRequest,
    ModelItem,
    ModelListResponse,
    ReviewMetadata,
)
from app.core.config import settings
from app.services import base_post_request

router = APIRouter(prefix="/v1", tags=["ai"])


def get_http_client(request: Request) -> AsyncClient:
    client = request.app.state.client  # type: ignore # pyright:ignore[reportAny]
    assert isinstance(client, AsyncClient)
    return client


@router.get("/models", response_model=ModelListResponse)
async def list_models() -> ModelListResponse:
    """OpenAI-compatible models list endpoint for Frigate provider initialization."""
    return ModelListResponse(
        data=[
            ModelItem(id=settings.ELORIAN_MODEL),
            ModelItem(id="glimpse"),
        ]
    )


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    client: Annotated[AsyncClient, Depends(get_http_client)],
) -> ChatCompletionResponse:
    # 1. Preserve prompt directly from Frigate config (and optional system prefix)
    prepared_request = ChatCompletionRequest.apply_frigate_prompt(request)

    # 2. Sample image frames evenly to minimize latency and token costs
    sampled_request = ChatCompletionRequest.sample_images(prepared_request)

    logger.info(
        "Forwarding request to vision-language model",
        model=settings.ELORIAN_MODEL,
        prompt_len=len(sampled_request.inbound_prompt_text),
    )

    # 3. Request visual observation from VLM (e.g., Elorian Glimpse)
    vlm_res = await base_post_request(
        client=client,
        url=settings.elorian_chat_url,
        payload=sampled_request,
        response_model=ChatCompletionResponse,
        bearer=settings.ELORIAN_API_KEY if settings.ELORIAN_API_KEY else None,
    )

    observation_content = vlm_res.content
    logger.debug(
        "VLM observation received",
        observation_preview=observation_content[:200] if observation_content else "",
    )

    # 4. Assess threat level using TypeSafe System 1 / Jev if enabled and configured
    threat_level = 0
    confidence = 0.9

    if settings.ENABLE_TYPESAFE_THREAT_SCORING and settings.TYPESAFE_API_KEY:
        try:
            jev_res = await base_post_request(
                client=client,
                url=settings.typesafe_systemone_url,
                payload=JevRequest.threat_level_adapter(observation_content),
                response_model=JevEvaluationResponse,
                bearer=settings.TYPESAFE_API_KEY,
            )
            threat_level = jev_res.threat_level
            confidence = jev_res.confidence
            logger.debug(
                "Threat scoring response received",
                threat_level=threat_level,
                confidence=confidence,
            )
        except (httpx.HTTPError, ValueError) as e:
            logger.warning(
                "Threat assessment service call failed, defaulting to benign",
                error=str(e),
            )

    # 5. Build structured review metadata with distinct title, scene, and shortSummary
    metadata = ReviewMetadata.hybrid_adapter(
        observations=observation_content,
        threat_level=threat_level,
        confidence=confidence,
    )

    logger.info(
        "Generated review metadata for Frigate",
        title=metadata.title,
        short_summary=metadata.shortSummary,
        threat_level=metadata.potential_threat_level,
        confidence=metadata.confidence,
    )

    return ChatCompletionResponse.review_adapter(metadata)

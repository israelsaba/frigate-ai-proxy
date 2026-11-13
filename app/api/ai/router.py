from typing import Annotated

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
    client = request.app.state.client
    if not isinstance(client, AsyncClient):
        raise TypeError("HTTP client is not initialized in application state.")
    return client


@router.get("/models", response_model=ModelListResponse)
async def list_models() -> ModelListResponse:
    configured_model = settings.ELORIAN_MODEL
    models = [
        ModelItem(id=configured_model),
        ModelItem(id=f"{configured_model}-threat"),
    ]
    if configured_model not in ("glimpse", "glimpse-threat"):
        models.extend(
            [
                ModelItem(id="glimpse"),
                ModelItem(id="glimpse-threat"),
            ]
        )
    return ModelListResponse(data=models)


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    client: Annotated[AsyncClient, Depends(get_http_client)],
) -> ChatCompletionResponse:
    prepared_request = ChatCompletionRequest.apply_frigate_prompt(request)
    sampled_request = ChatCompletionRequest.sample_images(prepared_request)

    inbound_model = request.model
    if inbound_model.endswith("-threat"):
        stripped = inbound_model.removesuffix("-threat")
        sampled_request.model = stripped if stripped else settings.ELORIAN_MODEL
    elif inbound_model in ("threat", "jev"):
        sampled_request.model = settings.ELORIAN_MODEL

    logger.debug(
        "Forwarding request to vision-language model",
        model=sampled_request.model,
        prompt_len=len(sampled_request.inbound_prompt_text),
    )

    vlm_res = await base_post_request(
        client=client,
        url=settings.elorian_chat_url,
        payload=sampled_request,
        response_model=ChatCompletionResponse,
        bearer=settings.ELORIAN_API_KEY,
    )

    metadata = ReviewMetadata.from_llm_output(vlm_res.content)

    enable_threat_scoring = (
        "threat" in request.model.lower()
        or "jev" in request.model.lower()
        or settings.ENABLE_TYPESAFE_THREAT_SCORING
    )

    if enable_threat_scoring:
        jev_res = await base_post_request(
            client=client,
            url=settings.typesafe_systemone_url,
            payload=JevRequest.threat_level_adapter(metadata.scene),
            response_model=JevEvaluationResponse,
            bearer=settings.TYPESAFE_API_KEY,
        )
        metadata.potential_threat_level = jev_res.threat_level
        metadata.confidence = jev_res.confidence

    logger.debug(
        "Generated review metadata for Frigate",
        title=metadata.title,
        short_summary=metadata.shortSummary,
        threat_level=metadata.potential_threat_level,
        confidence=metadata.confidence,
    )

    return ChatCompletionResponse.review_adapter(metadata)

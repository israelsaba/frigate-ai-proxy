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
    assert isinstance(client, AsyncClient)
    return client


@router.get("/models", response_model=ModelListResponse)
async def list_models() -> ModelListResponse:
    return ModelListResponse(
        data=[
            ModelItem(id=settings.ELORIAN_MODEL),
            ModelItem(id=f"{settings.ELORIAN_MODEL}-threat"),
            ModelItem(id="glimpse"),
            ModelItem(id="glimpse-threat"),
        ]
    )


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    client: Annotated[AsyncClient, Depends(get_http_client)],
) -> ChatCompletionResponse:
    prepared_request = ChatCompletionRequest.apply_frigate_prompt(request)
    sampled_request = ChatCompletionRequest.sample_images(prepared_request)

    logger.debug(
        "Forwarding request to vision-language model",
        model=settings.ELORIAN_MODEL,
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

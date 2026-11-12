import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient, Response

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() is True


@pytest.mark.asyncio
async def test_models_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) >= 1


@pytest.mark.asyncio
async def test_chat_completions_pipeline():
    vlm_mock_response = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": (
                        "**Scene overview:** Front driveway.\n\n"
                        "**Activity observed:** A resident stepped out of a car, walked to the front door, and entered the house."
                    ),
                },
                "finish_reason": "stop",
            }
        ],
    }

    mock_request = httpx.Request("POST", "https://api.elorian.ai/v1/chat/completions")
    mock_http_client = AsyncMock(spec=AsyncClient)
    mock_http_client.post.return_value = Response(
        status_code=200,
        content=json.dumps(vlm_mock_response).encode(),
        request=mock_request,
    )

    app.state.client = mock_http_client

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "model": "glimpse",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Detect any break-in attempts or vandalism. ## Sequence Details",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/jpeg;base64,ZmFrZQ==",
                                "detail": "low",
                            },
                        },
                    ],
                }
            ],
        }

        with patch("app.api.ai.router.settings.ENABLE_TYPESAFE_THREAT_SCORING", False):
            res = await client.post("/v1/chat/completions", json=payload)
            assert res.status_code == 200
            data = res.json()
            assert data["object"] == "chat.completion"
            review_json = json.loads(data["choices"][0]["message"]["content"])
            assert "title" in review_json
            assert "scene" in review_json
            assert "shortSummary" in review_json
            assert review_json["title"] != review_json["scene"]
            assert review_json["shortSummary"] != review_json["scene"]
            assert review_json["potential_threat_level"] == 0

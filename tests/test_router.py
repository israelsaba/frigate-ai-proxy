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

        with patch("app.api.ai.router.settings.UPSTREAM_THREAT_ENABLED", False):
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


@pytest.mark.asyncio
async def test_chat_completions_with_threat_scoring_via_frigate_model():
    vlm_mock = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Person breaking window using crowbar",
                },
                "finish_reason": "stop",
            }
        ],
    }
    jev_mock = {
        "answers": {
            "threat_level": {
                "choice": "2",
                "confidence": 0.99,
            }
        }
    }

    mock_http_client = AsyncMock(spec=AsyncClient)
    mock_http_client.post.side_effect = [
        Response(
            status_code=200,
            content=json.dumps(vlm_mock).encode(),
            request=httpx.Request("POST", "https://api.elorian.ai/v1/chat/completions"),
        ),
        Response(
            status_code=200,
            content=json.dumps(jev_mock).encode(),
            request=httpx.Request("POST", "https://api.typesafe.ai/v1/systemone"),
        ),
    ]

    app.state.client = mock_http_client

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "model": "glimpse-threat",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze event"},
                    ],
                }
            ],
        }

        with patch("app.api.ai.router.settings.UPSTREAM_THREAT_ENABLED", False):
            res = await client.post("/v1/chat/completions", json=payload)
            assert res.status_code == 200
            data = res.json()
            review_json = json.loads(data["choices"][0]["message"]["content"])
            assert review_json["potential_threat_level"] == 2
            assert review_json["confidence"] == 0.99


@pytest.mark.asyncio
async def test_models_endpoint_with_custom_model():
    with patch("app.api.ai.router.settings.UPSTREAM_VLM_MODEL", "gpt-4o-mini"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/v1/models")
            assert response.status_code == 200
            model_ids = [m["id"] for m in response.json()["data"]]
            assert "gpt-4o-mini" in model_ids
            assert "gpt-4o-mini-threat" in model_ids
            assert "glimpse" in model_ids
            assert "glimpse-threat" in model_ids


@pytest.mark.asyncio
async def test_chat_completions_strips_threat_suffix_for_upstream():
    vlm_mock = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "A courier placed a parcel at the door.",
                },
                "finish_reason": "stop",
            }
        ],
    }
    jev_mock = {
        "answers": {
            "threat_level": {
                "choice": "0",
                "confidence": 0.95,
            }
        }
    }

    mock_http_client = AsyncMock(spec=AsyncClient)
    mock_http_client.post.side_effect = [
        Response(
            status_code=200,
            content=json.dumps(vlm_mock).encode(),
            request=httpx.Request("POST", "https://api.elorian.ai/v1/chat/completions"),
        ),
        Response(
            status_code=200,
            content=json.dumps(jev_mock).encode(),
            request=httpx.Request("POST", "https://api.typesafe.ai/v1/systemone"),
        ),
    ]

    app.state.client = mock_http_client

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "model": "gpt-4o-threat",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Analyze event"}],
                }
            ],
        }

        with patch("app.api.ai.router.settings.UPSTREAM_THREAT_ENABLED", False):
            res = await client.post("/v1/chat/completions", json=payload)
            assert res.status_code == 200
            first_call_payload = mock_http_client.post.call_args_list[0].kwargs["json"]
            assert first_call_payload["model"] == "gpt-4o"

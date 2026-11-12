import httpx
from httpx import AsyncClient
from loguru import logger
from pydantic import BaseModel, HttpUrl


async def base_post_request[T: BaseModel](
    client: AsyncClient,
    url: HttpUrl,
    payload: BaseModel,
    response_model: type[T],
    bearer: str | None = None,
) -> T:
    headers = httpx.Headers({"Content-Type": "application/json"})
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"

    response = await client.post(
        str(url),
        headers=headers,
        json=payload.model_dump(exclude_none=True),
    )
    logger.debug(
        "Response received from upstream",
        extra={
            "url": str(url),
            "status": response.status_code,
            "response_model": response_model.__name__,
        },
    )
    _ = response.raise_for_status()
    return response_model.model_validate_json(response.content)


def sample_evenly[T](items: list[T], k: int) -> list[T]:
    """Sample at most k items evenly spaced across the input list, preserving endpoints."""
    if len(items) <= k or k <= 0:
        return items
    if k == 1:
        return [items[0]]

    step = (len(items) - 1) / (k - 1)
    indices = [round(i * step) for i in range(k)]
    return [items[idx] for idx in indices]

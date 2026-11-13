from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import uuid4

import pydantic_core
from loguru import logger
from pydantic import (
    BaseModel,
    Field,
    computed_field,
)

from app.core.config import settings
from app.services import sample_evenly


class ImageUrlModel(BaseModel):
    url: str
    detail: str = "auto"


class TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str = Field(min_length=1)


class ImageContent(BaseModel):
    type: Literal["image_url"] = "image_url"
    image_url: ImageUrlModel


ContentItem = Annotated[TextContent | ImageContent, Field(discriminator="type")]


class InboundMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: list[ContentItem] | str


class AssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


class ReasoningChoice(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    MAX = "max"


class ReviewMetadata(BaseModel):
    title: str = Field(min_length=1)
    scene: str = Field(min_length=1)
    shortSummary: str = Field(min_length=1)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    potential_threat_level: int = Field(default=0, ge=0, le=2)

    @classmethod
    def from_llm_output(cls, content: str) -> Self:
        clean = content.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        start = clean.find("{")
        end = clean.rfind("}")
        json_slice = clean[start : end + 1] if start != -1 and end != -1 else clean

        try:
            data = pydantic_core.from_json(json_slice, allow_partial="trailing-strings")
            if isinstance(data, dict):
                title = str(data.get("title", "")).strip()
                scene = str(data.get("scene", "")).strip()
                summary = str(data.get("shortSummary", data.get("summary", ""))).strip()
                conf = float(data.get("confidence", 1.0))
                threat = int(data.get("potential_threat_level", data.get("threat_level", 0)))
                if title and scene:
                    return cls(
                        title=title[:70],
                        scene=scene,
                        shortSummary=(summary if summary else scene.split(".")[0].strip())[:280],
                        confidence=conf,
                        potential_threat_level=threat,
                    )
        except (ValueError, TypeError, KeyError):
            pass

        paragraphs = [p.replace("**", "").strip() for p in clean.split("\n\n") if p.strip()]
        first_para = paragraphs[0] if paragraphs else clean
        first_sentence = first_para.split(".")[0].strip()
        return cls(
            title=first_sentence[:70] if first_sentence else "Detected Activity",
            scene=clean,
            shortSummary=first_para[:280],
            confidence=1.0,
            potential_threat_level=0,
        )


class ChatCompletionRequest(BaseModel, extra="ignore"):
    model: str = settings.ELORIAN_MODEL
    messages: list[InboundMessage] = Field(min_length=1)
    max_completion_tokens: int = settings.MAX_OUTPUT_TOKENS
    reasoning_effort: ReasoningChoice | None = ReasoningChoice.LOW

    @property
    def inbound_prompt_text(self) -> str:
        first_msg = self.messages[0]
        if isinstance(first_msg.content, str):
            return first_msg.content
        for item in first_msg.content:
            if isinstance(item, TextContent):
                return item.text
        return ""

    @classmethod
    def apply_frigate_prompt(cls, request: Self) -> Self:
        out = request.model_copy(deep=True)
        first_msg = out.messages[0]

        if not settings.SYSTEM_PROMPT_PREFIX:
            return out

        prefix = settings.SYSTEM_PROMPT_PREFIX.strip() + "\n\n"
        if isinstance(first_msg.content, str):
            first_msg.content = prefix + first_msg.content
        elif isinstance(first_msg.content, list):
            for i, item in enumerate(first_msg.content):
                if isinstance(item, TextContent):
                    first_msg.content[i] = TextContent(text=prefix + item.text)
                    break
        return out

    @classmethod
    def sample_images(cls, request: Self, max_images: int = settings.MAX_SAMPLED_IMAGES) -> Self:
        out = request.model_copy(deep=True)
        first_msg = out.messages[0]

        if not isinstance(first_msg.content, list):
            return out

        text_items: list[ContentItem] = []
        image_items: list[ContentItem] = []

        for item in first_msg.content:
            if isinstance(item, ImageContent):
                image_items.append(item)
            else:
                text_items.append(item)

        sampled_images = sample_evenly(image_items, max_images)
        logger.debug(
            "Subsampled frames for request",
            original_frames=len(image_items),
            sampled_frames=len(sampled_images),
            max_cap=max_images,
        )

        first_msg.content = text_items + sampled_images
        return out


class PipelineState(BaseModel):
    pipeline: Literal[
        "Frigate NVR real-time CCTV stream with Elorian Glimpse visual reasoning agent"
    ] = "Frigate NVR real-time CCTV stream with Elorian Glimpse visual reasoning agent"
    domain: Literal["Residential perimeter and entry security monitoring"] = (
        "Residential perimeter and entry security monitoring"
    )
    visual_observation: str


class JevChoiceQuestion(BaseModel):
    type: Literal["choice"] = "choice"
    instructions: str
    criteria: dict[str, str]


class JevRequest(BaseModel):
    model: str = settings.TYPESAFE_MODEL
    state: PipelineState
    questions: dict[str, JevChoiceQuestion]

    @classmethod
    def threat_level_adapter(cls, observations: str) -> Self:
        return cls(
            state=PipelineState(visual_observation=observations),
            questions={
                "threat_level": JevChoiceQuestion(
                    instructions="Rate the security threat level for this residential camera event based on the visual interpretation produced by Elorian Glimpse.",
                    criteria={
                        "0": "Normal benign activity: residents, postal/courier deliveries, passing pedestrians or traffic, domestic pets, or wildlife.",
                        "1": "Suspicious activity warranting human review: loitering, peering into windows, testing handles or locks, scouting during unusual hours.",
                        "2": "Direct active threat or emergency: forced entry, carrying weapons or burglary tools, active vandalism, or aggressive intrusion.",
                    },
                )
            },
        )


class JevAnswer(BaseModel):
    choice: str
    confidence: float


class JevEvaluationResponse(BaseModel):
    answers: dict[str, JevAnswer]

    @computed_field
    @property
    def threat_level(self) -> int:
        val = self.answers.get("threat_level")
        if val and val.choice.isdigit():
            return int(val.choice)
        return 0

    @computed_field
    @property
    def confidence(self) -> float:
        val = self.answers.get("threat_level")
        if val:
            return float(val.confidence)
        return 0.8


class ChatCompletionChoice(BaseModel):
    message: AssistantMessage
    index: int = 0
    finish_reason: Literal["stop", "length"] | None = "stop"


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid4()}")
    object: Literal["chat.completion"] = "chat.completion"
    choices: list[ChatCompletionChoice] = Field(min_length=1)

    @computed_field
    @property
    def content(self) -> str:
        return self.choices[0].message.content

    @classmethod
    def review_adapter(cls, metadata: ReviewMetadata) -> Self:
        return cls(
            choices=[
                ChatCompletionChoice(message=AssistantMessage(content=metadata.model_dump_json()))
            ]
        )


class ModelItem(BaseModel):
    id: str
    object: Literal["model"] = "model"
    max_model_len: int = 262144


class ModelListResponse(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelItem]

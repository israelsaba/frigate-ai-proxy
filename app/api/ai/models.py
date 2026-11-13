import json
import re
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import uuid4

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


def clean_markdown_artifacts(text: str) -> str:
    """Strip markdown headers, bold tags, and list markers for plain text display."""
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
    cleaned = re.sub(r"#+\s*", "", cleaned)
    cleaned = re.sub(r"^[ \t]*[-*]\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def extract_sentences(text: str, max_sentences: int = 2) -> str:
    """Extract first n full sentences up to sentence terminators (. ! ?)."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    selected = [s.strip() for s in sentences if s.strip()][:max_sentences]
    return " ".join(selected)


def extract_review_narrative(content: str) -> tuple[str, str, str]:
    """
    Extract (title, scene, short_summary) from model response.
    Supports either pre-structured JSON or freeform vision narrative.
    Guarantees title, scene, and shortSummary are distinct.
    """
    clean_content = content.strip()

    try:
        json_candidate = clean_content
        if "```json" in json_candidate:
            json_candidate = json_candidate.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in json_candidate:
            json_candidate = json_candidate.split("```", 1)[1].split("```", 1)[0].strip()

        start = json_candidate.find("{")
        end = json_candidate.rfind("}")
        if start != -1 and end != -1:
            data = json.loads(json_candidate[start : end + 1])
            if isinstance(data, dict):
                title = str(data.get("title", "")).strip()
                scene = str(data.get("scene", "")).strip()
                summary = str(data.get("shortSummary", data.get("summary", ""))).strip()
                if title and scene:
                    return (
                        title[:80],
                        scene,
                        (summary if summary else extract_sentences(scene, 2))[:280],
                    )
    except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
        logger.debug(
            "Content not parsed as direct JSON, proceeding with narrative extraction", error=str(e)
        )

    scene = clean_content

    activity_match = re.search(
        r"(?:\*\*|##)?\s*(?:Activity observed|Activities|Activity assessment|Persons and activity|Subjects and activities|Activity description)\s*(?:\*\*|##)?:?\s*(.*?)(?=\n\s*(?:\*\*|##)|$)",
        clean_content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    activity_text = activity_match.group(1).strip() if activity_match else ""

    overview_match = re.search(
        r"(?:\*\*|##)?\s*(?:Scene overview|Scene description|Scene and camera view)\s*(?:\*\*|##)?:?\s*(.*?)(?=\n\s*(?:\*\*|##)|$)",
        clean_content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    overview_text = overview_match.group(1).strip() if overview_match else ""

    summary_source = (
        activity_text if activity_text else (overview_text if overview_text else clean_content)
    )
    cleaned_summary_source = clean_markdown_artifacts(summary_source)

    cleaned_summary_source = re.sub(
        r"^(The footage shows|The camera shows|Overhead view of|The video displays|In this clip|Throughout the clip)\s*,?\s*",
        "",
        cleaned_summary_source,
        flags=re.IGNORECASE,
    )
    if cleaned_summary_source:
        cleaned_summary_source = cleaned_summary_source[0].upper() + cleaned_summary_source[1:]

    short_summary = extract_sentences(cleaned_summary_source, max_sentences=2)
    if not short_summary or len(short_summary) < 10:
        short_summary = clean_markdown_artifacts(clean_content)[:250]
    short_summary = short_summary[:280].strip()

    first_clause = re.split(r"[,;—–.-]", short_summary)[0].strip()
    if 10 <= len(first_clause) <= 70:
        title = first_clause
    else:
        words = short_summary.split()
        title = " ".join(words[:7])
        if len(title) > 65:
            title = title[:65].rsplit(" ", 1)[0]

    title = clean_markdown_artifacts(title).strip(".,;: ")
    if title:
        title = title[0].upper() + title[1:]
    else:
        title = "Detected Activity"

    return title, scene, short_summary


class ChatCompletionRequest(BaseModel, extra="ignore"):
    model: str = settings.ELORIAN_MODEL
    messages: list[InboundMessage] = Field(min_length=1)
    max_completion_tokens: int = settings.MAX_OUTPUT_TOKENS
    reasoning_effort: ReasoningChoice | None = ReasoningChoice.LOW

    @property
    def inbound_prompt_text(self) -> str:
        """Extract the text prompt passed in by Frigate."""
        first_msg = self.messages[0]
        if isinstance(first_msg.content, str):
            return first_msg.content
        for item in first_msg.content:
            if isinstance(item, TextContent):
                return item.text
        return ""

    @classmethod
    def apply_frigate_prompt(cls, request: Self) -> Self:
        """
        Preserve the prompt configured directly in Frigate.
        Optionally prepend a system prompt prefix if defined in settings.
        """
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
        """Subsample image frames to control inference latency and token consumption."""
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


class ReviewMetadata(BaseModel):
    title: str = Field(min_length=1)
    scene: str = Field(min_length=1)
    shortSummary: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    potential_threat_level: int = Field(ge=0, le=2)

    @classmethod
    def hybrid_adapter(
        cls,
        observations: str,
        threat_level: int,
        confidence: float,
    ) -> Self:
        title, scene, short_summary = extract_review_narrative(observations)
        return cls(
            title=title,
            scene=scene,
            shortSummary=short_summary,
            confidence=confidence,
            potential_threat_level=threat_level,
        )


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

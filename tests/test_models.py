from app.api.ai.models import (
    ChatCompletionRequest,
    ImageContent,
    ImageUrlModel,
    InboundMessage,
    JevAnswer,
    JevEvaluationResponse,
    ReviewMetadata,
    TextContent,
)


def test_frigate_prompt_retention():
    frigate_prompt = (
        "Respond strictly with valid JSON with keys: title, scene, shortSummary.\n"
        "Activity context prompt:\n"
        "### Normal Activity Indicators (Level 0)\n"
        "- Known people in zone\n"
        "### Critical Threat Indicators (Level 2)\n"
        "- Active pixação or vandalism\n"
        "## Sequence Details\n"
        "- Camera: Entry Door\n"
        "- Duration: 45s\n"
    )
    request = ChatCompletionRequest(
        model="glimpse",
        messages=[
            InboundMessage(
                role="user",
                content=[
                    TextContent(text=frigate_prompt),
                    ImageContent(image_url=ImageUrlModel(url="data:image/jpeg;base64,abc")),
                ],
            )
        ],
    )

    prepared = ChatCompletionRequest.apply_frigate_prompt(request)
    assert prepared.inbound_prompt_text == frigate_prompt
    assert "Active pixação or vandalism" in prepared.inbound_prompt_text
    assert "Activity context prompt" in prepared.inbound_prompt_text


def test_image_sampling_preserves_prompt_and_limits_frames():
    images = [
        ImageContent(image_url=ImageUrlModel(url=f"data:image/jpeg;base64,img_{i}"))
        for i in range(50)
    ]
    prompt_text = "Analyze this sequence from Street Camera."
    request = ChatCompletionRequest(
        model="glimpse",
        messages=[
            InboundMessage(
                role="user",
                content=[TextContent(text=prompt_text), *images],
            )
        ],
    )

    sampled = ChatCompletionRequest.sample_images(request, max_images=10)
    msg_content = sampled.messages[0].content
    assert isinstance(msg_content, list)
    assert len(msg_content) == 11
    assert isinstance(msg_content[0], TextContent)
    assert msg_content[0].text == prompt_text
    assert all(isinstance(item, ImageContent) for item in msg_content[1:])


def test_jev_evaluation_response_parsing():
    response = JevEvaluationResponse(
        answers={"threat_level": JevAnswer(choice="2", confidence=0.98)}
    )
    assert response.threat_level == 2
    assert response.confidence == 0.98


def test_review_metadata_hybrid_adapter_distinct_fields():
    narrative = (
        "**Scene overview:** Front porch monitored by camera.\n"
        "**Activity observed:** A postal worker delivered an envelope to the mail slot and left immediately."
    )
    metadata = ReviewMetadata.hybrid_adapter(
        observations=narrative,
        threat_level=0,
        confidence=0.99,
    )
    assert metadata.potential_threat_level == 0
    assert metadata.confidence == 0.99
    assert metadata.title != metadata.scene
    assert metadata.shortSummary != metadata.scene
    assert metadata.title != metadata.shortSummary

import json

from app.api.ai.models import ReviewMetadata


def test_extract_review_metadata_from_json():
    payload = json.dumps(
        {
            "title": "Delivery courier dropping parcel",
            "scene": "A courier in a blue uniform walked up the front steps, placed a small cardboard box by the door, took a confirmation photo, and returned to their vehicle.",
            "shortSummary": "Courier placed a package on the porch and departed.",
            "confidence": 0.98,
            "potential_threat_level": 0,
        }
    )
    metadata = ReviewMetadata.from_llm_output(payload)
    assert metadata.title == "Delivery courier dropping parcel"
    assert "courier in a blue uniform" in metadata.scene
    assert metadata.shortSummary == "Courier placed a package on the porch and departed."
    assert metadata.confidence == 0.98
    assert metadata.potential_threat_level == 0
    assert metadata.title != metadata.scene
    assert metadata.shortSummary != metadata.scene


def test_extract_review_metadata_from_markdown_json_block():
    payload = """
    ```json
    {
      "title": "Person loitering near window",
      "scene": "An unidentified person approached the side garden window at 02:15 AM and stood observing the interior for 40 seconds.",
      "shortSummary": "Unidentified individual loitered near the side window during late hours.",
      "confidence": 0.91,
      "potential_threat_level": 1
    }
    ```
    """
    metadata = ReviewMetadata.from_llm_output(payload)
    assert metadata.title == "Person loitering near window"
    assert "02:15 AM" in metadata.scene
    assert "Unidentified individual" in metadata.shortSummary
    assert metadata.potential_threat_level == 1
    assert metadata.confidence == 0.91
    assert metadata.title != metadata.scene


def test_extract_review_metadata_partial_json():
    payload = '{"title": "Break-in Attempt", "scene": "Person attempting to force open entry door with tool", "potential_threat_level": 2'
    metadata = ReviewMetadata.from_llm_output(payload)
    assert metadata.title == "Break-in Attempt"
    assert "force open entry door" in metadata.scene
    assert metadata.potential_threat_level == 2


def test_extract_review_metadata_from_glimpse_freeform():
    sample_glimpse_output = """
**Scene overview**
The frame is an elevated outdoor view, filmed through a chain-link fence. The pavement is wet, suggesting recent rain. Several vehicles are parked in a service lane.

**Persons and activity**
One individual wearing a green T-shirt, gray shorts, white shoes, and a blue cap stands at the open driver's door of the white box truck.
The person is leaning forward into the cab area, appearing to reach inside.
    """
    metadata = ReviewMetadata.from_llm_output(sample_glimpse_output)

    assert metadata.title != metadata.scene
    assert metadata.shortSummary != metadata.scene
    assert len(metadata.title) <= 70
    assert len(metadata.shortSummary) <= 280
    assert "elevated outdoor view" in metadata.scene


def test_extract_review_metadata_fallback_short_text():
    short_text = "A dog ran across the front driveway chasing a ball."
    metadata = ReviewMetadata.from_llm_output(short_text)

    assert metadata.scene == short_text
    assert "dog ran across" in metadata.shortSummary
    assert len(metadata.title) <= 70
    assert metadata.title != metadata.scene

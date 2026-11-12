import json

from app.api.ai.models import extract_review_narrative


def test_extract_review_narrative_from_json():
    payload = json.dumps(
        {
            "title": "Delivery courier dropping parcel",
            "scene": "A courier in a blue uniform walked up the front steps, placed a small cardboard box by the door, took a confirmation photo, and returned to their vehicle.",
            "shortSummary": "Courier placed a package on the porch and departed.",
        }
    )
    title, scene, summary = extract_review_narrative(payload)
    assert title == "Delivery courier dropping parcel"
    assert "courier in a blue uniform" in scene
    assert summary == "Courier placed a package on the porch and departed."
    assert title != scene
    assert summary != scene


def test_extract_review_narrative_from_markdown_json_block():
    payload = """
    ```json
    {
      "title": "Person loitering near window",
      "scene": "An unidentified person approached the side garden window at 02:15 AM and stood observing the interior for 40 seconds.",
      "shortSummary": "Unidentified individual loitered near the side window during late hours."
    }
    ```
    """
    title, scene, summary = extract_review_narrative(payload)
    assert title == "Person loitering near window"
    assert "02:15 AM" in scene
    assert "Unidentified individual" in summary
    assert title != scene


def test_extract_review_narrative_from_glimpse_freeform():
    sample_glimpse_output = """
**Scene overview**
The frame is an elevated outdoor view, filmed through a chain-link fence. The pavement is wet, suggesting recent rain. Several vehicles are parked in a service lane.

**Persons and activity**
- One individual wearing a green T-shirt, gray shorts, white shoes, and a blue cap stands at the open driver's door of the white box truck.
- The person is leaning forward into the cab area, appearing to reach inside — consistent with retrieving an item.
    """
    title, scene, summary = extract_review_narrative(sample_glimpse_output)

    assert title != scene
    assert summary != scene
    assert title != summary
    assert len(title) <= 70
    assert len(summary) <= 280
    assert "green T-shirt" in summary or "box truck" in summary
    assert "elevated outdoor view" in scene


def test_extract_review_narrative_activity_observed_header():
    sample_output = """
**Scene overview:** The camera ("Entry Door") shows an indoor reception space.

**Activity observed:** Throughout the entire clip, a single person with long dark hair, wearing a dark top, remains seated at the table on the right side of the frame. The person shifts slightly while reviewing papers on the desktop.
    """
    title, scene, summary = extract_review_narrative(sample_output)

    assert title != scene
    assert summary != scene
    assert "remains seated at the table" in summary
    assert len(title) <= 70
    assert title != "The camera shows an indoor reception space."


def test_extract_review_narrative_fallback_short_text():
    short_text = "A dog ran across the front driveway chasing a ball."
    title, scene, summary = extract_review_narrative(short_text)

    assert scene == short_text
    assert "dog ran across" in summary
    assert len(title) <= 70
    assert title != scene

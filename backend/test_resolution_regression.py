import uuid

import pytest


def _non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def test_resolution_is_2_to_3_lines_and_single_video():
    """Regression lock for Slide-4 resolution format: warm 2-3 lines + one video."""
    from chatbot_engine import handle_message

    session_id = f"resolution-regression-{uuid.uuid4().hex[:8]}"
    patient_id = f"test-user-{uuid.uuid4().hex[:8]}"
    # Use seeded sample patient code because initial turns may be intake/greeting.
    patient_code = "PAT-002"

    scripted_messages = [
        "Hello.",
        "I have been using alcohol to unwind after work and my family is worried about me.",
        "I also wake up tired most mornings and want to change this.",
    ]

    result = None
    resolution = None
    for message in scripted_messages:
        result = handle_message(
            message,
            session_id=session_id,
            patient_id=patient_id,
            patient_code=patient_code,
        )
        resolution = result.get("resolution")
        if resolution:
            break

    assert result is not None
    assert resolution, "Expected a resolution payload on a non-crisis therapeutic turn"

    lines = resolution.get("lines") or _non_empty_lines(resolution.get("text", ""))
    assert 2 <= len(lines) <= 3, f"Expected 2-3 resolution lines, got {len(lines)}: {lines}"

    response_lines = _non_empty_lines(result.get("response", ""))
    assert response_lines == lines, "Expected final response text to match resolution lines"

    video = result.get("video")
    assert isinstance(video, dict), "Expected exactly one video object"
    assert video.get("title"), "Expected video title to be populated"
    assert video.get("url"), "Expected video url to be populated"


@pytest.mark.parametrize(
    ("message", "expected_intent", "expected_video_tag"),
    [
        ("I game all night and I get angry when I cannot stop.", "addiction_gaming", "addiction_gaming"),
        ("I cannot stop scrolling and I compare myself to others every time I post.", "addiction_social_media", "addiction_social_media"),
        ("I vape constantly and I reach for it whenever stress hits.", "addiction_nicotine", "addiction_nicotine"),
        ("I keep gambling to win back what I lost and the debt is building.", "addiction_gambling", "addiction_gambling"),
        ("I binge eat in secret when I feel overwhelmed and ashamed.", "addiction_food", "addiction_food"),
        ("I cannot stop working and I feel guilty whenever I rest.", "addiction_work", "addiction_work"),
        ("I shop online when I am stressed and hide the purchases after.", "addiction_shopping", "addiction_shopping"),
        ("I feel ashamed because I cannot stop watching porn even when I want to.", "addiction_pornography", "addiction_pornography"),
    ],
)
def test_non_alcohol_addictions_return_resolution_and_precise_video(message, expected_intent, expected_video_tag):
    from chatbot_engine import handle_message

    session_id = f"resolution-addiction-{uuid.uuid4().hex[:8]}"
    patient_id = f"test-user-{uuid.uuid4().hex[:8]}"

    result = handle_message(
        message,
        session_id=session_id,
        patient_id=patient_id,
        patient_code="PAT-002",
    )

    assert result.get("intent") == expected_intent

    resolution = result.get("resolution")
    assert resolution, f"Expected resolution payload for {expected_intent}"

    lines = resolution.get("lines") or _non_empty_lines(resolution.get("text", ""))
    assert 2 <= len(lines) <= 3, f"Expected 2-3 resolution lines for {expected_intent}, got {len(lines)}"

    video = result.get("video")
    assert isinstance(video, dict), f"Expected single video object for {expected_intent}"
    assert expected_video_tag in (video.get("tags") or []), (
        f"Expected video tags for {expected_intent} to include {expected_video_tag}, got {video.get('tags')}"
    )


@pytest.mark.parametrize(
    ("message", "expected_relationship"),
    [
        ("My wife is worried about how much I drink after work.", "wife"),
        ("My sister keeps telling me my gambling is getting worse.", "sister"),
        ("My parents are worried because I cannot stop vaping.", "parents"),
        ("My friends say I disappear into gaming every night.", "friends"),
    ],
)
def test_resolution_mentions_exact_relationship_when_present(message, expected_relationship):
    from chatbot_engine import handle_message

    session_id = f"resolution-relationship-{uuid.uuid4().hex[:8]}"
    patient_id = f"test-user-{uuid.uuid4().hex[:8]}"

    result = handle_message(
        message,
        session_id=session_id,
        patient_id=patient_id,
        patient_code="PAT-002",
    )

    resolution = result.get("resolution")
    assert resolution, "Expected resolution payload when relationship language is present"
    assert expected_relationship in result.get("response", "").lower()
    assert expected_relationship in " ".join(resolution.get("lines") or []).lower()


@pytest.mark.parametrize(
    ("message", "expected_focus", "expected_relationship", "unexpected_fragment"),
    [
        (
            "My dad is not aware about my drinking.",
            "disclosure_readiness",
            "dad",
            "closeness and concern",
        ),
        (
            "My mom is hating this idea about my drinking.",
            "relationship_friction",
            "mom",
            "closeness and concern",
        ),
    ],
)
def test_relationship_clause_tone_shapes_resolution(message, expected_focus, expected_relationship, unexpected_fragment):
    from chatbot_engine import handle_message

    session_id = f"resolution-clause-{uuid.uuid4().hex[:8]}"
    patient_id = f"test-user-{uuid.uuid4().hex[:8]}"

    result = handle_message(
        message,
        session_id=session_id,
        patient_id=patient_id,
        patient_code="PAT-001",
    )

    resolution = result.get("resolution")
    assert resolution, "Expected resolution payload for relationship clause handling"
    assert resolution.get("focus") == expected_focus
    assert expected_relationship in result.get("response", "").lower()
    assert unexpected_fragment not in result.get("response", "").lower()


def test_non_urge_relationship_message_does_not_force_urge_language():
    from chatbot_engine import handle_message

    result = handle_message(
        "My dad is not aware about my drinking.",
        session_id=f"resolution-no-urge-{uuid.uuid4().hex[:8]}",
        patient_id=f"test-user-{uuid.uuid4().hex[:8]}",
        patient_code="PAT-001",
    )

    response_text = result.get("response", "").lower()
    assert "feeling this urge" not in response_text
    assert "urge regulation" not in response_text


def test_explicit_alcohol_language_refines_generic_substance_intent():
    from chatbot_engine import handle_message

    result = handle_message(
        "My wife is worried about how much I drink after work.",
        session_id=f"resolution-alcohol-refine-{uuid.uuid4().hex[:8]}",
        patient_id=f"test-user-{uuid.uuid4().hex[:8]}",
        patient_code="PAT-001",
    )

    assert result.get("intent") == "addiction_alcohol"


@pytest.mark.parametrize(
    ("message", "expected_focus", "expected_fragment"),
    [
        (
            "I want to stop drinking before this gets worse.",
            "change_commitment",
            "wants to stop or do this differently",
        ),
        (
            "I slipped and had a drink last night.",
            "reset_after_lapse",
            "next stabilizing move",
        ),
        (
            "I feel ashamed that I drank again.",
            "shame_relief",
            "When shame takes over",
        ),
        (
            "Everyone expects me to fix my drinking and I feel pressured.",
            "boundary_protection",
            "pressure or scrutiny starts closing in",
        ),
    ],
)
def test_non_relationship_recovery_clauses_shape_resolution(message, expected_focus, expected_fragment):
    from chatbot_engine import handle_message

    result = handle_message(
        message,
        session_id=f"resolution-recovery-clause-{uuid.uuid4().hex[:8]}",
        patient_id=f"test-user-{uuid.uuid4().hex[:8]}",
        patient_code="PAT-001",
    )

    resolution = result.get("resolution")
    assert resolution, "Expected resolution payload for recovery clause handling"
    assert resolution.get("focus") == expected_focus
    assert expected_fragment.lower() in result.get("response", "").lower()


def test_specific_addiction_removes_generic_substance_secondary_tag():
    from chatbot_engine import handle_message

    result = handle_message(
        "My wife is worried about how much I drink after work.",
        session_id=f"resolution-secondary-clean-{uuid.uuid4().hex[:8]}",
        patient_id=f"test-user-{uuid.uuid4().hex[:8]}",
        patient_code="PAT-001",
    )

    assert result.get("intent") == "addiction_alcohol"
    assert "addiction_drugs" not in (result.get("secondary_intents") or [])

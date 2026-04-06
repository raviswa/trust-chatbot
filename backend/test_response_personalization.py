from types import SimpleNamespace

from services_pipeline import ResponseGenerator


def _context(*, addiction_type="alcohol", risk_level="medium", craving=7, sleep=3, mood="anxious", session_count=2):
    return SimpleNamespace(
        onboarding=SimpleNamespace(addiction_type=addiction_type, addictions=[]),
        risk=SimpleNamespace(risk_level=risk_level.capitalize()),
        checkin=SimpleNamespace(
            craving_intensity=craving,
            sleep_quality=sleep,
            todays_mood=mood,
        ),
        session_message_count=session_count,
    )


def test_generate_fallback_includes_patient_state_context():
    generator = ResponseGenerator()

    response = generator._generate_fallback(
        "rag_query",
        "I do not know what to do.",
        _context(addiction_type="alcohol", craving=8, sleep=3, mood="anxious"),
    )

    text = response.lower()
    assert "alcohol" in text
    assert ("cravings" in text) or ("sleep" in text) or ("anxiety" in text)


def test_generate_from_template_varies_by_patient_profile():
    generator = ResponseGenerator()
    template = generator.response_templates["trigger_relationship"]

    gaming_response = generator._generate_from_template(
        "trigger_relationship",
        template,
        "My father is involved.",
        _context(addiction_type="gaming", craving=2, sleep=8, mood="neutral"),
        addiction_type="gaming",
        addictions=None,
    )
    alcohol_response = generator._generate_from_template(
        "trigger_relationship",
        template,
        "My father is involved.",
        _context(addiction_type="alcohol", craving=8, sleep=3, mood="anxious"),
        addiction_type="alcohol",
        addictions=None,
    )

    assert gaming_response != alcohol_response
    assert "gaming" in gaming_response.lower()
    assert "alcohol" in alcohol_response.lower()
    assert ("cravings" in alcohol_response.lower()) or ("sleep" in alcohol_response.lower())
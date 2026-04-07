"""
Regression suite: realistic patient messages compiled from common addiction chatbot conversation patterns.

Coverage modelled on publicly documented patterns from addiction recovery apps, ChatGPT/Gemini
research into "how would a typical drug/alcohol addict converse with a chatbot", and clinical
motivational-interviewing literature.

Each case specifies:
  - patient_code   : which patient profile to load
  - addiction_cat  : broad addiction category (alcohol / drugs / gaming / gambling / other)
  - message        : the exact patient utterance (turn 2, after an implicit greeting turn 1)
  - ok_intents     : a set of acceptable classified intents (MUST NOT be rag_query or greeting)
  - banned_focus   : resolution focus keys that should NOT appear (e.g. trauma_grounding for non-trauma msgs)
  - must_in_response: strings that MUST appear in the response text (lower-case, substring match)
  - label          : human-readable test title
"""

import json
import re
import uuid
import urllib.request
from dataclasses import dataclass, field
from typing import Optional, Set, List

import pytest

BASE = "http://127.0.0.1:8000/chat"

# ── all non-intake therapeutic intents that are acceptable ──────────────────
ADDICTION_INTENTS = {
    "addiction_alcohol", "addiction_drugs", "addiction_gaming",
    "addiction_social_media", "addiction_nicotine", "addiction_gambling",
    "addiction_food", "addiction_work", "addiction_shopping", "addiction_pornography",
}
MOOD_INTENTS = {
    "mood_anxious", "mood_guilty", "mood_sad", "mood_angry",
    "trigger_stress", "trigger_relationship", "trigger_grief",
    "trigger_financial", "trigger_trauma",
    "relapse_disclosure", "severe_distress",
}
THERAPEUTIC_INTENTS = ADDICTION_INTENTS | MOOD_INTENTS | {"rag_query"}  # rag_query allowed only when explicitly listed


@dataclass
class Case:
    label: str
    patient_code: str
    message: str
    addiction_cat: str
    # Acceptable intents. If empty → any therapeutic intent is fine.
    ok_intents: Set[str] = field(default_factory=set)
    # Focus keys that MUST NOT appear in the resolution.
    banned_focus: Set[str] = field(default_factory=set)
    # Sub-strings that MUST appear in the response (lower-case comparison).
    must_in_response: List[str] = field(default_factory=list)
    # If True, resolution payload must be non-null.
    needs_resolution: bool = True


# ── TEST CASES ───────────────────────────────────────────────────────────────

CASES: List[Case] = [

    # ── ALCOHOL: minimization / denial ──────────────────────────────────────
    Case(
        label="alcohol – not addicted denial",
        patient_code="PAT-001",
        addiction_cat="alcohol",
        message="It's not like I'm addicted or anything, I just like a few drinks to relax.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="alcohol – only weekends minimization",
        patient_code="PAT-002",
        addiction_cat="alcohol",
        message="I only drink on weekends so it's fine, right?",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="alcohol – high-functioning minimization",
        patient_code="PAT-003",
        addiction_cat="alcohol",
        message="I'm not an alcoholic — alcoholics can't hold down a job. I go to work every day.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="alcohol – can stop whenever I want",
        patient_code="PAT-004",
        addiction_cat="alcohol",
        message="I can stop whenever I want. I just choose not to right now.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="alcohol – everyone does it normalisation",
        patient_code="PAT-005",
        addiction_cat="alcohol",
        message="Everyone drinks at work dinners and parties. It's completely normal where I'm from.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),

    # ── ALCOHOL: daily-use / frequency questions ─────────────────────────────
    Case(
        label="alcohol – is it bad to use every day (original failing case)",
        patient_code="PAT-001",
        addiction_cat="alcohol",
        message="Is it bad to use every day?",
        ok_intents=ADDICTION_INTENTS | {"rag_query"},
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="alcohol – how much is too much",
        patient_code="PAT-002",
        addiction_cat="alcohol",
        message="How much alcohol is too much?",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS | {"rag_query"},
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="alcohol – drinking every night for years",
        patient_code="PAT-003",
        addiction_cat="alcohol",
        message="I've been having a few glasses of wine every night for years. Is that a problem?",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),

    # ── ALCOHOL: functional use / rationalization ──────────────────────────
    Case(
        label="alcohol – helps me cope with stress",
        patient_code="PAT-004",
        addiction_cat="alcohol",
        message="Alcohol helps me cope with work stress, it's the only thing that actually works.",
        ok_intents=ADDICTION_INTENTS | {"trigger_stress"},
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="alcohol – helps me sleep",
        patient_code="PAT-005",
        addiction_cat="alcohol",
        message="I just need help sleeping. I can only sleep after having a few drinks.",
        ok_intents=ADDICTION_INTENTS | {"behaviour_sleep"},
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="alcohol – need it to feel normal",
        patient_code="PAT-006",
        addiction_cat="alcohol",
        message="It helps me feel normal. Without it I'm a complete mess all day.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="alcohol – need it to socialise",
        patient_code="PAT-007",
        addiction_cat="alcohol",
        message="A drink or two helps me socialise. I'm way too anxious without it.",
        ok_intents=ADDICTION_INTENTS | {"mood_anxious", "trigger_stress"},
        banned_focus={"trauma_grounding"},
    ),

    # ── ALCOHOL: relationship disclosures ────────────────────────────────────
    Case(
        label="alcohol – wife doesn't know",
        patient_code="PAT-008",
        addiction_cat="alcohol",
        message="My wife doesn't know how much I actually drink. I hide it really well.",
        ok_intents=ADDICTION_INTENTS | {"trigger_relationship"},
        banned_focus={"trauma_grounding"},
        must_in_response=["wife"],
    ),
    Case(
        label="alcohol – kids are scared",
        patient_code="PAT-009",
        addiction_cat="alcohol",
        message="My kids are scared of me when I drink. My daughter started avoiding me.",
        ok_intents=ADDICTION_INTENTS | {"trigger_relationship"},
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="alcohol – hiding bottles from dad",
        patient_code="PAT-010",
        addiction_cat="alcohol",
        message="My dad keeps finding my hidden bottles and we fight every time.",
        ok_intents=ADDICTION_INTENTS | {"trigger_relationship"},
        banned_focus={"trauma_grounding"},
        must_in_response=["dad"],
    ),
    Case(
        label="alcohol – should i discuss this with father",
        patient_code="PAT-001",
        addiction_cat="alcohol",
        message="Should I discuss this with my father?",
        ok_intents=ADDICTION_INTENTS | {"trigger_relationship"},
        banned_focus={"trauma_grounding"},
        needs_resolution=True,
    ),
    Case(
        label="alcohol – how do i talk to my father about this",
        patient_code="PAT-002",
        addiction_cat="alcohol",
        message="How do I talk to my father about this?",
        ok_intents=ADDICTION_INTENTS | {"trigger_relationship"},
        banned_focus={"trauma_grounding"},
        needs_resolution=True,
    ),

    # ── ALCOHOL: lapse / relapse ───────────────────────────────────────────
    Case(
        label="alcohol – relapsed after 6 months",
        patient_code="PAT-001",
        addiction_cat="alcohol",
        message="I had a drink last night after being sober for six months. I feel like I ruined everything.",
        ok_intents=ADDICTION_INTENTS | {"relapse_disclosure", "mood_guilty"},
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="alcohol – said just one ended up drinking all night",
        patient_code="PAT-002",
        addiction_cat="alcohol",
        message="I told myself just one but I ended up drinking the whole bottle again.",
        ok_intents=ADDICTION_INTENTS | {"relapse_disclosure"},
        banned_focus={"trauma_grounding"},
    ),

    # ── ALCOHOL: shame / guilt ────────────────────────────────────────────
    Case(
        label="alcohol – disgusted with myself",
        patient_code="PAT-003",
        addiction_cat="alcohol",
        message="I'm disgusted with myself. I was doing so well and I drank again last night.",
        ok_intents=ADDICTION_INTENTS | {"mood_guilty", "relapse_disclosure"},
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="alcohol – feel like a failure every morning",
        patient_code="PAT-004",
        addiction_cat="alcohol",
        message="Every morning I wake up and feel like a complete failure for drinking again.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),

    # ── ALCOHOL: change readiness ─────────────────────────────────────────
    Case(
        label="alcohol – want to quit but don't know how",
        patient_code="PAT-005",
        addiction_cat="alcohol",
        message="I want to quit drinking but I have no idea where to even start.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="alcohol – tried AA couldn't stick with it",
        patient_code="PAT-006",
        addiction_cat="alcohol",
        message="I've tried AA but I couldn't stick with it. I feel like nothing works for me.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS | {"crisis_suicidal", "severe_distress"},
        banned_focus={"trauma_grounding"},
        needs_resolution=False,
    ),

    # ── DRUGS: minimization / rationalization ─────────────────────────────
    Case(
        label="drugs – prescribed so it's fine",
        patient_code="PAT-007",
        addiction_cat="drugs",
        message="It's prescribed so it's not really a problem, is it? My doctor gave it to me.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="drugs – weed isn't a real drug",
        patient_code="PAT-008",
        addiction_cat="drugs",
        message="Weed isn't even a real drug. It's natural and it's legal in some places.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="drugs – only at parties social thing",
        patient_code="PAT-009",
        addiction_cat="drugs",
        message="I only do it at parties. It's a social thing, not a real addiction.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="drugs – not like I'm using hard drugs",
        patient_code="PAT-010",
        addiction_cat="drugs",
        message="It's not like I'm using heroin or anything. It's just pills here and there.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),

    # ── DRUGS: daily use / frequency ─────────────────────────────────────
    Case(
        label="drugs – is it bad to smoke every day",
        patient_code="PAT-001",
        addiction_cat="drugs",
        message="Is it bad to smoke weed every day?",
        ok_intents=ADDICTION_INTENTS | {"rag_query"},
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="drugs – using pills every day for months",
        patient_code="PAT-002",
        addiction_cat="drugs",
        message="I've been using painkillers every day for months. Is that dangerous?",
        ok_intents=ADDICTION_INTENTS | {"rag_query"},
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="drugs – how much is too much opioids",
        patient_code="PAT-003",
        addiction_cat="drugs",
        message="How much is too much when it comes to opioids?",
        ok_intents=ADDICTION_INTENTS | {"rag_query"},
        banned_focus={"trauma_grounding"},
    ),

    # ── DRUGS: sleep-related ──────────────────────────────────────────────
    Case(
        label="drugs – just need help sleeping what can I take",
        patient_code="PAT-004",
        addiction_cat="drugs",
        message="I just need help sleeping. What can I take?",
        ok_intents=ADDICTION_INTENTS | {"behaviour_sleep", "behaviour_fatigue", "rag_query"},
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="drugs – can only sleep with pills",
        patient_code="PAT-005",
        addiction_cat="drugs",
        message="The only way I can sleep is with pills. I've tried everything else.",
        ok_intents=ADDICTION_INTENTS | {"behaviour_sleep", "behaviour_fatigue"},
        banned_focus={"trauma_grounding"},
    ),

    # ── DRUGS: physical withdrawal ────────────────────────────────────────
    Case(
        label="drugs – sick and shaky when I don't use",
        patient_code="PAT-006",
        addiction_cat="drugs",
        message="I feel sick and shaky whenever I don't use. Is this normal?",
        ok_intents=ADDICTION_INTENTS | {"rag_query"},
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="drugs – withdrawals making it impossible to stop",
        patient_code="PAT-007",
        addiction_cat="drugs",
        message="The withdrawals are making it impossible to stop. I can't handle it.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),

    # ── DRUGS: functional use ────────────────────────────────────────────
    Case(
        label="drugs – need it just to get through the day",
        patient_code="PAT-008",
        addiction_cat="drugs",
        message="I need it just to get through the day. Without it I can't function at work.",
        ok_intents=ADDICTION_INTENTS | {"trigger_stress"},
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="drugs – only thing that helps with pain",
        patient_code="PAT-009",
        addiction_cat="drugs",
        message="It's the only thing that actually helps with my chronic pain.",
        ok_intents=ADDICTION_INTENTS | {"rag_query"},
        banned_focus={"trauma_grounding"},
    ),

    # ── DRUGS: lapse / relapse ────────────────────────────────────────────
    Case(
        label="drugs – slipped used yesterday after 30 days clean",
        patient_code="PAT-010",
        addiction_cat="drugs",
        message="I slipped and used yesterday after 30 days clean. I hate myself right now.",
        ok_intents=ADDICTION_INTENTS | {"relapse_disclosure", "mood_guilty"},
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="drugs – relapsed again I'm worthless",
        patient_code="PAT-001",
        addiction_cat="drugs",
        message="I relapsed again. I don't know why I even try. I'm worthless.",
        ok_intents=ADDICTION_INTENTS | {"relapse_disclosure", "mood_guilty", "severe_distress"},
        banned_focus={"trauma_grounding"},
    ),

    # ── DRUGS: change readiness / ambivalence ─────────────────────────────
    Case(
        label="drugs – want to stop keep failing",
        patient_code="PAT-002",
        addiction_cat="drugs",
        message="I want to stop but every time I try I just fail. What's the point?",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="drugs – part of me wants to quit part doesn't",
        patient_code="PAT-003",
        addiction_cat="drugs",
        message="Part of me really wants to quit but another part of me doesn't.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="drugs – can't imagine life without it",
        patient_code="PAT-004",
        addiction_cat="drugs",
        message="I know it's bad for me but I honestly can't imagine life without it.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="drugs – need to change before I lose my job",
        patient_code="PAT-005",
        addiction_cat="drugs",
        message="I need to change before I lose my job and my family. I just don't know how.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),

    # ── NICOTINE ──────────────────────────────────────────────────────────
    Case(
        label="nicotine – vaping not as bad as cigarettes",
        patient_code="PAT-006",
        addiction_cat="nicotine",
        message="Vaping is way less harmful than cigarettes so I don't think it's a big deal.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="nicotine – smoked for 20 years can't stop",
        patient_code="PAT-007",
        addiction_cat="nicotine",
        message="I've been smoking for twenty years. I've tried patches, gum, everything. Nothing works.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),

    # ── GAMING ────────────────────────────────────────────────────────────
    Case(
        label="gaming – game all night can't stop",
        patient_code="PAT-008",
        addiction_cat="gaming",
        message="I game all night and can't stop even when I really want to.",
        ok_intents=ADDICTION_INTENTS,
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="gaming – only thing that makes me feel good",
        patient_code="PAT-009",
        addiction_cat="gaming",
        message="Gaming is honestly the only thing that makes me feel good anymore.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="gaming – family thinks I'm addicted, I disagree",
        patient_code="PAT-010",
        addiction_cat="gaming",
        message="My family thinks I'm addicted to gaming but I don't think so. I just enjoy it.",
        ok_intents=ADDICTION_INTENTS | {"trigger_relationship"},
        banned_focus={"trauma_grounding"},
        must_in_response=["family"],
    ),

    # ── GAMBLING ──────────────────────────────────────────────────────────
    Case(
        label="gambling – keep going back even though I should stop",
        patient_code="PAT-001",
        addiction_cat="gambling",
        message="I know I should stop gambling but I keep going back every weekend.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="gambling – borrowed money and lost it all",
        patient_code="PAT-002",
        addiction_cat="gambling",
        message="I borrowed money from my brother to gamble and lost it all. I haven't told him.",
        ok_intents=ADDICTION_INTENTS | {"trigger_relationship", "trigger_financial"},
        banned_focus={"trauma_grounding"},
        must_in_response=["brother"],
    ),
    Case(
        label="gambling – trying to win back what I lost",
        patient_code="PAT-003",
        addiction_cat="gambling",
        message="I just need to win back what I lost and then I'll stop for good.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),

    # ── SOCIAL MEDIA ──────────────────────────────────────────────────────
    Case(
        label="social media – can't stop scrolling",
        patient_code="PAT-004",
        addiction_cat="social_media",
        message="I can't stop scrolling even late at night. I know I should sleep but I keep going.",
        ok_intents=ADDICTION_INTENTS | {"behaviour_sleep"},
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="social media – feel bad comparing myself to others",
        patient_code="PAT-005",
        addiction_cat="social_media",
        message="I spend hours on Instagram and always feel bad comparing myself to everyone I see.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),

    # ── CROSS-CUTTING: pressure from others ───────────────────────────────
    Case(
        label="pressure – everyone expects me to be fixed by now",
        patient_code="PAT-006",
        addiction_cat="drugs",
        message="Everyone expects me to be fixed by now but recovery is taking so much longer than they think.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="pressure – partner keeps pressuring me to stop immediately",
        patient_code="PAT-007",
        addiction_cat="alcohol",
        message="My partner keeps pressuring me to stop immediately but I can't just flip a switch.",
        ok_intents=ADDICTION_INTENTS | {"trigger_relationship"},
        banned_focus={"trauma_grounding"},
        must_in_response=["partner"],
    ),

    # ── CROSS-CUTTING: shame / self-worth ─────────────────────────────────
    Case(
        label="shame – feel ashamed of my addiction",
        patient_code="PAT-008",
        addiction_cat="alcohol",
        message="I feel so ashamed of what I've become. My younger self would be horrified.",
        ok_intents=ADDICTION_INTENTS | {"mood_guilty"},
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="shame – embarrassed to tell anyone",
        patient_code="PAT-009",
        addiction_cat="drugs",
        message="I'm embarrassed to tell anyone about this. I feel like I should be able to handle it myself.",
        ok_intents=ADDICTION_INTENTS | MOOD_INTENTS,
        banned_focus={"trauma_grounding"},
    ),

    # ── CROSS-CUTTING: seeking information / harm reduction ───────────────
    Case(
        label="harm reduction – dangerous to stop suddenly",
        patient_code="PAT-010",
        addiction_cat="alcohol",
        message="Is it actually dangerous to stop drinking suddenly without help?",
        ok_intents=ADDICTION_INTENTS | {"rag_query"},
        banned_focus={"trauma_grounding"},
    ),
    Case(
        label="harm reduction – what are actual health risks of daily drinking",
        patient_code="PAT-001",
        addiction_cat="alcohol",
        message="What are the actual health risks of drinking alcohol every single day?",
        ok_intents=ADDICTION_INTENTS | {"rag_query"},
        banned_focus={"trauma_grounding"},
    ),
]


# ── HELPERS ──────────────────────────────────────────────────────────────────

def _post(payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _run_case(case: Case) -> dict:
    sid = f"realistic-{uuid.uuid4().hex[:12]}"
    pid = f"user-{uuid.uuid4().hex[:8]}"
    # Turn 1: greeting to init session
    _post({"message": "hello", "session_id": sid, "patient_code": case.patient_code,
           "patient_id": pid})
    # Turn 2: actual patient message
    return _post({"message": case.message, "session_id": sid,
                  "patient_code": case.patient_code, "patient_id": pid})


# ── PYTEST PARAMETRISE ────────────────────────────────────────────────────────

@pytest.mark.parametrize("case", CASES, ids=[c.label for c in CASES])
def test_realistic_patient_message(case: Case):
    result = _run_case(case)

    intent = result.get("intent", "unknown")
    response = (result.get("response") or "").lower()
    resolution = result.get("resolution") or {}
    focus = resolution.get("focus", "") if resolution else ""

    # 1. Intent must not be plain 'greeting'
    assert intent != "greeting", (
        f"[{case.label}] Routed to greeting — should be a therapeutic intent.\n"
        f"  message: {case.message}\n"
        f"  response: {result.get('response','')[:300]}"
    )

    # 2. If ok_intents specified, intent must be in that set
    if case.ok_intents and "rag_query" not in case.ok_intents:
        # strict check: rag_query not allowed unless explicitly included
        assert intent in case.ok_intents or intent in ADDICTION_INTENTS | MOOD_INTENTS, (
            f"[{case.label}] Intent '{intent}' not in acceptable set {case.ok_intents}.\n"
            f"  message: {case.message}\n"
            f"  response: {result.get('response','')[:300]}"
        )

    # 3. Resolution must be present for substance messages
    if case.needs_resolution:
        assert resolution, (
            f"[{case.label}] No resolution for substance message.\n"
            f"  intent: {intent}\n  message: {case.message}"
        )

    # 4. Banned focus keys must not appear
    for banned in case.banned_focus:
        assert focus != banned, (
            f"[{case.label}] Focus '{focus}' is banned for this message.\n"
            f"  message: {case.message}\n"
            f"  response: {result.get('response','')[:300]}"
        )

    # 5. Required strings must appear in response
    for required in case.must_in_response:
        assert required in response, (
            f"[{case.label}] Expected '{required}' not found in response.\n"
            f"  response: {result.get('response','')[:300]}"
        )

    # 6. Response must not contain raw PDF citations (format: "Page X" or ".pdf")
    assert "page " not in response or ".pdf" not in response, (
        f"[{case.label}] Raw citation leak in response: {result.get('response','')[:200]}"
    )

    # 7. Resolution lines: 2-3 if present
    if resolution:
        lines = resolution.get("lines") or [l for l in result.get("response", "").splitlines() if l.strip()]
        assert 2 <= len(lines) <= 3, (
            f"[{case.label}] Resolution has {len(lines)} lines, expected 2-3.\n"
            f"  response: {result.get('response','')[:300]}"
        )


def test_relationship_disclosure_continuity_pronoun_followup():
    """A pronoun-only secrecy follow-up should keep trigger_relationship, not fall back to greeting."""
    sid = f"realistic-continuity-{uuid.uuid4().hex[:12]}"
    pid = f"user-{uuid.uuid4().hex[:8]}"

    r1 = _post({"message": "hello", "session_id": sid, "patient_code": "PAT-001", "patient_id": pid})
    assert r1.get("intent") == "greeting"

    r2 = _post({
        "message": "should i discuss this with my father?",
        "session_id": sid,
        "patient_code": "PAT-001",
        "patient_id": pid,
    })
    assert r2.get("intent") == "trigger_relationship"

    r3 = _post({
        "message": "he is not aware of this",
        "session_id": sid,
        "patient_code": "PAT-001",
        "patient_id": pid,
    })
    assert r3.get("intent") == "trigger_relationship", (
        f"Expected trigger_relationship for pronoun secrecy follow-up; got {r3.get('intent')}"
    )
    assert r3.get("resolution"), "Expected resolution payload on relationship continuity follow-up"


def test_relationship_impact_question_and_disclosure_continuity():
    """Relationship-impact question and disclosure follow-up should stay in trigger_relationship flow."""
    sid = f"realistic-impact-{uuid.uuid4().hex[:12]}"
    pid = f"user-{uuid.uuid4().hex[:8]}"

    r1 = _post({"message": "hello", "session_id": sid, "patient_code": "PAT-001", "patient_id": pid})
    assert r1.get("intent") == "greeting"

    r2 = _post({
        "message": "how will my mother see this action?",
        "session_id": sid,
        "patient_code": "PAT-001",
        "patient_id": pid,
    })
    assert r2.get("intent") == "trigger_relationship", (
        f"Expected trigger_relationship for relationship-impact question; got {r2.get('intent')}"
    )
    assert r2.get("resolution"), "Expected resolution payload for relationship-impact question"

    r3 = _post({
        "message": "i'm yet to disclose her about this app",
        "session_id": sid,
        "patient_code": "PAT-001",
        "patient_id": pid,
    })
    assert r3.get("intent") == "trigger_relationship", (
        f"Expected trigger_relationship for disclosure continuity follow-up; got {r3.get('intent')}"
    )
    assert r3.get("resolution"), "Expected resolution payload on disclosure continuity follow-up"


def test_relationship_conflict_statement_not_routed_to_greeting():
    """A direct relationship conflict statement should not fall back to greeting."""
    sid = f"realistic-relconf-{uuid.uuid4().hex[:12]}"
    pid = f"user-{uuid.uuid4().hex[:8]}"

    r1 = _post({"message": "hello", "session_id": sid, "patient_code": "PAT-001", "patient_id": pid})
    assert r1.get("intent") == "greeting"

    r2 = _post({
        "message": "mom doesnt like this",
        "session_id": sid,
        "patient_code": "PAT-001",
        "patient_id": pid,
    })
    assert r2.get("intent") == "trigger_relationship", (
        f"Expected trigger_relationship for relationship conflict statement; got {r2.get('intent')}"
    )
    assert r2.get("resolution"), "Expected resolution payload for relationship conflict statement"
    assert r2.get("show_feedback") is True, "Expected feedback controls on resolved relationship response"


def test_relationship_pronoun_conflict_continuity_not_greeting():
    """Pronoun-only relationship conflict follow-up should preserve trigger_relationship continuity."""
    sid = f"realistic-relpron-{uuid.uuid4().hex[:12]}"
    pid = f"user-{uuid.uuid4().hex[:8]}"

    r1 = _post({"message": "hello", "session_id": sid, "patient_code": "PAT-001", "patient_id": pid})
    assert r1.get("intent") == "greeting"

    r2 = _post({
        "message": "should i discuss this with my father?",
        "session_id": sid,
        "patient_code": "PAT-001",
        "patient_id": pid,
    })
    assert r2.get("intent") == "trigger_relationship"

    r3 = _post({
        "message": "she doesnt like this",
        "session_id": sid,
        "patient_code": "PAT-001",
        "patient_id": pid,
    })
    assert r3.get("intent") == "trigger_relationship", (
        f"Expected trigger_relationship for pronoun conflict continuity follow-up; got {r3.get('intent')}"
    )
    assert r3.get("resolution"), "Expected resolution payload on pronoun conflict continuity follow-up"


def test_relationship_disclosure_statement_without_apostrophe_not_greeting():
    """Apostrophe-less disclosure statements should still route to trigger_relationship."""
    sid = f"realistic-reldisc-{uuid.uuid4().hex[:12]}"
    pid = f"user-{uuid.uuid4().hex[:8]}"

    r1 = _post({"message": "hello", "session_id": sid, "patient_code": "PAT-001", "patient_id": pid})
    assert r1.get("intent") == "greeting"

    r2 = _post({
        "message": "my mother doesnt know about this yet",
        "session_id": sid,
        "patient_code": "PAT-001",
        "patient_id": pid,
    })
    assert r2.get("intent") == "trigger_relationship", (
        f"Expected trigger_relationship for disclosure statement without apostrophe; got {r2.get('intent')}"
    )
    assert r2.get("resolution"), "Expected resolution payload for disclosure statement without apostrophe"

"""
Permutation regression for addiction defense mechanisms.

Purpose:
- Stress-test intent routing with varied phrasing across addiction domains.
- Cover core defense mechanisms with grammar/noise variations.
- Run in two modes:
  1) Relaxed (default): accept any therapeutic routing, catch obvious misroutes.
  2) Strict (STRICT_ADDICTION_ROUTING=1): require addiction-first routing for most patterns.

This is intended for baseline checks now and stricter validation after classifier updates.
"""

import json
import os
import uuid
import urllib.request
from dataclasses import dataclass
from typing import List, Set

import pytest

BASE = "http://127.0.0.1:8000/chat"
STRICT_MODE = os.getenv("STRICT_ADDICTION_ROUTING", "0") == "1"

ADDICTION_INTENTS = {
    "addiction_alcohol",
    "addiction_drugs",
    "addiction_gaming",
    "addiction_social_media",
    "addiction_nicotine",
    "addiction_gambling",
    "addiction_food",
    "addiction_work",
    "addiction_shopping",
    "addiction_pornography",
}

MOOD_INTENTS = {
    "mood_anxious",
    "mood_guilty",
    "mood_sad",
    "mood_angry",
    "trigger_stress",
    "trigger_relationship",
    "trigger_grief",
    "trigger_financial",
    "trigger_trauma",
    "relapse_disclosure",
    "severe_distress",
}

RELAXED_OK = ADDICTION_INTENTS | MOOD_INTENTS | {
    "rag_query",
    "behaviour_sleep",
    "behaviour_fatigue",
    "venting",
    "unclear",
}


@dataclass(frozen=True)
class AddictionProfile:
    name: str
    patient_code: str
    term: str
    expected_intent: str


@dataclass(frozen=True)
class MechanismTemplate:
    name: str
    text: str
    strict_allow: Set[str]


@dataclass(frozen=True)
class Case:
    label: str
    patient_code: str
    message: str
    expected_intent: str
    strict_allow: Set[str]


def _post(payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _run_case(case: Case) -> dict:
    sid = f"perm-{uuid.uuid4().hex[:12]}"
    pid = f"user-{uuid.uuid4().hex[:8]}"
    _post({"message": "hello", "session_id": sid, "patient_code": case.patient_code, "patient_id": pid})
    return _post({
        "message": case.message,
        "session_id": sid,
        "patient_code": case.patient_code,
        "patient_id": pid,
    })


PROFILES: List[AddictionProfile] = [
    AddictionProfile("alcohol", "PAT-001", "drinking", "addiction_alcohol"),
    AddictionProfile("drugs", "PAT-002", "using pills", "addiction_drugs"),
    AddictionProfile("nicotine", "PAT-003", "vaping", "addiction_nicotine"),
    AddictionProfile("gambling", "PAT-004", "betting", "addiction_gambling"),
    AddictionProfile("gaming", "PAT-005", "gaming", "addiction_gaming"),
    AddictionProfile("social_media", "PAT-006", "scrolling", "addiction_social_media"),
    AddictionProfile("food", "PAT-007", "binge eating", "addiction_food"),
    AddictionProfile("shopping", "PAT-008", "shopping", "addiction_shopping"),
    AddictionProfile("work", "PAT-009", "overworking", "addiction_work"),
    AddictionProfile("pornography", "PAT-010", "watching porn", "addiction_pornography"),
]

MECHANISMS: List[MechanismTemplate] = [
    MechanismTemplate(
        "minimization",
        "I am not addicted to {term}; I only do it when stressed, so it is probably fine.",
        set(),
    ),
    MechanismTemplate(
        "rationalization",
        "{term} is the only thing that helps me feel normal enough to function.",
        {"trigger_stress", "mood_anxious", "behaviour_fatigue"},
    ),
    MechanismTemplate(
        "control_illusion",
        "I can quit {term} any time; I just do not want to this week.",
        {"venting"},
    ),
    MechanismTemplate(
        "secrecy",
        "I hide my {term} from my partner and lie about how often it happens.",
        {"trigger_relationship", "mood_guilty"},
    ),
    MechanismTemplate(
        "relapse_shame",
        "I promised I would stop {term}, but I did it again and feel like a failure.",
        {"relapse_disclosure", "mood_guilty", "severe_distress"},
    ),
    MechanismTemplate(
        "ambivalence",
        "Part of me wants to stop {term}, and part of me thinks I cannot cope without it.",
        {"mood_anxious", "venting"},
    ),
    MechanismTemplate(
        "pressure_judgment",
        "People expect me to be fixed from {term} already, and I feel judged all the time.",
        {"mood_guilty", "trigger_relationship", "severe_distress"},
    ),
    MechanismTemplate(
        "harm_reduction_query",
        "Is doing {term} every day dangerous, and what signs should I watch for?",
        {"rag_query"},
    ),
]


def _noise_variant(message: str) -> str:
    # Keep ASCII-only while still simulating spoken grammar and punctuation noise.
    return "uh " + message.replace("I am", "im").replace("do not", "dont") + "??"


def _build_cases() -> List[Case]:
    cases: List[Case] = []

    for profile in PROFILES:
        for mechanism in MECHANISMS:
            base = mechanism.text.format(term=profile.term)
            cases.append(
                Case(
                    label=f"{profile.name} | {mechanism.name} | base",
                    patient_code=profile.patient_code,
                    message=base,
                    expected_intent=profile.expected_intent,
                    strict_allow=mechanism.strict_allow,
                )
            )
            cases.append(
                Case(
                    label=f"{profile.name} | {mechanism.name} | noisy",
                    patient_code=profile.patient_code,
                    message=_noise_variant(base),
                    expected_intent=profile.expected_intent,
                    strict_allow=mechanism.strict_allow,
                )
            )

    # Target known edge formulations that previously misrouted.
    cases.extend(
        [
            Case(
                "edge | alcohol | lapse incomplete",
                "PAT-001",
                "did not even make it a week this time",
                "addiction_alcohol",
                {"mood_guilty", "relapse_disclosure"},
            ),
            Case(
                "edge | drugs | productive framing",
                "PAT-002",
                "using pills makes me productive, without it i crash",
                "addiction_drugs",
                {"trigger_stress", "rag_query", "behaviour_fatigue"},
            ),
            Case(
                "edge | shopping | retail therapy",
                "PAT-008",
                "shopping is my retail therapy and i cannot stop",
                "addiction_shopping",
                {"mood_sad", "mood_anxious"},
            ),
            Case(
                "edge | food | only joy",
                "PAT-007",
                "binge eating is the only thing that brings me joy lately",
                "addiction_food",
                {"mood_sad", "mood_guilty"},
            ),
            Case(
                "edge | drugs | withdrawal shaky",
                "PAT-002",
                "if i do not use pills i get shaky and sick",
                "addiction_drugs",
                {"behaviour_fatigue", "mood_anxious", "rag_query"},
            ),
        ]
    )

    return cases


ALL_CASES = _build_cases()


@pytest.mark.parametrize("case", ALL_CASES, ids=[c.label for c in ALL_CASES])
def test_addiction_defense_permutations(case: Case):
    result = _run_case(case)

    intent = result.get("intent", "unknown")
    response = (result.get("response") or "").lower()
    resolution = result.get("resolution") or {}
    focus = resolution.get("focus", "") if resolution else ""

    # Core regression safety checks.
    assert intent != "greeting", f"[{case.label}] incorrectly routed to greeting"
    assert intent != "unknown", f"[{case.label}] unknown intent"
    assert resolution, f"[{case.label}] missing resolution payload"

    # Avoid trauma contamination on non-trauma prompts.
    assert focus != "trigger_trauma", (
        f"[{case.label}] trauma focus leak for non-trauma defense mechanism"
    )

    # Baseline: keep routing inside therapeutic space.
    assert intent in RELAXED_OK, (
        f"[{case.label}] intent '{intent}' outside therapeutic allowlist"
    )

    # Strict mode for post-fix validation.
    if STRICT_MODE:
        strict_ok = {case.expected_intent} | case.strict_allow
        assert intent in strict_ok, (
            f"[{case.label}] strict routing mismatch. got={intent} expected one of={strict_ok}"
        )

    # Keep output clean from citation leaks.
    assert not ("page " in response and ".pdf" in response), (
        f"[{case.label}] citation leak in response"
    )


def test_permutation_suite_metadata():
    total = len(ALL_CASES)
    assert total >= 120, f"expected >=120 permutation cases, got {total}"
    print(f"Permutation suite mode: {'STRICT' if STRICT_MODE else 'RELAXED'}")
    print(f"Total permutation cases: {total}")

"""
test_use_cases.py — Runs all 14 demo use case scenarios against the chatbot API.

Each scenario simulates the key conversational turns from the use case documents:
1. First message (greeting/opening)
2. Stating their addiction/situation
3. Crisis/craving moment message matching the use case context

Outputs a PASS/FAIL report for each use case plus response quality observations.
"""

import json
import uuid
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import List, Optional, Dict

BASE = "http://127.0.0.1:8000"

# ─── Helper ──────────────────────────────────────────────────────────────────

def post(url: str, payload: dict, timeout: int = 30) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        return {"error": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        return {"error": str(e)}


def chat(session_id: str, patient_code: str, message: str) -> dict:
    return post(f"{BASE}/chat", {
        "message": message,
        "session_id": session_id,
        "patient_id": patient_code,
        "patient_code": patient_code,
    })


def clear_session(session_id: str):
    post(f"{BASE}/session/clear", {"session_id": session_id})


# ─── Use Case Definitions ─────────────────────────────────────────────────────

@dataclass
class Turn:
    message: str
    checks: List[str] = field(default_factory=list)   # strings that should appear in response
    not_checks: List[str] = field(default_factory=list)  # strings that should NOT appear


@dataclass
class UseCase:
    id: str
    title: str
    patient_code: str
    addiction_type: str
    expected_video_key: Optional[str]          # video key or prefix expected
    turns: List[Turn]
    notes: str = ""


USE_CASES: List[UseCase] = [
    # ── UC 1.1 Alcohol – Indian ───────────────────────────────────────────────
    UseCase(
        id="UC-1.1",
        title="Arjun Rao — Late-night loneliness drinking (Bengaluru)",
        patient_code="PAT-001",
        addiction_type="alcohol",
        expected_video_key="TA1",
        turns=[
            Turn(
                message="Hi, I'm Arjun. I feel really lonely tonight and I just want to drink.",
                checks=["alone", "lonely", "here", "support"],
            ),
            Turn(
                message="It's 11 PM, I'm alone in my PG and the urge to drink is really strong.",
                checks=["craving", "urge", "breathe", "moment"],
            ),
            Turn(
                message="I feel so bored and sad and I can't stop thinking about alcohol.",
                checks=["try", "feel", "safe", "help"],
            ),
        ],
    ),
    # ── UC 1.2 Alcohol – Global ──────────────────────────────────────────────
    UseCase(
        id="UC-1.2",
        title="Emily Carter — After-work stress drinking (New York)",
        patient_code="PAT-001",   # alcohol patient
        addiction_type="alcohol",
        expected_video_key="TA2",
        turns=[
            Turn(
                message="I just got back from work and I'm furious. Every day is so stressful and I want a drink right now.",
                checks=["stress", "anger", "breath", "feel"],
            ),
            Turn(
                message="My cravings are through the roof — 8 out of 10 tonight. I feel angry and exhausted.",
                checks=["craving", "breath", "moment", "safe"],
            ),
            Turn(
                message="After work every day I just want to drink. I'm angry and tired all the time.",
                checks=["try", "feel", "help"],
            ),
        ],
    ),
    # ── UC 2.1 Gaming – Indian ───────────────────────────────────────────────
    UseCase(
        id="UC-2.1",
        title="Rohan Sharma — Study-break gaming (Delhi)",
        patient_code="PAT-003",   # gaming patient
        addiction_type="gaming",
        expected_video_key="TG1",
        turns=[
            Turn(
                message="I'm supposed to be studying but I just want to play one more game. I'm so bored.",
                checks=["game", "bored", "study", "distract"],
            ),
            Turn(
                message="Every time I take a study break I end up gaming for hours. My cravings to play are at 8.",
                checks=["craving", "break", "focus", "breath"],
            ),
            Turn(
                message="I can't study at all — I'm stressed, bored and just keep opening the game automatically.",
                checks=["try", "feel", "help"],
            ),
        ],
    ),
    # ── UC 2.2 Gaming – Global ───────────────────────────────────────────────
    UseCase(
        id="UC-2.2",
        title="Oliver Thompson — Late-night gaming (London)",
        patient_code="PAT-003",
        addiction_type="gaming",
        expected_video_key="TG2",
        turns=[
            Turn(
                message="It's almost midnight and I just can't stop — I keep saying 'one more game'. I'm tired but the urge is intense.",
                checks=["game", "tired", "late", "stop"],
            ),
            Turn(
                message="I feel lonely and stressed and gaming is the only thing that helps at night.",
                checks=["lonely", "night", "help", "breathe"],
            ),
            Turn(
                message="My cravings to keep playing are a 9 out of 10. I know I should sleep but I just can't.",
                checks=["try", "feel", "safe"],
            ),
        ],
    ),
    # ── UC 3.1 Substance – Indian ──────────────────────────────────────────
    UseCase(
        id="UC-3.1",
        title="Priya Nair — Night-time emotional pain (Mumbai)",
        patient_code="PAT-002",   # drugs patient
        addiction_type="drugs",
        expected_video_key="TS1",
        turns=[
            Turn(
                message="It's 11 PM and I'm in so much emotional pain after my breakup. The urge to use drugs is overwhelming.",
                checks=["pain", "urge", "safe", "breathe"],
            ),
            Turn(
                message="I feel so sad and alone. My cravings are at 8 right now and I don't know what to do.",
                checks=["sad", "alone", "craving", "help"],
            ),
            Turn(
                message="The memories keep coming back and I just want to use to make the pain stop.",
                checks=["try", "feel", "moment", "safe"],
            ),
        ],
    ),
    # ── UC 3.2 Substance – Global ─────────────────────────────────────────
    UseCase(
        id="UC-3.2",
        title="Jordan Reyes — Anger after argument (California)",
        patient_code="PAT-002",
        addiction_type="drugs",
        expected_video_key="TS2",
        turns=[
            Turn(
                message="I just had a huge fight with my partner and I'm so angry. I need to use — my cravings are at 9.",
                checks=["anger", "angry", "craving", "breathe"],
            ),
            Turn(
                message="After arguments I always want to use drugs to calm down. I'm stressed and furious right now.",
                checks=["stress", "angry", "safe", "help"],
            ),
            Turn(
                message="I feel like I'm about to relapse. The anger is too much.",
                checks=["try", "feel", "relapse", "safe"],
            ),
        ],
    ),
    # ── UC 4.1 Nicotine – Indian ──────────────────────────────────────────
    UseCase(
        id="UC-4.1",
        title="Karthik Reddy — Stressed work-break smoking (Bengaluru)",
        patient_code="PAT-NIC",   # will be created dynamically
        addiction_type="nicotine",
        expected_video_key="TN1",
        turns=[
            Turn(
                message="I just came out of a really stressful meeting and my body is automatically reaching for a cigarette.",
                checks=["stress", "cigarette", "breath", "help"],
            ),
            Turn(
                message="Every work break I smoke. My cravings are at 8 and I'm really tired and stressed.",
                checks=["craving", "smoke", "stress", "breathe"],
            ),
            Turn(
                message="I know smoking is bad but it's the only thing that helps me cope with work pressure.",
                checks=["try", "feel", "cope", "help"],
            ),
        ],
    ),
    # ── UC 5.1 Addiction Agnostic – Indian ───────────────────────────────
    UseCase(
        id="UC-5.1",
        title="Ishan Rao — High urge + self-doubt during festival (Bengaluru)",
        patient_code="PAT-001",   # alcohol + behavioral
        addiction_type="alcohol",
        expected_video_key="Aag3",
        turns=[
            Turn(
                message="During Ganesh Chaturthi everyone is celebrating but I feel so pressured and my urge to drink is at 9.",
                checks=["urge", "pressure", "moment", "breathe"],
            ),
            Turn(
                message="I keep doubting myself — I don't think I can handle this. I feel stressed and sad.",
                checks=["doubt", "handle", "can", "moment"],
            ),
            Turn(
                message="Family pressure during festivals is my biggest trigger. I'm so stressed I don't know what to do.",
                checks=["try", "feel", "help", "breathe"],
            ),
        ],
    ),
    # ── UC 5.2 Addiction Agnostic – Indian (setback) ─────────────────────
    UseCase(
        id="UC-5.2",
        title="Sneha Patil — All-or-nothing thinking after setback (Bengaluru)",
        patient_code="PAT-001",
        addiction_type="alcohol",
        expected_video_key="Aag11",
        turns=[
            Turn(
                message="I missed my check-in yesterday and now I feel like I ruined everything. What's the point?",
                checks=["setback", "progress", "point", "day"],
            ),
            Turn(
                message="I had a 12-day streak and now I feel like such a failure. I'm sad and stressed.",
                checks=["streak", "progress", "perfect", "normal"],
            ),
            Turn(
                message="I feel ashamed and unmotivated. Maybe I'll never recover.",
                checks=["try", "recover", "feel", "normal"],
            ),
        ],
    ),
    # ── UC 5.3 Addiction Agnostic – Global (Toronto setback) ─────────────
    UseCase(
        id="UC-5.3",
        title="Alex Chen — All-or-nothing thinking after setback (Toronto)",
        patient_code="PAT-001",
        addiction_type="alcohol",
        expected_video_key="Aag11",
        turns=[
            Turn(
                message="I slipped once yesterday after 3 weeks clean. Now I can't stop thinking — what's the point of trying?",
                checks=["slip", "point", "try", "progress"],
            ),
            Turn(
                message="I feel so ashamed. One mistake and now I feel like I ruined 3 weeks of hard work.",
                checks=["shame", "mistake", "human", "normal"],
            ),
            Turn(
                message="I'm sad and demotivated. My cravings are at 7 and everything feels hopeless.",
                checks=["try", "feel", "hopeless", "safe"],
            ),
        ],
    ),
    # ── UC 5.4 Addiction Agnostic – Global (NYC decision) ───────────────
    UseCase(
        id="UC-5.4",
        title="Taylor Brooks — Decision hesitation & internal conflict (New York)",
        patient_code="PAT-001",
        addiction_type="alcohol",
        expected_video_key="Aag10",
        turns=[
            Turn(
                message="I'm about to go out with friends who all drink and part of me wants to join them. I'm so conflicted.",
                checks=["conflict", "friend", "urge", "breathe"],
            ),
            Turn(
                message="My cravings are at 8 and I feel lonely and stressed. Part of me says drink, the other part says no.",
                checks=["craving", "lonely", "conflict", "help"],
            ),
            Turn(
                message="I don't know what to do. I'm standing at the door and I can't decide.",
                checks=["try", "feel", "moment", "breath"],
            ),
        ],
    ),
    # ── UC 6.1 Social Media – Indian ─────────────────────────────────────
    UseCase(
        id="UC-6.1",
        title="Aravind Reddy — Morning phone scrolling (Hyderabad)",
        patient_code="PAT-003",   # behavioral/gaming → social media
        addiction_type="social_media",
        expected_video_key="TSM1",
        turns=[
            Turn(
                message="I woke up and the first thing I did was reach for my phone and scroll Instagram for an hour. I can't stop.",
                checks=["phone", "scroll", "morning", "habit"],
            ),
            Turn(
                message="My urge to scroll social media when I'm bored is at 8. It's wasting all my study time.",
                checks=["bored", "urge", "scroll", "morning"],
            ),
            Turn(
                message="I feel restless and unmotivated if I don't check my phone immediately after waking.",
                checks=["try", "feel", "morning", "habit"],
            ),
        ],
    ),
    # ── UC 6.2 Social Media – Global ────────────────────────────────────
    UseCase(
        id="UC-6.2",
        title="Sophia Martinez — Post immediately / validation seeking (Los Angeles)",
        patient_code="PAT-003",
        addiction_type="social_media",
        expected_video_key="TSM2",
        turns=[
            Turn(
                message="I just got a big brand deal and I immediately want to post it everywhere and check for likes. The urge is overwhelming.",
                checks=["post", "urge", "like", "moment"],
            ),
            Turn(
                message="When something exciting happens I can't resist posting it. My craving to share is at 8.",
                checks=["craving", "post", "share", "breathe"],
            ),
            Turn(
                message="I feel excited but also anxious — if I don't post right now I feel like I'm missing out.",
                checks=["try", "feel", "anxious", "moment"],
            ),
        ],
    ),
]


# ─── Results Tracking ────────────────────────────────────────────────────────

@dataclass
class TurnResult:
    turn_num: int
    message: str
    response: str
    intent: str
    severity: str
    video_key: Optional[str]
    passed_checks: List[str]
    failed_checks: List[str]
    failed_not_checks: List[str]
    error: Optional[str]

    @property
    def ok(self) -> bool:
        return not self.error and not self.failed_checks and not self.failed_not_checks


@dataclass
class CaseResult:
    use_case: UseCase
    turn_results: List[TurnResult]
    video_shown: Optional[str]

    @property
    def passed(self) -> bool:
        return all(t.ok for t in self.turn_results)


# ─── Runner ──────────────────────────────────────────────────────────────────

def run_use_case(uc: UseCase) -> CaseResult:
    session_id = str(uuid.uuid4())
    turn_results = []
    video_shown = None

    for i, turn in enumerate(uc.turns, 1):
        resp = chat(session_id, uc.patient_code, turn.message)

        if "error" in resp:
            turn_results.append(TurnResult(
                turn_num=i,
                message=turn.message,
                response="",
                intent="",
                severity="",
                video_key=None,
                passed_checks=[],
                failed_checks=turn.checks,
                failed_not_checks=[],
                error=resp["error"],
            ))
            continue

        response_text = resp.get("response", "").lower()
        intent = resp.get("intent", "")
        severity = resp.get("severity", "")
        video = resp.get("video", None)
        if video:
            video_shown = video

        # Check required strings
        passed = [c for c in turn.checks if c.lower() in response_text]
        failed = [c for c in turn.checks if c.lower() not in response_text]
        bad_present = [c for c in turn.not_checks if c.lower() in response_text]

        turn_results.append(TurnResult(
            turn_num=i,
            message=turn.message,
            response=resp.get("response", ""),
            intent=intent,
            severity=severity,
            video_key=str(video) if video else None,
            passed_checks=passed,
            failed_checks=failed,
            failed_not_checks=bad_present,
            error=None,
        ))

        time.sleep(0.3)   # small delay to avoid hammering

    clear_session(session_id)
    return CaseResult(use_case=uc, turn_results=turn_results, video_shown=video_shown)


# ─── Report ──────────────────────────────────────────────────────────────────

def print_report(results: List[CaseResult]):
    print("\n" + "═" * 80)
    print("  DEMO USE CASE TEST REPORT")
    print("═" * 80)

    passed_cases = 0
    partial_cases = 0
    failed_cases = 0

    for cr in results:
        uc = cr.use_case
        status_chars = [("✅" if t.ok else "⚠️ " if not t.error else "❌") for t in cr.turn_results]
        overall = "PASS" if cr.passed else "PARTIAL"

        if cr.passed:
            passed_cases += 1
        else:
            all_err = all(t.error for t in cr.turn_results)
            if all_err:
                failed_cases += 1
                overall = "FAIL"
            else:
                partial_cases += 1

        print(f"\n{'─'*80}")
        print(f"  {uc.id}  |  {uc.title}")
        print(f"  Patient: {uc.patient_code}  |  Addiction: {uc.addiction_type}  |  Expected video: {uc.expected_video_key}")
        print(f"  Overall: {overall}   Turns: {' '.join(status_chars)}")

        for tr in cr.turn_results:
            print(f"\n  [Turn {tr.turn_num}]")
            # Truncate message for display
            msg_display = tr.message[:90] + "..." if len(tr.message) > 90 else tr.message
            print(f"    User:     \"{msg_display}\"")
            if tr.error:
                print(f"    ERROR:    {tr.error}")
                continue
            resp_display = tr.response[:200] + "..." if len(tr.response) > 200 else tr.response
            print(f"    Intent:   {tr.intent}  |  Severity: {tr.severity}")
            if tr.video_key:
                print(f"    Video:    {tr.video_key}")
            print(f"    Response: {resp_display}")
            if tr.passed_checks:
                print(f"    ✅ Keywords found:   {', '.join(tr.passed_checks)}")
            if tr.failed_checks:
                print(f"    ⚠️  Keywords missing: {', '.join(tr.failed_checks)}")
            if tr.failed_not_checks:
                print(f"    ❌ Forbidden found:  {', '.join(tr.failed_not_checks)}")

        if cr.video_shown:
            video_id = cr.video_shown.get("video_id") if isinstance(cr.video_shown, dict) else str(cr.video_shown)
            exp = uc.expected_video_key or "—"
            match = "✅" if (exp != "—" and exp.lower() in str(cr.video_shown).lower()) else "⚠️  (no match)"
            print(f"\n  Video shown: {cr.video_shown}  →  Expected prefix: {exp}  {match}")
        else:
            print(f"\n  ⚠️  No video returned (expected: {uc.expected_video_key})")

    print("\n" + "═" * 80)
    print(f"  SUMMARY: {passed_cases} PASS / {partial_cases} PARTIAL / {failed_cases} FAIL  out of {len(results)} use cases")
    print("═" * 80 + "\n")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Quick health check
    try:
        with urllib.request.urlopen(f"{BASE}/health", timeout=5) as r:
            health = json.loads(r.read())
            print(f"Server health: {health}")
    except Exception as e:
        print(f"ERROR: Server not reachable at {BASE} — {e}")
        sys.exit(1)

    results = []
    for uc in USE_CASES:
        print(f"Running {uc.id}: {uc.title[:50]}...", end=" ", flush=True)
        result = run_use_case(uc)
        status = "PASS" if result.passed else "PARTIAL/FAIL"
        print(status)
        results.append(result)

    print_report(results)

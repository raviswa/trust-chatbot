# Clinical Data Synthesis System - Implementation Guide

**Date:** March 27, 2026  
**Status:** ✅ **COMPLETE & READY FOR DEPLOYMENT**

---

## Overview

You now have a complete **Clinical Data Synthesis System** that generates personalized, context-aware greeting messages following the 5-Layer Conversation Model and clinical guardrails.

The system:
- ✅ Synthesizes data from 3 sources (subjective, physiological, historical)
- ✅ Implements clinical guardrails (never correct patient, silent risk adjustment)
- ✅ Generates 5-Layer greetings (contextual opening → validation → agency)
- ✅ Provides tone directives based on patient state
- ✅ Handles contradictory data with compassion
- ✅ Adjusts risk scoring intelligently

---

## Architecture

### Data Sources (3-Priority System)

#### Priority 1: Subjective State (Daily Check-in)
**Source:** `daily_checkins` table  
**Fields:** emotional_state, craving_intensity, sleep_quality, medication_taken, triggers_today  
**Weight:** 70% of final risk score  
**Principle:** Patient's reported reality is primary

#### Priority 2: Physiological State (Wearables)
**Source:** `wearable_readings` table  
**Fields:** heart_rate, hrv (HRV < 20ms = stress), stress_score, sleep_hours, steps, anomalies  
**Weight:** 30% of final risk score  
**Principle:** Informs tone, provides silent risk adjustment

#### Priority 3: Historical Context (Session History)
**Source:** `conversations` table  
**Fields:** recurring_themes, recent_intents, crisis_history, session_count  
**Weight:** Adds continuity layer  
**Principle:** Shows bot remembers patient's journey

### New Modules

| Module | Lines | Purpose |
|--------|-------|---------|
| `patient_context_synthesis.py` | ~430 | Data synthesis engine, clinical guardrails, tone logic |
| `greeting_generator.py` | ~420 | 5-Layer greeting generation |
| Updated `db.py` | ~150 | Data fetchers for all 3 sources |
| Updated `chatbot_engine.py` | API endpoints | `/patient/{code}/checkin-status` |

---

## How to Use

### Option 1: Direct Python Usage (Backend)

```python
from patient_context_synthesis import (
    synthesize_patient_context,
    SubjectiveState,
    PhysiologicalState,
    HistoricalContext
)
from greeting_generator import generate_greeting_message

# Build patient context
context = synthesize_patient_context(
    subjective=SubjectiveState(
        emotional_state="stressed",
        craving_intensity=8,
        sleep_quality=2,
        medication_taken=True,
        triggers_today=["workplace stress"],
        checkin_timestamp="2026-03-27T14:00:00",
        hours_ago=2.5
    ),
    physiological=PhysiologicalState(
        heart_rate=98,
        hrv=18,  # Low HRV = stress signal
        sleep_hours=4.5,
        stress_score=0.78,
        personal_anomaly_flag=False
    ),
    patient_name="Alvin"
)

# Generate greeting
greeting = generate_greeting_message(context)

print(greeting["greeting"])      # Full greeting message
print(greeting["tone"])          # "calm_grounding"
print(greeting["risk_score"])    # 65 (1-100 scale)
print(greeting["layers"])        # Dict with contextual_opening, validation, agency
```

### Option 2: REST API (Frontend)

```javascript
// In frontend code (e.g., React)
async function getGreetingContext() {
  const res = await fetch(
    `http://localhost:8000/patient/ABC001/checkin-status?hours=240`, 
    { method: 'GET' }
  );
  const data = await res.json();
  
  // Returns:
  // {
  //   status: "ok",
  //   greeting: "Hi Alvin 👋 I see you're feeling stressed...",
  //   tone: "calm_grounding",
  //   risk_score: 65,
  //   data_freshness: {
  //     subjective_hours_ago: 2.5,
  //     physiological_hours_ago: 12,
  //     is_returning_user: true
  //   }
  // }
  
  setMessages([{ role: 'assistant', content: data.greeting }]);
}
```

---

## Clinical Features

### Feature 1: Priority-Based Synthesis

The system doesn't just pick the "latest" data point. Instead, it applies priority weighting:

```
Patient says: "Slept great!" (sleep_quality: 8)
Wearable shows: 4.5 hours of sleep
  ↓
Synthesis Decision:
  - Subjective risk: 20 (patient feels good)
  - Objective risk: 45 (wearable shows poor sleep)
  - Clinical risk: 28 (70% subjective + 30% objective)
  - Tone: VALIDATING (honor what patient feels)
  ↓
Greeting: "I see you're feeling rested today. Sometimes our 
body can surprise us with less sleep than we realize..."
```

### Feature 2: Tone Engine

Tone is adjusted based on physiological and emotional state:

| Condition | Tone | Example |
|-----------|------|---------|
| High physiological stress + subjective distress | **CALM_GROUNDING** | "I'm here. You can tell me what's on your mind, or I can walk you through a grounding practice." |
| Emotional distress detected | **VALIDATING** | "Loneliness is one of the most powerful human experiences. It's not weakness — it's your need for connection." |
| Neutral/positive state | **CURIOUS** | "I'm here to listen. What's on your mind today?" |
| Crisis indicators | **CRISIS_SAFE** | "I want to make sure you're safe. Tell me what's happening..." |

### Feature 3: Clinical Guardrails

#### Guardrail 1: Lead with Patient's Reality
```python
# NEVER do this:
"Your watch says you slept well, but you say you're tired."

# Instead do this (Trust AI way):
"I see you're feeling really drained today. Sometimes even 
when the numbers look okay, the mental load can make things 
feel heavy. I'm here."
```

#### Guardrail 2: Silent Risk Adjustment
```python
# Don't change tone based on wearable contradiction
# Instead, use wearable data for backend risk management:

subjective_risk = 30  # What patient reports
objective_risk = 45   # What wearables show
clinical_risk = int(subjective_risk * 0.7 + objective_risk * 0.3)
# Result: 34 (closer to patient's reality, but informed by objective data)
```

#### Guardrail 3: Contextual Bridge
When data contradicts, acknowledge without correcting:
```python
# Contradiction detected: Patient felt rested but slept poorly
bridge = (
    "Sometimes our mind and body are out of sync. "
    "You might feel you rested, but your body may have been "
    "working hard all night. That can leave you depleted "
    "in ways you can't quite feel until midday."
)
```

---

## 5-Layer Greeting Structure

### Layer 1: Contextual Opening
**Never generic "How are you?"**

Examples:
- ✅ "Hi Alvin 👋 I see you're feeling stressed today, and your wearable showed some tension last night."
- ❌ "How are you doing today?"

### Layer 2: Validation (Optional)
**Normalize the struggle**

Examples:
- ✅ "That stress and low sleep combination can make cravings feel much stronger, especially in the evening. It's not weakness — it's how our nervous system works."
- ✅ "Loneliness is the most powerful human experience. It's not weakness — it's your need for connection."

### Layer 3: Agency
**Invite, don't interrogate**

Examples:
- ✅ "You can tell me what's on your mind, or I can suggest a grounding tool. What feels right?"
- ✅ "I have some tools that have helped others with what you're experiencing. What would be most helpful?"
- ❌ "Tell me exactly how you've been feeling."

---

## Data Freshness Handling

The system tracks how recent data is:

```json
{
  "data_freshness": {
    "subjective_hours_ago": 2.5,        // Check-in 2.5h ago
    "physiological_hours_ago": 12.0,    // Wearable 12h ago
    "is_returning_user": true,          // Has recent activity
    "all_data_recent": false             // Not all sources fresh
  }
}
```

**Rules:**
- Subjective data older than 12 hours: treated as stale
- Physiological data older than 48 hours: treated as stale
- If all data stale: use first-contact greeting instead

---

## Risk Scoring

### Subjective Risk (What Patient Reports)
```
Base: 20
+ Emotional state (5-60 depending on emotion)
+ Craving intensity > 7 (+20)
+ Poor sleep quality (+15)
+ Medication missed (+10)
+ Active triggers (+5 per trigger)
Result: 20-100 scale
```

### Objective Risk (What Wearables Show)
```
Base: 20
+ HRV < 20ms (+40 critical)
+ Heart rate > 95 bpm (+20)
+ Sleep < 5 hours (+25)
+ Stress score > 0.7 (+40)
+ Personal anomaly detected (+15)
Result: 20-100 scale
```

### Clinical Risk (Final Score)
```
Blended = (Subjective × 0.7) + (Objective × 0.3)
Apply contradiction adjustment if needed
Result: 1-100 scale for backend use
```

---

## Testing the System

### Test 1: High Stress + Low Sleep
```python
context = synthesize_patient_context(
    subjective=SubjectiveState(
        emotional_state="overwhelmed",
        craving_intensity=8,
        sleep_quality=2,
        checkin_timestamp="2026-03-27T14:00:00",
        hours_ago=1.0
    ),
    physiological=PhysiologicalState(
        hrv=18,
        stress_score=0.82,
        sleep_hours=4.0
    ),
    patient_name="Alvin"
)

greeting = generate_greeting_message(context)
assert greeting["tone"] == "calm_grounding"
assert greeting["risk_score"] > 60
assert "grounding" in greeting["layers"]["agency"]
```

### Test 2: Contradiction Handling
```python
context = synthesize_patient_context(
    subjective=SubjectiveState(
        emotional_state="happy",
        sleep_quality=8,
        hours_ago=1.0
    ),
    physiological=PhysiologicalState(
        sleep_hours=4.0,
        hrv=18,
        stress_score=0.75
    ),
    patient_name="Alex"
)

assert context.contradiction_detected == True
assert "sync" in context.layers["validation"].lower()
```

### Test 3: Recurring Theme Recognition
```python
context = synthesize_patient_context(
    historical=HistoricalContext(
        recurring_themes=["workplace_stress"],
        session_count=5,
        last_session_timestamp="2026-03-26T10:00:00"
    ),
    patient_name="Jordan"
)

assert "workplace" in context.dominant_theme or len(context.historical.recurring_themes) > 0
```

---

## Deployment Checklist

- [ ] Deploy `patient_context_synthesis.py`
- [ ] Deploy `greeting_generator.py`
- [ ] Update `db.py` with three new fetcher functions
- [ ] Update `chatbot_engine.py` with new API endpoints
- [ ] Run syntax check: `python3 -m py_compile backend/*.py`
- [ ] Test API endpoint: `GET /patient/TEST001/checkin-status?hours=240`
- [ ] Update frontend to use new API response format
- [ ] Deploy to staging and verify with real data
- [ ] Monitor risk scores and tone directives in logs
- [ ] Collect feedback on greeting quality

---

## Common Issues & Solutions

### Issue 1: "Endpoint returns generic greeting instead of context greeting"
**Cause:** Data isn't recent (older than threshold)  
**Solution:** Check `data_freshness.is_returning_user` — if false, system uses first-contact greeting by design

### Issue 2: "Risk score seems too low/high compared to patient state"
**Cause:** Weight distribution or contradiction adjustment  
**Solution:** Review the `_calculate_clinical_risk()` method. Adjust 0.7/0.3 weights if needed

### Issue 3: "Wearable data not being fetched"
**Cause:** `get_latest_wearable_reading()` looks for `read ingdate` not `created_at`  
**Solution:** Verify wearable_readings table schema matches db.py fetch function

### Issue 4: "Tone is too calm when patient is in crisis"
**Cause:** CRISIS_SAFE tone only triggers on explicit crisis indicators  
**Solution:** Ensure crisis_events table is being logged and queried

---

## Next Steps

### Phase 1: Monitor & Validate (First Week)
- [ ] Monitor greeting quality across 10+ users
- [ ] Collect feedback on accuracy of emotional anchors
- [ ] Verify risk scores align with clinical team expectations
- [ ] Check tone directives are appropriate

### Phase 2: Expand (Second Week)
- [ ] Integrate with video recommendation engine
- [ ] Add wearables-based intervention triggers
- [ ] Implement anomaly alerting for clinicians
- [ ] Build admin dashboard for greeting analytics

### Phase 3: Optimize (Ongoing)
- [ ] A/B test different greeting variations
- [ ] Collect outcome data (did greeting improve engagement?)
- [ ] Refine weights based on clinical feedback
- [ ] Add more tone directives if needed

---

## Files Changed Summary

| File | Changes | Impact |
|------|---------|--------|
| `patient_context_synthesis.py` | **NEW** | Core synthesis engine (430 lines) |
| `greeting_generator.py` | **NEW** | Greeting generation (420 lines) |
| `db.py` | **ADDED 3 functions** | Fetchers for daily_checkins, wearable_readings, historical context |
| `chatbot_engine.py` | **ADDED 2 endpoints** | `/patient/{code}/checkin-status` and `/patient/{code}/set-continuity` |

**Total Code:** ~850 lines of new Python code

---

## Questions?

Reference the inline documentation in:
- `patient_context_synthesis.py` — How synthesis works
- `greeting_generator.py` — How greetings are built
- `db.py` — How data is fetched
- [GREETING_CONTEXT_VERIFICATION.md](GREETING_CONTEXT_VERIFICATION.md) — Detailed verification report

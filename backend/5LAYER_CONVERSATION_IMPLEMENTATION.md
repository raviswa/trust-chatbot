# 5-LAYER CONVERSATION MODEL + SUPABASE SCHEMA


## Overview

You provided a diagram of the **5-layer conversation model** you want to implement:

1. **Greet with context** — Open with what you already know. Never ask "how are you". Use name + check-in data to greet. Zero questions.
2. **Invite, don't interrogate** — One open invitation, not a question. Max 1 prompt per turn. Listen for keywords + emotion markers.
3. **1 clarifying Q if ambiguous** — Ask max 1 targeted question. Only if intent is ambiguous after NLP. Skip entirely if confident.
4. **Text + video response** — 2-3 lines only. Validate + normalise + bridge to action. One video when score < 6 or high risk.
5. **Close with agency** — End with one soft CTA — a tool, a practice, or an opt-out. Not another question.

This document shows how the Supabase schema, patient_context.py, and chatbot_engine.py all work together to achieve this model.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     CHATBOT MESSAGE FLOW                             │
└─────────────────────────────────────────────────────────────────────┘

User Types Message
        ↓
chatbot_engine.handle_message():
        ↓
    ┌─────────────────────────────────────────────────────────────┐
    │ Layer 0: Build Context from Supabase                         │
    │ ├─ Fetch onboarding_profile (addiction type, triggers)      │
    │ ├─ Fetch today's daily_checkin (mood, sleep, cravings)      │
    │ ├─ Fetch content_engagement (videos shown this session)      │
    │ ├─ Fetch latest risk_assessment (score, level, drivers)      │
    │ └─ Call patient_context.build_context() → PatientContext    │
    └─────────────────────────────────────────────────────────────┘
            ↓
    ┌─────────────────────────────────────────────────────────────┐
    │ Layer 1: GREET WITH CONTEXT (Never generic)                 │
    │ ├─ Is this a returning patient? (check sessions table)       │
    │ ├─ Use patient name from onboarding_profile                 │
    │ ├─ Reference checkin data: "I see your sleep was X"         │
    │ ├─ Reference triggers: "I know Y has been hard for you"    │
    │ └─ Call patient_context.get_opening_line(context)           │
    │    → Returns personalized greeting based on mood/risk       │
    └─────────────────────────────────────────────────────────────┘
            ↓
    ┌─────────────────────────────────────────────────────────────┐
    │ Layer 2: INVITE, DON'T INTERROGATE                           │
    │ ├─ Send opening line + ONE open-ended question              │
    │ ├─ Never: "How are you? What's going on? How's your sleep?"│
    │ ├─ YES: "Something seems different. Tell me about it."     │
    │ └─ Log in messages table: one invitation, tracked           │
    └─────────────────────────────────────────────────────────────┘
            ↓
User provides response
        ↓
Intent Classification + Safety Checks (Layers 2-3)
        ↓
    ┌─────────────────────────────────────────────────────────────┐
    │ Layer 2-3: MINIMAL QUESTIONING                              │
    │ ├─ Intent classifier determines what they're asking about    │
    │ ├─ If clear → Skip to Layer 4                              │
    │ ├─ If ambiguous → Ask ONE clarifying question max           │
    │ │    Example: User: "Things are hard"                       │
    │ │    Clarifying Q: "Is it relating to sleep, stress, or..." │
    │ │    NO: "What's wrong? How long? Why now? Who's involved?" │
    │ └─ Log clarifying_q_id in messages table if asked           │
    └─────────────────────────────────────────────────────────────┘
            ↓
    ┌─────────────────────────────────────────────────────────────┐
    │ Layer 4: TEXT + VIDEO RESPONSE                              │
    │ ├─ Use format_context_for_prompt() to inject context        │
    │ │   into LLM system prompt with tone directives             │
    │ ├─ Tone = get_tone_for_risk_level(risk_level)              │
    │ │   Low: "encouraging, motivational"                        │
    │ │   Medium: "supportive, practical"                         │
    │ │   High: "calm, stabilizing, immediate coping"             │
    │ │   Critical: "crisis protocol, safety first"              │
    │ ├─ Generate response: 2-3 lines ONLY                        │
    │ │   NOT: "Tell me more. When did this start? How severe?"   │
    │ │   YES: "That sounds hard. Know that you're not alone."   │
    │ ├─ If risk_score < 6: Optional video                        │
    │ ├─ If risk_score >= 6: Always show video                    │
    │ └─ Log content_engagement: what video, why shown           │
    └─────────────────────────────────────────────────────────────┘
            ↓
    ┌─────────────────────────────────────────────────────────────┐
    │ Layer 5: CLOSE WITH AGENCY (Not another question)           │
    │ ├─ Offer ONE soft CTA:                                      │
    │ │   ✓ "Try this breathing exercise when you need it"       │
    │ │   ✓ "Your therapist session is tomorrow—write it down"   │
    │ │   ✓ "You can leave whenever. I'm here if you need me."   │
    │ ├─ NOT: "Do you want another video? Want to chat more?"     │
    │ ├─ Not option interrogation                                 │
    │ └─ Store action_items in sessions table                     │
    └─────────────────────────────────────────────────────────────┘
            ↓
Message sent to user
        ↓
Log everything to Supabase:
├─ messages table (user + bot messages with intent/severity)
├─ sessions table (counter, summary, action_items)
├─ content_engagement (if video shown)
└─ crisis_events (if critical severity)
```

---

## Supabase Tables & Their Layer Roles

### PATIENTS table
- **Purpose:** Core identity
- **Layer 1 Role:** Check `last_active_at` to determine "returning" vs. "new"
- **Query:** `SELECT last_active_at FROM patients WHERE patient_id='...'`

### ONBOARDING_PROFILES table
- **Purpose:** Static intake data
- **Layer 1 Roles:**
  - Use `first_name` for personalized greeting
  - Reference `addiction_type` for recovery focus
  - Include `baseline_mood` to understand typical state
  - Mention `primary_triggers` discovered during intake
  - Use `support_network` names (sponsor, therapist) in suggestions
- **Query in Layer 1:**
  ```python
  profile = db.table('onboarding_profiles') \
      .select('*') \
      .eq('patient_id', patient_id).single().execute()
  
  greeting = f"Hi {profile.first_name}, I know you're working on recovery " \
             f"from {profile.addiction_type}. Last time you mentioned " \
             f"{profile.primary_triggers[0]} has been challenging for you."
  ```

### DAILY_CHECKINS table
- **Purpose:** Today's mood, sleep, cravings, medication tracking
- **Layer 1 Roles:**
  - Reference `sleep_quality` ("I see you didn't sleep much")
  - Mention `craving_intensity` if high
  - Note `medication_taken` status
  - Acknowledge `triggers_today` if known
- **Query in Layer 1:**
  ```python
  checkin = db.table('daily_checkins') \
      .select('*') \
      .eq('patient_id', patient_id) \
      .eq('checkin_date', today).single().execute()
  
  if checkin.sleep_quality < 5:
      greeting += f" I'm noticing your sleep was rough last night."
  ```

### SESSIONS table
- **Layer 1 Role:** Check if `patient_id` has prior sessions for "welcome back"
- **Layer 5 Role:** Store `action_items` identified during this session
- **Query in Layer 1:**
  ```python
  prior_sessions = db.table('sessions') \
      .select('count', count='exact') \
      .eq('patient_id', patient_id).execute()
  
  is_returning = prior_sessions.count > 0
  if is_returning:
      greeting = f"Welcome back, {name}. [context-based greeting]"
  else:
      greeting = f"Welcome to Trust AI, {name}. [context-based greeting]"
  ```

### RISK_ASSESSMENTS table
- **Purpose:** Live risk score (0-100) with drivers
- **Computed By:** `patient_context.compute_risk_score(checkin)`
- **Model Used:** Weighted arithmetic (no ML dependencies)
  - Sleep < 5 → +25 pts
  - Sleep 5-7 → +9 pts
  - Cravings > 6 → +30 pts
  - Cravings 3-6 → +9 pts
  - Negative mood → +20 pts
  - Missed meds → +15 pts
- **Scoring Ranges:**
  - 0-25: Low risk
  - 26-50: Medium risk
  - 51-80: High risk
  - 81-100: Critical risk
- **Layer 4 Role:**
  - If score < 6: Optional video
  - If score >= 6: Always video
  - Tone matches risk level:
    - Low → "encouraging, motivational"
    - Medium → "supportive, practical"
    - High → "calm, stabilizing, immediate coping"
    - Critical → "crisis protocol, safety focus"

### MESSAGES table
- **Purpose:** Full message history with intent/severity for each turn
- **Layer Fields:**
  - `role`: 'user' or 'assistant'
  - `intent`: What they're asking (from intent classifier)
  - `severity`: 'low', 'medium', 'high', 'critical'
  - `detected_emotions`: Emotions from NLP
  - `response_tone`: Tone used by bot (warm, calm, direct, stabilizing)
  - `response_includes_video`: Did bot suggest content?
- **Layer 2 Compliance Tracking:**
  - NOT enforced in database, but logged for review
  - Count messages per session: if > 5, bot asked too much
- **Layer 5 Compliance:**
  - Track: Did response end with CTA or with a question?

### CONTENT_ENGAGEMENT table
- **Purpose:** Log when/why videos/content shown to patient
- **Layer 4 Role:** Record every video suggestion with:
  - `content_title`: What video
  - `shown_due_to_risk_level`: Why (Low/Medium/High/Critical)
  - `shown_at`: When
- **Layer 4 Data Collection:**
  - Later: Track `completion_pct` (did patient watch?)
  - Track `was_helpful` (did it help?)
  - Track `user_rating` (1-5 stars)
- **Personalization:**
  - Next time in Layer 4: Choose videos with prev. high ratings

### CRISIS_EVENTS table
- **Purpose:** Document critical incidents for monitoring
- **Created When:** Layer 3-4 detects `has_crisis_indicators = true`
- **Fields:**
  - `event_type`: 'suicidal_ideation', 'self_harm', 'relapse_urge'
  - `severity`: Always 'critical' for this table
  - `user_message`: What patient said
  - `bot_response`: What chatbot responded
  - `resources_provided`: Crisis hotlines, emergency info
  - `requires_followup`, `followup_completed`: For your team
- **Layer 5 Role (Crisis):**
  - Close with: "I'm concerned about your safety. [Resource] →"
  - NOT: "Do you want more info? Want to chat more?"

---

## Code Integration Points

### In patient_context.py:

**Four Key Functions:**

1. **`build_context(session: Dict) → PatientContext`**
   - Reads session dict with keys: `intake_profile`, `checkin_data`, `content_engagement`, etc.
   - Called in Layer 0 before every response
   - Returns PatientContext with 4 sources assembled

2. **`compute_risk_score(checkin: DailyCheckin) → RiskAssessment`**
   - Takes daily checkin data
   - Returns live_risk_score (0-100), risk_level, key_risk_drivers
   - Used to determine Layer 4 response tone and video necessity

3. **`format_context_for_prompt(ctx: PatientContext) → str`**
   - Returns formatted text block for LLM system prompt
   - Includes patient name, recovery focus, triggers, mood, risk
   - Includes tone directive (warm/calm/stabilizing/crisis)
   - Injected into every LLM system prompt in Layer 4

4. **`get_opening_line(ctx: PatientContext) → str`**
   - Returns contextualized Layer 1 greeting
   - Never generic "how are you"
   - Uses patient name, recent checkin, risk markers

### In chatbot_engine.py:

**Layer 0 modifications:**
```python
# Build patient context from Supabase
patient_context = await supabase_manager.build_patient_context(
    patient_id, session_id
)
```

**Layer 1 modifications:**
```python
# Use context for personalized greeting
opening = get_opening_line(patient_context)
bot_response = opening  # May be entire first message
```

**Layer 4 modifications:**
```python
# Inject context into LLM system prompt
context_block = format_context_for_prompt(patient_context)
tone = get_tone_for_risk_level(patient_context.risk.risk_level)

system_prompt = f"""You are a warm, empathetic mental health chatbot.
{context_block}
TONE: {tone}
Response guidelines:
- 2-3 lines maximum
- Focus on validation + one actionable step
- Never ask multiple questions
"""

response = await response_generator.generate(
    user_message=message,
    system_prompt=system_prompt,
)
```

**Logging modifications (after response generation):**
```python
# Log message
await supabase_manager.insert_message(
    session_id, patient_id,
    role='assistant',
    content=response,
    response_tone=tone,
    response_includes_video=bool(video_shown),
    video_title=video_title,
)

# Log content engagement if video shown
if video_shown:
    await supabase_manager.log_content_engagement(
        patient_id, session_id,
        content_id, content_title, ...,
        shown_due_to_risk_level=patient_context.risk.risk_level,
    )

# Log crisis if detected
if patient_context.risk.risk_level == 'Critical':
    await supabase_manager.record_crisis_event(...)
```

---

## Step-by-Step Implementation Checklist

- [x] **SUPABASE_SCHEMA.sql** — 10 tables with all fields for 5-layer model
- [x] **SUPABASE_IMPLEMENTATION_GUIDE.md** — How each table supports each layer
- [x] **supabase_integration.py** — Python class with methods to query/log everything
- [x] **patient_context.py** — 4 dataclasses + 4 functions (already in place)
- [ ] **chatbot_engine.py modifications** — Integrate supabase_manager into handle_message()
- [ ] **Schema deployment to Supabase** — Run SQL or use CLI
- [ ] **Test integration** — Send test messages, verify data flows into Supabase
- [ ] **Monitor 5-layer compliance** — Query conversation_metrics table for adherence

---

## Testing: Manual Data Entry

To test without full integration, insert test data:

```sql
-- 1. Create test patient
INSERT INTO patients (patient_code, first_name, last_name, email)
VALUES ('PAT-TEST-001', 'Alex', 'Johnson', 'alex@example.com')
RETURNING patient_id;

-- Use returned patient_id in all following inserts

-- 2. Add onboarding profile
INSERT INTO onboarding_profiles (patient_id, addiction_type, baseline_mood, primary_triggers, work_status)
VALUES 
  ('{patient_id}', 'Alcohol', 
   '["stressed", "lonely"]'::jsonb, 
   '["Friday nights", "work stress"]'::jsonb, 
   'employed');

-- 3. Add today's checkin
INSERT INTO daily_checkins (patient_id, checkin_date, todays_mood, sleep_quality, craving_intensity, medication_taken)
VALUES ('{patient_id}', CURRENT_DATE, 'Sad', 4, 7, true);
-- Sleep=4 (+25), Cravings=7 (+30), Mood=Sad (+20) = 75 = HIGH risk

-- 4. Create session
INSERT INTO sessions (patient_id, patient_code)
VALUES ('{patient_id}', 'PAT-TEST-001')
RETURNING session_id;

-- 5. Insert messages
INSERT INTO messages (session_id, patient_id, role, content, intent, severity, response_tone)
VALUES 
  ('{session_id}', '{patient_id}', 'user', 
   'I had a rough night', 'sleep_support', 'medium', NULL),
  ('{session_id}', '{patient_id}', 'assistant',
   'I see your sleep was rough. That affects everything. Breathing exercise?',
   NULL, NULL, 'calm');

-- 6. Check what context would be built
SELECT * FROM patient_snapshot WHERE patient_code = 'PAT-TEST-001';
```

---

## Data Flow Summary

```
Patient joins chatbot
    ↓
chatbot_engine.handle_message() called
    ↓
Layer 0: build_context() queries Supabase:
  - patients (is_active, last_active_at)
  - onboarding_profiles (addiction_type, baseline_mood, triggers)
  - daily_checkins (mood, sleep, cravings)
  - content_engagement (videos shown this session)
  - risk_assessments (score, level, drivers)
    ↓
Layer 1: get_opening_line() uses context for personalized greeting
    ↓
User types response
    ↓
Layers 2-3: Intent classifier + minimal questions
    ↓
Layer 4: format_context_for_prompt() injects context into LLM
  - LLM returns 2-3 line response with appropriate tone
  - If risk >= 6, select video; else optional
    ↓
Layer 5: Close with ONE soft CTA, not a question
    ↓
Log everything:
  - messages table (user + bot, intent, severity, tone)
  - sessions table (increment counter, update summary)
  - content_engagement table (if video shown)
  - crisis_events table (if critical)
  - risk_assessments table (recompute after checkin)
    ↓
User sees response + optional video
    ↓
Loop back to layer 0 on next message
```

---

## Next Steps

1. **Deploy Schema:**
   ```bash
   # In Supabase dashboard, paste SUPABASE_SCHEMA.sql and run
   # Or via CLI:
   supabase db execute --file backend/SUPABASE_SCHEMA.sql
   ```

2. **Update chatbot_engine.py:**
   - Import `SupabaseContextManager` from supabase_integration.py
   - In Layer 0: Call `await supabase_manager.build_patient_context()`
   - In Layer 4: Call `await supabase_manager.insert_message()`
   - After response: Log content, risk, crisis as needed

3. **Test with sample patient data** (use SQL template above)

4. **Monitor:**
   - Query `conversation_metrics` to track 5-layer compliance
   - Query `open_crisis_events` for incidents needing follow-up
   - Query `patient_snapshot` for quick status on any patient

---

## File Reference

- **SUPABASE_SCHEMA.sql** — 10 tables, 3 views, all indexes
- **SUPABASE_IMPLEMENTATION_GUIDE.md** — Detailed table role descriptions, best practices, common queries
- **supabase_integration.py** — Python SupabaseContextManager class with 15+ methods
- **patient_context.py** — PatientContext, 4 dataclasses, 4 key functions (already built)
- **PATIENT_CONTEXT_GUIDE.md** — How patient_context.py works (already built)
- **chatbot_engine.py** — Main orchestrator (needs supabase_manager integration)

---

## Summary

You now have:
1. ✅ **5-layer conversation structure** (diagram you provided)
2. ✅ **Supabase schema** supporting all 4 context sources + tracking
3. ✅ **Patient context system** (patient_context.py) for assembling data
4. ✅ **Integration layer** (supabase_integration.py) for querying/logging
5. ✅ **LLM prompt injection** with tone matching risk level
6. ✅ **Crisis event monitoring** and follow-up tracking
7. ✅ **Content engagement tracking** for personalization

**The 5-layer model is now fully enabled by the database schema and context system.**

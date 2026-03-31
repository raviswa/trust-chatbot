# SUPABASE SCHEMA QUICK REFERENCE FOR 5-LAYER MODEL


## How Each Table Supports Each Layer

### LAYER 1: GREET WITH CONTEXT (Never "How are you?")

| Data Source | Field | Usage |
|---|---|---|
| **patients** | `last_active_at` | Determine "Welcome back" vs "Welcome" |
| **patients** | `first_name` | Use in greeting: "Hi {name}," |
| **onboarding_profiles** | `addiction_type` | "You're working on recovery from {type}" |
| **onboarding_profiles** | `baseline_mood` | "I know you typically feel {mood}" |
| **onboarding_profiles** | `primary_triggers` | "I know {trigger} is hard for you" |
| **onboarding_profiles** | `support_network` | "How's it been with your {sponsor/therapist}?" |
| **daily_checkins** | `todays_mood` | "I see you're feeling {mood} today" |
| **daily_checkins** | `sleep_quality` | "I'm noticing your sleep was rough" |
| **daily_checkins** | `craving_intensity` | "Cravings seem elevated today" |
| **sessions** | (count prior) | Check if returning user |

**✅ Example Greeting:**
```
"Hi Sarah, I know you're working on recovery from alcohol, and stress has been 
particularly hard for you. I see your sleep was rough last night. How are you 
holding up this morning?"
```
**❌ Do NOT:**
```
"How are you?"
"What's your name?"
"What brings you here today?"
```

---

### LAYER 2: INVITE, DON'T INTERROGATE (Max 1 open invitation)

| Data Source | Field | Usage |
|---|---|---|
| **messages** | `role`, `content` | Count messages per session; if > 5, bot asking too much |
| **messages** | (track questions) | Log every question asked this turn |
| **session** | `message_count` | Correlate: more messages = more questions? |

**✅ Layer 2 Response:**
```
"That sounds really hard. Tell me what's on your mind."
(1 open invitation)
```
**❌ Do NOT:**
```
"What's going on? How long has this been going on? 
What triggered it? Who's around you? When did you last sleep?"
(5 questions = Layer 2 FAIL)
```

---

### LAYER 3: 1 CLARIFYING Q IF AMBIGUOUS (Only if needed)

| Data Source | Field | Usage |
|---|---|---|
| **messages** | `intent` | Returned from intent classifier |
| **messages** | `intent_confidence` | If < 0.7 confidence, ask clarifying Q |
| **messages** | `minimal_question_id` | Flag if a clarifying Q was asked |
| **services_intent_classifier** | n/a | Determine confidence score |

**✅ Layer 3 Example:**
```
User: "Things are hard"
Confidence: LOW (0.4) → Ask clarifying Q

Clarifying Q: "Are you struggling with cravings, sleep, or something else?"
(1 question, only because confidence was low)
```

**❌ Do NOT:**
```
User: "I want to quit"
Confidence: HIGH (0.95) → DO NOT ask clarifying Q

Skip to Layer 4 directly
```

---

### LAYER 4: TEXT + VIDEO RESPONSE (2-3 lines + 1 video when appropriate)

| Data Source | Field | Usage |
|---|---|---|
| **risk_assessments** | `live_risk_score` (0-100) | If < 6: optional video. If >= 6: show video |
| **risk_assessments** | `risk_level` | Determine tone: Low→warm, Medium→supportive, High→calm, Critical→crisis |
| **risk_assessments** | `key_risk_drivers` | Include in system prompt: "Heavy influence: poor sleep (+25)" |
| **daily_checkins** | `sleep_quality`, `craving_intensity`, `todays_mood` | Factors in final risk score |
| **onboarding_profiles** | `communication_preference` | Prefer short/interactive/narrative content |
| **content_engagement** (history) | `was_helpful`, `user_rating` | Choose videos with prior 4-5 stars |
| **sessions** | (store responses) | Log response text, tone, video suggested |

**Tone by Risk Level:**
| Risk | Level | Tone | System Prompt |
|---|---|---|---|
| 0-25 | Low | Warm, encouraging | "You're doing great. Celebrate small wins." |
| 26-50 | Medium | Supportive, practical | "Let's break this down. Here's a concrete step." |
| 51-80 | High | Calm, stabilizing | "I'm here. Let's focus on immediate stability." |
| 81-100 | Critical | Crisis protocol | "Your safety matters. Here are immediate resources." |

**Response Formula:**
```
IF risk_score < 6:
    response = 2-3 lines of validation + 1 step
    video = optional (offer, don't mandate)
ELSE:
    response = 2-3 lines of validation + 1 step
    video = mandatory (select best-rated or category-matched)
    
Response length = 2-3 lines MAXIMUM
```

**✅ Layer 4 Response (High Risk):**
```
Text: "I can hear how exhausted you are. When sleep's this bad, everything 
feels bigger. Let's do 2 minutes of grounding—I have a video that'll help."

Video: [Grounding exercise - 2 min]
```
(2-3 lines + 1 video)

**❌ Do NOT:**
```
Text: "That sounds tough. Tell me more. How long has this been? 
What's making it worse? Have you tried anything? What about sleep?"

Video: [Offered but not core to response]

(Too many questions, response too long)
```

**Video Decision Logic:**
```python
if risk_level == 'Critical':
    video = crisis_resources (hotline, emergency)
elif risk_level == 'High':
    video = immediate_coping (breathwork, grounding)
elif risk_level == 'Medium':
    video = coping_strategies (sleep, stress)
elif risk_level == 'Low':
    video = optional (motivation, recovery_stories)

# Filter by communication_preference + prior ratings
if patient.communication_preference == 'short-form':
    video = videos where duration_minutes < 5
elif patient.communication_preference == 'interactive':
    video = videos with highest user_rating from this patient
```

---

### LAYER 5: CLOSE WITH AGENCY (Soft CTA, not a question)

| Data Source | Field | Usage |
|---|---|---|
| **sessions** | `action_items` | Store what was suggested for next time |
| **support_networks** | `contact_name`, `involve_in_crisis` | If crisis: "Reach out to {sponsor}" |
| **crisis_events** | `resources_provided` | Log crisis resources shared |
| **messages** | (track closure) | Did response end with CTA or question? |

**✅ Layer 5 Closings:**
```
"Try this breathing when the urge rises. You've got this."
(Tool: breathing exercise)

"Your session with Dr. Kelly is tomorrow. Write down 1 thing you want to talk about."
(Practice: session prep)

"I'm here if you need. You can step back anytime."
(Opt-out: acknowledged agency)
```

**❌ Do NOT:**
```
"Want another video?" (Another question)
"Should I help more?" (Interrogation)
"Want to chat about something else?" (Continuing questions)
"How are you feeling now?" (Back to Layer 1!)
```

**Special Case: Critical Risk**
```
"I'm concerned about your safety. Here's the crisis line: [number]. 
Can you reach your sponsor {name} right now? Please do."

Then log to crisis_events table:
  ├─ event_type: 'suicidal_ideation' | 'self_harm' | etc.
  ├─ severity: 'critical'
  └─ resources_provided: ['National Suicide Prevention Lifeline: 988']
```

---

## Critical Table Relationships for Each Layer

```
Layer 1 (Greet) needs:
  ├─ patients.first_name
  ├─ patients.last_active_at
  ├─ onboarding_profiles.*
  ├─ daily_checkins (latest)
  └─ sessions (count)

Layer 2 (Invite) needs:
  ├─ messages (track questions per turn)
  └─ sessions (message_count)

Layer 3 (Clarify) needs:
  ├─ messages.intent_confidence
  └─ services_intent_classifier (output)

Layer 4 (Respond) needs:
  ├─ risk_assessments (score, level, drivers)
  ├─ onboarding_profiles (communication_preference)
  ├─ content_engagement (history + ratings)
  └─ messages (to log response + tone + video)

Layer 5 (Close) needs:
  ├─ sessions (action_items)
  ├─ support_networks (if contact needed)
  └─ crisis_events (if critical)
```

---

## Risk Score Computation (Determines Layer 4 Tone & Video)

**From daily_checkins, compute in patient_context.py:**

```
risk_score = 0

if sleep_quality < 5:
    risk_score += 25
elif 5 <= sleep_quality <= 7:
    risk_score += 9

if craving_intensity > 6:
    risk_score += 30
elif 3 <= craving_intensity <= 6:
    risk_score += 9

if todays_mood in ['Sad', 'Angry', 'Stressed', 'Lonely']:
    risk_score += 20

if not medication_taken:
    risk_score += 15

# Thresholds
if risk_score <= 25:
    risk_level = 'Low'
elif risk_score <= 50:
    risk_level = 'Medium'
elif risk_score <= 80:
    risk_level = 'High'
else:
    risk_level = 'Critical'
```

**Store in risk_assessments table:**
```sql
INSERT INTO risk_assessments (
  patient_id, 
  live_risk_score, 
  risk_level, 
  key_risk_drivers
) VALUES (
  'patient_id',
  65,
  'High',
  '["sleep -25", "cravings +30", "mood +20"]'::jsonb
);
```

---

## Querying Supabase for Each Layer

### Layer 1: Build Context
```python
async def layer1_greet(patient_id):
    # Fetch all context sources
    patient = db.table('patients').select('*').eq('patient_id', patient_id).single()
    profile = db.table('onboarding_profiles').select('*').eq('patient_id', patient_id).single()
    checkin = db.table('daily_checkins').select('*') \
        .eq('patient_id', patient_id) \
        .eq('checkin_date', today) \
        .order('created_at', desc=True).limit(1)
    
    # Use patient_context.py
    context = build_context({
        'patient_id': patient_id,
        'intake_profile': profile.data,
        'checkin_data': checkin.data[0] if checkin.data else {},
    })
    
    # Get greeting
    opening = get_opening_line(context)
    return opening
```

### Layer 2: Track Questions
```python
async def layer2_check_interrogation(session_id):
    messages = db.table('messages').select('*') \
        .eq('session_id', session_id) \
        .eq('role', 'assistant') \
        .order('created_at', desc=True) \
        .limit(5).execute()
    
    question_count = sum(1 for m in messages.data if '?' in m.content)
    
    if question_count > 1:
        print(f"WARNING: Bot asked {question_count} questions in last turn!")
    
    return question_count
```

### Layer 3: Check Intent Confidence
```python
async def layer3_need_clarifying_q(message_id):
    message = db.table('messages').select('intent_confidence') \
        .eq('message_id', message_id).single().execute()
    
    if message.data['intent_confidence'] < 0.7:
        return True  # Ask clarifying Q
    else:
        return False  # Skip to Layer 4
```

### Layer 4: Get Risk & Select Video
```python
async def layer4_generate_response(patient_id):
    risk = db.table('risk_assessments').select('*') \
        .eq('patient_id', patient_id) \
        .order('computed_at', desc=True).limit(1).single()
    
    profile = db.table('onboarding_profiles').select('communication_preference') \
        .eq('patient_id', patient_id).single()
    
    # Determine tone
    tone = get_tone_for_risk_level(risk.data['risk_level'])
    
    # Select video if needed
    video = None
    if risk.data['live_risk_score'] >= 6:
        # Get best-rated video in category
        videos = db.table('content_engagement').select('*') \
            .eq('patient_id', patient_id) \
            .filter('user_rating', 'gte', 4)
        video = videos.data[0] if videos.data else None
    
    return tone, video
```

### Layer 5: Log Action Items
```python
async def layer5_record_closure(session_id, action_items):
    db.table('sessions').update({
        'action_items': action_items,
        'ended_at': now()
    }).eq('session_id', session_id).execute()
```

---

## Monitoring 5-Layer Compliance

### Query: Are we following the model?

```sql
-- Check Layer 1: Are greetings context-aware?
SELECT 
    COUNT(*) as total_sessions,
    SUM(CASE WHEN 
        messages.role = 'assistant' 
        AND messages.created_at = (
            SELECT MIN(created_at) FROM messages m2 
            WHERE m2.session_id = messages.session_id
        ) THEN 1 ELSE 0 END) as personalized_greetings
FROM messages
JOIN sessions ON messages.session_id = sessions.session_id
WHERE sessions.started_at > now() - INTERVAL '7 days';

-- Check Layer 2/3: Message counts (should be low)
SELECT 
    s.session_id,
    COUNT(CASE WHEN m.role = 'assistant' THEN 1 END) as bot_messages,
    COUNT(CASE WHEN m.content LIKE '%?' THEN 1 END) as questions_asked,
    AVG(LENGTH(m.content)) as avg_response_length
FROM sessions s
JOIN messages m ON s.session_id = m.session_id
WHERE s.started_at > now() - INTERVAL '24 hours'
GROUP BY s.session_id
ORDER BY questions_asked DESC;

-- Check Layer 4: Videos being shown appropriately?
SELECT 
    s.peak_risk_level,
    COUNT(DISTINCT c.session_id) as sessions,
    SUM(CASE WHEN c.content_id IS NOT NULL THEN 1 ELSE 0 END) as videos_shown,
    ROUND(
        SUM(CASE WHEN c.content_id IS NOT NULL THEN 1 ELSE 0 END)::numeric 
        / COUNT(DISTINCT c.session_id), 2
    ) as video_ratio
FROM sessions s
LEFT JOIN content_engagement c ON s.session_id = c.session_id
WHERE s.started_at > now() - INTERVAL '7 days'
GROUP BY s.peak_risk_level;

-- Check Layer 5: Sessions ending with CTA vs questions?
SELECT 
    COUNT(*) as total_sessions,
    SUM(CASE WHEN 
        (SELECT SUBSTRING(content FROM LENGTH(content) - 50 FOR 50))
        LIKE '%?' 
        FROM messages m2 
        WHERE m2.session_id = s.session_id 
        AND m2.role = 'assistant'
        ORDER BY created_at DESC LIMIT 1
    THEN 1 ELSE 0 END) as ends_with_question,
    SUM(CASE WHEN action_items IS NOT NULL THEN 1 ELSE 0 END) as action_items_recorded
FROM sessions s
WHERE s.started_at > now() - INTERVAL '7 days';
```

---

## Summary: Field Checklist for Each Layer

### Implement Layer 1
- [ ] Use `patients.first_name` and `patients.last_active_at`
- [ ] Include `onboarding_profiles.addiction_type` and `primary_triggers`
- [ ] Reference `daily_checkins.sleep_quality` and `todays_mood`
- [ ] Call `patient_context.get_opening_line()` for personalized greeting
- [ ] Avoid: Any form of "How are you?"

### Implement Layer 2
- [ ] Ensure bot sends ONE open invitation max per turn
- [ ] Log every question asked in `messages` table
- [ ] Monitor: `messages.content` char count (should be short)

### Implement Layer 3
- [ ] Check `messages.intent_confidence` from intent classifier
- [ ] Only ask clarifying Q if confidence < 0.7
- [ ] If asked, log `minimal_question_id` in messages table

### Implement Layer 4
- [ ] Compute `risk_assessments.live_risk_score` from `daily_checkins`
- [ ] Get tone from `get_tone_for_risk_level(risk_level)`
- [ ] Inject into system prompt with `format_context_for_prompt()`
- [ ] If risk >= 6: Show video; else: optional
- [ ] Response length: 2-3 lines max
- [ ] Log: `response_tone`, `response_includes_video`, `video_title`

### Implement Layer 5
- [ ] End with ONE soft CTA (tool, practice, or opt-out)
- [ ] NOT: Another question
- [ ] Store in `sessions.action_items`
- [ ] If crisis: Log to `crisis_events` with resources

---

## Files to Review

1. [SUPABASE_SCHEMA.sql](SUPABASE_SCHEMA.sql) — Full DDL for all tables
2. [SUPABASE_IMPLEMENTATION_GUIDE.md](SUPABASE_IMPLEMENTATION_GUIDE.md) — Detailed table descriptions
3. [supabase_integration.py](supabase_integration.py) — Python SupabaseContextManager class
4. [patient_context.py](patient_context.py) — PatientContext dataclasses + 4 functions
5. [5LAYER_CONVERSATION_IMPLEMENTATION.md](5LAYER_CONVERSATION_IMPLEMENTATION.md) — Full architecture overview

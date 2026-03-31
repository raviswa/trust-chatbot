# SUPABASE SCHEMA GUIDE FOR TRUST AI CHATBOT

## Overview

This schema supports the **5-layer chat interaction model**:
1. **Greet with context** (never generic)
2. **Invite, don't interrogate** (1 open invitation max)
3. **1 clarifying Q if ambiguous** (only when needed)
4. **Text + video response** (2-3 lines + video when appropriate)
5. **Close with agency** (soft CTA, not a question)

Every table is designed to provide the data needed for context-aware, risk-driven responses.

---

## Table Relationships & Data Flow

```
PATIENTS (core identity)
    ├── onboarding_profiles (intake data: addiction type, triggers, support network)
    ├── daily_checkins (daily tracking: mood, sleep, cravings, medication)
    │   └── risk_assessments (computed: risk score, drivers, crisis flag)
    ├── sessions (conversation sessions)
    │   ├── messages (user + bot messages in session)
    │   ├── risk_assessments (session-specific risk snapshot)
    │   └── content_engagement (what videos/content shown when)
    ├── support_networks (therapist, sponsor, family)
    └── crisis_events (incidents requiring follow-up)
```

---

## Key Tables & Their Roles

### 1. **PATIENTS**
- **Purpose:** Core patient record and identity
- **Key Fields:**
  - `patient_id` (UUID): Internal identifier
  - `patient_code` (VARCHAR): Human-readable code (PAT-001)
  - `last_active_at`: For determining returning vs. new users
  - `is_active`: Soft delete flag

- **Used For:**
  - Identifying returning patients before greeting
  - Building session context
  - Privacy/access control

---

### 2. **ONBOARDING_PROFILES**
- **Purpose:** Initial intake data collected during first session
- **Key Fields:**
  - `addiction_type`: Type of recovery focus (alcohol, opioids, gaming, etc.)
  - `baseline_mood` (JSONB array): Typical moods
  - `primary_triggers` (JSONB array): Known trigger situations
  - `support_network` (JSONB object): Names of key supporters
  - `work_status`: Employment situation (context for responses)
  - `diagnosed_conditions`: Mental health comorbidities
  - `communication_preference`: How patient prefers to engage

- **Used For:**
  - **LAYER 1 (Greet with context):**
    - Name from onboarding
    - "I know you're working on recovery from [addiction_type]"
    - Uses baseline_mood and primary_triggers to understand baseline state
  - **LAYER 4 (Video response):**
    - Content preferences guide which videos to show

---

### 3. **DAILY_CHECKINS**
- **Purpose:** Daily mood/craving/medication/sleep tracking
- **Key Fields:**
  - `todays_mood`: Current emotional state
  - `sleep_quality` (0-10): Sleep score (critical for risk)
  - `craving_intensity` (0-10): Current craving level
  - `medication_taken`: Adherence marker
  - `triggers_today` (JSONB array): What activated them today
  - `social_contact`: Did they reach out to support network?
  - `exercise_done`: Self-care indicator
  - `checkin_date`: Can query today's vs. historical

- **Used For:**
  - **LAYER 1 (Greet with context):**
    - If checkin exists today: "I see you didn't sleep much last night" or "How are you feeling about last night's sleep?"
    - Links to known triggers: "I know stress has been a trigger for you"
  - **Risk Assessment (compute_risk_score in patient_context.py):**
    - Sleep < 5 hours → +25 risk points
    - Cravings > 6/10 → +30 risk points
    - Negative mood → +20 risk points
    - Missed medication → +15 risk points

---

### 4. **SESSIONS**
- **Purpose:** Track conversation sessions with metadata
- **Key Fields:**
  - `patient_id`: Which patient
  - `started_at`, `ended_at`: Session timing
  - `message_count`: How many messages exchanged
  - `peak_risk_level`, `peak_risk_score`: Highest risk detected this session
  - `crisis_detected`: Did chatbot detect crisis indicators?
  - `conversation_summary`: Key outcomes and topics
  - `action_items` (JSONB array): Follow-ups identified

- **Used For:**
  - **LAYER 1 (Greet with context):**
    - Is this a returning user? Check if patient_id has prior sessions
    - "Welcome back" vs. "Welcome to Trust AI"
  - **LAYER 5 (Close with agency):**
    - Record action items for next session
  - **Risk Tracking:**
    - Query sessions by crisis_detected for monitoring

---

### 5. **MESSAGES**
- **Purpose:** Individual messages (user + bot) with NLP classification
- **Key Fields:**
  - `role`: 'user' or 'assistant'
  - `content`: The actual message text
  - `intent`: What the user is asking about (from intent classifier)
  - `severity`: Urgency level (low, medium, high, critical)
  - `detected_emotions` (JSONB array): Emotions detected via NLP
  - `has_crisis_indicators`: Does this message contain warning signs?
  - `response_tone`: What tone did bot use? (warm, calm, direct, stabilising)
  - `response_includes_video`: Did bot suggest a video?

- **Used For:**
  - **LAYER 2 (Invite, don't interrogate):**
    - Track: Did bot ask 1 open invitation or multiple questions?
    - Store response_tone to guide next turn's response
  - **LAYER 3 (Clarifying Q if needed):**
    - Store clarifying_q_id if one was asked
  - **LAYER 4 (Text + video):**
    - Record if/what video was suggested
  - **Crisis Detection:**
    - Query messages with crisis_indicators for monitoring

---

### 6. **RISK_ASSESSMENTS**
- **Purpose:** Live risk scores computed from recent checkin data
- **Key Fields:**
  - `live_risk_score`: 0-100 integer
  - `risk_level`: 'Low' (0-25), 'Medium' (26-50), 'High' (51-80), 'Critical' (81+)
  - `key_risk_drivers` (JSONB array): What's driving the risk
    - Example: `["sleep -25", "cravings +30", "mood +20"]`
  - `crisis_flag`: Boolean, triggers immediate response
  - `crisis_reason`: Why flagged as crisis

- **Scoring Formula** (from patient_context.py):
  ```
  sleep_quality < 5  → +25 points
  sleep_quality 5-7  → +9 points
  craving_intensity > 6 → +30 points
  craving_intensity 3-6 → +9 points
  mood is negative    → +20 points
  medication_missed   → +15 points
  max score = 100
  ```

- **Used For:**
  - **LAYER 1 (Greet with context):**
    - "I'm noticing your sleep has been rough lately—is that affecting your mood?"
  - **LAYER 4 (Video response):**
    - Risk < 6 → Optional video
    - Risk >= 6 → Always show video (different content by risk level)
      - Low: Breathing exercises, motivation
      - Medium: Coping strategies, sleep tips
      - High: Crisis support, immediate coping
      - Critical: Crisis hotline, emergency resources
  - **LAYER 5 (Close with agency):**
    - If High/Critical: "I'm concerned about your safety. Here's an action: [crisis resource]"

---

### 7. **CONTENT_ENGAGEMENT**
- **Purpose:** Track therapetic content (videos, articles) shown and interaction
- **Key Fields:**
  - `content_id`, `content_title`: What content
  - `content_type`: 'video', 'article', 'exercise', 'meditation'
  - `content_category`: 'breathing', 'sleep', 'crisis', 'motivation'
  - `shown_at`: When it was served
  - `completion_pct`: Did they watch it? How much?
  - `was_helpful`: Thumbs up/down
  - `user_rating`: 1-5 star rating
  - `shown_due_to_risk_level`: Why was this suggested?

- **Used For:**
  - **LAYER 4 (Text + video):**
    - Query: What videos has this patient found helpful?
    - Store: Which video we're showing and why
  - **Learning:**
    - Track which content works for which risk levels
    - "Last time you found the sleep meditation helpful—want that again?"
  - **Personalization:**
    - Prefer videos they've rated 4-5 stars

---

### 8. **SUPPORT_NETWORKS**
- **Purpose:** Therapist, sponsor, family contacts for follow-up or escalation
- **Key Fields:**
  - `contact_type`: 'sponsor', 'therapist', 'family', 'friend', 'counselor'
  - `contact_name`, `contact_phone`, `contact_email`
  - `availability_notes`: When/how they're available
  - `involve_in_crisis`: Should we suggest contacting them if crisis detected?

- **Used For:**
  - **LAYER 1 (Greet with context):**
    - "How's your support system been? Any chats with your sponsor since last time?"
  - **LAYER 5 (Close with agency):**
    - If High/Critical risk: "Consider reaching out to [sponsor/therapist name]"
  - **Escalation:**
    - If crisis, query who to contact

---

### 9. **CRISIS_EVENTS**
- **Purpose:** Document critical incidents for monitoring and follow-up
- **Key Fields:**
  - `event_type`: 'suicidal_ideation', 'self_harm', 'relapse_risk', 'abuse', etc.
  - `severity`: 'critical' or 'high'
  - `user_message`: What patient said
  - `bot_response`: How chatbot responded
  - `crisis_protocol_triggered`: Did we activate safety procedure?
  - `resources_provided` (JSONB array): What help was offered
  - `requires_followup`, `followup_completed`: Track next steps
  - `followup_date`, `followup_notes`: When/what happened

- **Used For:**
  - **Incident Tracking:**
    - Register every crisis to track patterns
  - **Follow-up:**
    - Query `open_crisis_events` view to see unfollowed escalations
  - **Compliance & Audit:**
    - Full record of what happened and response taken

---

### 10. **CONVERSATION_METRICS** (Optional but recommended)
- **Purpose:** Track adherence to 5-layer model and overall conversation quality
- **Key Fields:**
  - `clarity_score`, `empathy_score`, `actionability_score`: 1-5 ratings
  - `layer1_context_greeting`: Did bot use context?
  - `layer2_single_invitation`: Did bot ask 1 thing max?
  - `layer3_clarifying_q`: Was clarifying Q only asked if needed?
  - `layer4_text_video`: 2-3 lines + appropriate video?
  - `layer5_soft_cta`: Closed with agency, not question?
  - `adherence_score`: (layers_followed / 5) * 100

- **Used For:**
  - **Quality Control:**
    - Track whether bot is following 5-layer model
    - Query: `SELECT AVG(adherence_score) FROM conversation_metrics WHERE created_at > now() - INTERVAL '7 days'`
  - **Continuous Improvement:**
    - Identify which layers are hardest to follow

---

## How To Deploy This Schema to Supabase

### Option 1: Direct SQL in Supabase Dashboard
1. Go to your Supabase project → **SQL Editor**
2. Click **New Query**
3. Copy entire contents of `SUPABASE_SCHEMA.sql`
4. Click **Run**
5. Check the **SQL Logs** tab to verify success

### Option 2: Using Supabase CLI
```bash
# If you haven't installed Supabase CLI:
npm install -g supabase

# Link your project
supabase link --project-id YOUR_PROJECT_ID

# Push migrations
supabase db push

# Or manually run SQL:
supabase db execute --file SUPABASE_SCHEMA.sql
```

### Option 3: Using Python with supabase-py
```python
from supabase import create_client
import os

url = "https://your-project.supabase.co"
key = "your-key"
supabase = create_client(url, key)

with open('SUPABASE_SCHEMA.sql', 'r') as f:
    schema_sql = f.read()

# Execute via Postgres connection
# (requires direct DB access, not recommended for client-side)
```

---

## Row Level Security (RLS) Policies

If you're using Supabase Auth, add RLS policies so patients only see their own data:

```sql
-- Enable RLS on all tables
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE onboarding_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_checkins ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_engagement ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_networks ENABLE ROW LEVEL SECURITY;
ALTER TABLE crisis_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_metrics ENABLE ROW LEVEL SECURITY;

-- Example: Patients can only read their own data
CREATE POLICY "Patients see own data" ON sessions
  FOR SELECT
  USING (auth.uid()::text = patient_id::text);

-- Example: Therapists (admin role) can see all
CREATE POLICY "Admins see all data" ON sessions
  USING (auth.jwt() ->> 'role' = 'admin');
```

---

## Integration with patient_context.py

### Query Pattern: Build Patient Context

```python
from supabase import create_client
from patient_context import build_context, compute_risk_score

# In your chatbot_engine.py or message handler:

async def get_patient_context(patient_id: str, supabase_client):
    """
    Fetch all 4 context sources from Supabase and build PatientContext
    """
    
    # 1. Get onboarding profile (static)
    profile = supabase_client.table('onboarding_profiles') \
        .select('*') \
        .eq('patient_id', patient_id) \
        .single() \
        .execute()
    
    # 2. Get today's check-in (latest)
    checkin = supabase_client.table('daily_checkins') \
        .select('*') \
        .eq('patient_id', patient_id) \
        .eq('checkin_date', date.today().isoformat()) \
        .order('created_at', desc=True) \
        .limit(1) \
        .single() \
        .execute()
    
    # 3. Get content engagement from this session
    content = supabase_client.table('content_engagement') \
        .select('*') \
        .eq('patient_id', patient_id) \
        .eq('session_id', session_id) \
        .order('shown_at', desc=True) \
        .execute()
    
    # 4. Get latest risk assessment
    risk = supabase_client.table('risk_assessments') \
        .select('*') \
        .eq('patient_id', patient_id) \
        .order('computed_at', desc=True) \
        .limit(1) \
        .single() \
        .execute()
    
    # Build session dict from Supabase data
    session = {
        'patient_id': patient_id,
        'intake_profile': profile.data,
        'checkin_data': checkin.data if checkin.data else {},
        'content_engagement': [c for c in content.data],
        'risk_assessment': risk.data if risk.data else {},
        'message_count': 0,
    }
    
    # Use patient_context.py functions
    from patient_context import build_context
    patient_context = build_context(session)
    
    return patient_context
```

---

## Common Queries

### 1. Get patient snapshot (latest status)
```sql
SELECT * FROM patient_snapshot
WHERE patient_code = 'PAT-001';
```

### 2. Find patients at high/critical risk
```sql
SELECT DISTINCT p.patient_code, p.first_name, r.risk_level, r.live_risk_score
FROM patients p
JOIN risk_assessments r ON p.patient_id = r.patient_id
WHERE r.risk_level IN ('High', 'Critical')
  AND r.computed_at > now() - INTERVAL '24 hours'
ORDER BY r.live_risk_score DESC;
```

### 3. Get patient's last 5 sessions with summaries
```sql
SELECT session_id, started_at, message_count, peak_risk_level, conversation_summary
FROM sessions
WHERE patient_id = '...'
ORDER BY started_at DESC
LIMIT 5;
```

### 4. Track today's check-ins (who has checked in vs. who hasn't)
```sql
SELECT p.patient_code, p.first_name, c.checkin_date
FROM patients p
LEFT JOIN daily_checkins c ON p.patient_id = c.patient_id 
  AND c.checkin_date = CURRENT_DATE
WHERE p.is_active = true
ORDER BY c.created_at DESC NULLS LAST;
```

### 5. Open crisis events needing follow-up
```sql
SELECT * FROM open_crisis_events
ORDER BY created_at DESC;
```

### 6. Videos that patients actually complete and rate highly
```sql
SELECT content_title, content_category, 
  AVG(completion_pct) as avg_completion,
  AVG(user_rating) as avg_rating,
  COUNT(*) as times_shown
FROM content_engagement
WHERE user_rating >= 4 AND completion_pct >= 75
GROUP BY content_id, content_title, content_category
ORDER BY avg_rating DESC;
```

### 7. Conversation quality: Are we following the 5-layer model?
```sql
SELECT 
  DATE_TRUNC('day', created_at) as day,
  AVG(adherence_score) as avg_adherence,
  SUM(CASE WHEN layer1_context_greeting THEN 1 ELSE 0 END)::float / COUNT(*) as layer1_adherence,
  SUM(CASE WHEN layer5_soft_cta THEN 1 ELSE 0 END)::float / COUNT(*) as layer5_adherence
FROM conversation_metrics
WHERE created_at > now() - INTERVAL '7 days'
GROUP BY DATE_TRUNC('day', created_at)
ORDER BY day DESC;
```

---

## Best Practices

### 1. Cascade deletes are set to DELETE for history preservation
If you need to preserve all data even after patient deletion, change `ON DELETE CASCADE` to `ON DELETE RESTRICT`.

### 2. JSONB fields allow flexibility
- `primary_triggers`, `baseline_mood`, `support_network` are JSONB for flexibility
- Example: `baseline_mood` = `["lonely", "guilty", "stressed"]`
- Query JSONB: `WHERE baseline_mood @> '["lonely"]'::jsonb`

### 3. Keep daily_checkins fresh
Create a scheduled job (e.g., Supabase Edge Function) to send daily check-in prompts around the same time each day.

### 4. Compute risk scores frequently
After each check-in or session, recompute risk_assessments:
```python
checkin = daily_checkins_table.fetch_today(patient_id)
risk = compute_risk_score(checkin)  # From patient_context.py
risk_assessments_table.insert(risk)
```

### 5. Monitor crisis_events
Set Supabase alerts on the `open_crisis_events` view. If any new events are added with severity='critical', notify your team.

### 6. Archive old sessions
Backup and archive sessions > 1 year old for compliance, but keep them accessible:
```sql
-- Create archive table
CREATE TABLE sessions_archive AS 
SELECT * FROM sessions WHERE started_at < now() - INTERVAL '1 year';

-- Delete from main table
DELETE FROM sessions WHERE started_at < now() - INTERVAL '1 year';
```

---

## Manual Data Entry for Testing

```sql
-- Insert test patient
INSERT INTO patients (patient_code, first_name, last_name, email) 
VALUES ('PAT-TEST-001', 'John', 'Doe', 'john@example.com');

-- Fetch the UUID
SELECT patient_id FROM patients WHERE patient_code = 'PAT-TEST-001';

-- Insert onboarding (replace patient_id)
INSERT INTO onboarding_profiles (patient_id, addiction_type, baseline_mood, primary_triggers, work_status)
VALUES 
  ('{patient_id}', 'Alcohol', '["stressed", "lonely"]'::jsonb, '["after work", "social events"]'::jsonb, 'employed');

-- Insert today's check-in
INSERT INTO daily_checkins (patient_id, checkin_date, todays_mood, sleep_quality, craving_intensity, medication_taken)
VALUES ('{patient_id}', CURRENT_DATE, 'Sad', 5, 4, true);

-- Insert session
INSERT INTO sessions (patient_id, patient_code) 
VALUES ('{patient_id}', 'PAT-TEST-001')
RETURNING session_id;

-- Insert messages
INSERT INTO messages (session_id, patient_id, role, content, intent, severity)
VALUES 
  ('{session_id}', '{patient_id}', 'user', 'I had a rough night', 'sleep_support', 'medium'),
  ('{session_id}', '{patient_id}', 'assistant', 'I see your sleep was rough. That can affect everything.', 'empathy', 'low');
```

---

## Migrations & Schema Updates

Keep your schema version-controlled:

```
backend/
  migrations/
    001_initial_schema.sql
    002_add_conversation_metrics.sql
    003_add_follow_up_fields.sql
```

Then apply in order or with Supabase migrations.

---

## Summary

This schema provides:
- ✅ All 4 patient context sources (onboarding, checkin, content, risk)
- ✅ Full message history for conversation analysis
- ✅ Risk tracking with computed scores
- ✅ Content engagement metrics
- ✅ Crisis monitoring
- ✅ Support network directory
- ✅ Views for common queries
- ✅ Foundation for 5-layer conversation compliance tracking

Your `patient_context.py` system will query these tables to populate context for every message, enabling truly personalized, risk-aware mental health support.

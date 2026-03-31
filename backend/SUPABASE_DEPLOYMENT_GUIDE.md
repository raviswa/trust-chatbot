# DEPLOYING THE SCHEMA TO SUPABASE

> **TL;DR:** Copy the entire contents of `SUPABASE_SCHEMA.sql` into Supabase's SQL Editor and click Run. Takes 2-3 minutes.

---

## Prerequisites

- Supabase project created and running
- Access to your Supabase project dashboard
- `supabase_integration.py` installed dependencies: `pip install supabase python-dotenv`

---

## Method 1: Supabase Dashboard (Easiest)

### Step 1: Go to SQL Editor
1. Open your Supabase project: https://app.supabase.com
2. Click on your project
3. Left sidebar → **SQL Editor**
4. Click **New Query**

### Step 2: Copy & Paste Schema
1. Open `backend/SUPABASE_SCHEMA.sql` in your editor
2. Select all (Ctrl+A / Cmd+A)
3. Copy
4. In Supabase SQL Editor, paste into the query box

### Step 3: Execute
1. Click **Run** (or Cmd+Enter / Ctrl+Enter)
2. Wait for completion (1-2 minutes)
3. Check **SQL Logs** tab for success confirmation
4. Should see: "Success" for each CREATE TABLE statement

### Step 4: Verify Tables Created
Left sidebar → **Table Editor** → You should see:
- `patients`
- `onboarding_profiles`
- `daily_checkins`
- `sessions`
- `messages`
- `risk_assessments`
- `content_engagement`
- `support_networks`
- `crisis_events`
- `conversation_metrics` (optional)

---

## Method 2: Supabase CLI (For DevOps/CI-CD)

### Step 1: Install CLI
```bash
npm install -g supabase
# or
brew install supabase/tap/supabase
```

### Step 2: Link Your Project
```bash
supabase link --project-id YOUR_PROJECT_ID

# You'll be prompted for your Supabase password
# Find YOUR_PROJECT_ID in Supabase dashboard URL:
# https://app.supabase.com/project/YOUR_PROJECT_ID/...
```

### Step 3: Run Migrations
```bash
# Navigate to workspace root
cd /workspaces/trust-chatbot

# Push the schema
supabase db execute --file backend/SUPABASE_SCHEMA.sql
```

### Step 4: Verify
```bash
# List all tables
supabase db tables list

# Show patient table structure
supabase db show patients
```

---

## Method 3: Python (Supabase Client)

If you want to run it programmatically:

```python
import os
from supabase import create_client

# Initialize
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase = create_client(url, key)

# Read schema file
with open('backend/SUPABASE_SCHEMA.sql', 'r') as f:
    schema = f.read()

# Note: Direct SQL execution requires admin credentials
# Better to use Supabase CLI or Dashboard for first-time setup
# Once tables exist, use supabase_integration.py for data operations
```

---

## Method 4: Docker/Supabase Local (Development)

If running Supabase locally for testing:

```bash
# Start local Supabase
docker-compose up

# In another terminal:
supabase start

# Link to local instance
supabase link --project-id local

# Execute schema
supabase db execute --file backend/SUPABASE_SCHEMA.sql
```

---

## Post-Deployment: Initial Data

### Create Test Patient

Use this SQL to create a test patient for development:

```sql
-- 1. Create patient
INSERT INTO patients (patient_code, first_name, last_name, email, date_of_birth, gender)
VALUES ('PAT-DEV-001', 'Alex', 'Johnson', 'alex@example.com', '1990-05-15', 'M')
RETURNING patient_id;

-- Copy the returned patient_id for use below

-- 2. Add onboarding profile
INSERT INTO onboarding_profiles (
    patient_id,
    addiction_type,
    baseline_mood,
    primary_triggers,
    support_network,
    work_status,
    housing_status,
    diagnosed_conditions,
    current_medications,
    communication_preference,
    content_preferences
) VALUES (
    '{paste_patient_id_here}',
    'Alcohol',
    '["stressed", "lonely", "guilty"]'::jsonb,
    '["social events", "Friday evenings", "work stress"]'::jsonb,
    '{"sponsor": "Mike", "therapist": "Dr. Smith", "family": "Sister"}',
    'employed',
    'stable',
    '["anxiety", "depression"]'::jsonb,
    '["Sertraline 50mg"]'::jsonb,
    'text',
    '["short-form", "interactive"]'::jsonb
);

-- 3. Add today's check-in
INSERT INTO daily_checkins (
    patient_id,
    checkin_date,
    todays_mood,
    sleep_quality,
    sleep_hours,
    craving_intensity,
    medication_taken,
    triggers_today,
    trigger_intensity,
    social_contact,
    exercise_done
) VALUES (
    '{paste_patient_id_here}',
    CURRENT_DATE,
    'Sad',
    4,
    4.5,
    7,
    true,
    '["work deadline", "morning tension"]',
    6,
    false,
    false
);

-- 4. Create session
INSERT INTO sessions (patient_id, patient_code, message_count)
VALUES ('{paste_patient_id_here}', 'PAT-DEV-001', 0)
RETURNING session_id;

-- Copy the returned session_id

-- 5. Add sample messages
INSERT INTO messages (
    session_id,
    patient_id,
    role,
    content,
    intent,
    severity,
    detected_emotions,
    response_tone
) VALUES 
    ('{paste_session_id_here}', '{paste_patient_id_here}', 'user', 
     'Had a rough night. Work stress got to me.', 'sleep_support', 'medium',
     '["stressed", "tired"]'::jsonb, NULL),
    ('{paste_session_id_here}', '{paste_patient_id_here}', 'assistant',
     'I can hear how exhausted you are. Work stress on top of rough sleep is a lot. Let''s try a 2-minute breathing exercise.',
     NULL, 'low', NULL, 'calm');

-- 6. Compute and insert risk assessment
INSERT INTO risk_assessments (
    patient_id,
    session_id,
    live_risk_score,
    risk_level,
    key_risk_drivers,
    sleep_quality_score,
    craving_intensity_score,
    mood_risk_contribution,
    medication_adherence_score
) VALUES (
    '{paste_patient_id_here}',
    '{paste_session_id_here}',
    75,
    'High',
    '["sleep +25", "cravings +30", "mood +20"]'::jsonb,
    4,
    7,
    20,
    1.0
);

-- 7. Verify patient snapshot
SELECT * FROM patient_snapshot WHERE patient_code = 'PAT-DEV-001';
```

---

## Environment Configuration

### Create `.env.local` in backend directory:

```bash
# backend/.env.local

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-public-anon-key
SUPABASE_SERVICE_KEY=your-service-key  # For admin operations

# Database
DATABASE_URL=postgresql://user:password@db.supabase.co:5432/postgres

# LLM
OLLAMA_BASE_URL=http://localhost:11434

# ChatBot
CHATBOT_PORT=8000
```

### Then in your Python code:

```python
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
```

---

## Integration with chatbot_engine.py

### Step 1: Install Dependencies

```bash
pip install python-dotenv supabase
```

### Step 2: Update Imports

```python
# chatbot_engine.py

import os
from dotenv import load_dotenv
from supabase import create_client
from supabase_integration import SupabaseContextManager

load_dotenv()

# Initialize Supabase
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# Initialize context manager
supabase_manager = SupabaseContextManager(supabase)
```

### Step 3: Update handle_message()

```python
async def handle_message(user_message: str, session_id: str, patient_id: str):
    """
    Updated to use Supabase + patient context system
    """
    
    # Layer 0: Build context from Supabase
    patient_context = await supabase_manager.build_patient_context(
        patient_id, session_id
    )
    
    # Layer 0: Log user message
    await supabase_manager.insert_message(
        session_id=session_id,
        patient_id=patient_id,
        role='user',
        content=user_message,
        intent=intent_type,  # from intent classifier
        severity=severity_level,  # from safety checker
    )
    
    # Layer 0: Increment message count
    await supabase_manager.increment_session_messages(session_id)
    
    # Layer 1: Personalized greeting
    opening_line = get_opening_line(patient_context)
    
    # Layers 2-3: Intent classification + minimal questions
    # (existing code)
    
    # Layer 4: Generate response with context injection
    context_block = format_context_for_prompt(patient_context)
    tone = get_tone_for_risk_level(patient_context.risk.risk_level)
    
    system_prompt = f"""You are a warm, empathetic mental health support chatbot.
{context_block}
TONE: {tone}

Guidelines:
- Keep responses to 2-3 lines maximum
- Focus on validation + one actionable step
- Never ask multiple questions
"""
    
    response = await response_generator.generate(
        user_message=user_message,
        system_prompt=system_prompt,
    )
    
    # Determine if video should be shown
    show_video = patient_context.risk.live_risk_score >= 6
    video_shown = None
    if show_video:
        video_shown = await supabase_manager.get_recommended_content(
            patient_id, 
            patient_context.risk.risk_level
        )
    
    # Layer 4: Log bot response
    await supabase_manager.insert_message(
        session_id=session_id,
        patient_id=patient_id,
        role='assistant',
        content=response,
        response_tone=tone,
        response_includes_video=bool(video_shown),
        video_title=video_shown.get('content_title') if video_shown else None,
    )
    
    # Log content engagement if video shown
    if video_shown:
        await supabase_manager.log_content_engagement(
            patient_id=patient_id,
            session_id=session_id,
            content_id=video_shown.get('content_id'),
            content_title=video_shown.get('content_title'),
            content_type=video_shown.get('content_type', 'video'),
            content_category=video_shown.get('content_category'),
            shown_due_to_risk_level=patient_context.risk.risk_level,
        )
    
    # Crisis monitoring
    if patient_context.risk.crisis_flag:
        await supabase_manager.record_crisis_event(
            patient_id=patient_id,
            event_type='detected_crisis_indicators',
            severity='critical',
            user_message=user_message,
            bot_response=response,
            session_id=session_id,
            resources_provided=[
                'National Suicide Prevention Lifeline: 988',
                'Crisis Text Line: Text HOME to 741741'
            ],
        )
        
        # Include crisis resources in response
        response += "\n\n📞 If you're in crisis: Call 988 or text HOME to 741741"
    
    return response
```

---

## Testing the Schema

### Test 1: Verify Tables Exist

```sql
-- Should return 10 rows (all tables)
SELECT table_name FROM information_schema.tables 
WHERE table_schema='public' 
ORDER BY table_name;
```

### Test 2: Insert Test Data

Use the "Initial Data" SQL provided above.

### Test 3: Query Patient Snapshot

```sql
SELECT * FROM patient_snapshot 
WHERE patient_code = 'PAT-DEV-001';
```

Should show:
```
patient_code   | patient_id | risk_level | sleep_quality | ...
PAT-DEV-001    | [uuid]     | High       | 4             | ...
```

### Test 4: Calculate Risk Score

```python
from patient_context import compute_risk_score, DailyCheckin

checkin = DailyCheckin(
    todays_mood='Sad',
    sleep_quality=4,
    craving_intensity=7,
    medication_taken=True,
    triggers_today=['work', 'stress']
)

risk = compute_risk_score(checkin)
print(f"Risk Score: {risk.live_risk_score}/100")
print(f"Risk Level: {risk.risk_level}")
print(f"Drivers: {risk.key_risk_drivers}")
```

Expected output:
```
Risk Score: 75/100
Risk Level: High
Drivers: ['sleep +25', 'cravings +30', 'mood +20']
```

### Test 5: Build Full Context

```python
from supabase_integration import SupabaseContextManager

manager = SupabaseContextManager(supabase)

context = await manager.build_patient_context(
    'PAT-DEV-001', 
    '{session_id}'
)

print(f"Patient: {context.patient_id}")
print(f"Risk Level: {context.risk.risk_level}")
print(f"Risk Score: {context.risk.live_risk_score}")
print(f"Mood Today: {context.checkin.todays_mood}")
```

---

## Troubleshooting

### Error: "Table already exists"

**Solution:** If re-deploying, drop tables first:

```sql
DROP TABLE IF EXISTS conversation_metrics CASCADE;
DROP TABLE IF EXISTS crisis_events CASCADE;
DROP TABLE IF EXISTS content_engagement CASCADE;
DROP TABLE IF EXISTS support_networks CASCADE;
DROP TABLE IF EXISTS risk_assessments CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS sessions CASCADE;
DROP TABLE IF EXISTS daily_checkins CASCADE;
DROP TABLE IF EXISTS onboarding_profiles CASCADE;
DROP TABLE IF EXISTS patients CASCADE;
```

Then re-run the full schema.

### Error: "Foreign key constraint violation"

**Solution:** Tables must be created in order (parents before children). The schema SQL already handles this. If you're inserting test data, make sure:
1. `patients` row exists before `onboarding_profiles`
2. `sessions` row exists before `messages`
3. etc.

### Error: "JSONB field not recognized"

**Solution:** Ensure PostgreSQL version >= 9.4. Supabase always has JSONB support, so this is unlikely unless you're using very old middleware.

### Error: "Index creation failed"

**Solution:** Indexes fail silently in some cases. You can drop them and recreate:

```sql
DROP INDEX IF EXISTS idx_patients_code;
CREATE INDEX idx_patients_code ON patients(patient_code);
```

---

## Performance Tuning (After Testing)

### Add Partitioning for Large Message Volume

```sql
-- If messages table grows > 10M rows, partition by date:

CREATE TABLE messages_2024_q1 PARTITION OF messages
FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');

CREATE TABLE messages_2024_q2 PARTITION OF messages
FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');
```

### Add Indexes for Common Queries

```sql
-- Already included in schema, but if needed:
CREATE INDEX idx_messages_patient_date 
ON messages(patient_id, created_at DESC);

CREATE INDEX idx_risk_patient_timestamp 
ON risk_assessments(patient_id, computed_at DESC);
```

---

## Backup & Recovery

### Backup Schema

```bash
# Using pg_dump (Supabase provides database credentials)
pg_dump -h db.supabase.co -U postgres -d postgres > backup.sql

# Or via Supabase CLI
supabase db dump --local > backup.sql
```

### Restore Schema

```bash
psql -h db.supabase.co -U postgres -d postgres < backup.sql
```

---

## Next Steps

1. ✅ Deploy schema (this guide)
2. ✅ Populate test data (Initial Data section)
3. ✅ Integrate supabase_manager into chatbot_engine.py
4. ✅ Test with sample messages
5. ✅ Monitor query performance
6. 🔄 Collect real patient data
7. 🔄 Iterate on risk scoring weights as you see real patterns
8. 🔄 Adjust video recommendations based on user feedback

---

## Support & Documentation

- **Supabase Docs:** https://supabase.com/docs
- **PostgreSQL Docs:** https://www.postgresql.org/docs/
- **JSONB Guide:** https://www.postgresql.org/docs/current/datatype-json.html
- **Trust AI Chatbot Docs:** See other .md files in this directory

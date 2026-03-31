-- ================================================================
-- TRUST AI — DUMMY PATIENT DATA FOR POC / DEMO
-- ================================================================
-- 10 patients across different programmes and risk profiles.
-- Covers the full range: alcohol, drugs, gaming, social media,
-- anxiety, trauma, grief — with varied severity for demo purposes.
--
-- HOW TO RUN:
--   psql -U postgres -d chatbot_db -f dummy_patients.sql
--
-- TO RESET AND RE-RUN:
--   DELETE FROM conversations; DELETE FROM sessions;
--   DELETE FROM crisis_events; DELETE FROM policy_violations;
--   DELETE FROM patients;
--   Then re-run this file.
-- ================================================================

-- ── Patient 1: Alcohol Recovery, High Risk ───────────────────────
INSERT INTO patients (
    patient_code, display_name, date_of_birth, gender,
    assigned_clinician, programme, referral_source,
    is_active, metadata
) VALUES (
    'PAT-001', 'Arjun', '1988-04-12', 'Male',
    'Dr. Meena Krishnan', 'Alcohol Recovery', 'GP Referral',
    TRUE,
    '{"risk_level":"high","primary_addiction":"alcohol","comorbidities":["depression","insomnia"],"sessions_completed":4}'
)
ON CONFLICT (patient_code) DO NOTHING;

-- ── Patient 2: Drug Use Disorder, Medium Risk ────────────────────
INSERT INTO patients (
    patient_code, display_name, date_of_birth, gender,
    assigned_clinician, programme, referral_source,
    is_active, metadata
) VALUES (
    'PAT-002', 'Priya', '1995-09-23', 'Female',
    'Dr. Meena Krishnan', 'Substance Use Disorder', 'Self-Referral',
    TRUE,
    '{"risk_level":"medium","primary_addiction":"cannabis","comorbidities":["anxiety"],"sessions_completed":2}'
)
ON CONFLICT (patient_code) DO NOTHING;

-- ── Patient 3: Gaming Addiction, Low Risk ────────────────────────
INSERT INTO patients (
    patient_code, display_name, date_of_birth, gender,
    assigned_clinician, programme, referral_source,
    is_active, metadata
) VALUES (
    'PAT-003', 'Karthik', '2001-01-30', 'Male',
    'Counsellor Ravi Suresh', 'Digital Addiction', 'Parent Referral',
    TRUE,
    '{"risk_level":"low","primary_addiction":"gaming","comorbidities":["social_isolation"],"sessions_completed":1}'
)
ON CONFLICT (patient_code) DO NOTHING;

-- ── Patient 4: Anxiety & Trauma, High Risk ───────────────────────
INSERT INTO patients (
    patient_code, display_name, date_of_birth, gender,
    assigned_clinician, programme, referral_source,
    is_active, metadata
) VALUES (
    'PAT-004', 'Divya', '1992-07-15', 'Female',
    'Dr. Suresh Balaji', 'Trauma & Anxiety Programme', 'Psychiatrist Referral',
    TRUE,
    '{"risk_level":"high","primary_addiction":null,"comorbidities":["PTSD","anxiety","depression"],"sessions_completed":6}'
)
ON CONFLICT (patient_code) DO NOTHING;

-- ── Patient 5: Nicotine, Low Risk ────────────────────────────────
INSERT INTO patients (
    patient_code, display_name, date_of_birth, gender,
    assigned_clinician, programme, referral_source,
    is_active, metadata
) VALUES (
    'PAT-005', 'Rajesh', '1979-11-08', 'Male',
    'Counsellor Ravi Suresh', 'Nicotine Cessation', 'Self-Referral',
    TRUE,
    '{"risk_level":"low","primary_addiction":"nicotine","comorbidities":[],"sessions_completed":3}'
)
ON CONFLICT (patient_code) DO NOTHING;

-- ── Patient 6: Social Media Addiction, Medium Risk ───────────────
INSERT INTO patients (
    patient_code, display_name, date_of_birth, gender,
    assigned_clinician, programme, referral_source,
    is_active, metadata
) VALUES (
    'PAT-006', 'Ananya', '1999-03-27', 'Female',
    'Counsellor Ravi Suresh', 'Digital Addiction', 'Self-Referral',
    TRUE,
    '{"risk_level":"medium","primary_addiction":"social_media","comorbidities":["low_self_esteem","anxiety"],"sessions_completed":2}'
)
ON CONFLICT (patient_code) DO NOTHING;

-- ── Patient 7: Grief & Loss, Medium Risk ─────────────────────────
INSERT INTO patients (
    patient_code, display_name, date_of_birth, gender,
    assigned_clinician, programme, referral_source,
    is_active, metadata
) VALUES (
    'PAT-007', 'Suresh', '1965-06-19', 'Male',
    'Dr. Meena Krishnan', 'Grief Support Programme', 'GP Referral',
    TRUE,
    '{"risk_level":"medium","primary_addiction":null,"comorbidities":["complicated_grief","insomnia"],"sessions_completed":5}'
)
ON CONFLICT (patient_code) DO NOTHING;

-- ── Patient 8: Alcohol + Crisis History, Critical ────────────────
INSERT INTO patients (
    patient_code, display_name, date_of_birth, gender,
    assigned_clinician, programme, referral_source,
    is_active, metadata
) VALUES (
    'PAT-008', 'Lakshmi', '1990-12-03', 'Female',
    'Dr. Suresh Balaji', 'Alcohol Recovery', 'Emergency Referral',
    TRUE,
    '{"risk_level":"critical","primary_addiction":"alcohol","comorbidities":["depression","suicidal_ideation_history"],"sessions_completed":8}'
)
ON CONFLICT (patient_code) DO NOTHING;

-- ── Patient 9: Work Addiction, Low Risk ──────────────────────────
INSERT INTO patients (
    patient_code, display_name, date_of_birth, gender,
    assigned_clinician, programme, referral_source,
    is_active, metadata
) VALUES (
    'PAT-009', 'Vikram', '1983-08-22', 'Male',
    'Counsellor Ravi Suresh', 'Behavioural Addiction', 'Self-Referral',
    TRUE,
    '{"risk_level":"low","primary_addiction":"work","comorbidities":["burnout","relationship_strain"],"sessions_completed":1}'
)
ON CONFLICT (patient_code) DO NOTHING;

-- ── Patient 10: Discharged / Completed Programme ─────────────────
INSERT INTO patients (
    patient_code, display_name, date_of_birth, gender,
    assigned_clinician, programme, referral_source,
    is_active, discharged_at, discharge_reason, metadata
) VALUES (
    'PAT-010', 'Meera', '1987-02-14', 'Female',
    'Dr. Meena Krishnan', 'Substance Use Disorder', 'Court Order',
    FALSE, NOW() - INTERVAL '30 days', 'Programme completed successfully',
    '{"risk_level":"low","primary_addiction":"cannabis","comorbidities":[],"sessions_completed":12}'
)
ON CONFLICT (patient_code) DO NOTHING;


-- ================================================================
-- DUMMY SESSIONS
-- 2-3 sessions per active patient to simulate return visits.
-- ================================================================

-- PAT-001 sessions
INSERT INTO sessions (session_id, patient_id, patient_code, started_at, last_active, message_count, user_message_count, bot_message_count, severity_flags, intents_seen, last_topic, last_topic_tag, is_crisis, channel)
SELECT 'SESSION-PAT001-A', id, 'PAT-001', NOW() - INTERVAL '10 days', NOW() - INTERVAL '10 days' + INTERVAL '25 minutes', 8, 4, 4, ARRAY['medium'], ARRAY['addiction_alcohol','mood_anxious','trigger_stress'], 'alcohol use disorder', 'addiction_alcohol', FALSE, 'flutter'
FROM patients WHERE patient_code = 'PAT-001'
ON CONFLICT (session_id) DO NOTHING;

INSERT INTO sessions (session_id, patient_id, patient_code, started_at, last_active, message_count, user_message_count, bot_message_count, severity_flags, intents_seen, last_topic, last_topic_tag, is_crisis, channel)
SELECT 'SESSION-PAT001-B', id, 'PAT-001', NOW() - INTERVAL '3 days', NOW() - INTERVAL '3 days' + INTERVAL '18 minutes', 6, 3, 3, ARRAY['medium','high'], ARRAY['addiction_alcohol','mood_sad','trigger_stress'], 'alcohol use disorder', 'addiction_alcohol', FALSE, 'flutter'
FROM patients WHERE patient_code = 'PAT-001'
ON CONFLICT (session_id) DO NOTHING;

-- PAT-002 sessions
INSERT INTO sessions (session_id, patient_id, patient_code, started_at, last_active, message_count, user_message_count, bot_message_count, severity_flags, intents_seen, last_topic, last_topic_tag, is_crisis, channel)
SELECT 'SESSION-PAT002-A', id, 'PAT-002', NOW() - INTERVAL '7 days', NOW() - INTERVAL '7 days' + INTERVAL '15 minutes', 6, 3, 3, ARRAY['medium'], ARRAY['addiction_drugs','mood_anxious'], 'substance use disorder', 'addiction_drugs', FALSE, 'flutter'
FROM patients WHERE patient_code = 'PAT-002'
ON CONFLICT (session_id) DO NOTHING;

-- PAT-004 sessions (trauma, high risk)
INSERT INTO sessions (session_id, patient_id, patient_code, started_at, last_active, message_count, user_message_count, bot_message_count, severity_flags, intents_seen, last_topic, last_topic_tag, is_crisis, channel)
SELECT 'SESSION-PAT004-A', id, 'PAT-004', NOW() - INTERVAL '14 days', NOW() - INTERVAL '14 days' + INTERVAL '30 minutes', 12, 6, 6, ARRAY['high'], ARRAY['trigger_trauma','mood_anxious','mood_sad'], 'trauma', 'trigger_trauma', FALSE, 'flutter'
FROM patients WHERE patient_code = 'PAT-004'
ON CONFLICT (session_id) DO NOTHING;

-- PAT-008 session (crisis history patient — has a crisis event)
INSERT INTO sessions (session_id, patient_id, patient_code, started_at, last_active, message_count, user_message_count, bot_message_count, severity_flags, intents_seen, last_topic, last_topic_tag, is_crisis, crisis_intent, crisis_at, channel)
SELECT 'SESSION-PAT008-A', id, 'PAT-008', NOW() - INTERVAL '5 days', NOW() - INTERVAL '5 days' + INTERVAL '20 minutes', 10, 5, 5, ARRAY['critical'], ARRAY['addiction_alcohol','crisis_suicidal','mood_sad'], 'alcohol use disorder', 'addiction_alcohol', TRUE, 'crisis_suicidal', NOW() - INTERVAL '5 days' + INTERVAL '12 minutes', 'flutter'
FROM patients WHERE patient_code = 'PAT-008'
ON CONFLICT (session_id) DO NOTHING;

-- PAT-007 session (grief)
INSERT INTO sessions (session_id, patient_id, patient_code, started_at, last_active, message_count, user_message_count, bot_message_count, severity_flags, intents_seen, last_topic, last_topic_tag, is_crisis, channel)
SELECT 'SESSION-PAT007-A', id, 'PAT-007', NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days' + INTERVAL '22 minutes', 8, 4, 4, ARRAY['medium'], ARRAY['trigger_grief','mood_sad','mood_lonely'], 'grief and loss', 'trigger_grief', FALSE, 'flutter'
FROM patients WHERE patient_code = 'PAT-007'
ON CONFLICT (session_id) DO NOTHING;


-- ================================================================
-- DUMMY CONVERSATIONS
-- Sample messages for PAT-001 to show realistic chat history.
-- ================================================================

INSERT INTO conversations (session_id, patient_id, patient_code, role, content, intent, severity, has_rag_context, show_resources, policy_checked, created_at)
SELECT 'SESSION-PAT001-A', id, 'PAT-001', 'user', 'Hi, I need some help today', 'greeting', 'low', FALSE, FALSE, FALSE, NOW() - INTERVAL '10 days'
FROM patients WHERE patient_code = 'PAT-001';

INSERT INTO conversations (session_id, patient_id, patient_code, role, content, intent, severity, has_rag_context, show_resources, policy_checked, created_at)
SELECT 'SESSION-PAT001-A', id, 'PAT-001', 'assistant', 'Hi Arjun, I am glad you reached out. I am here to listen. What is on your mind today?', 'greeting', 'low', FALSE, FALSE, TRUE, NOW() - INTERVAL '10 days' + INTERVAL '10 seconds'
FROM patients WHERE patient_code = 'PAT-001';

INSERT INTO conversations (session_id, patient_id, patient_code, role, content, intent, severity, has_rag_context, show_resources, policy_checked, created_at)
SELECT 'SESSION-PAT001-A', id, 'PAT-001', 'user', 'I have been drinking more than usual this week, feeling stressed about work', 'addiction_alcohol', 'medium', FALSE, FALSE, FALSE, NOW() - INTERVAL '10 days' + INTERVAL '1 minute'
FROM patients WHERE patient_code = 'PAT-001';

INSERT INTO conversations (session_id, patient_id, patient_code, role, content, intent, severity, has_rag_context, show_resources, policy_checked, created_at)
SELECT 'SESSION-PAT001-A', id, 'PAT-001', 'assistant', 'Thank you for sharing that. It takes courage to recognise that pattern. Work stress is one of the most common triggers for increased alcohol use. Would you like to explore what has been driving the stress this week?', 'addiction_alcohol', 'medium', TRUE, FALSE, TRUE, NOW() - INTERVAL '10 days' + INTERVAL '1 minute' + INTERVAL '15 seconds'
FROM patients WHERE patient_code = 'PAT-001';

INSERT INTO conversations (session_id, patient_id, patient_code, role, content, intent, severity, has_rag_context, show_resources, policy_checked, created_at)
SELECT 'SESSION-PAT001-A', id, 'PAT-001', 'user', 'I feel anxious all the time and drinking helps me calm down', 'mood_anxious', 'medium', FALSE, FALSE, FALSE, NOW() - INTERVAL '10 days' + INTERVAL '3 minutes'
FROM patients WHERE patient_code = 'PAT-001';

INSERT INTO conversations (session_id, patient_id, patient_code, role, content, intent, severity, has_rag_context, show_resources, policy_checked, created_at)
SELECT 'SESSION-PAT001-A', id, 'PAT-001', 'assistant', 'That makes a lot of sense. Many people use alcohol to manage anxiety because it feels like it works in the short term. However, alcohol can actually increase anxiety over time as it leaves the system. I would really encourage you to discuss this with Dr. Krishnan at your next session.', 'mood_anxious', 'medium', TRUE, FALSE, TRUE, NOW() - INTERVAL '10 days' + INTERVAL '3 minutes' + INTERVAL '20 seconds'
FROM patients WHERE patient_code = 'PAT-001';


-- ================================================================
-- DUMMY CRISIS EVENT (PAT-008 — for demo of crisis dashboard)
-- ================================================================

INSERT INTO crisis_events (
    session_id, patient_id, patient_code,
    crisis_type, trigger_message, bot_response, severity,
    detected_at, follow_up_status
)
SELECT
    'SESSION-PAT008-A', id, 'PAT-008',
    'crisis_suicidal',
    'I cannot do this anymore. I just want it all to stop.',
    'I am really sorry you are feeling this way. You do not have to face this alone. Please reach out to emergency services: 112 / 911 / 999 or Crisis Text Line: Text HOME to 741741.',
    'critical',
    NOW() - INTERVAL '5 days' + INTERVAL '12 minutes',
    'pending'
FROM patients WHERE patient_code = 'PAT-008'
ON CONFLICT DO NOTHING;


-- ================================================================
-- VERIFY — run after inserting to confirm data is in place
-- ================================================================

SELECT
    p.patient_code,
    p.display_name,
    p.programme,
    p.is_active,
    (p.metadata->>'risk_level')         AS risk_level,
    COUNT(DISTINCT s.session_id)        AS sessions,
    COUNT(c.id)                         AS messages
FROM patients p
LEFT JOIN sessions     s ON s.patient_id = p.id
LEFT JOIN conversations c ON c.patient_id = p.id
GROUP BY p.id, p.patient_code, p.display_name, p.programme, p.is_active, p.metadata
ORDER BY p.patient_code;

-- ================================================================
-- TRUST AI — MENTAL HEALTH CHATBOT
-- Database Schema — Full Create + Grant Script
-- PostgreSQL 15+
--
-- Tables:
--   1. patients           Patient registry
--   2. sessions           One per app/browser session, linked to patient
--   3. conversations      Every message exchanged, linked to both
--   4. policy_violations  Audit log for ethical AI policy breaches
--   5. crisis_events      High-priority log for all crisis interactions
--
-- HOW TO RUN:
--   Step 1 — Connect as postgres superuser and run once:
--     psql -U postgres
--     CREATE DATABASE chatbot_db;
--     CREATE USER chatbot_user WITH PASSWORD 'your_password';
--     GRANT ALL PRIVILEGES ON DATABASE chatbot_db TO chatbot_user;
--     \q
--
--   Step 2 — Run this file:
--     psql -U postgres -d chatbot_db -f create_schema.sql
--
--   Step 3 — Verify:
--     psql -U postgres -d chatbot_db -c "\dt"
-- ================================================================


-- ── Extension ────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- ================================================================
-- TABLE 1: PATIENTS
-- One row per patient. Created on first chat contact.
-- patient_code = your internal MRN / user ID from your auth system.
-- ================================================================

CREATE TABLE IF NOT EXISTS patients (

    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_code        TEXT        UNIQUE NOT NULL,
    display_name        TEXT,

    date_of_birth       DATE,
    gender              TEXT,
    assigned_clinician  TEXT,
    programme           TEXT,
    referral_source     TEXT,

    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    enrolled_at         TIMESTAMP   NOT NULL DEFAULT NOW(),
    discharged_at       TIMESTAMP,
    discharge_reason    TEXT,

    created_at          TIMESTAMP   NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP   NOT NULL DEFAULT NOW(),

    metadata            JSONB       NOT NULL DEFAULT '{}'

);

COMMENT ON TABLE  patients                  IS 'Patient registry. One row per patient. patient_code maps to your auth system user ID or MRN.';
COMMENT ON COLUMN patients.patient_code     IS 'Your internal patient identifier from your auth/EHR system.';
COMMENT ON COLUMN patients.metadata         IS 'Extra clinical data. E.g. {"risk_level":"high","primary_addiction":"alcohol"}';


-- ================================================================
-- TABLE 2: SESSIONS
-- One row per app/browser visit.
-- A patient will have many sessions over time.
-- ================================================================

CREATE TABLE IF NOT EXISTS sessions (

    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          TEXT        UNIQUE NOT NULL,
    patient_id          UUID        REFERENCES patients(id) ON DELETE SET NULL,
    patient_code        TEXT,

    started_at          TIMESTAMP   NOT NULL DEFAULT NOW(),
    last_active         TIMESTAMP   NOT NULL DEFAULT NOW(),
    ended_at            TIMESTAMP,

    message_count       INTEGER     NOT NULL DEFAULT 0,
    user_message_count  INTEGER     NOT NULL DEFAULT 0,
    bot_message_count   INTEGER     NOT NULL DEFAULT 0,

    severity_flags      TEXT[]      NOT NULL DEFAULT '{}',
    intents_seen        TEXT[]      NOT NULL DEFAULT '{}',
    last_topic          TEXT,
    last_topic_tag      TEXT,

    is_crisis           BOOLEAN     NOT NULL DEFAULT FALSE,
    crisis_intent       TEXT,
    crisis_at           TIMESTAMP,

    channel             TEXT        NOT NULL DEFAULT 'web',
    device_info         TEXT,

    created_at          TIMESTAMP   NOT NULL DEFAULT NOW(),
    metadata            JSONB       NOT NULL DEFAULT '{}'

);

COMMENT ON TABLE  sessions                  IS 'One session per app or browser visit. A patient will have many sessions over time.';
COMMENT ON COLUMN sessions.severity_flags   IS 'All severity levels seen: low, medium, high, critical.';
COMMENT ON COLUMN sessions.intents_seen     IS 'All unique intent tags detected in this session.';
COMMENT ON COLUMN sessions.is_crisis        IS 'TRUE if any message triggered a crisis or high-risk intent.';
COMMENT ON COLUMN sessions.crisis_intent    IS 'The specific crisis intent tag that first set is_crisis = TRUE.';
COMMENT ON COLUMN sessions.channel          IS 'Origin channel: web, mobile, flutter.';


-- ================================================================
-- TABLE 3: CONVERSATIONS
-- Every single message — both user and assistant turns.
-- patient_id and patient_code are denormalised for fast
-- per-patient queries without joins.
-- ================================================================

CREATE TABLE IF NOT EXISTS conversations (

    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id              TEXT        NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    patient_id              UUID        REFERENCES patients(id) ON DELETE SET NULL,
    patient_code            TEXT,

    role                    TEXT        NOT NULL CHECK (role IN ('user', 'assistant')),
    content                 TEXT        NOT NULL,

    intent                  TEXT,
    severity                TEXT        CHECK (
                                            severity IN ('low','medium','high','critical')
                                            OR severity IS NULL
                                        ),

    citations               TEXT[]      NOT NULL DEFAULT '{}',
    has_rag_context         BOOLEAN     NOT NULL DEFAULT FALSE,
    show_resources          BOOLEAN     NOT NULL DEFAULT FALSE,

    policy_checked          BOOLEAN     NOT NULL DEFAULT FALSE,
    policy_violation        BOOLEAN     NOT NULL DEFAULT FALSE,
    policy_violation_type   TEXT,

    created_at              TIMESTAMP   NOT NULL DEFAULT NOW()

);

COMMENT ON TABLE  conversations                       IS 'Every message exchanged. patient_id and patient_code are denormalised for fast per-patient queries.';
COMMENT ON COLUMN conversations.intent                IS 'Intent tag. E.g. mood_anxious, crisis_suicidal, severe_distress, psychosis_indicator.';
COMMENT ON COLUMN conversations.citations             IS 'PDF sources used to ground the response.';
COMMENT ON COLUMN conversations.has_rag_context       IS 'TRUE if Qdrant RAG retrieval was used for this response.';
COMMENT ON COLUMN conversations.show_resources        IS 'TRUE if crisis helpline resources were shown to the user.';
COMMENT ON COLUMN conversations.policy_checked        IS 'TRUE if ethical_policy.check_policy() was run on this response.';
COMMENT ON COLUMN conversations.policy_violation      IS 'TRUE if a policy violation was detected and the safe fallback was returned.';
COMMENT ON COLUMN conversations.policy_violation_type IS 'Which rule was breached: diagnosis, medication, replacement, identity.';


-- ================================================================
-- TABLE 4: POLICY_VIOLATIONS
-- Dedicated audit log for every ethical AI policy breach.
-- Populated by ethical_policy.check_policy() via db.log_policy_violation().
--
-- Required for:
--   EU AI Act 2024 Annex III  — audit trail for high-risk AI
--   HIPAA                     — AI safety intervention log
--   Clinical governance       — evidence guardrails are working
-- ================================================================

CREATE TABLE IF NOT EXISTS policy_violations (

    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          TEXT        REFERENCES sessions(session_id) ON DELETE SET NULL,
    patient_id          UUID        REFERENCES patients(id) ON DELETE SET NULL,
    patient_code        TEXT,
    conversation_id     UUID        REFERENCES conversations(id) ON DELETE SET NULL,

    violation_type      TEXT        NOT NULL,
    intent_at_time      TEXT,
    original_response   TEXT,
    safe_response_used  TEXT,
    pattern_matched     TEXT,

    detected_at         TIMESTAMP   NOT NULL DEFAULT NOW(),
    reviewed_by         TEXT,
    reviewed_at         TIMESTAMP,
    review_notes        TEXT

);

COMMENT ON TABLE  policy_violations                  IS 'Audit log for all ethical policy violations intercepted at runtime by ethical_policy.py.';
COMMENT ON COLUMN policy_violations.violation_type   IS 'Which rule was breached: diagnosis, medication, replacement, identity.';
COMMENT ON COLUMN policy_violations.original_response IS 'The blocked LLM output (truncated to 1000 chars).';
COMMENT ON COLUMN policy_violations.safe_response_used IS 'The fallback response that was returned to the user instead.';


-- ================================================================
-- TABLE 5: CRISIS_EVENTS
-- High-priority log for all crisis interactions.
-- Every row must be reviewed by the clinical team.
-- Tracks escalation and follow-up status.
-- ================================================================

CREATE TABLE IF NOT EXISTS crisis_events (

    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          TEXT        REFERENCES sessions(session_id) ON DELETE SET NULL,
    patient_id          UUID        REFERENCES patients(id) ON DELETE SET NULL,
    patient_code        TEXT,
    conversation_id     UUID        REFERENCES conversations(id) ON DELETE SET NULL,

    crisis_type         TEXT        NOT NULL,
    trigger_message     TEXT,
    bot_response        TEXT,
    severity            TEXT        NOT NULL DEFAULT 'critical',

    detected_at         TIMESTAMP   NOT NULL DEFAULT NOW(),
    escalated_to        TEXT,
    escalated_at        TIMESTAMP,

    follow_up_status    TEXT        NOT NULL DEFAULT 'pending'
                                    CHECK (follow_up_status IN (
                                        'pending',
                                        'in_progress',
                                        'resolved',
                                        'no_action'
                                    )),
    follow_up_notes     TEXT,
    resolved_at         TIMESTAMP,
    resolved_by         TEXT

);

COMMENT ON TABLE  crisis_events                  IS 'High-priority log for all crisis interactions. Every row requires clinical review.';
COMMENT ON COLUMN crisis_events.crisis_type      IS 'crisis_suicidal, crisis_abuse, behaviour_self_harm, severe_distress, or psychosis_indicator.';
COMMENT ON COLUMN crisis_events.trigger_message  IS 'The user message that triggered the crisis response.';
COMMENT ON COLUMN crisis_events.follow_up_status IS 'pending=not yet reviewed | in_progress=clinician active | resolved=complete | no_action=reviewed, none needed.';


-- ================================================================
-- INDEXES
-- ================================================================

-- patients
CREATE INDEX IF NOT EXISTS idx_patients_code            ON patients(patient_code);
CREATE INDEX IF NOT EXISTS idx_patients_active          ON patients(is_active);
CREATE INDEX IF NOT EXISTS idx_patients_programme       ON patients(programme);

-- sessions
CREATE INDEX IF NOT EXISTS idx_sessions_patient_id      ON sessions(patient_id);
CREATE INDEX IF NOT EXISTS idx_sessions_patient_code    ON sessions(patient_code);
CREATE INDEX IF NOT EXISTS idx_sessions_last_active     ON sessions(last_active DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_started_at      ON sessions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_is_crisis       ON sessions(is_crisis)
    WHERE is_crisis = TRUE;

-- conversations
CREATE INDEX IF NOT EXISTS idx_conv_session             ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conv_patient_id          ON conversations(patient_id);
CREATE INDEX IF NOT EXISTS idx_conv_patient_code        ON conversations(patient_code);
CREATE INDEX IF NOT EXISTS idx_conv_created             ON conversations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conv_intent              ON conversations(intent)
    WHERE intent IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_conv_severity            ON conversations(severity)
    WHERE severity IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_conv_show_resources      ON conversations(session_id)
    WHERE show_resources = TRUE;
CREATE INDEX IF NOT EXISTS idx_conv_policy_violation    ON conversations(session_id)
    WHERE policy_violation = TRUE;

-- policy_violations
CREATE INDEX IF NOT EXISTS idx_pv_session               ON policy_violations(session_id);
CREATE INDEX IF NOT EXISTS idx_pv_patient_id            ON policy_violations(patient_id);
CREATE INDEX IF NOT EXISTS idx_pv_type                  ON policy_violations(violation_type);
CREATE INDEX IF NOT EXISTS idx_pv_detected              ON policy_violations(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_pv_unreviewed            ON policy_violations(detected_at)
    WHERE reviewed_at IS NULL;

-- crisis_events
CREATE INDEX IF NOT EXISTS idx_ce_patient_id            ON crisis_events(patient_id);
CREATE INDEX IF NOT EXISTS idx_ce_patient_code          ON crisis_events(patient_code);
CREATE INDEX IF NOT EXISTS idx_ce_type                  ON crisis_events(crisis_type);
CREATE INDEX IF NOT EXISTS idx_ce_detected              ON crisis_events(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_ce_status                ON crisis_events(follow_up_status);
CREATE INDEX IF NOT EXISTS idx_ce_pending               ON crisis_events(detected_at)
    WHERE follow_up_status = 'pending';


-- ================================================================
-- GRANTS
-- ================================================================

-- Table-level: full read/write for chatbot_user
GRANT ALL ON TABLE patients          TO chatbot_user;
GRANT ALL ON TABLE sessions          TO chatbot_user;
GRANT ALL ON TABLE conversations     TO chatbot_user;
GRANT ALL ON TABLE policy_violations TO chatbot_user;
GRANT ALL ON TABLE crisis_events     TO chatbot_user;

-- Schema-level: required to access any object in the schema
GRANT USAGE ON SCHEMA public TO chatbot_user;

-- Sequence-level: required for gen_random_uuid() and any serial columns
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO chatbot_user;

-- Future tables: ensures tables created later are also accessible
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON TABLES    TO chatbot_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON SEQUENCES TO chatbot_user;


-- ================================================================
-- VERIFY (uncomment and run in psql to confirm)
-- ================================================================

-- Check all tables were created:
-- \dt

-- Check columns on each table:
-- \d patients
-- \d sessions
-- \d conversations
-- \d policy_violations
-- \d crisis_events

-- Confirm chatbot_user has correct grants:
-- SELECT table_name, privilege_type
-- FROM information_schema.role_table_grants
-- WHERE grantee = 'chatbot_user'
-- ORDER BY table_name, privilege_type;


-- ================================================================
-- TABLE 6: PATIENT_SCORES
-- 0-10 score captured once per session per group.
-- score_group: mood / addiction / triggers / sleep
-- 10 = best, 0 = worst
-- ================================================================

CREATE TABLE IF NOT EXISTS patient_scores (

    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      TEXT        REFERENCES sessions(session_id) ON DELETE SET NULL,
    patient_id      UUID        REFERENCES patients(id) ON DELETE SET NULL,
    patient_code    TEXT        NOT NULL,
    score_group     TEXT        NOT NULL CHECK (score_group IN ('mood','addiction','triggers','sleep')),
    score           INTEGER     NOT NULL CHECK (score BETWEEN 0 AND 10),
    intent_at_time  TEXT,
    scored_at       TIMESTAMP   NOT NULL DEFAULT NOW(),

    -- One score per group per session
    UNIQUE (session_id, score_group)
);

COMMENT ON TABLE  patient_scores             IS 'One 0-10 score per score group per session. Never overwritten — captured once only.';
COMMENT ON COLUMN patient_scores.score       IS '0 = worst, 10 = best. Mood: 0 very low, 10 very well. Addiction: 0 no urge, 10 very strong urge.';
COMMENT ON COLUMN patient_scores.score_group IS 'mood / addiction / triggers / sleep';

CREATE INDEX IF NOT EXISTS idx_scores_patient_code ON patient_scores(patient_code);
CREATE INDEX IF NOT EXISTS idx_scores_session      ON patient_scores(session_id);
CREATE INDEX IF NOT EXISTS idx_scores_group        ON patient_scores(score_group);
CREATE INDEX IF NOT EXISTS idx_scores_scored_at    ON patient_scores(scored_at DESC);

GRANT ALL ON TABLE patient_scores TO chatbot_user;

/**
 * SUPABASE SCHEMA FOR TRUST AI — FINAL
 * Updated: March 2026
 *
 * Incorporates:
 *   — Original SUPABASE_SCHEMA_UPDATED.sql (14 tables, 4 views)
 *   — PDF gap analysis: all 48 dataset columns mapped and verified
 *   — PPT screen fields: 8 fields visible in app UI now captured in DB
 *   — New table: wearable_readings (Slide 9)
 *
 * Changes vs previous version marked [ADDED]
 *
 * Tables:
 *  1.  patients              Core patient demographics and identifiers
 *  2.  onboarding_profiles   Intake data collected at first contact
 *  3.  daily_checkins        Daily mood / craving / medication / sleep tracking
 *  4.  sessions              Conversation sessions with metadata
 *  5.  messages              Individual messages (user + bot)
 *  6.  risk_assessments      Computed risk scores and drivers
 *  7.  content_engagement    Video views, completions, ratings
 *  8.  support_networks      Therapists, sponsors, family contacts
 *  9.  crisis_events         Crisis-level incidents for monitoring
 *  10. conversation_metrics  Per-session 5-layer compliance tracking
 *  11. relapse_events        Disclosed relapses with context
 *  12. patient_milestones    Sober streaks and achievement tracking
 *  13. policy_violations     Chatbot ethical guardrail breaches
 *  14. treatment_outcomes    TRUST improvement and abstinence outcomes
 *  15. wearable_readings     [ADDED] Daily wearable device readings (Slide 9)
 *  16. patient_addictions    [ADDED] Junction table — one row per addiction type per patient
 *  17. response_routing      [ADDED] Clinician-editable matrix: (addiction × intent) → routing strategy
 *  18. patient_context_vectors [ADDED] Greeting synthesis audit trail — snapshot of context at greeting time
 */


-- ============================================================================
-- 1. PATIENTS
-- No changes from previous version
-- ============================================================================

CREATE TABLE patients (
  patient_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_code        VARCHAR(20) UNIQUE NOT NULL,
  first_name          VARCHAR(100),
  last_name           VARCHAR(100),
  email               VARCHAR(255),
  phone               VARCHAR(20),

  -- Demographics
  date_of_birth       DATE,
  gender              VARCHAR(50),
  country             VARCHAR(100),

  -- Localisation — drives chatbot language and time-of-day tone logic
  preferred_language  VARCHAR(10)  DEFAULT 'en',
  timezone            VARCHAR(50)  DEFAULT 'UTC',

  -- Status flags
  is_active           BOOLEAN     DEFAULT true,
  enrollment_date     TIMESTAMP   DEFAULT now(),
  last_active_at      TIMESTAMP,

  -- Audit
  created_at          TIMESTAMP   DEFAULT now(),
  updated_at          TIMESTAMP   DEFAULT now(),

  CONSTRAINT patient_code_not_empty CHECK (patient_code <> '')
);

CREATE INDEX idx_patients_code  ON patients(patient_code);
CREATE INDEX idx_patients_email ON patients(email);


-- ============================================================================
-- 2. ONBOARDING PROFILES
-- [ADDED] drug_using_peers          — PDF gap col 32; chatbot peer-advice guard
-- [ADDED] medication_adherence_baseline — Slide 2 Baseline Assessment intake field
-- ============================================================================

CREATE TABLE onboarding_profiles (
  profile_id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id                    UUID        NOT NULL UNIQUE REFERENCES patients(patient_id) ON DELETE CASCADE,

  -- Addiction / Recovery focus
  addiction_type                VARCHAR(100),
  baseline_mood                 JSONB,        -- ["lonely","angry","guilty","stressed"]
  primary_triggers              JSONB,        -- ["social situations","stress","specific places"]

  -- Addiction severity
  duration_heavy_use_years      INTEGER,
  high_baseline_consumption     BOOLEAN      DEFAULT false,
  morning_or_continuous_use     BOOLEAN      DEFAULT false,  -- strong relapse predictor
  injection_use_history         BOOLEAN      DEFAULT false,  -- medical safety flag
  polysubstance_use             BOOLEAN      DEFAULT false,  -- affects RAG retrieval focus
  early_onset_use               BOOLEAN      DEFAULT false,  -- use started before age 25

  -- Support & Context
  support_network               JSONB,        -- {"sponsor":"John","therapist":"Dr Smith"}
  work_status                   VARCHAR(50),  -- employed, unemployed, student, on_leave
  housing_status                VARCHAR(50),  -- stable, transitional, unstable

  -- Social / environmental risk flags
  family_member_uses            BOOLEAN      DEFAULT false,  -- CRITICAL: chatbot cannot suggest "talk to family" if true
  drug_using_peers              BOOLEAN      DEFAULT false,  -- [ADDED] PDF col 32; chatbot cannot suggest peer socialising if true
  poor_family_support           BOOLEAN      DEFAULT false,
  relationship_problems         BOOLEAN      DEFAULT false,
  legal_problems                BOOLEAN      DEFAULT false,
  trauma_history                BOOLEAN      DEFAULT false,  -- activates TRAUMA_RESPONSE_INTRO
  strong_social_support_flag    BOOLEAN      DEFAULT false,
  mutual_help_group             BOOLEAN      DEFAULT false,  -- AA/NA attendance
  lower_education               BOOLEAN      DEFAULT false,

  -- Medical
  diagnosed_conditions          JSONB,        -- ["anxiety","depression","PTSD"]
  current_medications           JSONB,

  -- Clinical safety flags — explicit booleans, not just JSONB
  suicide_attempt_history       BOOLEAN      DEFAULT false,  -- elevates crisis escalation immediately
  cognitive_impairment          BOOLEAN      DEFAULT false,  -- shortens chatbot response length
  chronic_pain                  BOOLEAN      DEFAULT false,

  -- Psychological profile — drives tone engine and RAG routing
  cue_reactivity                BOOLEAN      DEFAULT false,  -- high = show video faster on craving intent
  low_self_efficacy             BOOLEAN      DEFAULT false,  -- drives warm/energising tone
  avoidant_coping               BOOLEAN      DEFAULT false,  -- never suggest avoidance strategies
  high_impulsivity              BOOLEAN      DEFAULT false,  -- triggers delay-response technique
  low_motivation                BOOLEAN      DEFAULT false,  -- drives motivational interviewing tone
  emotion_regulation_difficulty BOOLEAN      DEFAULT false,  -- routes to DBT-style RAG content
  high_neuroticism              BOOLEAN      DEFAULT false,
  low_conscientiousness         BOOLEAN      DEFAULT false,  -- predicts medication non-adherence

  -- Sleep baseline (separate from daily check-in sleep score)
  insomnia                      BOOLEAN      DEFAULT false,
  irregular_sleep_schedule      BOOLEAN      DEFAULT false,
  uses_substance_for_sleep      BOOLEAN      DEFAULT false,  -- CRITICAL: never suggest sedatives as sleep aid

  -- Baseline scores for risk delta calculation
  sleep_quality_baseline        INTEGER      CHECK (sleep_quality_baseline IS NULL OR (sleep_quality_baseline BETWEEN 0 AND 10)),
  craving_frequency_baseline    VARCHAR(20),  -- rarely, sometimes, often, almost_always
  physical_health_score         INTEGER      CHECK (physical_health_score IS NULL OR (physical_health_score BETWEEN 0 AND 10)),

  -- Treatment History
  previous_treatment            BOOLEAN,
  multiple_prior_treatments     BOOLEAN      DEFAULT false,
  short_treatment_duration      BOOLEAN      DEFAULT false,
  previous_treatment_notes      TEXT,

  -- [ADDED] Baseline medication adherence — Slide 2 intake "Medication Adherence Yes/No"
  -- Distinct from daily_checkins.medication_taken (daily) — this captures historical pattern at intake
  -- Feeds Baseline Vulnerability Score in Model 1
  medication_adherence_baseline BOOLEAN      DEFAULT false,

  -- Preferences
  communication_preference      VARCHAR(50),  -- text, voice, written_journal
  content_preferences           JSONB,        -- ["short-form","narrative","interactive"]

  -- Intake completion tracking
  intake_consent_given          BOOLEAN      DEFAULT false,
  consent_timestamp             TIMESTAMP,
  intake_completion_pct         INTEGER      CHECK (intake_completion_pct IS NULL OR (intake_completion_pct BETWEEN 0 AND 100)),
  last_intake_phase             INTEGER      DEFAULT 0,      -- 0-5, resumes from here on session start

  -- Audit
  completed_at                  TIMESTAMP   DEFAULT now(),
  created_at                    TIMESTAMP   DEFAULT now(),
  updated_at                    TIMESTAMP   DEFAULT now(),

  CONSTRAINT profile_patient_fk FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

CREATE INDEX idx_onboarding_patient          ON onboarding_profiles(patient_id);
CREATE INDEX idx_onboarding_addiction_type   ON onboarding_profiles(addiction_type);
CREATE INDEX idx_onboarding_high_risk_flags  ON onboarding_profiles(patient_id)
  WHERE suicide_attempt_history = true OR drug_using_peers = true OR family_member_uses = true;


-- ============================================================================
-- 3. DAILY CHECKINS
-- [ADDED] stress_score              — Slide 2 & 6: numeric stress slider (0–10)
-- [ADDED] trigger_exposure_flag     — Slide 2 & 3: binary yes/no trigger flag
-- [ADDED] recovery_activity_today   — Slide 3: AA/therapy/journaling logged today
-- [ADDED] recovery_social_support   — Slide 2: recovery-specific social support
-- [ADDED] addiction_specific_data   — Slides 6–8: type-specific daily questions
-- ============================================================================

CREATE TABLE daily_checkins (
  checkin_id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id                    UUID        NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  session_id                    UUID,

  -- Check-in date
  checkin_date                  DATE        NOT NULL,

  -- Mood & Emotional State
  todays_mood                   VARCHAR(50),  -- Happy, Neutral, Sad, Angry, Stressed, Lonely, Guilty, Distrust, Boredom
  emotional_notes               TEXT,

  -- Explicit risk flags
  negative_affect               BOOLEAN      DEFAULT false,  -- 35% relapse rate vs 31% baseline
  high_life_stress              BOOLEAN      DEFAULT false,  -- boolean flag for quick queries

  -- [ADDED] Numeric stress slider — Slide 2 & 6 "Stress Level Low ← 5 → High"
  -- Risk engine: stress_contribution = (stress_score / 10) * 10, max 10 pts
  -- high_life_stress BOOLEAN above retained for fast index queries
  stress_score                  INTEGER      CHECK (stress_score IS NULL OR (stress_score BETWEEN 0 AND 10)),

  -- Sleep
  sleep_quality                 INTEGER      CHECK (sleep_quality IS NULL OR (sleep_quality BETWEEN 0 AND 10)),
  sleep_hours                   DECIMAL(4,1),
  sleep_notes                   TEXT,
  rest_level                    INTEGER      CHECK (rest_level IS NULL OR (rest_level BETWEEN 0 AND 10)),

  -- Cravings
  craving_intensity             INTEGER      CHECK (craving_intensity IS NULL OR (craving_intensity BETWEEN 0 AND 10)),
  craving_triggers              JSONB,        -- ["work stress","social event","conflict"]

  -- Medication Adherence
  medication_taken              BOOLEAN,
  medications_list              JSONB,
  medication_notes              TEXT,

  -- Environmental Triggers
  triggers_today                JSONB,        -- content/description of triggers
  trigger_intensity             INTEGER      CHECK (trigger_intensity IS NULL OR (trigger_intensity BETWEEN 0 AND 10)),
  trigger_response              TEXT,

  -- [ADDED] Binary trigger flag — Slide 2 "Have you encountered people or places that trigger cravings? Yes/No"
  -- Slide 3 "Have you faced triggers? Yes/No"
  -- Distinct from triggers_today JSONB which stores descriptions
  -- Risk engine: trigger domain base = 10 pts if true; 0 if false
  trigger_exposure_flag         BOOLEAN      DEFAULT false,

  -- Social / Support
  social_contact                BOOLEAN,      -- any social contact today
  social_notes                  TEXT,

  -- [ADDED] Recovery-specific social support — Slide 2 "Social Support Yes/No"
  -- Captures sponsor/AA group/counselor contact specifically, not general socialising
  -- Risk engine: recovery_social_support = true → -3 pts adherence domain
  recovery_social_support       BOOLEAN      DEFAULT false,

  -- Additional Context
  exercise_done                 BOOLEAN,
  exercise_duration_minutes     INTEGER,
  self_care_activities          JSONB,        -- ["meditation","journaling","outdoor"]

  -- [ADDED] Recovery activity — Slide 3 recovery actions checklist
  -- Covers AA/NA meeting, therapy session, journaling, mindfulness
  -- Distinct from exercise_done — exercise ≠ recovery activity
  -- Risk engine: recovery_activity_today = true → -5 pts adherence domain
  recovery_activity_today       BOOLEAN      DEFAULT false,

  -- [ADDED] Addiction-specific daily flags — Slides 6, 7, 8
  -- Stores type-specific yes/no daily questions as JSONB to avoid 6 sparse column sets
  -- Alcohol:    {"drank_today":1, "units_consumed_today":6}
  -- Opioids:    {"used_opioid_today":0, "took_mat_dose_today":1, "withdrawal_symptoms_today":0}
  -- Stimulants: {"used_stimulant_today":0, "paranoia_today":0, "energy_crash_today":1}
  -- Cannabis:   {"smoked_weed_today":1, "sessions_today":3, "motivation_level_today":2}
  -- Nicotine:   {"smoked_or_vaped_today":1, "cigarettes_today":12, "stress_craving_link_today":1}
  -- Behavioral: {"hours_gamed_today":7, "gamed_past_midnight":1, "gaming_control_problem":1}
  addiction_specific_data       JSONB,

  -- Check-in meta
  checkin_risk_score            INTEGER      CHECK (checkin_risk_score IS NULL OR (checkin_risk_score BETWEEN 0 AND 100)),
  checkin_completed_via         VARCHAR(20)  DEFAULT 'chat',  -- 'chat' or 'form'
  missed_checkin_days           INTEGER      DEFAULT 0,        -- consecutive days gap — itself a risk signal

  -- Audit
  created_at                    TIMESTAMP   DEFAULT now(),
  updated_at                    TIMESTAMP   DEFAULT now(),

  CONSTRAINT checkin_patient_fk FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

CREATE INDEX idx_checkins_patient_date    ON daily_checkins(patient_id, checkin_date DESC);
CREATE INDEX idx_checkins_session         ON daily_checkins(session_id);
CREATE INDEX idx_checkins_high_risk       ON daily_checkins(patient_id, checkin_risk_score DESC)
  WHERE checkin_risk_score >= 70;
CREATE INDEX idx_checkins_trigger_flag    ON daily_checkins(patient_id, trigger_exposure_flag)
  WHERE trigger_exposure_flag = true;
CREATE INDEX idx_checkins_stress          ON daily_checkins(patient_id, stress_score);
CREATE INDEX idx_checkins_missed          ON daily_checkins(patient_id, missed_checkin_days)
  WHERE missed_checkin_days >= 2;
CREATE INDEX idx_checkins_addiction_data  ON daily_checkins USING gin(addiction_specific_data)
  WHERE addiction_specific_data IS NOT NULL;


-- ============================================================================
-- 4. SESSIONS
-- No changes from previous version
-- ============================================================================

CREATE TABLE sessions (
  session_id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id                    UUID        NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  patient_code                  VARCHAR(20) NOT NULL,

  -- Session Timing
  started_at                    TIMESTAMP   DEFAULT now(),
  ended_at                      TIMESTAMP,

  -- Session classification
  session_type                  VARCHAR(30) DEFAULT 'support',  -- intake, daily_checkin, support, crisis
  intake_phase_reached          INTEGER,                         -- 0-5 for incomplete intake sessions

  -- Conversation Metadata
  message_count                 INTEGER     DEFAULT 0,
  last_intent                   VARCHAR(100),
  severity_flags                JSONB       DEFAULT '[]'::jsonb,
  conversation_duration_minutes INTEGER,
  questions_asked_count         INTEGER     DEFAULT 0,   -- Layer 2: should stay <= 1 per turn

  -- Topics Covered
  topics_covered                JSONB,

  -- Risk State During Session
  peak_risk_level               VARCHAR(20),
  peak_risk_score               INTEGER,
  crisis_detected               BOOLEAN     DEFAULT false,

  -- Human escalation
  escalated_to_human            BOOLEAN     DEFAULT false,
  escalation_reason             TEXT,

  -- Outcomes
  conversation_summary          TEXT,
  action_items                  JSONB,

  -- Patient satisfaction
  user_satisfaction_score       INTEGER     CHECK (user_satisfaction_score IS NULL OR (user_satisfaction_score BETWEEN 1 AND 5)),

  -- Treatment alliance score (protective factor — good_treatment_alliance from dataset)
  treatment_alliance_score      INTEGER     CHECK (treatment_alliance_score IS NULL OR (treatment_alliance_score BETWEEN 1 AND 5)),

  -- Audit
  created_at                    TIMESTAMP   DEFAULT now(),
  updated_at                    TIMESTAMP   DEFAULT now(),

  CONSTRAINT session_patient_fk FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

CREATE INDEX idx_sessions_patient    ON sessions(patient_id, started_at DESC);
CREATE INDEX idx_sessions_crisis     ON sessions(patient_id, crisis_detected) WHERE crisis_detected = true;
CREATE INDEX idx_sessions_type       ON sessions(patient_id, session_type);
CREATE INDEX idx_sessions_escalated  ON sessions(escalated_to_human) WHERE escalated_to_human = true;


-- ============================================================================
-- 5. MESSAGES
-- No changes from previous version
-- ============================================================================

CREATE TABLE messages (
  message_id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id                    UUID        NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  patient_id                    UUID        NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,

  -- Message Info
  role                          VARCHAR(20) NOT NULL,   -- 'user' or 'assistant'
  content                       TEXT        NOT NULL,

  -- Split empathy/solution storage — enables ML training on response quality
  response_empathy_line         TEXT,        -- first 1-2 lines: validation
  response_solution_line        TEXT,        -- remaining lines: action/info

  -- Intent & Severity (from NLP)
  intent                        VARCHAR(100),
  intent_confidence             DECIMAL(3,2),
  severity                      VARCHAR(20),

  -- Message-level risk
  has_crisis_indicators         BOOLEAN     DEFAULT false,
  detected_emotions             JSONB,

  -- Response Metadata (bot messages only)
  response_tone                 VARCHAR(50),  -- warm_energising, calm_grounding, direct_immediate, quiet_stabilising
  response_includes_video       BOOLEAN,
  video_title                   VARCHAR(255),
  video_id                      VARCHAR(100),
  input_widget_type             VARCHAR(30),  -- slider, yesno, mood_picker, text

  -- RAG metadata
  rag_context_used              BOOLEAN     DEFAULT false,
  rag_source_docs               JSONB,        -- ["Alcohol-use-disorders.pdf p3", ...]

  -- Minimal Question System
  minimal_question_id           VARCHAR(100),
  response_latency_ms           INTEGER,

  -- Audit
  created_at                    TIMESTAMP   DEFAULT now()
);

CREATE INDEX idx_messages_session  ON messages(session_id, created_at DESC);
CREATE INDEX idx_messages_patient  ON messages(patient_id, created_at DESC);
CREATE INDEX idx_messages_intent   ON messages(intent);
CREATE INDEX idx_messages_crisis   ON messages(patient_id, has_crisis_indicators) WHERE has_crisis_indicators = true;
CREATE INDEX idx_messages_video    ON messages(video_id) WHERE video_id IS NOT NULL;


-- ============================================================================
-- 6. RISK ASSESSMENTS
-- [ADDED] ai_confidence_score  — Slide 4 clinician view "AI Confidence 90%"
-- ============================================================================

CREATE TABLE risk_assessments (
  risk_id                       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id                    UUID        NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  session_id                    UUID        REFERENCES sessions(session_id) ON DELETE SET NULL,

  -- Risk Score (0-100)
  live_risk_score               INTEGER     NOT NULL CHECK (live_risk_score BETWEEN 0 AND 100),
  risk_level                    VARCHAR(20) NOT NULL,   -- Low, Medium, High, Critical

  -- Trend
  risk_score_delta              INTEGER,                -- change from previous e.g. +23 or -14
  risk_trend_7day               VARCHAR(20),            -- improving, worsening, stable

  -- What's driving the risk
  key_risk_drivers              JSONB,        -- ["sleep -25","cravings +30","mood +20"]
  trigger_exposure_score        INTEGER      CHECK (trigger_exposure_score IS NULL OR (trigger_exposure_score BETWEEN 0 AND 100)),

  -- Crisis Flag
  crisis_flag                   BOOLEAN     DEFAULT false,
  crisis_reason                 VARCHAR(255),

  -- Domain scores (for audit and ML)
  sleep_quality_score           INTEGER,
  craving_intensity_score       INTEGER,
  mood_risk_contribution        INTEGER,
  medication_adherence_score    DECIMAL(3,2),

  -- [ADDED] AI confidence — Slide 4 clinician list "AI Confidence" column and alert card
  -- 0–1 scale displayed as % to clinician (0.92 → "92%")
  -- Lower when streams are missing or conflict detected between NLP and self-report
  ai_confidence_score           DECIMAL(4,3) CHECK (ai_confidence_score IS NULL OR (ai_confidence_score BETWEEN 0 AND 1)),

  -- Tone applied by chatbot based on this risk level
  tone_applied                  VARCHAR(30),  -- warm_energising, calm_grounding, direct_immediate, quiet_stabilising

  -- Computed At
  computed_at                   TIMESTAMP   DEFAULT now(),
  created_at                    TIMESTAMP   DEFAULT now()
);

CREATE INDEX idx_risk_patient_latest  ON risk_assessments(patient_id, computed_at DESC);
CREATE INDEX idx_risk_crisis          ON risk_assessments(patient_id, crisis_flag) WHERE crisis_flag = true;
CREATE INDEX idx_risk_worsening       ON risk_assessments(patient_id, risk_trend_7day) WHERE risk_trend_7day = 'worsening';
CREATE INDEX idx_risk_low_confidence  ON risk_assessments(patient_id, ai_confidence_score) WHERE ai_confidence_score < 0.70;


-- ============================================================================
-- 7. CONTENT ENGAGEMENT
-- No changes from previous version
-- ============================================================================

CREATE TABLE content_engagement (
  engagement_id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id                    UUID        REFERENCES sessions(session_id) ON DELETE SET NULL,
  patient_id                    UUID        NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,

  -- Content Info
  content_id                    VARCHAR(100),
  content_type                  VARCHAR(50),   -- video, article, exercise, meditation
  content_title                 VARCHAR(255),
  content_category              VARCHAR(100),  -- breathing, sleep, crisis, motivation, craving_management
  content_duration_minutes      INTEGER,

  -- When shown
  shown_at                      TIMESTAMP   DEFAULT now(),

  -- Engagement Metrics
  completion_pct                INTEGER      CHECK (completion_pct IS NULL OR (completion_pct BETWEEN 0 AND 100)),
  time_watched_minutes          INTEGER,
  skipped                       BOOLEAN     DEFAULT false,
  was_autoplay                  BOOLEAN     DEFAULT false,

  -- User Feedback
  was_helpful                   BOOLEAN,
  user_rating                   INTEGER      CHECK (user_rating IS NULL OR (user_rating BETWEEN 1 AND 5)),
  user_notes                    TEXT,

  -- Context when shown
  shown_due_to_risk_level       VARCHAR(20),
  intent_at_time                VARCHAR(100),
  risk_score_at_time            INTEGER,

  -- Audit
  created_at                    TIMESTAMP   DEFAULT now(),
  updated_at                    TIMESTAMP   DEFAULT now()
);

CREATE INDEX idx_engagement_patient  ON content_engagement(patient_id, shown_at DESC);
CREATE INDEX idx_engagement_helpful  ON content_engagement(patient_id, was_helpful);
CREATE INDEX idx_engagement_skipped  ON content_engagement(patient_id, skipped) WHERE skipped = true;
CREATE INDEX idx_engagement_content  ON content_engagement(content_id, completion_pct);


-- ============================================================================
-- 8. SUPPORT NETWORKS
-- No changes from previous version
-- ============================================================================

CREATE TABLE support_networks (
  network_id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id                    UUID        NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,

  contact_type                  VARCHAR(50) NOT NULL,  -- sponsor, therapist, family, friend, counselor
  contact_name                  VARCHAR(100),
  contact_phone                 VARCHAR(20),
  contact_email                 VARCHAR(255),
  relationship_description      TEXT,
  availability_notes            TEXT,
  is_active                     BOOLEAN     DEFAULT true,
  involve_in_crisis             BOOLEAN     DEFAULT false,

  created_at                    TIMESTAMP   DEFAULT now(),
  updated_at                    TIMESTAMP   DEFAULT now()
);

CREATE INDEX idx_support_patient  ON support_networks(patient_id);
CREATE INDEX idx_support_type     ON support_networks(patient_id, contact_type);
CREATE INDEX idx_support_crisis   ON support_networks(patient_id, involve_in_crisis) WHERE involve_in_crisis = true;


-- ============================================================================
-- 9. CRISIS EVENTS
-- No changes from previous version
-- ============================================================================

CREATE TABLE crisis_events (
  event_id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id                    UUID        NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  session_id                    UUID        REFERENCES sessions(session_id) ON DELETE SET NULL,

  event_type                    VARCHAR(100),  -- suicidal_ideation, abuse, self_harm, relapse_risk
  severity                      VARCHAR(20)  NOT NULL,  -- critical, high
  user_message                  TEXT,
  bot_response                  TEXT,
  detected_intent               VARCHAR(100),
  crisis_protocol_triggered     BOOLEAN,
  resources_provided            JSONB,
  support_contact_suggested     VARCHAR(100),
  requires_followup             BOOLEAN,
  followup_completed            BOOLEAN     DEFAULT false,
  followup_notes                TEXT,
  followup_date                 DATE,

  created_at                    TIMESTAMP   DEFAULT now(),
  updated_at                    TIMESTAMP   DEFAULT now()
);

CREATE INDEX idx_crisis_patient  ON crisis_events(patient_id, created_at DESC);
CREATE INDEX idx_crisis_open     ON crisis_events(patient_id, followup_completed) WHERE followup_completed = false;


-- ============================================================================
-- 10. CONVERSATION METRICS
-- No changes from previous version
-- ============================================================================

CREATE TABLE conversation_metrics (
  metric_id                     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id                    UUID        NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  patient_id                    UUID        NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,

  clarity_score                 INTEGER      CHECK (clarity_score IS NULL OR (clarity_score BETWEEN 1 AND 5)),
  empathy_score                 INTEGER      CHECK (empathy_score IS NULL OR (empathy_score BETWEEN 1 AND 5)),
  actionability_score           INTEGER      CHECK (actionability_score IS NULL OR (actionability_score BETWEEN 1 AND 5)),

  -- 5-layer model compliance
  layer1_context_greeting       BOOLEAN,
  layer2_single_invitation      BOOLEAN,
  layer3_clarifying_q           BOOLEAN,
  layer4_text_video             BOOLEAN,
  layer5_soft_cta               BOOLEAN,
  adherence_score               DECIMAL(5,2),

  created_at                    TIMESTAMP   DEFAULT now()
);

CREATE INDEX idx_metrics_patient    ON conversation_metrics(patient_id, created_at DESC);
CREATE INDEX idx_metrics_adherence  ON conversation_metrics(patient_id, adherence_score DESC);


-- ============================================================================
-- 11. RELAPSE EVENTS
-- No changes from previous version
-- ============================================================================

CREATE TABLE relapse_events (
  relapse_id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id                    UUID        NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  session_id                    UUID        REFERENCES sessions(session_id) ON DELETE SET NULL,
  message_id                    UUID        REFERENCES messages(message_id) ON DELETE SET NULL,

  relapse_date                  DATE,
  substance_type                VARCHAR(100),
  relapse_context               TEXT,
  disclosed_voluntarily         BOOLEAN     DEFAULT true,
  risk_score_before             INTEGER,
  risk_score_after              INTEGER,
  bot_response_type             VARCHAR(50),   -- compassionate, normalising, escalated
  shame_language_detected       BOOLEAN     DEFAULT false,
  therapist_notified            BOOLEAN     DEFAULT false,
  sponsor_notified              BOOLEAN     DEFAULT false,

  created_at                    TIMESTAMP   DEFAULT now(),
  updated_at                    TIMESTAMP   DEFAULT now()
);

CREATE INDEX idx_relapse_patient  ON relapse_events(patient_id, relapse_date DESC);
CREATE INDEX idx_relapse_shame    ON relapse_events(patient_id, shame_language_detected) WHERE shame_language_detected = true;


-- ============================================================================
-- 12. PATIENT MILESTONES
-- No changes from previous version
-- ============================================================================

CREATE TABLE patient_milestones (
  milestone_id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id                    UUID        NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  session_id                    UUID        REFERENCES sessions(session_id) ON DELETE SET NULL,

  milestone_type                VARCHAR(50) NOT NULL,  -- sober_days, checkin_streak, video_completed, treatment_goal
  milestone_value               INTEGER     NOT NULL,
  milestone_label               VARCHAR(100),
  achieved_at                   TIMESTAMP   DEFAULT now(),
  acknowledged_by_bot           BOOLEAN     DEFAULT false,
  bot_celebration_message       TEXT,
  next_milestone_target         INTEGER,

  created_at                    TIMESTAMP   DEFAULT now()
);

CREATE INDEX idx_milestones_patient  ON patient_milestones(patient_id, achieved_at DESC);
CREATE INDEX idx_milestones_type     ON patient_milestones(patient_id, milestone_type);
CREATE INDEX idx_milestones_unacked  ON patient_milestones(patient_id, acknowledged_by_bot) WHERE acknowledged_by_bot = false;


-- ============================================================================
-- 13. POLICY VIOLATIONS
-- No changes from previous version
-- ============================================================================

CREATE TABLE policy_violations (
  violation_id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id                    UUID        REFERENCES patients(patient_id) ON DELETE SET NULL,
  session_id                    UUID        REFERENCES sessions(session_id) ON DELETE SET NULL,
  message_id                    UUID        REFERENCES messages(message_id) ON DELETE SET NULL,

  violation_type                VARCHAR(100) NOT NULL,
  intent_at_time                VARCHAR(100),
  original_llm_output           TEXT,
  bot_response_overridden       TEXT,
  policy_rule_triggered         VARCHAR(100),
  reviewed_by_admin             BOOLEAN     DEFAULT false,
  review_notes                  TEXT,
  reviewed_at                   TIMESTAMP,

  created_at                    TIMESTAMP   DEFAULT now()
);

CREATE INDEX idx_violations_session    ON policy_violations(session_id);
CREATE INDEX idx_violations_unreviewed ON policy_violations(reviewed_by_admin) WHERE reviewed_by_admin = false;
CREATE INDEX idx_violations_type       ON policy_violations(violation_type);


-- ============================================================================
-- 14. TREATMENT OUTCOMES
-- No changes from previous version
-- ============================================================================

CREATE TABLE treatment_outcomes (
  outcome_id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id                    UUID        NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,

  improved_with_trust           BOOLEAN,     -- Primary KPI: 72.6% of patients
  abstinence_gt_3_months        BOOLEAN,     -- 48.4% of patients
  relapse_within_90_days        BOOLEAN,     -- 32.4% of patients; key ML training label

  assessment_date               DATE        NOT NULL,
  assessed_by                   VARCHAR(100),  -- clinician, self_report, automated
  assessment_notes              TEXT,
  risk_score_at_assessment      INTEGER,
  total_sessions                INTEGER,
  total_checkins                INTEGER,
  longest_sober_streak_days     INTEGER,

  created_at                    TIMESTAMP   DEFAULT now(),
  updated_at                    TIMESTAMP   DEFAULT now()
);

CREATE INDEX idx_outcomes_patient   ON treatment_outcomes(patient_id, assessment_date DESC);
CREATE INDEX idx_outcomes_improved  ON treatment_outcomes(improved_with_trust);
CREATE INDEX idx_outcomes_relapse   ON treatment_outcomes(relapse_within_90_days);


-- ============================================================================
-- 15. WEARABLE READINGS  [ADDED — Slide 9]
-- All fields map directly to the wearable screens in Slide 9:
--   Screen 1: Log Your Sleep    → sleep_hours, sleep_quality_rating
--   Screen 2: Log Your Stress   → stress_self_report
--   Screen 3: Daily Vitals      → hr_bpm, hrv_ms, spo2_pct, steps_today, sleep_latency_minutes
--   Screen 4: Activity & SpO₂   → spo2_pct, restlessness_level, stress_level_device,
--                                  active_minutes, hrv trend (7-day averages)
-- ============================================================================

CREATE TABLE wearable_readings (
  reading_id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id                    UUID        NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,

  -- One aggregated row per patient per day
  reading_date                  DATE        NOT NULL,

  -- Device info
  device_type                   VARCHAR(50),   -- Apple Watch, Fitbit, Samsung, Garmin, Other
  device_id                     VARCHAR(100),  -- paired device identifier

  -- Screen 3: Daily Vitals — Heart Rate
  hr_bpm                        INTEGER      CHECK (hr_bpm IS NULL OR (hr_bpm BETWEEN 30 AND 220)),

  -- Screen 3 & 4: HRV — "HRV: 25 ms ↓ Low"
  hrv_ms                        INTEGER      CHECK (hrv_ms IS NULL OR (hrv_ms BETWEEN 0 AND 300)),

  -- Screen 3: Sleep — "Sleep: 5h 30m Poor Sleep"
  sleep_hours                   DECIMAL(4,1) CHECK (sleep_hours IS NULL OR (sleep_hours BETWEEN 0 AND 24)),

  -- Screen 3: Sleep latency — minutes to fall asleep
  sleep_latency_minutes         INTEGER      CHECK (sleep_latency_minutes IS NULL OR (sleep_latency_minutes BETWEEN 0 AND 120)),

  -- Screen 1: Sleep quality rating bar (1–5)
  sleep_quality_rating          INTEGER      CHECK (sleep_quality_rating IS NULL OR (sleep_quality_rating BETWEEN 1 AND 5)),

  -- Screen 3: Steps — "8,450 today"
  steps_today                   INTEGER      CHECK (steps_today IS NULL OR (steps_today BETWEEN 0 AND 100000)),

  -- Screen 4: SpO₂ — "92%"
  spo2_pct                      INTEGER      CHECK (spo2_pct IS NULL OR (spo2_pct BETWEEN 70 AND 100)),

  -- Screen 4: Restlessness — "Restlessness Level High"
  restlessness_level            VARCHAR(10)  CHECK (restlessness_level IS NULL OR restlessness_level IN ('Low','Moderate','High')),

  -- Screen 4: Stress level from device — "Stress Level High"
  stress_level_device           VARCHAR(10)  CHECK (stress_level_device IS NULL OR stress_level_device IN ('Low','Moderate','High','Severe')),

  -- Screen 2: Stress self-report from emoji grid — "Log Your Stress"
  stress_self_report            VARCHAR(20),   -- Calm, Moderate, Severe, High

  -- Activity patterns bar chart (Screen 3 bottom)
  active_minutes                INTEGER      CHECK (active_minutes IS NULL OR (active_minutes BETWEEN 0 AND 1440)),

  -- 7-day rolling averages — HRV trend chart visible in Screen 4
  resting_hr_7day_avg           INTEGER,
  hrv_7day_avg                  INTEGER,
  steps_7day_avg                INTEGER,
  sleep_hours_7day_avg          DECIMAL(4,1),

  -- Derived composite scores (computed by Wearable Processor Model 4)
  -- Cross-validates daily_checkins.sleep_quality and stress_score
  sleep_quality_derived         INTEGER      CHECK (sleep_quality_derived IS NULL OR (sleep_quality_derived BETWEEN 1 AND 5)),
  physiological_stress_score    DECIMAL(4,3) CHECK (physiological_stress_score IS NULL OR (physiological_stress_score BETWEEN 0 AND 1)),
  arousal_proxy_score           DECIMAL(4,3) CHECK (arousal_proxy_score IS NULL OR (arousal_proxy_score BETWEEN 0 AND 1)),

  -- Personal anomaly detection (reading outside patient's own normal range)
  personal_anomaly_flag         BOOLEAN      DEFAULT false,
  personal_anomaly_detail       TEXT,          -- e.g. "HRV 18ms vs personal avg 52ms"

  -- Data quality
  wear_hours_today              DECIMAL(4,1),
  data_quality                  VARCHAR(10)  DEFAULT 'good'
    CHECK (data_quality IN ('good','partial','poor')),

  -- Audit
  created_at                    TIMESTAMP   DEFAULT now(),
  updated_at                    TIMESTAMP   DEFAULT now(),

  CONSTRAINT wearable_unique_daily UNIQUE (patient_id, reading_date),
  CONSTRAINT wearable_patient_fk   FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

CREATE INDEX idx_wearable_patient_date   ON wearable_readings(patient_id, reading_date DESC);
CREATE INDEX idx_wearable_anomaly        ON wearable_readings(patient_id, personal_anomaly_flag) WHERE personal_anomaly_flag = true;
CREATE INDEX idx_wearable_poor_quality   ON wearable_readings(patient_id, data_quality) WHERE data_quality = 'poor';
CREATE INDEX idx_wearable_low_hrv        ON wearable_readings(patient_id, hrv_ms) WHERE hrv_ms IS NOT NULL AND hrv_ms < 20;
CREATE INDEX idx_wearable_high_stress    ON wearable_readings(patient_id, physiological_stress_score) WHERE physiological_stress_score > 0.7;


-- ============================================================================
-- VIEWS
-- ============================================================================

-- Latest daily check-in per patient — includes all new columns
CREATE VIEW latest_checkins AS
SELECT DISTINCT ON (patient_id)
  patient_id,
  checkin_id,
  checkin_date,
  todays_mood,
  stress_score,
  sleep_quality,
  sleep_hours,
  rest_level,
  craving_intensity,
  medication_taken,
  trigger_exposure_flag,
  triggers_today,
  trigger_intensity,
  recovery_activity_today,
  recovery_social_support,
  social_contact,
  addiction_specific_data,
  negative_affect,
  high_life_stress,
  exercise_done,
  self_care_activities,
  checkin_risk_score,
  checkin_completed_via,
  missed_checkin_days,
  created_at
FROM daily_checkins
ORDER BY patient_id, checkin_date DESC;


-- Patient snapshot for admin dashboard
CREATE VIEW patient_snapshot AS
SELECT
  p.patient_id,
  p.patient_code,
  p.first_name,
  p.is_active,
  p.last_active_at,
  s.session_id,
  s.started_at          AS last_session_start,
  s.session_type        AS last_session_type,
  r.live_risk_score,
  r.risk_level,
  r.risk_score_delta,
  r.risk_trend_7day,
  r.ai_confidence_score,
  lc.todays_mood,
  lc.stress_score,
  lc.sleep_quality,
  lc.craving_intensity,
  lc.trigger_exposure_flag,
  lc.missed_checkin_days
FROM patients p
LEFT JOIN sessions s ON p.patient_id = s.patient_id
  AND s.started_at = (SELECT MAX(started_at) FROM sessions WHERE patient_id = p.patient_id)
LEFT JOIN risk_assessments r ON s.session_id = r.session_id
  AND r.computed_at = (SELECT MAX(computed_at) FROM risk_assessments WHERE patient_id = p.patient_id)
LEFT JOIN latest_checkins lc ON p.patient_id = lc.patient_id;


-- Open crisis events requiring follow-up
CREATE VIEW open_crisis_events AS
SELECT
  e.*,
  p.first_name,
  p.patient_code
FROM crisis_events e
JOIN patients p ON e.patient_id = p.patient_id
WHERE e.followup_completed = false
ORDER BY e.created_at DESC;


-- Patient context vector — full data object assembled before patient types a word
-- Used by chatbot_engine.py at session start; now includes all 3 data streams
CREATE VIEW patient_context_vector AS
SELECT
  p.patient_id,
  p.patient_code,
  p.first_name                          AS patient_name,
  p.preferred_language,
  p.timezone,

  -- From onboarding
  o.addiction_type,
  o.baseline_mood,
  o.primary_triggers,
  o.trauma_history,
  o.suicide_attempt_history,
  o.cognitive_impairment,
  o.family_member_uses,
  o.drug_using_peers,
  o.uses_substance_for_sleep,
  o.high_impulsivity,
  o.avoidant_coping,
  o.low_self_efficacy,
  o.low_motivation,
  o.emotion_regulation_difficulty,
  o.cue_reactivity,
  o.insomnia,
  o.mutual_help_group,
  o.support_network,
  o.sleep_quality_baseline,
  o.craving_frequency_baseline,
  o.medication_adherence_baseline,

  -- From latest daily check-in
  lc.checkin_date,
  lc.todays_mood,
  lc.stress_score,
  lc.sleep_quality,
  lc.rest_level,
  lc.sleep_hours,
  lc.craving_intensity,
  lc.medication_taken,
  lc.trigger_exposure_flag,
  lc.recovery_activity_today,
  lc.recovery_social_support,
  lc.addiction_specific_data,
  lc.negative_affect,
  lc.high_life_stress,
  lc.missed_checkin_days,

  -- From latest risk assessment
  r.live_risk_score,
  r.risk_level,
  r.risk_score_delta,
  r.risk_trend_7day,
  r.key_risk_drivers,
  r.crisis_flag,
  r.ai_confidence_score,
  r.tone_applied                        AS last_tone_applied,

  -- From latest wearable reading
  w.reading_date                        AS wearable_date,
  w.hr_bpm,
  w.hrv_ms,
  w.spo2_pct,
  w.steps_today,
  w.restlessness_level,
  w.sleep_hours                         AS wearable_sleep_hours,
  w.sleep_quality_derived               AS wearable_sleep_quality,
  w.physiological_stress_score,
  w.arousal_proxy_score,
  w.personal_anomaly_flag,
  w.stress_level_device,

  -- From content engagement (last video shown)
  ce.content_title                      AS last_video_title,
  ce.content_id                         AS last_video_id,
  ce.completion_pct                     AS last_video_completion,
  ce.shown_at                           AS last_video_shown_at,
  ce.skipped                            AS last_video_skipped

FROM patients p
LEFT JOIN onboarding_profiles o   ON p.patient_id = o.patient_id
LEFT JOIN latest_checkins lc      ON p.patient_id = lc.patient_id
LEFT JOIN LATERAL (
  SELECT * FROM risk_assessments
  WHERE patient_id = p.patient_id
  ORDER BY computed_at DESC LIMIT 1
) r ON true
LEFT JOIN LATERAL (
  SELECT * FROM wearable_readings
  WHERE patient_id = p.patient_id
  ORDER BY reading_date DESC LIMIT 1
) w ON true
LEFT JOIN LATERAL (
  SELECT * FROM content_engagement
  WHERE patient_id = p.patient_id
  ORDER BY shown_at DESC LIMIT 1
) ce ON true;


-- 7-day risk trend per patient — feeds Risk Trend Over Time chart in the app
CREATE VIEW risk_trend_7day AS
SELECT
  ra.patient_id,
  DATE(ra.computed_at)             AS risk_date,
  AVG(ra.live_risk_score)::INTEGER AS avg_risk_score,
  MAX(ra.live_risk_score)          AS peak_risk_score,
  BOOL_OR(ra.crisis_flag)          AS had_crisis
FROM risk_assessments ra
WHERE ra.computed_at >= NOW() - INTERVAL '7 days'
GROUP BY ra.patient_id, DATE(ra.computed_at)
ORDER BY ra.patient_id, risk_date DESC;


-- ============================================================================
-- 16. PATIENT_ADDICTIONS  [ADDED]
--
-- Each patient may have 1..N addiction types.
-- Replaces the single onboarding_profiles.addiction_type text column for
-- clinical cases where a patient presents with comorbid addictions.
-- The original column is retained for backward compatibility (mobile app) but
-- this table is the authoritative multi-addiction source for the chatbot.
--
-- is_primary = TRUE  → patient's declared main addiction
-- is_primary = FALSE → known comorbid addiction (treated as higher risk than
--                      a novel cross-craving because the brain pathway is
--                      already established).
--
-- Chatbot behaviour:
--   PRIMARY craving   → standard recovery craving response
--   COMORBIDITY craving (is_primary=FALSE here) → escalated dual-addiction response
--   NOVEL cross-craving (not in this table at all) → awareness / moderate response
-- ============================================================================

CREATE TABLE patient_addictions (
  addiction_id    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id      UUID        NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  patient_code    VARCHAR(20) NOT NULL,   -- denormalised for fast chatbot lookup without join

  addiction_type  TEXT        NOT NULL
    CHECK (addiction_type IN (
      'alcohol','drugs','gaming','social_media','nicotine','smoking','gambling','work'
    )),

  is_primary      BOOLEAN     NOT NULL DEFAULT FALSE,

  -- Clinical severity of this specific addiction (may differ per addiction)
  severity        TEXT        NOT NULL DEFAULT 'high'
    CHECK (severity IN ('critical','high','medium','low')),

  -- Approximate date clinician recorded this addiction (may be NULL for historical data)
  noted_at        DATE,

  -- Free-text space for clinician audit notes about this addiction
  clinical_notes  TEXT,

  -- Soft-delete — set to FALSE rather than DELETE when patient enters full remission
  is_active       BOOLEAN     DEFAULT TRUE,

  created_at      TIMESTAMP   DEFAULT now(),
  updated_at      TIMESTAMP   DEFAULT now(),

  UNIQUE (patient_id, addiction_type)
);

-- Enforce exactly one primary addiction per active patient
CREATE UNIQUE INDEX idx_patient_addictions_one_primary
  ON patient_addictions (patient_id)
  WHERE is_primary = TRUE AND is_active = TRUE;

CREATE INDEX idx_patient_addictions_code   ON patient_addictions(patient_code);
CREATE INDEX idx_patient_addictions_type   ON patient_addictions(addiction_type);
CREATE INDEX idx_patient_addictions_active ON patient_addictions(patient_id) WHERE is_active = TRUE;


-- ============================================================================
-- 17. RESPONSE_ROUTING  [ADDED]  — Phase 2: DB-driven routing matrix
--
-- Maps (patient_addiction × detected_intent) → chatbot routing strategy.
-- Clinicians can update routing rules here without a code deployment.
--
-- relationship values:
--   primary           — intent is the patient's own primary addiction craving
--   comorbidity       — intent matches a known secondary addiction (high risk)
--   cross_high        — novel cross-craving, clinically high risk (e.g. gaming→drugs)
--   cross_medium      — novel cross-craving, moderate risk (e.g. alcohol→gaming)
--   sleep             — sleep-related intent
--   mood              — emotional mood intent
--   trigger           — environmental/life trigger intent
--   behaviour         — eating/exercise behaviour intent
--   distress          — severe distress intent
--   relapse           — relapse disclosure intent (non-judgmental, no-directive route)
--
-- Precedence: DB row > code fallback.
-- If no row exists for a (patient_addiction, detected_intent) pair, the
-- code-based logic in _get_addiction_aware_base() acts as the fallback.
-- ============================================================================

CREATE TABLE response_routing (
  routing_id          UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_addiction   TEXT    NOT NULL,   -- 'alcohol', 'gaming', etc.
  detected_intent     TEXT    NOT NULL,   -- 'mood_sad', 'addiction_drugs', 'trigger_stress', etc.

  relationship        TEXT    NOT NULL
    CHECK (relationship IN (
      'primary','comorbidity','cross_high','cross_medium',
      'sleep','mood','trigger','behaviour','distress','relapse'
    )),

  -- NULL = inherit from intent's default severity in the code
  severity_override   TEXT    CHECK (severity_override IN ('critical','high','medium','low')),

  -- NULL = use code-default video selection logic
  video_key           TEXT,

  -- TRUE = immediately flag in conversation_metrics for clinician review
  requires_escalation BOOLEAN DEFAULT FALSE,

  -- Informational note for clinicians editing this table
  clinical_note       TEXT,

  is_active           BOOLEAN DEFAULT TRUE,
  created_at          TIMESTAMP DEFAULT now(),
  updated_at          TIMESTAMP DEFAULT now(),

  UNIQUE (patient_addiction, detected_intent)
);

CREATE INDEX idx_response_routing_pair   ON response_routing(patient_addiction, detected_intent) WHERE is_active = TRUE;
CREATE INDEX idx_response_routing_escalate ON response_routing(patient_addiction) WHERE requires_escalation = TRUE;

-- ── Seed data: encode the current hardcoded routing logic into DB rows ──────
-- PRIMARY cravings (patient craves their own addiction)
INSERT INTO response_routing (patient_addiction, detected_intent, relationship, severity_override, video_key, requires_escalation, clinical_note) VALUES
  ('alcohol',      'addiction_drugs',        'primary',      'high',   'addiction_alcohol',      false, 'Alcohol patient craving alcohol/substances — primary craving response'),
  ('drugs',        'addiction_drugs',        'primary',      'high',   'addiction_drugs',        false, 'Drug patient craving substances — primary craving response'),
  ('gaming',       'addiction_gaming',       'primary',      'high',   'addiction_gaming',       false, 'Gaming patient craving gaming — primary craving response'),
  ('social_media', 'addiction_social_media', 'primary',      'medium', 'addiction_social_media', false, 'Social media patient craving social media — primary response'),
  ('nicotine',     'addiction_nicotine',     'primary',      'high',   'addiction_nicotine',     false, 'Nicotine patient craving nicotine — primary craving response'),
  ('smoking',      'addiction_nicotine',     'primary',      'high',   'addiction_nicotine',     false, 'Smoking patient craving nicotine — primary craving response'),
  ('gambling',     'addiction_gambling',     'primary',      'high',   'addiction_gambling',     false, 'Gambling patient craving gambling — primary craving response'),
  -- CROSS-ADDICTION: behavioural addict craving alcohol/drugs (HIGH risk — substance onset)
  ('gaming',       'addiction_drugs',        'cross_high',   'high',   'addiction_drugs',        true,  'Gaming patient craving alcohol/drugs — high risk cross-addiction: clinician review'),
  ('social_media', 'addiction_drugs',        'cross_high',   'high',   'addiction_drugs',        true,  'Social media patient craving alcohol/drugs — high risk cross-addiction'),
  ('gambling',     'addiction_drugs',        'cross_high',   'high',   'addiction_drugs',        true,  'Gambling patient craving alcohol/drugs — high risk cross-addiction'),
  ('nicotine',     'addiction_drugs',        'cross_high',   'high',   'addiction_drugs',        false, 'Nicotine patient craving alcohol/drugs — elevated cross-craving risk'),
  -- CROSS-ADDICTION: substance patient craving gambling (HIGH risk — shared impulsivity)
  ('alcohol',      'addiction_gambling',     'cross_high',   'high',   'addiction_gambling',     true,  'Alcohol patient craving gambling — high risk: impulsivity pathways overlap'),
  ('drugs',        'addiction_gambling',     'cross_high',   'high',   'addiction_gambling',     true,  'Drug patient craving gambling — high risk: impulsivity pathways overlap'),
  -- CROSS-ADDICTION: substance patient craving behavioural (MEDIUM risk)
  ('alcohol',      'addiction_gaming',       'cross_medium', 'medium', 'addiction_gaming',       false, 'Alcohol patient craving gaming — moderate cross-craving; monitor for compulsion'),
  ('alcohol',      'addiction_social_media', 'cross_medium', 'medium', 'addiction_social_media', false, 'Alcohol patient craving social media — moderate cross-craving'),
  ('alcohol',      'addiction_nicotine',     'cross_medium', 'medium', 'addiction_nicotine',     false, 'Alcohol patient craving nicotine — moderate cross-craving'),
  ('drugs',        'addiction_gaming',       'cross_medium', 'medium', 'addiction_gaming',       false, 'Drug patient craving gaming — moderate cross-craving'),
  ('drugs',        'addiction_social_media', 'cross_medium', 'medium', 'addiction_social_media', false, 'Drug patient craving social media — moderate cross-craving'),
  ('drugs',        'addiction_nicotine',     'cross_medium', 'medium', 'addiction_nicotine',     false, 'Drug patient craving nicotine — moderate cross-craving'),
  -- CROSS-ADDICTION: gambling ↔ gaming (MEDIUM risk)
  ('gambling',     'addiction_gaming',       'cross_medium', 'medium', 'addiction_gaming',       false, 'Gambling patient craving gaming — moderate; watch for dopamine substitution'),
  ('gaming',       'addiction_gambling',     'cross_medium', 'medium', 'addiction_gambling',     false, 'Gaming patient craving gambling — moderate; watch for escalation to financial risk'),
  -- CROSS-ADDICTION: nicotine ↔ others (cross-craving awareness level)
  ('nicotine',     'addiction_gaming',       'cross_medium', 'medium', 'addiction_gaming',       false, 'Nicotine patient craving gaming — cross-craving awareness'),
  ('nicotine',     'addiction_social_media', 'cross_medium', 'medium', 'addiction_social_media', false, 'Nicotine patient craving social media — cross-craving awareness'),
  ('nicotine',     'addiction_gambling',     'cross_medium', 'medium', 'addiction_gambling',     false, 'Nicotine patient craving gambling — cross-craving awareness'),
  -- SLEEP
  ('alcohol',      'behaviour_sleep', 'sleep', 'medium', NULL, false, 'Alcohol patient reporting sleep problems'),
  ('drugs',        'behaviour_sleep', 'sleep', 'medium', NULL, false, 'Drug patient reporting sleep problems (PAWS common)'),
  ('gaming',       'behaviour_sleep', 'sleep', 'medium', NULL, false, 'Gaming patient reporting sleep problems (screen/cortisol)'),
  ('social_media', 'behaviour_sleep', 'sleep', 'medium', NULL, false, 'Social media patient reporting sleep problems'),
  ('nicotine',     'behaviour_sleep', 'sleep', 'medium', NULL, false, 'Nicotine patient reporting sleep problems (stimulant)'),
  ('smoking',      'behaviour_sleep', 'sleep', 'medium', NULL, false, 'Smoking patient reporting sleep problems'),
  ('gambling',     'behaviour_sleep', 'sleep', 'medium', NULL, false, 'Gambling patient reporting sleep problems (rumination/financial stress)'),
  -- RELAPSE DISCLOSURE (distinct from active craving)
  ('alcohol',      'relapse_disclosure', 'relapse', 'medium', NULL, false, 'Alcohol relapse disclosure: normalise slip, avoid judgment/advice'),
  ('drugs',        'relapse_disclosure', 'relapse', 'medium', NULL, false, 'Drug relapse disclosure: normalise slip, avoid judgment/advice'),
  ('gaming',       'relapse_disclosure', 'relapse', 'medium', NULL, false, 'Gaming relapse disclosure: normalise slip, avoid judgment/advice'),
  ('social_media', 'relapse_disclosure', 'relapse', 'medium', NULL, false, 'Social media relapse disclosure: normalise slip, avoid judgment/advice'),
  ('nicotine',     'relapse_disclosure', 'relapse', 'medium', NULL, false, 'Nicotine relapse disclosure: normalise slip, avoid judgment/advice'),
  ('smoking',      'relapse_disclosure', 'relapse', 'medium', NULL, false, 'Smoking relapse disclosure: normalise slip, avoid judgment/advice'),
  ('gambling',     'relapse_disclosure', 'relapse', 'medium', NULL, false, 'Gambling relapse disclosure: normalise slip, avoid judgment/advice');


-- ============================================================================
-- 18. PATIENT_CONTEXT_VECTORS
-- Audit trail of synthesized context vectors for every greeting shown.
-- Not a source of truth — clinical data lives in daily_checkins,
-- wearable_readings, and sessions. This is a SNAPSHOT of synthesis
-- at greeting time for clinical review, debugging, and analytics.
-- ============================================================================

CREATE TABLE IF NOT EXISTS patient_context_vectors (
  vector_id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

  patient_id                   UUID        NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  patient_code                 VARCHAR(20),
  session_id                   TEXT,

  -- Data source availability at time of synthesis
  has_subjective_data          BOOLEAN     DEFAULT false,
  has_physiological_data       BOOLEAN     DEFAULT false,
  has_historical_data          BOOLEAN     DEFAULT false,

  -- Synthesis results
  dominant_theme               VARCHAR(100),  -- e.g. "emotional_distress:stressed", "high_craving:8"
  emotional_anchor             VARCHAR(100),  -- e.g. "feeling stressed and overwhelmed"
  tone_directive               VARCHAR(50),   -- calm_grounding, validating, celebratory, curious, crisis_safe

  -- Risk scores (1–100)
  subjective_risk_score        INTEGER     CHECK (subjective_risk_score BETWEEN 1 AND 100),
  objective_risk_score         INTEGER     CHECK (objective_risk_score BETWEEN 1 AND 100),
  clinical_risk_score          INTEGER     CHECK (clinical_risk_score BETWEEN 1 AND 100),  -- 70% subj + 30% obj

  -- Contradiction detection
  contradiction_detected       BOOLEAN     DEFAULT false,
  contradiction_type           VARCHAR(100),  -- e.g. "patient_felt_rested_but_objectively_poor"

  -- Data freshness
  subjective_hours_ago         DECIMAL(5,1),
  physiological_hours_ago      DECIMAL(5,1),
  subjective_timestamp         TIMESTAMP,
  physiological_timestamp      TIMESTAMP,

  -- Greeting output
  greeting_text                TEXT,
  contextual_opening           TEXT,   -- Layer 1: Never generic "how are you?"
  validation_note              TEXT,   -- Layer 2: Normalize the struggle
  agency_note                  TEXT,   -- Layer 3: Invite, don't interrogate

  created_at                   TIMESTAMP   DEFAULT now(),

  CONSTRAINT context_vector_unique UNIQUE (patient_id, created_at)
);

CREATE INDEX idx_context_patient_time    ON patient_context_vectors(patient_id, created_at DESC);
CREATE INDEX idx_context_high_risk       ON patient_context_vectors(patient_code, clinical_risk_score DESC) WHERE clinical_risk_score > 60;
CREATE INDEX idx_context_contradictions  ON patient_context_vectors(patient_code, created_at DESC) WHERE contradiction_detected = true;
CREATE INDEX idx_context_tone            ON patient_context_vectors(patient_code, tone_directive, created_at DESC);
CREATE INDEX idx_context_theme           ON patient_context_vectors(patient_code, dominant_theme, created_at DESC);
CREATE INDEX idx_context_time_range      ON patient_context_vectors(patient_code, created_at DESC);
  ('work',         'relapse_disclosure', 'relapse', 'medium', NULL, false, 'Work-addiction relapse disclosure: normalise slip, avoid judgment/advice');
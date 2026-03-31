-- Mental Health Chatbot — Supabase Database Schema
-- Run this in Supabase SQL Editor: https://app.supabase.com/project/odxtrlhrfivvxojizixw/sql

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- PATIENTS table — Patient registry
CREATE TABLE IF NOT EXISTS patients (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_code TEXT UNIQUE NOT NULL,
  display_name TEXT,
  date_of_birth DATE,
  gender TEXT,
  programme TEXT,
  assigned_clinician TEXT,
  referral_source TEXT,
  assigned_to TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- SESSIONS table — One per browser/app session
CREATE TABLE IF NOT EXISTS sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id TEXT UNIQUE NOT NULL,
  patient_id UUID REFERENCES patients(id) ON DELETE CASCADE,
  patient_code TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- CONVERSATIONS table — Every message exchanged
CREATE TABLE IF NOT EXISTS conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  patient_id UUID REFERENCES patients(id) ON DELETE CASCADE,
  patient_code TEXT,
  role TEXT NOT NULL,
  message TEXT NOT NULL,
  intent TEXT,
  severity TEXT,
  show_resources BOOLEAN DEFAULT FALSE,
  timestamp TIMESTAMP DEFAULT NOW()
);

-- POLICY_VIOLATIONS table — Audit log for ethical AI policy breaches
CREATE TABLE IF NOT EXISTS policy_violations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id TEXT NOT NULL,
  patient_id UUID REFERENCES patients(id) ON DELETE CASCADE,
  violation_type TEXT NOT NULL,
  details TEXT,
  user_message TEXT,
  bot_response TEXT,
  timestamp TIMESTAMP DEFAULT NOW()
);

-- CRISIS_EVENTS table — High-priority log for crisis interactions
CREATE TABLE IF NOT EXISTS crisis_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id TEXT NOT NULL,
  patient_id UUID REFERENCES patients(id) ON DELETE CASCADE,
  patient_code TEXT,
  severity TEXT NOT NULL,
  user_message TEXT,
  bot_response TEXT,
  intent TEXT,
  acknowledged BOOLEAN DEFAULT FALSE,
  timestamp TIMESTAMP DEFAULT NOW()
);

-- SCORES table — Patient QoL scores
CREATE TABLE IF NOT EXISTS scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id TEXT NOT NULL,
  patient_id UUID REFERENCES patients(id) ON DELETE CASCADE,
  patient_code TEXT,
  score_group TEXT NOT NULL,
  score INT CHECK (score >= 0 AND score <= 10),
  intent TEXT,
  timestamp TIMESTAMP DEFAULT NOW()
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_patients_patient_code ON patients(patient_code);
CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_patient_id ON sessions(patient_id);
CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_patient_id ON conversations(patient_id);
CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp);
CREATE INDEX IF NOT EXISTS idx_crisis_events_patient_id ON crisis_events(patient_id);
CREATE INDEX IF NOT EXISTS idx_crisis_events_timestamp ON crisis_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_scores_patient_id ON scores(patient_id);

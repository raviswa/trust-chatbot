#!/usr/bin/env python3
"""
Load Sample Data into Supabase
===============================

Creates realistic test patients and data for the chatbot.

Run with: python load_sample_data.py
"""

import os
import json
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
import logging

# Load environment
dotenv_path = os.path.join(os.path.dirname(__file__), ".env.local")
load_dotenv(dotenv_path)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY required")

client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Sample patient data
SAMPLE_PATIENTS = [
    {
        "patient_code": "PAT-001",
        "first_name": "Arjun",
        "last_name": "Kumar",
        "email": "arjun@example.com",
        "phone": "+44 7700 900001",
        "date_of_birth": "1988-04-12",
        "gender": "Male",
        "country": "UK",
        "profile": {
            "addiction_type": "Alcohol",
            "baseline_mood": ["stressed", "guilty"],
            "primary_triggers": ["work stress", "social situations"],
            "support_network": {"sponsor": "Michael", "therapist": "Dr. Smith", "family": "Sister"},
            "work_status": "employed",
            "housing_status": "stable",
            "diagnosed_conditions": ["depression", "anxiety"],
            "current_medications": ["Sertraline 50mg"],
            "previous_treatment": True,
            "previous_treatment_notes": "Attended 12-week rehab, 2020",
            "communication_preference": "text",
            "content_preferences": ["short-form", "narrative"],
        }
    },
    {
        "patient_code": "PAT-002",
        "first_name": "Priya",
        "last_name": "Patel",
        "email": "priya@example.com",
        "phone": "+44 7700 900002",
        "date_of_birth": "1995-09-23",
        "gender": "Female",
        "country": "UK",
        "profile": {
            "addiction_type": "Cannabis",
            "baseline_mood": ["anxious", "isolated"],
            "primary_triggers": ["peer pressure", "boredom"],
            "support_network": {"therapist": "Dr. Patel", "family": "Parents"},
            "work_status": "student",
            "housing_status": "transitional",
            "diagnosed_conditions": ["anxiety"],
            "current_medications": ["Propranolol"],
            "previous_treatment": False,
            "previous_treatment_notes": None,
            "communication_preference": "text",
            "content_preferences": ["interactive"],
        }
    },
    {
        "patient_code": "PAT-003",
        "first_name": "Karthik",
        "last_name": "Singh",
        "email": "karthik@example.com",
        "phone": "+44 7700 900003",
        "date_of_birth": "2001-01-30",
        "gender": "Male",
        "country": "UK",
        "profile": {
            "addiction_type": "Gaming",
            "baseline_mood": ["angry", "frustrated"],
            "primary_triggers": ["gaming urges", "sleep deprivation"],
            "support_network": {"therapist": "Dr. Lewis", "family": "Brother"},
            "work_status": "unemployed",
            "housing_status": "stable",
            "diagnosed_conditions": [],
            "current_medications": [],
            "previous_treatment": False,
            "previous_treatment_notes": None,
            "communication_preference": "text",
            "content_preferences": ["short-form"],
        }
    },
    {
        "patient_code": "PAT-004",
        "first_name": "Divya",
        "last_name": "Sharma",
        "email": "divya@example.com",
        "phone": "+44 7700 900004",
        "date_of_birth": "1990-03-18",
        "gender": "Female",
        "country": "UK",
        "profile": {
            "addiction_type": "Trauma & Anxiety",
            "baseline_mood": ["anxious", "fearful"],
            "primary_triggers": ["trauma reminders", "crowded places", "sudden sounds"],
            "support_network": {"therapist": "Dr. Ramani", "family": "Sister"},
            "work_status": "employed",
            "housing_status": "stable",
            "diagnosed_conditions": ["PTSD", "anxiety", "depression"],
            "current_medications": ["Sertraline 100mg", "Prazosin 2mg"],
            "previous_treatment": True,
            "previous_treatment_notes": "Trauma-focused CBT 2021-2022",
            "communication_preference": "text",
            "content_preferences": ["narrative", "short-form"],
        }
    },
    {
        "patient_code": "PAT-005",
        "first_name": "Rajesh",
        "last_name": "Nair",
        "email": "rajesh@example.com",
        "phone": "+44 7700 900005",
        "date_of_birth": "1980-06-22",
        "gender": "Male",
        "country": "UK",
        "profile": {
            "addiction_type": "Nicotine",
            "baseline_mood": ["frustrated", "determined"],
            "primary_triggers": ["work stress", "coffee", "after meals"],
            "support_network": {"family": "Wife", "gp": "Dr. Harrison"},
            "work_status": "employed",
            "housing_status": "stable",
            "diagnosed_conditions": [],
            "current_medications": ["Nicotine patch 21mg"],
            "previous_treatment": False,
            "previous_treatment_notes": None,
            "communication_preference": "text",
            "content_preferences": ["short-form"],
        }
    },
    {
        "patient_code": "PAT-006",
        "first_name": "Ananya",
        "last_name": "Reddy",
        "email": "ananya@example.com",
        "phone": "+44 7700 900006",
        "date_of_birth": "2001-11-14",
        "gender": "Female",
        "country": "UK",
        "profile": {
            "addiction_type": "Digital Addiction",
            "baseline_mood": ["anxious", "restless", "lonely"],
            "primary_triggers": ["FOMO", "boredom", "loneliness"],
            "support_network": {"counsellor": "Ms. Reddy", "family": "Parents"},
            "work_status": "student",
            "housing_status": "stable",
            "diagnosed_conditions": ["social anxiety disorder"],
            "current_medications": [],
            "previous_treatment": False,
            "previous_treatment_notes": None,
            "communication_preference": "text",
            "content_preferences": ["interactive", "short-form"],
        }
    },
    {
        "patient_code": "PAT-007",
        "first_name": "Suresh",
        "last_name": "Menon",
        "email": "suresh@example.com",
        "phone": "+44 7700 900007",
        "date_of_birth": "1968-08-09",
        "gender": "Male",
        "country": "UK",
        "profile": {
            "addiction_type": "Grief Support",
            "baseline_mood": ["sad", "withdrawn", "hopeless"],
            "primary_triggers": ["anniversaries", "familiar places", "weekends"],
            "support_network": {"gp": "Dr. Chen", "family": "Adult children"},
            "work_status": "retired",
            "housing_status": "stable",
            "diagnosed_conditions": ["prolonged grief disorder", "depression"],
            "current_medications": ["Mirtazapine 15mg"],
            "previous_treatment": True,
            "previous_treatment_notes": "Bereavement counselling started 2024",
            "communication_preference": "text",
            "content_preferences": ["narrative"],
        }
    },
    {
        "patient_code": "PAT-008",
        "first_name": "Lakshmi",
        "last_name": "Iyer",
        "email": "lakshmi@example.com",
        "phone": "+44 7700 900008",
        "date_of_birth": "1975-05-30",
        "gender": "Female",
        "country": "UK",
        "profile": {
            "addiction_type": "Alcohol",
            "baseline_mood": ["hopeless", "ashamed", "volatile"],
            "primary_triggers": ["family conflict", "chronic pain", "loneliness"],
            "support_network": {"therapist": "Dr. Nair", "sponsor": "Mary (AA)"},
            "work_status": "unemployed",
            "housing_status": "unstable",
            "diagnosed_conditions": ["severe alcohol use disorder", "depression", "chronic pain"],
            "current_medications": ["Acamprosate 333mg", "Mirtazapine 30mg"],
            "previous_treatment": True,
            "previous_treatment_notes": "Residential detox 2021, relapsed 2022; detox again 2023",
            "communication_preference": "text",
            "content_preferences": ["narrative"],
        }
    },
    {
        "patient_code": "PAT-009",
        "first_name": "Vikram",
        "last_name": "Shah",
        "email": "vikram@example.com",
        "phone": "+44 7700 900009",
        "date_of_birth": "1993-10-17",
        "gender": "Male",
        "country": "UK",
        "profile": {
            "addiction_type": "Behavioural Addiction",
            "baseline_mood": ["impulsive", "restless"],
            "primary_triggers": ["sports events", "financial stress", "boredom"],
            "support_network": {"counsellor": "Mr. Shah", "family": "Fiancée"},
            "work_status": "employed",
            "housing_status": "stable",
            "diagnosed_conditions": ["gambling disorder"],
            "current_medications": [],
            "previous_treatment": False,
            "previous_treatment_notes": None,
            "communication_preference": "text",
            "content_preferences": ["interactive", "short-form"],
        }
    },
    {
        "patient_code": "PAT-010",
        "first_name": "Meera",
        "last_name": "Pillai",
        "email": "meera@example.com",
        "phone": "+44 7700 900010",
        "date_of_birth": "1997-02-11",
        "gender": "Female",
        "country": "UK",
        "profile": {
            "addiction_type": "Cannabis",
            "baseline_mood": ["hopeful", "cautious"],
            "primary_triggers": ["old peer groups", "stress"],
            "support_network": {"therapist": "Dr. Iyer", "family": "Parents"},
            "work_status": "employed",
            "housing_status": "stable",
            "diagnosed_conditions": ["cannabis use disorder (in remission)"],
            "current_medications": [],
            "previous_treatment": True,
            "previous_treatment_notes": "Completed outpatient cannabis programme 2024, successfully discharged",
            "communication_preference": "text",
            "content_preferences": ["short-form", "narrative"],
        }
    },
]

def insert_todays_checkins(patient_map):
    """Insert today's check-in for all 10 patients with clinically meaningful data."""
    print("\n" + "="*60)
    print("LOADING TODAY'S CHECK-INS")
    print("="*60)

    # Each entry mirrors the patient's profile for realistic contextual greetings
    TODAY_CHECKINS = {
        "PAT-001": {  # Arjun — Alcohol, baseline: stressed/guilty
            "todays_mood": "Stressed",
            "sleep_quality": 4,
            "sleep_hours": 5.5,
            "craving_intensity": 7,
            "trigger_intensity": 6,
            "medication_taken": True,
            "social_contact": False,
            "exercise_done": False,
            "trigger_exposure_flag": True,
        },
        "PAT-002": {  # Priya — Cannabis, baseline: anxious/isolated
            "todays_mood": "Anxious",
            "sleep_quality": 5,
            "sleep_hours": 6.0,
            "craving_intensity": 5,
            "trigger_intensity": 5,
            "medication_taken": True,
            "social_contact": False,
            "exercise_done": False,
            "trigger_exposure_flag": False,
        },
        "PAT-003": {  # Karthik — Gaming, baseline: angry/frustrated
            "todays_mood": "Angry",
            "sleep_quality": 3,
            "sleep_hours": 4.5,
            "craving_intensity": 6,
            "trigger_intensity": 7,
            "medication_taken": True,
            "social_contact": False,
            "exercise_done": False,
            "trigger_exposure_flag": True,
        },
        "PAT-004": {  # Divya — Trauma & Anxiety, PTSD
            "todays_mood": "Anxious",
            "sleep_quality": 3,
            "sleep_hours": 4.0,
            "craving_intensity": 2,
            "trigger_intensity": 8,
            "medication_taken": True,
            "social_contact": False,
            "exercise_done": False,
            "trigger_exposure_flag": True,
        },
        "PAT-005": {  # Rajesh — Nicotine, stressed/determined
            "todays_mood": "Stressed",
            "sleep_quality": 7,
            "sleep_hours": 7.0,
            "craving_intensity": 8,
            "trigger_intensity": 6,
            "medication_taken": True,
            "social_contact": True,
            "exercise_done": False,
            "trigger_exposure_flag": True,
        },
        "PAT-006": {  # Ananya — Digital Addiction, anxious/restless
            "todays_mood": "Anxious",
            "sleep_quality": 6,
            "sleep_hours": 6.5,
            "craving_intensity": 4,
            "trigger_intensity": 5,
            "medication_taken": True,
            "social_contact": True,
            "exercise_done": True,
            "exercise_duration_minutes": 20,
            "trigger_exposure_flag": False,
        },
        "PAT-007": {  # Suresh — Grief Support, sad/withdrawn
            "todays_mood": "Sad",
            "sleep_quality": 4,
            "sleep_hours": 5.0,
            "craving_intensity": 1,
            "trigger_intensity": 4,
            "medication_taken": True,
            "social_contact": False,
            "exercise_done": False,
            "trigger_exposure_flag": False,
        },
        "PAT-008": {  # Lakshmi — Alcohol (high risk), hopeless/volatile
            "todays_mood": "Overwhelmed",
            "sleep_quality": 2,
            "sleep_hours": 3.5,
            "craving_intensity": 9,
            "trigger_intensity": 9,
            "medication_taken": False,
            "social_contact": False,
            "exercise_done": False,
            "trigger_exposure_flag": True,
        },
        "PAT-009": {  # Vikram — Behavioural (Gambling), impulsive/restless
            "todays_mood": "Stressed",
            "sleep_quality": 5,
            "sleep_hours": 6.0,
            "craving_intensity": 7,
            "trigger_intensity": 7,
            "medication_taken": True,
            "social_contact": True,
            "exercise_done": False,
            "trigger_exposure_flag": True,
        },
        "PAT-010": {  # Meera — Cannabis (discharged), hopeful/cautious
            "todays_mood": "Hopeful",
            "sleep_quality": 8,
            "sleep_hours": 7.5,
            "craving_intensity": 2,
            "trigger_intensity": 2,
            "medication_taken": True,
            "social_contact": True,
            "exercise_done": True,
            "exercise_duration_minutes": 30,
            "trigger_exposure_flag": False,
        },
    }

    today = date.today().isoformat()
    for patient_code, patient_id in patient_map.items():
        checkin_data = TODAY_CHECKINS.get(patient_code, {})
        if not checkin_data:
            continue
        checkin_data["patient_id"] = patient_id
        checkin_data["checkin_date"] = today
        checkin_data["checkin_completed_via"] = "chat"
        try:
            client.table("daily_checkins").insert(checkin_data).execute()
            print(f"✅ {patient_code} — today's check-in ({checkin_data['todays_mood']}, "
                  f"sleep {checkin_data.get('sleep_quality')}/10, "
                  f"cravings {checkin_data.get('craving_intensity')}/10)")
        except Exception as e:
            print(f"⚠️  {patient_code} today's check-in: {str(e)[:80]}")


def insert_todays_wearables(patient_map):
    """Insert today's wearable reading for all 10 patients."""
    print("\n" + "="*60)
    print("LOADING TODAY'S WEARABLE READINGS")
    print("="*60)

    # Wearable data uses correct schema column names
    TODAY_WEARABLES = {
        "PAT-001": {"hr_bpm": 88, "hrv_ms": 18, "sleep_hours": 5.5, "steps_today": 2800, "physiological_stress_score": 0.72, "stress_level_device": "High",    "personal_anomaly_flag": True,  "personal_anomaly_detail": "elevated resting heart rate"},
        "PAT-002": {"hr_bpm": 82, "hrv_ms": 22, "sleep_hours": 6.0, "steps_today": 4200, "physiological_stress_score": 0.61, "stress_level_device": "Moderate", "personal_anomaly_flag": False},
        "PAT-003": {"hr_bpm": 91, "hrv_ms": 15, "sleep_hours": 4.5, "steps_today": 1200, "physiological_stress_score": 0.78, "stress_level_device": "High",    "personal_anomaly_flag": True,  "personal_anomaly_detail": "very low HRV and poor sleep"},
        "PAT-004": {"hr_bpm": 95, "hrv_ms": 12, "sleep_hours": 4.0, "steps_today": 900,  "physiological_stress_score": 0.85, "stress_level_device": "Severe",   "personal_anomaly_flag": True,  "personal_anomaly_detail": "physiological stress markers elevated"},
        "PAT-005": {"hr_bpm": 79, "hrv_ms": 28, "sleep_hours": 7.0, "steps_today": 5500, "physiological_stress_score": 0.55, "stress_level_device": "Moderate", "personal_anomaly_flag": False},
        "PAT-006": {"hr_bpm": 76, "hrv_ms": 30, "sleep_hours": 6.5, "steps_today": 6200, "physiological_stress_score": 0.48, "stress_level_device": "Low",      "personal_anomaly_flag": False},
        "PAT-007": {"hr_bpm": 72, "hrv_ms": 26, "sleep_hours": 5.0, "steps_today": 1800, "physiological_stress_score": 0.52, "stress_level_device": "Moderate", "personal_anomaly_flag": False},
        "PAT-008": {"hr_bpm": 98, "hrv_ms": 10, "sleep_hours": 3.5, "steps_today": 600,  "physiological_stress_score": 0.91, "stress_level_device": "Severe",   "personal_anomaly_flag": True,  "personal_anomaly_detail": "critical — very low HRV, elevated HR"},
        "PAT-009": {"hr_bpm": 84, "hrv_ms": 20, "sleep_hours": 6.0, "steps_today": 3800, "physiological_stress_score": 0.65, "stress_level_device": "Moderate", "personal_anomaly_flag": False},
        "PAT-010": {"hr_bpm": 68, "hrv_ms": 40, "sleep_hours": 7.5, "steps_today": 8200, "physiological_stress_score": 0.28, "stress_level_device": "Low",      "personal_anomaly_flag": False},
    }

    now = datetime.now().isoformat()
    for patient_code, patient_id in patient_map.items():
        wearable = TODAY_WEARABLES.get(patient_code, {})
        if not wearable:
            continue
        wearable["patient_id"] = patient_id
        wearable["reading_date"] = date.today().isoformat()
        try:
            client.table("wearable_readings").insert(wearable).execute()
            print(f"✅ {patient_code} — HR {wearable['hr_bpm']}bpm, "
                  f"HRV {wearable['hrv_ms']}ms, "
                  f"stress {wearable['physiological_stress_score']}, "
                  f"sleep {wearable['sleep_hours']}h")
        except Exception as e:
            print(f"⚠️  {patient_code} wearable: {str(e)[:80]}")



    print("\n" + "="*60)
    print("LOADING SAMPLE PATIENTS")
    print("="*60)
    
    patient_map = {}  # Store patient_id by patient_code
    
    for patient_data in SAMPLE_PATIENTS:
        try:
            profile_data = patient_data.pop("profile")
            
            # Insert patient
            response = client.table("patients").insert(patient_data).execute()
            patient = response.data[0]
            patient_id = patient["patient_id"]
            patient_map[patient_data["patient_code"]] = patient_id
            
            print(f"✅ {patient_data['patient_code']} — {patient_data['first_name']} {patient_data['last_name']}")
            
            # Insert onboarding profile
            profile_data["patient_id"] = patient_id
            profile_data["completed_at"] = datetime.now().isoformat()
            client.table("onboarding_profiles").insert(profile_data).execute()
            
        except Exception as e:
            print(f"❌ {patient_data['patient_code']} — {str(e)[:80]}")
    
    return patient_map


def insert_daily_checkins(patient_map):
    """Insert sample daily checkins."""
    print("\n" + "="*60)
    print("LOADING SAMPLE DAILY CHECKINS")
    print("="*60)
    
    moods = ["Happy", "Neutral", "Sad", "Angry", "Stressed", "Lonely"]
    
    for patient_code, patient_id in list(patient_map.items())[:3]:  # Just first 3
        # Create checkins for last 7 days
        for days_ago in range(7, 0, -1):
            checkin_date = (date.today() - timedelta(days=days_ago)).isoformat()
            
            checkin = {
                "patient_id": patient_id,
                "checkin_date": checkin_date,
                "todays_mood": moods[days_ago % len(moods)],
                "sleep_quality": 5 + (days_ago % 4),
                "sleep_hours": 6.0 + (days_ago % 3),
                "craving_intensity": 3 + (days_ago % 5),
                "medication_taken": True,
                "trigger_intensity": 4 + (days_ago % 4),
                "social_contact": days_ago % 2 == 0,
                "exercise_done": days_ago % 3 == 0,
                "exercise_duration_minutes": 30 if days_ago % 3 == 0 else None,
            }
            
            try:
                client.table("daily_checkins").insert(checkin).execute()
            except Exception as e:
                print(f"⚠️  Checkin for {patient_code} ({checkin_date}): {str(e)[:60]}")
        
        print(f"✅ {patient_code} — 7 days of checkins")


def insert_sessions_and_messages(patient_map):
    """Insert sample sessions and messages."""
    print("\n" + "="*60)
    print("LOADING SAMPLE SESSIONS & MESSAGES")
    print("="*60)
    
    intents = [
        "craving_support",
        "medication_reminder",
        "sleep_support",
        "trigger_management",
        "motivation",
        "emotional_check",
    ]
    
    for patient_code, patient_id in list(patient_map.items())[:2]:  # First 2
        # Create 2 sessions per patient
        for session_num in range(1, 3):
            try:
                session = {
                    "patient_id": patient_id,
                    "patient_code": patient_code,
                    "started_at": (datetime.now() - timedelta(days=7-session_num*3)).isoformat(),
                    "message_count": 4,
                    "last_intent": intents[session_num % len(intents)],
                    "peak_risk_level": ["Low", "Medium", "High"][session_num % 3],
                    "crisis_detected": False,
                }
                
                session_resp = client.table("sessions").insert(session).execute()
                session_id = session_resp.data[0]["session_id"]
                
                # Add 4 messages (2 user, 2 bot)
                messages = [
                    {"role": "user", "content": "I'm feeling really stressed today", "intent": "emotional_check", "severity": "medium"},
                    {"role": "assistant", "content": "I hear you. Tell me more about what's happening.", "response_tone": "warm"},
                    {"role": "user", "content": "Work was overwhelming and I'm craving badly", "intent": "craving_support", "severity": "high"},
                    {"role": "assistant", "content": "Let's work through this together. Have you called your sponsor yet?", "response_tone": "calm"},
                ]
                
                for msg in messages:
                    msg["session_id"] = session_id
                    msg["patient_id"] = patient_id
                    if msg["role"] == "assistant":
                        msg.pop("intent", None)
                    client.table("messages").insert(msg).execute()
                
                print(f"✅ {patient_code} — Session {session_num} with 4 messages")
                
            except Exception as e:
                print(f"⚠️  Session for {patient_code}: {str(e)[:60]}")


def insert_risk_assessments(patient_map):
    """Insert sample risk assessments."""
    print("\n" + "="*60)
    print("LOADING SAMPLE RISK ASSESSMENTS")
    print("="*60)
    
    for patient_code, patient_id in list(patient_map.items())[:3]:
        try:
            risk = {
                "patient_id": patient_id,
                "live_risk_score": 35 + (hash(patient_code) % 40),
                "risk_level": "Medium",
                "key_risk_drivers": ["sleep -20", "cravings +15", "mood -10"],
                "crisis_flag": False,
            }
            
            client.table("risk_assessments").insert(risk).execute()
            print(f"✅ {patient_code} — Risk score {risk['live_risk_score']}")
            
        except Exception as e:
            print(f"⚠️  Risk for {patient_code}: {str(e)[:60]}")


def main():
    print("\n" + "="*60)
    print("SUPABASE SAMPLE DATA LOADER")
    print("="*60)
    
    # 1. Insert patients + profiles
    patient_map = insert_patients()
    
    if not patient_map:
        print("\n❌ No patients inserted. Check your Supabase connection.")
        return
    
    # 2. Insert checkins (7 historical days)
    insert_daily_checkins(patient_map)

    # 3. Insert today's check-ins (contextual greeting data)
    insert_todays_checkins(patient_map)

    # 4. Insert today's wearable readings
    insert_todays_wearables(patient_map)

    # 5. Insert sessions + messages
    insert_sessions_and_messages(patient_map)

    # 6. Insert risk assessments
    insert_risk_assessments(patient_map)

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"✅ Loaded {len(patient_map)} patients")
    print(f"✅ Loaded onboarding profiles")
    print(f"✅ Loaded daily checkins (7 historical days)")
    print(f"✅ Loaded today's check-ins for all 10 patients")
    print(f"✅ Loaded today's wearable readings for all 10 patients")
    print(f"✅ Loaded sample sessions & messages")
    print(f"✅ Loaded risk assessments")
    print("\nYour database is ready for testing!")


if __name__ == "__main__":
    main()

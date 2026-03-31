#!/usr/bin/env python3
"""
Test Supabase Connection
========================

Verifies that the chatbot can successfully connect to Supabase
and access the database schema.

Run with: python test_supabase_connection.py
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables from .env.local
dotenv_path = os.path.join(os.path.dirname(__file__), ".env.local")
load_dotenv(dotenv_path)

# Also try .env as fallback
if not load_dotenv(dotenv_path):
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_connection():
    """Test Supabase connection and schema."""
    
    # 1. Check environment variables
    print("\n" + "="*60)
    print("STEP 1: Checking environment variables")
    print("="*60)
    
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    
    if not SUPABASE_URL:
        print("❌ SUPABASE_URL not found")
        return False
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY not found")
        return False
    
    print(f"✅ SUPABASE_URL: {SUPABASE_URL}")
    print(f"✅ SUPABASE_KEY: {SUPABASE_KEY[:20]}...")
    
    # 2. Import and initialize Supabase client
    print("\n" + "="*60)
    print("STEP 2: Initializing Supabase client")
    print("="*60)
    
    try:
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase client created successfully")
    except Exception as e:
        print(f"❌ Failed to create Supabase client: {e}")
        return False
    
    # 3. Test connection by querying a simple table
    print("\n" + "="*60)
    print("STEP 3: Testing database connection")
    print("="*60)
    
    try:
        # Try to fetch patients (limit 1 to be quick)
        response = client.table("patients").select("patient_id", count="exact").limit(1).execute()
        print(f"✅ Successfully queried 'patients' table")
        print(f"   Total patients in database: {response.count if hasattr(response, 'count') else 'unknown'}")
    except Exception as e:
        print(f"❌ Failed to query 'patients' table: {e}")
        # Don't return False yet - maybe the table is just empty
    
    # 4. Check schema - try all main tables
    print("\n" + "="*60)
    print("STEP 4: Checking database schema")
    print("="*60)
    
    tables_to_check = [
        "patients",
        "onboarding_profiles",
        "daily_checkins",
        "sessions",
        "messages",
        "risk_assessments",
        "content_engagement",
        "support_networks",
        "crisis_events",
        "conversation_metrics",
    ]
    
    tables_found = []
    tables_missing = []
    
    for table_name in tables_to_check:
        try:
            # Just try to select 0 rows to check if table exists
            response = client.table(table_name).select("*").limit(0).execute()
            tables_found.append(table_name)
            print(f"   ✅ {table_name}")
        except Exception as e:
            tables_missing.append(table_name)
            print(f"   ❌ {table_name} - {str(e)[:80]}")
    
    # 5. Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"✅ Connected to Supabase: {SUPABASE_URL}")
    print(f"✅ Tables found: {len(tables_found)}/{len(tables_to_check)}")
    
    if tables_missing:
        print(f"\n⚠️  Missing tables: {', '.join(tables_missing)}")
        print("    → You may need to run SUPABASE_SCHEMA.sql to initialize the database")
        return False
    else:
        print("\n✅ All tables found! Connection successful.")
        return True


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)

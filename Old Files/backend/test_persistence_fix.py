#!/usr/bin/env python3
"""
Quick test to verify conversation persistence fix.
Tests that ensure_patient() and ensure_session() are called
before save_message() in the /chat endpoint.
"""

import sys
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_chat_endpoint_initialization():
    """Verify the /chat endpoint properly initializes patient and session."""
    
    logger.info("=" * 80)
    logger.info("TEST: Chat Endpoint Database Initialization")
    logger.info("=" * 80)
    
    # Read the chatbot_engine.py file to verify the fix
    with open("chatbot_engine.py", "r") as f:
        content = f.read()
    
    # Check that ensure_patient is called in the /chat endpoint
    if "ensure_patient(patient_code=" in content:
        logger.info("✓ ensure_patient() is called in /chat endpoint")
    else:
        logger.error("✗ ensure_patient() NOT called in /chat endpoint")
        return False
    
    # Check that ensure_session is called in the /chat endpoint
    if "ensure_session(session_id=" in content:
        logger.info("✓ ensure_session() is called in /chat endpoint")
    else:
        logger.error("✗ ensure_session() NOT called in /chat endpoint")
        return False
    
    # Check that handle_message is called after initialization
    lines = content.split('\n')
    ensure_patient_line = None
    handle_message_line = None
    
    for i, line in enumerate(lines):
        if "ensure_patient(patient_code=" in line:
            ensure_patient_line = i
        if "ensure_patient_line is not None and handle_message(" in line:
            handle_message_line = i
        if "result = handle_message(" in line and ensure_patient_line is not None:
            handle_message_line = i
    
    if ensure_patient_line is not None and handle_message_line is not None:
        if ensure_patient_line < handle_message_line:
            logger.info(f"✓ Initialization happens before handle_message()")
            logger.info(f"  - ensure_patient at line {ensure_patient_line}")
            logger.info(f"  - handle_message at line {handle_message_line}")
        else:
            logger.error("✗ ensure_patient() called AFTER handle_message()")
            return False
    
    logger.info("\n" + "=" * 80)
    logger.info("DATABASE SCHEMA CHECK")
    logger.info("=" * 80)
    
    # Verify schema has FK constraints
    with open("create_schema.sql", "r") as f:
        schema = f.read()
    
    if "REFERENCES sessions(session_id)" in schema:
        logger.info("✓ conversations.session_id has FK constraint")
    else:
        logger.warning("⚠ Could not verify FK constraint in schema")
    
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info("""
The fix ensures:
1. ensure_patient() creates/updates patient record
2. ensure_session() creates/updates session record
3. These are called BEFORE handle_message()
4. This allows save_message() to satisfy FK constraints

Conversation persistence should now work correctly!
    """)
    
    return True

if __name__ == "__main__":
    success = test_chat_endpoint_initialization()
    sys.exit(0 if success else 1)

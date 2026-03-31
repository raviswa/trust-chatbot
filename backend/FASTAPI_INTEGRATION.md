"""
Integration Guide: Using New Microservices with FastAPI

This file shows how to update your FastAPI endpoints to use the new
microservices-based chatbot engine.

Original code in chatbot_engine.py around line 858:
    @app.post("/chat")
    async def chat(req: ChatRequest):
        return handle_message(req.message, req.session_id, req.patient_code)

New code (updated to use services):
    (see below)
"""

# ────────────────────────────────────────────────────────────────────────────
# MIGRATION: Update the /chat endpoint
# ────────────────────────────────────────────────────────────────────────────

# STEP 1: Update import at top of chatbot_engine.py

# OLD:
# from chatbot_engine import handle_message, clear_session, get_session_summary

# NEW:
from chatbot_engine import (
    handle_message,
    clear_session,
    get_session_summary,
    end_session,
    get_session_stats,
)

# STEP 2: Update the /chat endpoint

# The endpoint signature stays the same, but the response is enhanced:

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Trust AI Chatbot - Microservices Edition")


class ChatRequest(BaseModel):
    message: str
    session_id: str
    patient_id: Optional[str] = None  # Should be included for context tracking
    patient_code: Optional[str] = None


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Chat endpoint with enhanced microservices support.
    
    Now includes:
    - Patient context vector tracking
    - Minimal-question dialogue model
    - Enhanced response metadata
    - Better error handling per service
    """
    try:
        # The new handle_message requires patient_id for context tracking
        patient_id = req.patient_id or f"user_{req.session_id}"
        
        result = handle_message(
            message=req.message,
            session_id=req.session_id,
            patient_id=patient_id,
            patient_code=req.patient_code or "UNKNOWN",
        )
        
        # New response format includes additional fields
        return {
            "status": "ok",
            **result
        }
    
    except ValueError as ve:
        return {
            "status": "error",
            "error": str(ve),
            "session_id": req.session_id,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Chat handler error: {e}")
        return {
            "status": "error",
            "error": "An unexpected error occurred. Please try again.",
            "session_id": req.session_id,
            "timestamp": datetime.now().isoformat(),
        }


# STEP 3: Enhanced session management endpoints

@app.post("/session/clear")
async def session_clear(session_id: Optional[str] = None):
    """Clear session and associated context."""
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    
    summary = end_session(session_id)
    return {
        "status": "cleared",
        "session_id": session_id,
        "summary": summary,
    }


@app.get("/session/{session_id}/summary")
async def session_summary_endpoint(session_id: str):
    """Get session summary with context awareness."""
    try:
        summary = get_session_summary(session_id)
        return {
            "status": "ok",
            **summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/session/{session_id}/stats")
async def session_stats_endpoint(session_id: str):
    """Get detailed session statistics (NEW endpoint)."""
    try:
        stats = get_session_stats(session_id)
        return {
            "status": "ok",
            **stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# STEP 4: Helper endpoint for debugging (optional)

from services_context_manager import _context_cache

@app.get("/session/{session_id}/context")
async def session_context_endpoint(session_id: str):
    """
    Get patient context vector for debugging (requires auth in production).
    WARNING: This includes sensitive patient information - secure appropriately.
    """
    if session_id not in _context_cache:
        raise HTTPException(status_code=404, detail="Session context not found")
    
    context = _context_cache[session_id]
    return {
        "status": "ok",
        "context": context.to_dict(),
    }


# ────────────────────────────────────────────────────────────────────────────
# UPDATED RESPONSE EXAMPLES
# ────────────────────────────────────────────────────────────────────────────

"""
OLD response (from original chatbot_engine.py):
{
    "response": "Thank you for sharing...",
    "intent": "mood_anxious",
    "severity": "medium",
    "session_id": "sess-123"
}

NEW response (from chatbot_engine.py with microservices):
{
    "status": "ok",
    "response": "Thank you for sharing that with me. Anxiety can feel overwhelming...\n\nDo you have people in your life you can talk to about this?",
    "intent": "mood_anxious",
    "severity": "medium",
    "show_resources": false,
    "resource_links": {},
    "session_id": "sess-123",
    "patient_code": "PAT-001",
    "patient_id": "user_sess-123",
    "message_number": 3,
    "context_summary": "Current concerns: mood | Uses coping: journaling | Recurring themes: sleep",
    "has_minimal_question": true,
    "timestamp": "2026-03-18T10:30:45.123456",
    "metadata": {
        "intent_category": "mood",
        "requires_follow_up": false,
        "citations": []
    }
}

KEY DIFFERENCES:
1. Added "status" field for consistency
2. Response now includes embedded minimal question when appropriate
3. Added context_summary showing what we know about patient
4. Added has_minimal_question flag
5. Added message_number for conversation tracking
6. Enhanced metadata with intent_category and follow_up flags
7. Better category separation (metadata vs top-level fields)
"""

# ────────────────────────────────────────────────────────────────────────────
# INTEGRATION TESTING
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Test the microservices integration locally:
    
    $ python -c "from fastapi.testclient import TestClient; client = TestClient(app); \
      response = client.post('/chat', json={'message': 'Hi, how are you?', 'session_id': 'test-001', 'patient_id': 'USER-001', 'patient_code': 'PAT-001'}); \
      print(response.json())"
    """
    import uvicorn
    
    # Run with: python this_file.py
    uvicorn.run(app, host="127.0.0.1", port=8001)


# ────────────────────────────────────────────────────────────────────────────
# CURL EXAMPLES FOR TESTING
# ────────────────────────────────────────────────────────────────────────────

"""
# Test 1: Basic greeting
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, how can you help?",
    "session_id": "test-001",
    "patient_id": "USER-001",
    "patient_code": "PAT-001"
  }'

# Test 2: Mood issue (should include minimal question)
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I have been so anxious lately",
    "session_id": "test-001",
    "patient_id": "USER-001",
    "patient_code": "PAT-001"
  }'

# Test 3: Context awareness (follow-up won't repeat question)
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "It has gotten worse this week",
    "session_id": "test-001",
    "patient_id": "USER-001",
    "patient_code": "PAT-001"
  }'

# Test 4: Get session context
curl -X GET http://localhost:8001/session/test-001/context

# Test 5: Get session stats
curl -X GET http://localhost:8001/session/test-001/stats

# Test 6: End session
curl -X POST http://localhost:8001/session/clear \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-001"}'
"""

# ────────────────────────────────────────────────────────────────────────────
# DEPLOYMENT STEPS
# ────────────────────────────────────────────────────────────────────────────

"""
1. Rename/backup existing chatbot_engine.py:
   mv backend/chatbot_engine.py backend/chatbot_engine_v1_backup.py

2. Update import in pages/api/chat.js (or your FastAPI app):
   OLD: from chatbot_engine import handle_message
   NEW: from chatbot_engine import handle_message

3. Test endpoints:
   - Manual testing with curl (see examples above)
   - Automated testing (see test file)
   - Load testing with concurrent sessions

4. Monitor logs during transition:
   tail -f /var/log/chatbot/error.log

5. Gradual rollout:
   - Canary: Route 10% of traffic to new services
   - Monitor: Watch error rates, latency, user feedback
   - Increase: Gradually increase traffic
   - Complete: Once stable, route 100% to new services

6. Rollback plan:
   If issues detected:
   - Switch back to v1: mv backend/chatbot_engine_v1_backup.py backend/chatbot_engine.py
   - Restart services
   - Investigate issues
"""

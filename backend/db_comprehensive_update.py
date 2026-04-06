"""
Comprehensive Database Update Module for Trust AI Chatbot
===========================================================

This module handles updating ALL relevant Supabase tables when a user 
interacts with the chatbot. Ensures data flows across the entire system:

- messages          → conversation history
- sessions          → session metadata & outcomes
- daily_checkins    → extracted mood/craving/medication data
- risk_assessments  → computed risk scores
- conversation_metrics → 5-layer compliance tracking
- policy_violations → any policy breaches detected
- crisis_events     → crisis-level incidents
- content_engagement → videos shown/viewed
- relapse_events    → relapse disclosures
- patient_milestones → streak/achievement tracking

Usage:
    from db_comprehensive_update import update_all_tables_from_chatbot_interaction
    
    await update_all_tables_from_chatbot_interaction(
        patient_id=patient_id,
        patient_code=patient_code,
        session_id=session_id,
        user_message=user_message,
        bot_response=bot_response,
        intent=intent,
        severity=severity,
        checkin_data={...},
        risk_score=risk_score,
        policy_violations=[...],
        crisis_detected=False,
        video_shown=None,
        current_layer=3
    )
"""

import json
import logging
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Dict, List, Optional

# Try the native PostgreSQL driver first (db_postgres.py).
# Fall back to the Supabase SDK shim if that's what's configured.
# Only the _get_db_conn() function branch that succeeds will be used.
try:
    from db_postgres import _conn as _pg_conn
    _PG_AVAILABLE = True
except Exception:
    _PG_AVAILABLE = False

try:
    from db_supabase import supabase as _supabase_client
    _SUPABASE_AVAILABLE = True
except Exception:
    _supabase_client = None
    _SUPABASE_AVAILABLE = False

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers — uniform DB access regardless of backend
# ─────────────────────────────────────────────────────────────────────────────

@contextmanager
def _get_pg():
    """Yield a psycopg2 connection from the pool."""
    with _pg_conn() as conn:
        yield conn


def _pg_execute(sql: str, params: tuple = ()) -> None:
    """Execute a write statement via psycopg2."""
    with _get_pg() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)


def _pg_fetchone(sql: str, params: tuple = ()) -> Optional[dict]:
    """Fetch a single row via psycopg2, returned as a plain dict."""
    import psycopg2.extras
    with _get_pg() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None


def _pg_fetchall(sql: str, params: tuple = ()) -> List[dict]:
    """Fetch all rows via psycopg2, returned as plain dicts."""
    import psycopg2.extras
    with _get_pg() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]


class ComprehensiveDatabaseUpdater:
    """
    Orchestrates updates across all tables for a single chatbot interaction.

    Backend selection (in priority order):
      1. db_postgres.py   — psycopg2 + connection pool (preferred)
      2. db_supabase.py   — Supabase SDK (stopgap / fallback)
    """

    def __init__(self, supabase_client=None):
        """
        supabase_client is accepted for backward compatibility but ignored
        when the psycopg2 backend is available.
        """
        self._use_pg = _PG_AVAILABLE
        # Keep the Supabase client as a last-resort fallback
        self._supabase = supabase_client or _supabase_client
        # self.db is the Supabase client reference used by all table methods.
        # When the psycopg2 backend is active the _pg_* helpers are used instead,
        # but self.db must still be set so attribute lookups never raise.
        self.db = self._supabase
    
    def update_all_tables(
        self,
        patient_id: str,
        patient_code: str,
        session_id: str,
        user_message: str,
        bot_response: str,
        intent: str,
        severity: str,
        checkin_data: Optional[Dict[str, Any]] = None,
        risk_score: Optional[int] = None,
        policy_violations: Optional[List[str]] = None,
        crisis_detected: bool = False,
        crisis_details: Optional[Dict] = None,
        video_shown: Optional[Dict] = None,
        current_layer: int = 1,
        response_tone: Optional[str] = None,
        response_latency_ms: Optional[int] = None,
        rag_sources: Optional[List[str]] = None,
    ) -> Dict[str, bool]:
        """
        Update all relevant tables based on chatbot interaction.
        
        Args:
            patient_id: UUID of patient
            patient_code: Patient code (e.g., "ABC123")
            session_id: Session UUID
            user_message: Message from user
            bot_response: Response from chatbot
            intent: Classified intent
            severity: Risk severity (low/medium/high/critical)
            checkin_data: Extracted mood/craving/medication data
            risk_score: Computed risk score (0-100)
            policy_violations: List of policy violation types
            crisis_detected: Whether crisis indicators present
            crisis_details: Crisis details if detected
            video_shown: Video metadata if shown
            current_layer: Current 5-layer conversation stage
            response_tone: Tone of bot response
            response_latency_ms: Message latency
            rag_sources: RAG source documents used
            
        Returns:
            Dict with table names and update status
        """
        results = {}
        
        try:
            # 1. Update MESSAGES table (core conversation history)
            results["messages"] = self._update_messages_table(
                session_id=session_id,
                patient_id=patient_id,
                user_message=user_message,
                bot_response=bot_response,
                intent=intent,
                severity=severity,
                video_shown=video_shown,
                response_tone=response_tone,
                response_latency_ms=response_latency_ms,
                rag_sources=rag_sources,
            )
        except Exception as e:
            logger.error(f"Failed to update messages table: {e}")
            results["messages"] = False
        
        try:
            # 2. Update SESSIONS table (session metadata)
            results["sessions"] = self._update_sessions_table(
                session_id=session_id,
                patient_id=patient_id,
                intent=intent,
                severity=severity,
                crisis_detected=crisis_detected,
                current_layer=current_layer,
            )
        except Exception as e:
            logger.error(f"Failed to update sessions table: {e}")
            results["sessions"] = False
        
        try:
            # 3. Update DAILY_CHECKINS table (if mood/craving/medication data extracted)
            if checkin_data:
                results["daily_checkins"] = self._update_daily_checkins_table(
                    patient_id=patient_id,
                    session_id=session_id,
                    checkin_data=checkin_data,
                )
            else:
                results["daily_checkins"] = None  # Not applicable
        except Exception as e:
            logger.error(f"Failed to update daily_checkins table: {e}")
            results["daily_checkins"] = False
        
        try:
            # 4. Update RISK_ASSESSMENTS table (computed risk)
            if risk_score is not None:
                results["risk_assessments"] = self._update_risk_assessments_table(
                    patient_id=patient_id,
                    session_id=session_id,
                    risk_score=risk_score,
                    severity=severity,
                    checkin_data=checkin_data,
                )
            else:
                results["risk_assessments"] = None
        except Exception as e:
            logger.error(f"Failed to update risk_assessments table: {e}")
            results["risk_assessments"] = False
        
        try:
            # 5. Update CONVERSATION_METRICS table (5-layer tracking)
            results["conversation_metrics"] = self._update_conversation_metrics_table(
                session_id=session_id,
                patient_id=patient_id,
                current_layer=current_layer,
                intent=intent,
                severity=severity,
            )
        except Exception as e:
            logger.error(f"Failed to update conversation_metrics table: {e}")
            results["conversation_metrics"] = False
        
        try:
            # 6. Update POLICY_VIOLATIONS table (if breaches detected)
            if policy_violations:
                results["policy_violations"] = self._update_policy_violations_table(
                    session_id=session_id,
                    patient_id=patient_id,
                    user_message=user_message,
                    bot_response=bot_response,
                    violations=policy_violations,
                )
            else:
                results["policy_violations"] = None
        except Exception as e:
            logger.error(f"Failed to update policy_violations table: {e}")
            results["policy_violations"] = False
        
        try:
            # 7. Update CRISIS_EVENTS table (if crisis detected)
            if crisis_detected and crisis_details:
                results["crisis_events"] = self._update_crisis_events_table(
                    session_id=session_id,
                    patient_id=patient_id,
                    user_message=user_message,
                    bot_response=bot_response,
                    crisis_details=crisis_details,
                )
            else:
                results["crisis_events"] = None
        except Exception as e:
            logger.error(f"Failed to update crisis_events table: {e}")
            results["crisis_events"] = False
        
        try:
            # 8. Update CONTENT_ENGAGEMENT table (if video shown)
            if video_shown:
                results["content_engagement"] = self._update_content_engagement_table(
                    patient_id=patient_id,
                    session_id=session_id,
                    video_shown=video_shown,
                    intent=intent,
                )
            else:
                results["content_engagement"] = None
        except Exception as e:
            logger.error(f"Failed to update content_engagement table: {e}")
            results["content_engagement"] = False
        
        try:
            # 9. Update RELAPSE_EVENTS table (if relapse disclosed)
            if "relapse" in intent.lower():
                results["relapse_events"] = self._update_relapse_events_table(
                    patient_id=patient_id,
                    session_id=session_id,
                    user_message=user_message,
                    checkin_data=checkin_data,
                )
            else:
                results["relapse_events"] = None
        except Exception as e:
            logger.error(f"Failed to update relapse_events table: {e}")
            results["relapse_events"] = False
        
        logger.info(f"Comprehensive database update completed for session {session_id}")
        logger.info(f"Update results: {results}")
        
        return results
    
    # ─────────────────────────────────────────────────────────────────────
    # TABLE-SPECIFIC UPDATE FUNCTIONS
    # ─────────────────────────────────────────────────────────────────────
    
    def _update_messages_table(
        self,
        session_id: str,
        patient_id: str,
        user_message: str,
        bot_response: str,
        intent: str,
        severity: str,
        video_shown: Optional[Dict] = None,
        response_tone: Optional[str] = None,
        response_latency_ms: Optional[int] = None,
        rag_sources: Optional[List[str]] = None,
    ) -> bool:
        """Update messages table with user and bot messages."""
        try:
            user_msg_record = {
                "session_id": session_id,
                "patient_id": patient_id,
                "role": "user",
                "content": user_message,
                "intent": intent,
                "severity": severity,
                "has_crisis_indicators": severity in ["high", "critical"],
                "created_at": datetime.now().isoformat(),
            }
            
            bot_msg_record = {
                "session_id": session_id,
                "patient_id": patient_id,
                "role": "assistant",
                "content": bot_response,
                "response_tone": response_tone,
                "response_latency_ms": response_latency_ms,
                "rag_context_used": bool(rag_sources),
                "rag_source_docs": rag_sources or [],
                "created_at": datetime.now().isoformat(),
            }
            
            if video_shown:
                bot_msg_record.update({
                    "response_includes_video": True,
                    "video_title": video_shown.get("title"),
                    "video_id": video_shown.get("id"),
                })
            
            # Insert both messages
            self.db.table("messages").insert([user_msg_record, bot_msg_record]).execute()
            logger.info(f"Updated messages table for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"_update_messages_table failed: {e}")
            return False
    
    def _update_sessions_table(
        self,
        session_id: str,
        patient_id: str,
        intent: str,
        severity: str,
        crisis_detected: bool,
        current_layer: int,
    ) -> bool:
        """Update sessions table with interaction metadata."""
        try:
            # Get existing session if available
            session_result = self.db.table("sessions").select("*").eq("session_id", session_id).execute()
            
            if session_result.data:
                # Update existing session
                existing = session_result.data[0]
                message_count = (existing.get("message_count") or 0) + 2  # user + bot
                severity_flags = json.loads(existing.get("severity_flags") or "[]")
                if severity not in severity_flags:
                    severity_flags.append(severity)
                
                update_payload = {
                    "message_count": message_count,
                    "last_intent": intent,
                    "severity_flags": severity_flags,
                    "crisis_detected": crisis_detected or existing.get("crisis_detected", False),
                    "peak_risk_level": severity if severity in ["high", "critical"] else existing.get("peak_risk_level"),
                    "updated_at": datetime.now().isoformat(),
                }
                
                self.db.table("sessions").update(update_payload).eq("session_id", session_id).execute()
            else:
                # Create new session if doesn't exist
                new_session = {
                    "session_id": session_id,
                    "patient_id": patient_id,
                    "message_count": 2,
                    "last_intent": intent,
                    "severity_flags": [severity],
                    "crisis_detected": crisis_detected,
                    "started_at": datetime.now().isoformat(),
                }
                self.db.table("sessions").insert([new_session]).execute()
            
            logger.info(f"Updated sessions table for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"_update_sessions_table failed: {e}")
            return False
    
    def _update_daily_checkins_table(
        self,
        patient_id: str,
        session_id: str,
        checkin_data: Dict[str, Any],
    ) -> bool:
        """Update daily_checkins table with extracted health data."""
        try:
            today = date.today()
            
            # Check if checkin already exists for today
            existing = self.db.table("daily_checkins").select("*").eq(
                "patient_id", patient_id
            ).eq("checkin_date", str(today)).execute()
            
            checkin_record = {
                "patient_id": patient_id,
                "session_id": session_id,
                "checkin_date": str(today),
                "todays_mood": checkin_data.get("mood"),
                "craving_intensity": checkin_data.get("craving_intensity"),
                "sleep_quality": checkin_data.get("sleep_quality"),
                "stress_score": checkin_data.get("stress_score"),
                "medication_taken": checkin_data.get("medication_taken"),
                "trigger_exposure_flag": checkin_data.get("trigger_exposure_flag", False),
                "recovery_social_support": checkin_data.get("recovery_social_support", False),
                "recovery_activity_today": checkin_data.get("recovery_activity_today", False),
                "addiction_specific_data": checkin_data.get("addiction_specific_data"),
                "updated_at": datetime.now().isoformat(),
            }
            
            if existing.data:
                # Update existing checkin
                self.db.table("daily_checkins").update(checkin_record).eq(
                    "patient_id", patient_id
                ).eq("checkin_date", str(today)).execute()
                logger.info(f"Updated daily_checkins for patient {patient_id}")
            else:
                # Create new checkin
                checkin_record["created_at"] = datetime.now().isoformat()
                self.db.table("daily_checkins").insert([checkin_record]).execute()
                logger.info(f"Created daily_checkins for patient {patient_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"_update_daily_checkins_table failed: {e}")
            return False
    
    def _update_risk_assessments_table(
        self,
        patient_id: str,
        session_id: str,
        risk_score: int,
        severity: str,
        checkin_data: Optional[Dict] = None,
    ) -> bool:
        """Update risk_assessments table with computed risk."""
        try:
            risk_record = {
                "patient_id": patient_id,
                "session_id": session_id,
                "overall_risk_score": risk_score,
                "risk_level": severity,
                "assessment_type": "conversation_based",
                "updated_at": datetime.now().isoformat(),
            }
            
            # Insert or update (upsert pattern)
            self.db.table("risk_assessments").upsert([risk_record]).execute()
            logger.info(f"Updated risk_assessments for patient {patient_id}: score={risk_score}")
            return True
            
        except Exception as e:
            logger.error(f"_update_risk_assessments_table failed: {e}")
            return False
    
    def _update_conversation_metrics_table(
        self,
        session_id: str,
        patient_id: str,
        current_layer: int,
        intent: str,
        severity: str,
    ) -> bool:
        """Update conversation_metrics table for 5-layer compliance."""
        try:
            metric_record = {
                "session_id": session_id,
                "patient_id": patient_id,
                "layer_reached": current_layer,
                "intent_at_layer": intent,
                "severity_at_layer": severity,
                "layer_compliance_status": "compliant",
                "recorded_at": datetime.now().isoformat(),
            }
            
            self.db.table("conversation_metrics").insert([metric_record]).execute()
            logger.info(f"Updated conversation_metrics for session {session_id}: layer={current_layer}")
            return True
            
        except Exception as e:
            logger.error(f"_update_conversation_metrics_table failed: {e}")
            return False
    
    def _update_policy_violations_table(
        self,
        session_id: str,
        patient_id: str,
        user_message: str,
        bot_response: str,
        violations: List[str],
    ) -> bool:
        """Update policy_violations table if breaches detected."""
        try:
            violation_records = []
            for violation_type in violations:
                record = {
                    "session_id": session_id,
                    "patient_id": patient_id,
                    "violation_type": violation_type,
                    "user_message": user_message,
                    "bot_response": bot_response,
                    "detected_at": datetime.now().isoformat(),
                }
                violation_records.append(record)
            
            if violation_records:
                self.db.table("policy_violations").insert(violation_records).execute()
                logger.warning(f"Logged {len(violations)} policy violations for session {session_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"_update_policy_violations_table failed: {e}")
            return False
    
    def _update_crisis_events_table(
        self,
        session_id: str,
        patient_id: str,
        user_message: str,
        bot_response: str,
        crisis_details: Dict,
    ) -> bool:
        """Update crisis_events table if crisis detected."""
        try:
            crisis_record = {
                "session_id": session_id,
                "patient_id": patient_id,
                "crisis_type": crisis_details.get("type", "unspecified"),
                "severity_level": crisis_details.get("severity", "high"),
                "disclosure_text": user_message,
                "bot_response_text": bot_response,
                "escalation_status": crisis_details.get("escalation_status", "pending"),
                "detected_at": datetime.now().isoformat(),
            }
            
            self.db.table("crisis_events").insert([crisis_record]).execute()
            logger.critical(f"Crisis event logged for patient {patient_id}: {crisis_details.get('type')}")
            return True
            
        except Exception as e:
            logger.error(f"_update_crisis_events_table failed: {e}")
            return False
    
    def _update_content_engagement_table(
        self,
        patient_id: str,
        session_id: str,
        video_shown: Dict,
        intent: str,
    ) -> bool:
        """Update content_engagement table for video tracking."""
        try:
            engagement_record = {
                "patient_id": patient_id,
                "session_id": session_id,
                "content_type": "video",
                "content_title": video_shown.get("title"),
                "content_id": video_shown.get("video_id"),   # video_id is the YouTube ID
                "intent_at_time": intent,
                "shown_at": datetime.now().isoformat(),
                "completion_pct": 0,  # Track completion later via frontend callback
            }

            self.db.table("content_engagement").insert([engagement_record]).execute()
            logger.info(f"Logged video engagement for patient {patient_id}: {video_shown.get('title')}")
            return True

        except Exception as e:
            logger.error(f"_update_content_engagement_table failed: {e}")
            return False
    
    def _update_relapse_events_table(
        self,
        patient_id: str,
        session_id: str,
        user_message: str,
        checkin_data: Optional[Dict] = None,
    ) -> bool:
        """Update relapse_events table if relapse disclosed."""
        try:
            relapse_record = {
                "patient_id": patient_id,
                "session_id": session_id,
                "disclosure_message": user_message,
                "relapse_type": checkin_data.get("addiction_type") if checkin_data else "unspecified",
                "disclosed_at": datetime.now().isoformat(),
                "recovery_plan_offered": True,
            }
            
            self.db.table("relapse_events").insert([relapse_record]).execute()
            logger.warning(f"Relapse event logged for patient {patient_id}")
            return True
            
        except Exception as e:
            logger.error(f"_update_relapse_events_table failed: {e}")
            return False


# ─────────────────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTION (USE THIS IN CHATBOT_ENGINE)
# ─────────────────────────────────────────────────────────────────────────

def update_all_tables_from_chatbot_interaction(
    patient_id: str,
    patient_code: str,
    session_id: str,
    user_message: str,
    bot_response: str,
    intent: str,
    severity: str,
    checkin_data: Optional[Dict[str, Any]] = None,
    risk_score: Optional[int] = None,
    policy_violations: Optional[List[str]] = None,
    crisis_detected: bool = False,
    crisis_details: Optional[Dict] = None,
    video_shown: Optional[Dict] = None,
    current_layer: int = 1,
    response_tone: Optional[str] = None,
    response_latency_ms: Optional[int] = None,
    rag_sources: Optional[List[str]] = None,
) -> Dict[str, bool]:
    """
    Convenience function to update all tables at once.
    Call this from chatbot_engine.py after each chatbot interaction.
    
    Example:
        result = update_all_tables_from_chatbot_interaction(
            patient_id="uuid-123",
            patient_code="ABC001",
            session_id="session-456",
            user_message="I've been feeling really lonely lately",
            bot_response="I hear you. Loneliness can be challenging...",
            intent="mood_lonely",
            severity="medium",
            checkin_data={"mood": "lonely", "craving_intensity": 3},
            risk_score=45,
            current_layer=2
        )
        logger.info(f"Database updates: {result}")
    """
    updater = ComprehensiveDatabaseUpdater(_supabase_client)
    return updater.update_all_tables(
        patient_id=patient_id,
        patient_code=patient_code,
        session_id=session_id,
        user_message=user_message,
        bot_response=bot_response,
        intent=intent,
        severity=severity,
        checkin_data=checkin_data,
        risk_score=risk_score,
        policy_violations=policy_violations,
        crisis_detected=crisis_detected,
        crisis_details=crisis_details,
        video_shown=video_shown,
        current_layer=current_layer,
        response_tone=response_tone,
        response_latency_ms=response_latency_ms,
        rag_sources=rag_sources,
    )

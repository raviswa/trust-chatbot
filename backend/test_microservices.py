"""
Test Suite for Microservices-Based Chatbot

Tests the new architecture to ensure:
1. Minimal-question dialogue works correctly
2. Context vector tracking is accurate
3. Intent classification is reliable
4. Safety checks are comprehensive
5. Response generation is appropriate
"""

import json
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class ChatbotMicroservicesTestSuite:
    """Comprehensive test suite for the new microservices chatbot."""
    
    def __init__(self):
        """Initialize test suite with services."""
        from chatbot_engine import handle_message, get_session_summary
        from patient_context import get_or_create_context, _context_cache
        from services_pipeline import IntentClassifier, ResponseGenerator, SafetyChecker
        
        self.handle_message = handle_message
        self.get_session_summary = get_session_summary
        self.get_or_create_context = get_or_create_context
        self.context_cache = _context_cache
        self.intent_classifier = IntentClassifier()
        self.response_generator = ResponseGenerator()
        self.safety_checker = SafetyChecker()
        
        self.test_results = []
        self.session_id = None
        self.patient_id = None
        self.patient_code = None
    
    def setup_test_session(self):
        """Create a test session."""
        import uuid
        self.session_id = f"test-{uuid.uuid4().hex[:8]}"
        self.patient_id = f"user_{self.session_id}"
        self.patient_code = "TEST-PATIENT"
        print(f"\n{'='*80}")
        print(f"Test Session: {self.session_id}")
        print(f"Patient: {self.patient_code} (ID: {self.patient_id})")
        print(f"{'='*80}\n")
    
    def cleanup_test_session(self):
        """Clean up test session."""
        self.context_cache.pop(self.session_id, None)
    
    def record_test(self, test_name: str, passed: bool, details: str = ""):
        """Record test result."""
        result = {
            "name": test_name,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"       {details}\n")
    
    def print_summary(self):
        """Print test summary."""
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["passed"])
        failed = total - passed
        
        print(f"\n{'='*80}")
        print(f"TEST SUMMARY")
        print(f"{'='*80}")
        print(f"Total:  {total}")
        print(f"Passed: {passed} ({100*passed//total}%)")
        print(f"Failed: {failed}")
        print(f"{'='*80}\n")
        
        if failed > 0:
            print("FAILED TESTS:")
            for r in self.test_results:
                if not r["passed"]:
                    print(f"  - {r['name']}: {r['details']}")
    
    # ── INTENT CLASSIFICATION TESTS ──────────────────────────────────────
    
    def test_crisis_detection(self):
        """Test that crisis intents are detected reliably."""
        crisis_messages = [
            ("I want to die", "crisis_suicidal"),
            ("I'm going to kill myself", "crisis_suicidal"),
            ("He hits me regularly", "crisis_abuse"),
            ("I cut myself to cope", "behaviour_self_harm"),
        ]
        
        for msg, expected_intent in crisis_messages:
            intent = self.intent_classifier.classify(msg)
            passed = intent == expected_intent
            self.record_test(
                f"Crisis Detection: '{msg[:20]}...'",
                passed,
                f"Expected: {expected_intent}, Got: {intent}"
            )
    
    def test_mood_classification(self):
        """Test mood intent classification."""
        mood_messages = [
            ("I'm feeling really sad and hopeless", "mood_sad"),
            ("I have so much anxiety", "mood_anxious"),
            ("I'm really angry right now", "mood_angry"),
            ("I feel so alone", "mood_lonely"),
        ]
        
        for msg, expected_intent in mood_messages:
            intent = self.intent_classifier.classify(msg)
            passed = intent == expected_intent
            self.record_test(
                f"Mood Classification: {expected_intent}",
                passed,
                f"Message: '{msg[:30]}...', Got: {intent}"
            )
    
    def test_trauma_detection(self):
        """Test trauma trigger detection."""
        trauma_messages = [
            ("past events have been bothering me", "trigger_trauma"),
            ("I have PTSD from childhood abuse", "trigger_trauma"),
            ("I get flashbacks", "trigger_trauma"),
        ]
        
        for msg, expected_intent in trauma_messages:
            intent = self.intent_classifier.classify(msg)
            passed = intent == expected_intent
            self.record_test(
                f"Trauma Detection",
                passed,
                f"Message: '{msg[:30]}...', Got: {intent}"
            )
    
    # ── CONTEXT VECTOR TESTS ─────────────────────────────────────────────
    
    def test_context_extraction(self):
        """Test that context is extracted from conversations."""
        context = self.get_or_create_context(
            self.session_id,
            self.patient_id,
            self.patient_code
        )
        
        # Simulate a conversation turn
        user_message = "I'm on antidepressants and I have depression"
        context.extract_from_conversation(user_message, "mood_sad", {"severity": "medium"})
        
        # Check if context was updated
        passed = (
            "depression" in context.mental_health_profile["diagnosed_conditions"]
        )
        self.record_test(
            "Context Extraction: Diagnoses",
            passed,
            f"Conditions: {context.mental_health_profile['diagnosed_conditions']}"
        )
    
    def test_minimal_questions_not_repeated(self):
        """Test that minimal questions aren't asked twice."""
        self.setup_test_session()
        
        # First message (sad mood) - should get a minimal question
        r1 = self.handle_message(
            "I'm feeling really sad",
            self.session_id,
            self.patient_id,
            self.patient_code
        )
        
        has_first_question = r1.get("has_minimal_question", False)
        first_response = r1.get("response", "")
        
        # Second message - should NOT repeat the same question
        r2 = self.handle_message(
            "It's been going on for weeks",
            self.session_id,
            self.patient_id,
            self.patient_code
        )
        
        second_response = r2.get("response", "")
        
        # The second response shouldn't repeat "Do you have people you can talk to"
        # if it was asked in the first response
        first_has_support_q = "people in your life" in first_response.lower()
        second_has_support_q = "people in your life" in second_response.lower()
        
        passed = not (first_has_support_q and second_has_support_q)
        self.record_test(
            "Minimal Questions Not Repeated",
            passed,
            f"First Q asked: {first_has_support_q}, Second Q asked: {second_has_support_q}"
        )
        
        self.cleanup_test_session()
    
    def test_context_awareness(self):
        """Test that chatbot avoids asking about known information."""
        self.setup_test_session()
        
        # First: Provide context about medications
        r1 = self.handle_message(
            "I'm on sertraline and citalopram for anxiety",
            self.session_id,
            self.patient_id,
            self.patient_code
        )
        
        # Second: The chatbot shouldn't ask about medications again
        r2 = self.handle_message(
            "But I don't think they're helping",
            self.session_id,
            self.patient_id,
            self.patient_code
        )
        
        context = self.context_cache.get(self.session_id)
        asked_meds = context.has_been_asked("ask_current_meds") if context else False
        
        passed = asked_meds or "medication" not in r2["response"].lower()
        self.record_test(
            "Context Awareness: No Repeated Questions",
            passed,
            f"Asked about meds: {asked_meds}"
        )
        
        self.cleanup_test_session()
    
    # ── SAFETY TESTS ─────────────────────────────────────────────────────
    
    def test_crisis_response_includes_resources(self):
        """Test that crisis responses include emergency resources."""
        self.setup_test_session()
        
        r = self.handle_message(
            "I want to end my life right now",
            self.session_id,
            self.patient_id,
            self.patient_code
        )
        
        response = r["response"].lower()
        has_emergency = "emergency" in response or "911" in response or "call" in response
        is_critical = r["severity"] == "critical"
        shows_resources = r.get("show_resources", False)
        
        passed = has_emergency and is_critical and shows_resources
        self.record_test(
            "Crisis Response Includes Resources",
            passed,
            f"Has resources: {has_emergency}, Severity: {r['severity']}, Show resources: {shows_resources}"
        )
        
        self.cleanup_test_session()
    
    def test_medication_blocking(self):
        """Test that medication requests are blocked appropriately."""
        intent = self.intent_classifier.classify("What medication should I take for anxiety?")
        
        passed = intent == "medication_request"
        self.record_test(
            "Medication Request Detection",
            passed,
            f"Intent: {intent}"
        )
    
    def test_safety_checker_validation(self):
        """Test safety checker validation."""
        unsafe_response = "You should take 200mg of sertraline twice daily"
        safe_response = "A therapist can help you work through anxiety"
        
        is_safe_1, _ = self.safety_checker.check_medication_safety(unsafe_response)
        is_safe_2, _ = self.safety_checker.check_medication_safety(safe_response)
        
        passed = (not is_safe_1) and is_safe_2
        self.record_test(
            "Safety Checker: Medication Safety",
            passed,
            f"Unsafe blocked: {not is_safe_1}, Safe allowed: {is_safe_2}"
        )
    
    # ── RESPONSE GENERATION TESTS ────────────────────────────────────────
    
    def test_response_personalization(self):
        """Test that responses are personalized based on context."""
        self.setup_test_session()
        
        # Build up context
        self.handle_message(
            "I have depression",
            self.session_id,
            self.patient_id,
            self.patient_code
        )
        
        r = self.handle_message(
            "It's really affecting my sleep",
            self.session_id,
            self.patient_id,
            self.patient_code
        )
        
        response = r["response"]
        context_summary = r.get("context_summary", "")
        
        # Response should acknowledge known context
        passed = (
            len(response) > 50 and  # Non-trivial response
            len(context_summary) > 0  # Context tracked
        )
        
        self.record_test(
            "Response Personalization",
            passed,
            f"Response length: {len(response)}, Context summary: {context_summary[:50]}..."
        )
        
        self.cleanup_test_session()
    
    def test_response_severity_matches_intent(self):
        """Test that response severity matches intent severity."""
        severity_tests = [
            ("I want to die", "critical"),
            ("I'm a bit anxious", "medium"),
            ("Hello", "low"),
        ]
        
        for msg, expected_severity in severity_tests:
            intent = self.intent_classifier.classify(msg)
            metadata = self.intent_classifier.get_intent_metadata(intent)
            actual_severity = metadata["severity"]
            
            passed = actual_severity == expected_severity
            self.record_test(
                f"Severity Matching: {expected_severity}",
                passed,
                f"Message: '{msg}', Got: {actual_severity}"
            )
    
    # ── INTEGRATION TESTS ────────────────────────────────────────────────
    
    def test_full_conversation_flow(self):
        """Test a complete conversation flow."""
        self.setup_test_session()
        
        messages = [
            ("Hello", "greeting"),
            ("I've been feeling anxious lately", "mood_anxious"),
            ("It's affecting my sleep", "behaviour_sleep"),
            ("Yes, I have friends", "gratitude"),
            ("Thank you for listening", "gratitude"),
        ]
        
        all_passed = True
        for msg, expected_intent in messages:
            r = self.handle_message(msg, self.session_id, self.patient_id, self.patient_code)
            
            intent = r["intent"]
            passed = intent == expected_intent
            all_passed = all_passed and passed
            
            if not passed:
                print(f"  Warning: Expected {expected_intent}, got {intent} for '{msg}'")
        
        self.record_test(
            "Full Conversation Flow",
            all_passed,
            f"Processed {len(messages)} messages successfully"
        )
        
        summary = self.get_session_summary(self.session_id)
        print(f"  Session Summary: {summary['message_count']} messages, "\
              f"Flags: {summary.get('severity_flags', [])}")
        
        self.cleanup_test_session()
    
    def test_session_context_persistence(self):
        """Test that session context persists across messages."""
        self.setup_test_session()
        
        # First message
        self.handle_message(
            "I have anxiety",
            self.session_id,
            self.patient_id,
            self.patient_code
        )
        
        context_after_1 = self.context_cache.get(self.session_id)
        concerns_1 = context_after_1.current_state["primary_concerns"].copy() if context_after_1 else set()
        
        # Second message
        self.handle_message(
            "It's been getting worse",
            self.session_id,
            self.patient_id,
            self.patient_code
        )
        
        context_after_2 = self.context_cache.get(self.session_id)
        concerns_2 = context_after_2.current_state["primary_concerns"] if context_after_2 else set()
        
        # Context should be preserved
        passed = len(concerns_2) >= len(concerns_1)
        
        self.record_test(
            "Session Context Persistence",
            passed,
            f"Concerns tracked: {concerns_2}"
        )
        
        self.cleanup_test_session()
    
    # ── RUN ALL TESTS ───────────────────────────────────────────────────
    
    def run_all_tests(self):
        """Run all tests."""
        print("\n" + "="*80)
        print("CHATBOT MICROSERVICES TEST SUITE")
        print("="*80)
        
        # Intent Classification Tests
        print("\n[INTENT CLASSIFICATION TESTS]")
        self.test_crisis_detection()
        self.test_mood_classification()
        self.test_trauma_detection()
        
        # Context Vector Tests
        print("\n[CONTEXT VECTOR TESTS]")
        self.test_context_extraction()
        self.test_minimal_questions_not_repeated()
        self.test_context_awareness()
        
        # Safety Tests
        print("\n[SAFETY TESTS]")
        self.test_crisis_response_includes_resources()
        self.test_medication_blocking()
        self.test_safety_checker_validation()
        
        # Response Generation Tests
        print("\n[RESPONSE GENERATION TESTS]")
        self.test_response_personalization()
        self.test_response_severity_matches_intent()
        
        # Integration Tests
        print("\n[INTEGRATION TESTS]")
        self.test_full_conversation_flow()
        self.test_session_context_persistence()
        
        # Print Summary
        self.print_summary()


# ────────────────────────────────────────────────────────────────────────────
# RUN TESTS
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Run the full test suite:
    
    $ cd /workspaces/trust-chatbot/backend
    $ python -m pytest test_microservices.py -v
    
    Or run directly:
    $ python test_microservices.py
    """
    
    suite = ChatbotMicroservicesTestSuite()
    suite.run_all_tests()

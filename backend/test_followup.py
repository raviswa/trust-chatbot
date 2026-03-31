#!/usr/bin/env python3
"""
Test follow-up question with detailed error reporting
"""

import requests
import json

BASE_URL = "http://localhost:8000"

# Test 1: Initial message
print("="*70)
print("STEP 1: Initial Message (establish session)")
print("="*70)

payload1 = {
    "message": "I am feeling really anxious and isolated today",
    "session_id": "debug-session-1",
    "patient_code": "PAT-002"
}

print(f"\nRequest payload:\n{json.dumps(payload1, indent=2)}")

try:
    response1 = requests.post(f"{BASE_URL}/chat", json=payload1)
    print(f"\nStatus: {response1.status_code}")
    
    if response1.status_code == 200:
        result1 = response1.json()
        print(f"\n✅ Success!")
        print(f"Intent: {result1.get('intent')}")
        print(f"Severity: {result1.get('severity')}")
        print(f"Has follow-up Q: {result1.get('has_minimal_question')}")
        print(f"\nBot Response:\n{result1.get('response')}")
    else:
        print(f"\n❌ Error!")
        print(f"Response: {response1.text}")
except Exception as e:
    print(f"❌ Request error: {e}")

# Test 2: Follow-up message (SAME SESSION)
print("\n" + "="*70)
print("STEP 2: Follow-up Answer (same session)")
print("="*70)

payload2 = {
    "message": "Breathing exercises might help. I have been avoiding my therapist and friends.",
    "session_id": "debug-session-1",  # SAME session
    "patient_code": "PAT-002"
}

print(f"\nRequest payload:\n{json.dumps(payload2, indent=2)}")

try:
    response2 = requests.post(f"{BASE_URL}/chat", json=payload2)
    print(f"\nStatus: {response2.status_code}")
    
    if response2.status_code == 200:
        result2 = response2.json()
        print(f"\n✅ Success!")
        print(f"Intent: {result2.get('intent')}")
        print(f"Severity: {result2.get('severity')}")
        print(f"\nBot Response:\n{result2.get('response')}")
    else:
        print(f"\n❌ Error {response2.status_code}!")
        print(f"Response:\n{response2.text}")
except Exception as e:
    print(f"❌ Request error: {e}")

# Test 3: Try without patient_code
print("\n" + "="*70)
print("STEP 3: Follow-up without patient_code (alternative format)")
print("="*70)

payload3 = {
    "message": "I think the breathing exercises could really help me",
    "session_id": "debug-session-2"
}

print(f"\nRequest payload:\n{json.dumps(payload3, indent=2)}")

try:
    response3 = requests.post(f"{BASE_URL}/chat", json=payload3)
    print(f"\nStatus: {response3.status_code}")
    
    if response3.status_code == 200:
        result3 = response3.json()
        print(f"\n✅ Success!")
        print(f"Response:\n{result3.get('response')}")
    else:
        print(f"\n❌ Error {response3.status_code}!")
        print(f"Response:\n{response3.text}")
except Exception as e:
    print(f"❌ Request error: {e}")

print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print("""
For follow-up questions, use the SAME session_id:

✅ CORRECT:
{
  "message": "Your follow-up response here",
  "session_id": "test-session-2",
  "patient_code": "PAT-002"
}

❌ WRONG (different session):
{
  "message": "Your follow-up response here",
  "session_id": "test-session-2-NEW",
  "patient_code": "PAT-002"
}

⚠️  If you're still getting 422, check:
1. All required fields are present
2. String values don't have special characters
3. The endpoint URL is correct: http://localhost:8000/chat
4. Content-Type is application/json
""")

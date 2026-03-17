# Trust AI — Mental Health Chatbot · Setup & Usage Guide

---

## File Structure

```
chatbotcode11032026/
  ├── chatbot_engine.py          # Main engine + FastAPI server
  ├── conversational_intake.py   # Guided intake & daily check-in flow  ← NEW
  ├── rag_pipeline.py            # Qdrant retrieval layer
  ├── ethical_policy.py          # Ethical guardrails
  ├── language_sanitiser.py      # Person-first language enforcement
  ├── db.py                      # PostgreSQL persistence
  ├── ingest.py                  # PDF ingestion pipeline
  ├── intents.json               # Intent patterns and responses
  ├── requirements.txt           # Python dependencies
  ├── start_chatbot.bat          # One-click Windows startup
  └── pdfs/                      # Research PDFs (already ingested)
```

---

## Prerequisites

| Service | Purpose | Default Port |
|---|---|---|
| **Ollama** | Local LLM inference (qwen2.5:7b-instruct) | 11434 |
| **Qdrant** | Vector store for RAG retrieval | 6333 |
| **PostgreSQL 16** | Session and patient persistence | 5432 |

### Ollama
```bash
# Install from https://ollama.com, then:
ollama pull qwen2.5:7b-instruct
ollama pull nomic-embed-text
ollama serve          # Keep running in background
```

### Qdrant (no Docker version)
```bash
# Download from https://qdrant.tech/documentation/quick-start/
./qdrant.exe          # Windows — keep running in background
```

### PostgreSQL
```bash
psql -U postgres -c "CREATE DATABASE chatbot_db;"
psql -U postgres -c "CREATE USER chatbot_user WITH PASSWORD 'your_password';"
psql -U postgres -c "GRANT ALL ON DATABASE chatbot_db TO chatbot_user;"
psql -U postgres -d chatbot_db -f create_schema.sql
```

---

## Environment Variables

Edit `.env` in the project folder:

```
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=health_docs

PG_HOST=localhost
PG_PORT=5432
PG_DB=chatbot_db
PG_USER=chatbot_user
PG_PASSWORD=your_password
```

---

## Starting the Server

**Double-click `start_chatbot.bat`** — it handles everything:
- Checks Python, required files, and dependencies
- Verifies Ollama is running
- Prints all API endpoints
- Starts FastAPI on http://127.0.0.1:8001

> **TLS warning during pip install** — harmless. It occurs because PostgreSQL's SSL
> certificate path is registered system-wide. Your packages are already installed;
> pip just cannot self-update. Safe to ignore.

---

## Conversational Intake Flow

The chatbot now guides new users through clinical onboarding conversationally — no forms needed.
It collects the same data as the app's 5-step intake screens, one question at a time.

### New User Flow (first session)
```
App calls POST /session/start
  Bot: "Hi there — may I ask your name?"
User: "Alvin"
  Bot: "What feels heaviest for you lately?"
User: "Guilty and I can't stop drinking"
  Bot: "What are you working to recover from?"
... sleep, stress, cravings, medication, triggers, social support, work, health, consent
  Bot: "Your alcohol recovery plan is now active. Risk level: High. What's on your mind?"
  -> Hands off to RAG support loop
```

### Returning User Flow (daily check-in)
```
App calls POST /session/start  (intake already complete)
  Bot: "Hi Alvin — ready for your daily check-in? Cravings today on a scale of 1-10?"
... mood, rest, triggers, medication
  Bot: "Today's Risk Level: High — I'm noticing some signals. Want to try a breathing exercise?"
  -> Hands off to support loop
```

### Safety Override
If a user sends a crisis signal during intake, the safety layer fires immediately.
The onboarding funnel never traps someone in distress.

---

## API Endpoints

Server runs on http://127.0.0.1:8001
Swagger UI available at http://127.0.0.1:8001/docs

### Core Chat

| Method | Endpoint | Description |
|---|---|---|
| POST | /chat | Send a message, receive a response |
| POST | /session/start | Open app — triggers intake (new) or check-in (returning) |
| POST | /session/clear | Reset session memory |

### Intake and Check-In

| Method | Endpoint | Description |
|---|---|---|
| GET | /session/{id}/intake-profile | Full collected intake profile |
| GET | /session/{id}/checkin-data | Today's check-in data (for Patient State Engine) |
| GET | /session/{id}/summary | Session summary |
| GET | /session/{id}/history | Full conversation history |

### Patient

| Method | Endpoint | Description |
|---|---|---|
| GET | /patient/{code} | Patient profile |
| GET | /patient/{code}/sessions | All sessions for a patient |
| GET | /patient/{code}/history | Full conversation history |

### Admin

| Method | Endpoint | Description |
|---|---|---|
| GET | /admin/sessions | All sessions |
| GET | /admin/crisis | Crisis sessions |
| GET | /admin/crisis/pending | Unreviewed crisis events |
| GET | /admin/stats | Conversation statistics |
| GET | /admin/intents | Top intent breakdown |
| GET | /admin/policy/violations | Policy violation log |

### Other

| Method | Endpoint | Description |
|---|---|---|
| GET | /health | Server health check |
| GET | /policy | Ethical policy summary |
| GET | /documents | List of ingested PDFs |

---

## Response Fields

Every /chat and /session/start response includes:

```json
{
  "response":        "...",
  "intent":          "intake | daily_checkin | addiction_alcohol | ...",
  "severity":        "low | medium | high | critical",
  "show_resources":  false,
  "citations":       [],
  "session_id":      "...",
  "timestamp":       "2026-03-14T10:30:00",
  "patient_name":    "Alvin",
  "intake_complete": true,

  "intake_phase":    3,
  "intake_profile":  { "name": "Alvin", "addiction_type": "alcohol" },

  "checkin_complete": true,
  "checkin_data":     { "craving_intensity": 8, "mood_today": "anger" },
  "risk_score":       12
}
```

---

## Next.js Integration

### lib/trustai.js

```javascript
const API = 'http://127.0.0.1:8001'

export async function startSession(sessionId, patientCode = null) {
  const res = await fetch(`${API}/session/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: '', session_id: sessionId, patient_code: patientCode })
  })
  return res.json()
  // Returns first intake question OR first check-in question automatically
}

export async function sendMessage(message, sessionId, patientCode = null) {
  const res = await fetch(`${API}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId, patient_code: patientCode })
  })
  return res.json()
}

export async function getIntakeProfile(sessionId) {
  const res = await fetch(`${API}/session/${sessionId}/intake-profile`)
  return res.json()
  // Use to feed intake data into Patient State Engine
}

export async function getCheckinData(sessionId) {
  const res = await fetch(`${API}/session/${sessionId}/checkin-data`)
  return res.json()
  // Use to feed daily check-in data into relapse prediction model
}
```

### React Chat Component Pattern

```javascript
import { useState, useEffect } from 'react'
import { startSession, sendMessage } from '../lib/trustai'
import { v4 as uuid } from 'uuid'

export default function Chat({ patientCode }) {
  const [sessionId]   = useState(() => uuid())
  const [messages, setMessages] = useState([])
  const [input, setInput]       = useState('')
  const [intakeComplete, setIntakeComplete] = useState(false)
  const [patientName, setPatientName]       = useState(null)
  const [intakePhase, setIntakePhase]       = useState(0)

  useEffect(() => {
    startSession(sessionId, patientCode).then(data => appendBot(data))
  }, [])

  function appendBot(data) {
    setMessages(prev => [...prev, {
      role: 'assistant',
      text: data.response,
      intent: data.intent,
      severity: data.severity,
      showResources: data.show_resources
    }])
    if (data.patient_name)    setPatientName(data.patient_name)
    if (data.intake_complete) setIntakeComplete(true)
    if (data.intake_phase !== undefined) setIntakePhase(data.intake_phase)
  }

  async function handleSend() {
    if (!input.trim()) return
    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text: userMsg }])
    const data = await sendMessage(userMsg, sessionId, patientCode)
    appendBot(data)
  }

  return (
    <div className="chat-container">

      {/* Progress bar during intake */}
      {!intakeComplete && (
        <div className="intake-progress">
          <div className="bar" style={{ width: `${(intakePhase / 5) * 100}%` }} />
          <span>Step {intakePhase} of 5</span>
        </div>
      )}

      {patientName && <p className="greeting">Hi {patientName}</p>}

      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`message ${m.role}`}>
            <p>{m.text}</p>
            {m.showResources && <CrisisResources />}
            {m.intent === 'checkin_complete' && <RiskBadge severity={m.severity} />}
          </div>
        ))}
      </div>

      <div className="input-row">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSend()}
          placeholder="Type your message..."
        />
        <button onClick={handleSend}>Send</button>
      </div>

    </div>
  )
}
```

---

## Intent Tags Reference

| Category | Tags |
|---|---|
| Intake | intake, intake_complete, daily_checkin, checkin_complete |
| General | greeting, farewell, gratitude, unclear |
| Mood | mood_sad, mood_anxious, mood_angry, mood_lonely, mood_guilty |
| Behaviour | behaviour_isolation, behaviour_sleep, behaviour_eating, behaviour_self_harm |
| Triggers | trigger_stress, trigger_trauma, trigger_relationship, trigger_grief, trigger_financial |
| Addiction | addiction_alcohol, addiction_drugs, addiction_gaming, addiction_social_media, addiction_gambling, addiction_nicotine |
| Crisis | crisis_suicidal, crisis_abuse |
| Safety | severe_distress, psychosis_indicator |

---

## Adding New PDFs

Drop new PDFs into the pdfs/ folder and run:

```bash
python ingest.py --pdf_dir ./pdfs
```

Already-ingested files are skipped automatically.

---

## Quick Smoke Test

With the server running, open a second terminal:

```bash
# Health check
curl http://127.0.0.1:8001/health

# Start a session — get first intake question
curl -X POST http://127.0.0.1:8001/session/start \
     -H "Content-Type: application/json" \
     -d "{\"message\": \"\", \"session_id\": \"test-001\"}"

# Reply with your name
curl -X POST http://127.0.0.1:8001/chat \
     -H "Content-Type: application/json" \
     -d "{\"message\": \"My name is Alvin\", \"session_id\": \"test-001\"}"
```

Or open http://127.0.0.1:8001/docs for the interactive Swagger UI.

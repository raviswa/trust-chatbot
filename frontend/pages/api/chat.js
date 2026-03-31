// pages/api/chat.js
// Next.js API route — proxies requests to the Python chatbot backend.
// Includes timeout handling and one automatic retry on network failure.

export default async function handler(req, res) {

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { message, sessionId, patientCode } = req.body;

  if (!message || !sessionId) {
    return res.status(400).json({ error: 'message and sessionId are required' });
  }

  const apiUrl    = process.env.CHATBOT_API_URL || 'http://127.0.0.1:8000';
  const targetUrl = `${apiUrl}/chat`;
  const payload   = JSON.stringify({
    message:      message,
    session_id:   sessionId,
    patient_code: patientCode || null
  });

  // ── Fetch with timeout ───────────────────────────────────────
  const fetchWithTimeout = async (url, options, timeoutMs = 60000) => {
    const controller = new AbortController();
    const timer      = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(url, { ...options, signal: controller.signal });
      return response;
    } finally {
      clearTimeout(timer);
    }
  };

  // ── One automatic retry on network failure ───────────────────
  const attemptFetch = async (attempt = 1) => {
    try {
      return await fetchWithTimeout(targetUrl, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    payload,
      }, 60000);  // 60s timeout — LLM can be slow on CPU
    } catch (err) {
      if (attempt === 1) {
        console.warn(`[chat.js] Attempt 1 failed (${err.message}), retrying...`);
        await new Promise(r => setTimeout(r, 1000));  // wait 1s then retry
        return attemptFetch(2);
      }
      throw err;
    }
  };

  try {
    const response = await attemptFetch();

    if (!response.ok) {
      const body = await response.text();
      console.error(`[chat.js] Python API returned ${response.status}: ${body}`);
      throw new Error(`Backend error: ${response.status}`);
    }

    const data = await response.json();

    return res.status(200).json({
      response:      data.response,
      intent:        data.intent,
      severity:      data.severity,
      showResources: data.show_resources,
      citations:     data.citations      || [],
      sessionId:     data.session_id,
      timestamp:     data.timestamp,
      showScore:     data.show_score     || false,
      showFeedback:  data.show_feedback  || false,
      video:         data.video          || null,
    });

  } catch (error) {
    const isTimeout = error.name === 'AbortError';
    const isNetwork = error.message?.includes('fetch failed') ||
                      error.message?.includes('ECONNREFUSED');

    console.error(`[chat.js] Error: ${error.message}`);

    if (isTimeout) {
      return res.status(504).json({
        error:   'The AI is taking longer than usual. Please try again.',
        details: 'Request timed out after 60 seconds'
      });
    }

    if (isNetwork) {
      return res.status(503).json({
        error:   'Cannot reach the chatbot server. Please make sure the Python API is running.',
        details: `Tried: ${targetUrl}`
      });
    }

    return res.status(500).json({
      error:   'Something went wrong. Please try again.',
      details: error.message
    });
  }
}

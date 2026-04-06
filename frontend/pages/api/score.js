// pages/api/score.js
// Proxies score submission from frontend to Python /session/score endpoint.

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const { sessionId, patientCode, scoreGroup, score, intent } = req.body;
  if (!sessionId || !scoreGroup || score === undefined) {
    return res.status(400).json({ error: 'sessionId, scoreGroup and score are required' });
  }

  try {
    const apiUrl = process.env.CHATBOT_API_URL || 'http://127.0.0.1:8000';
    const response = await fetch(`${apiUrl}/session/score`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        session_id:   sessionId,
        patient_code: patientCode || null,
        score_group:  scoreGroup,
        score:        score,
        intent:       intent || null,
      }),
    });
    const data = await response.json();
    return res.status(200).json(data);
  } catch (err) {
    console.error('[score.js]', err.message);
    return res.status(500).json({ error: 'Failed to save score' });
  }
}

// pages/api/patient.js
// Server-side proxy for /patient/:code profile lookup.

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { code } = req.query;
  if (!code) {
    return res.status(400).json({ error: 'code is required' });
  }

  const apiUrl = process.env.CHATBOT_API_URL || 'http://127.0.0.1:8000';
  const targetUrl = `${apiUrl}/patient/${code}`;

  try {
    const response = await fetch(targetUrl, { headers: { 'Content-Type': 'application/json' } });
    const data = await response.json();
    return res.status(response.status).json(data);
  } catch (err) {
    console.error(`[patient.js] Failed to reach backend: ${err.message}`);
    return res.status(502).json({ error: 'Backend unavailable', detail: err.message });
  }
}

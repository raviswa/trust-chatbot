import { useState, useEffect, useRef } from 'react';

function generateId() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}

const PATIENTS = [
  { code:'PAT-001', name:'Arjun',   programme:'Alcohol Recovery',          risk:'high'     },
  { code:'PAT-002', name:'Priya',   programme:'Substance Use Disorder',    risk:'medium'   },
  { code:'PAT-003', name:'Karthik', programme:'Digital Addiction (Gaming)',risk:'low'      },
  { code:'PAT-004', name:'Divya',   programme:'Trauma & Anxiety',          risk:'high'     },
  { code:'PAT-005', name:'Rajesh',  programme:'Nicotine Cessation',        risk:'low'      },
  { code:'PAT-006', name:'Ananya',  programme:'Digital Addiction (Social)',risk:'medium'   },
  { code:'PAT-007', name:'Suresh',  programme:'Grief Support',             risk:'medium'   },
  { code:'PAT-008', name:'Lakshmi', programme:'Alcohol Recovery',          risk:'critical' },
  { code:'PAT-009', name:'Vikram',  programme:'Behavioural Addiction',     risk:'low'      },
  { code:'PAT-010', name:'Meera',   programme:'Substance Use (Discharged)',risk:'low'      },
];

const RISK_COLORS = {
  critical:{ dot:'#dc2626' },
  high:    { dot:'#ea580c' },
  medium:  { dot:'#d97706' },
  low:     { dot:'#22c55e' },
};

const API = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8001';

// ── Score card component ─────────────────────────────────────────
function ScoreCard({ scoreData, sessionId, patientCode, intent, onSubmit }) {
  const [val, setVal] = useState(5);
  const [submitted, setSubmitted] = useState(false);

  async function submit() {
    setSubmitted(true);
    try {
      await fetch('/api/score', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sessionId, patientCode,
          scoreGroup: scoreData.group,
          score: val, intent,
        }),
      });
    } catch(e) { console.error(e); }
    onSubmit(val);
  }

  if (submitted) return (
    <div style={{
      background:'rgba(45,106,159,0.12)', border:'1px solid rgba(45,106,159,0.3)',
      borderRadius:12, padding:'10px 14px', marginTop:10,
      fontSize:13, color:'#93c5fd', display:'flex', alignItems:'center', gap:8
    }}>
      ✓ Score recorded: <strong>{val}/10</strong>. Thank you.
    </div>
  );

  return (
    <div style={{
      background:'#1a2744', border:'1px solid rgba(45,106,159,0.35)',
      borderRadius:12, padding:'14px 16px', marginTop:10
    }}>
      <div style={{ fontSize:13, color:'#93c5fd', marginBottom:10, fontWeight:500 }}>
        📊 {scoreData.label}
      </div>
      <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:10 }}>
        <span style={{ fontSize:11, color:'#475569', minWidth:28 }}>0</span>
        <input
          type="range" min={0} max={10} value={val}
          onChange={e => setVal(Number(e.target.value))}
          style={{ flex:1, accentColor:'#2d6a9f', height:4, cursor:'pointer' }}
        />
        <span style={{ fontSize:11, color:'#475569', minWidth:28, textAlign:'right' }}>10</span>
        <span style={{
          background:'#2d6a9f', color:'white', borderRadius:8,
          padding:'2px 10px', fontSize:13, fontWeight:600, minWidth:36, textAlign:'center'
        }}>{val}</span>
      </div>
      <div style={{ display:'flex', justifyContent:'space-between', fontSize:10, color:'#475569', marginBottom:10 }}>
        <span>Worst</span><span>Best</span>
      </div>
      <button onClick={submit} style={{
        background:'linear-gradient(135deg,#1e3a5f,#2d6a9f)',
        color:'white', border:'none', borderRadius:8,
        padding:'7px 18px', fontSize:13, cursor:'pointer', fontWeight:500
      }}>Submit</button>
    </div>
  );
}

// ── Video card component ─────────────────────────────────────────
function VideoCard({ video }) {
  const [expanded, setExpanded] = useState(false);
  if (!video) return null;

  // Detect intent placeholder — real URL will be supplied when mobile app
  // integration is complete. Until then, render a placeholder card.
  const isPlaceholder = typeof video.url === 'string' && video.url.startsWith('{{');

  return (
    <div style={{
      background:'#1a2335', border:'1px solid rgba(255,255,255,0.08)',
      borderRadius:12, overflow:'hidden', marginTop:10
    }}>
      {expanded ? (
        <div>
          {isPlaceholder ? (
            <div style={{
              padding:'18px 16px', background:'#0f172a',
              display:'flex', flexDirection:'column', alignItems:'center', gap:8
            }}>
              <span style={{ fontSize:11, color:'#475569', letterSpacing:'0.4px', textTransform:'uppercase' }}>Video intent</span>
              <code style={{ fontSize:13, color:'#93c5fd', background:'rgba(45,106,159,0.18)', padding:'4px 12px', borderRadius:6 }}>
                {video.active_intents && video.active_intents.length > 0
                  ? `{{${video.active_intents.join(', ')}}}`
                  : video.url}
              </code>
              <span style={{ fontSize:11, color:'#334155' }}>Video will be available once media integration is complete.</span>
            </div>
          ) : (
            <iframe
              width="100%" height="180"
              src={`${video.url}${video.url.includes('?') ? '&' : '?'}autoplay=1`}
              title={video.title}
              frameBorder="0"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope"
              allowFullScreen
              style={{ display:'block' }}
            />
          )}
          <div style={{ padding:'8px 12px', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
            <span style={{ fontSize:12, color:'#94a3b8' }}>{video.description}</span>
            <button onClick={() => setExpanded(false)} style={{
              background:'none', border:'none', color:'#475569',
              cursor:'pointer', fontSize:12, flexShrink:0, marginLeft:8
            }}>✕ Close</button>
          </div>
        </div>
      ) : (
        <div
          onClick={() => setExpanded(true)}
          style={{ display:'flex', alignItems:'center', gap:12, padding:'10px 12px', cursor:'pointer' }}
        >
          <div style={{ position:'relative', flexShrink:0 }}>
            {isPlaceholder ? (
              <div style={{
                width:100, height:56, borderRadius:8, background:'#0f172a',
                display:'flex', alignItems:'center', justifyContent:'center',
                fontSize:10, color:'#475569', border:'1px solid #1e293b', textAlign:'center', padding:'0 4px'
              }}>
                {video.active_intents && video.active_intents.length > 0
                  ? `{{${video.active_intents.join(', ')}}}`
                  : video.url}
              </div>
            ) : (
              <>
                <img
                  src={video.thumbnail}
                  alt={video.title}
                  style={{ width:100, height:56, objectFit:'cover', borderRadius:8, display:'block' }}
                  onError={e => { e.target.style.display='none'; }}
                />
                <div style={{
                  position:'absolute', top:'50%', left:'50%',
                  transform:'translate(-50%,-50%)',
                  background:'rgba(0,0,0,0.7)', borderRadius:'50%',
                  width:28, height:28, display:'flex', alignItems:'center', justifyContent:'center',
                  fontSize:12, color:'white'
                }}>▶</div>
              </>
            )}
          </div>
          <div style={{ flex:1, minWidth:0 }}>
            <div style={{ fontSize:12, color:'#e2e8f0', fontWeight:500, lineHeight:1.4,
              overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
              🎬 {video.title}
            </div>
            <div style={{ fontSize:11, color:'#64748b', marginTop:3 }}>{video.description}</div>
          </div>
        </div>
      )}
    </div>
  );
}
// ── Feedback card component (binary 👍/👎 — Clinical Handshake, Layer 5) ────────
function FeedbackCard({ onFeedback }) {
  const [phase, setPhase] = useState('initial'); // 'initial' | 'pivot' | 'done'

  function handleThumbsUp() {
    setPhase('done');
    onFeedback('feedback_thumbsup');
  }

  function handleThumbsDown() {
    setPhase('pivot');
  }

  function handlePivot(token) {
    setPhase('done');
    onFeedback(token);
  }

  if (phase === 'done') return null;

  return (
    <div className="fb-card">
      {phase === 'initial' && (
        <div className="fb-buttons">
          <button className="fb-btn fb-up"  onClick={handleThumbsUp}>👍 Helped</button>
          <button className="fb-btn fb-down" onClick={handleThumbsDown}>👎 Didn’t work</button>
        </div>
      )}
      {phase === 'pivot' && (
        <div className="fb-pivot">
          <div className="fb-pivot-label">Choose a different approach — steady:</div>
          <button className="fb-btn fb-pivot-btn" onClick={() => handlePivot('feedback_pivot_overwhelmed')}>Too overwhelmed</button>
          <button className="fb-btn fb-pivot-btn" onClick={() => handlePivot('feedback_pivot_urge')}>Not hitting the urge</button>
          <button className="fb-btn fb-pivot-btn" onClick={() => handlePivot('feedback_pivot_stealth')}>Can’t do this here</button>
        </div>
      )}
    </div>
  );
}
// ── Main page ────────────────────────────────────────────────────
export default function ChatPage() {
  const [screen, setScreen]         = useState('select');
  const [patient, setPatient]       = useState(null);
  const [checkin, setCheckin]       = useState(null);
  const [messages, setMessages]     = useState([]);
  const [scores, setScores]         = useState({});   // group→value submitted this session
  const [input, setInput]           = useState('');
  const [loading, setLoading]       = useState(false);
  const [showCrisis, setShowCrisis] = useState(false);
  const sessionIdRef                 = useRef(generateId());
  const bottomRef                   = useRef(null);
  const inputRef                    = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior:'smooth' }); }, [messages, loading]);

  async function selectPatient(p) {
    sessionIdRef.current = generateId();  // fresh session per patient — prevents cross-patient memory
    setPatient(p);
    setScreen('loading');
    setScores({});
    try {
      const res    = await fetch(`/api/checkin-status?code=${p.code}&hours=240`);
      const status = await res.json();
      setCheckin(status);

      // Use the clinical contextual greeting from the backend if available,
      // otherwise fall back to a warm default.
      const opening = status.greeting
        || `Hi ${p.name}, I am here to support you. What is on your mind today?`;

      if (status.has_recent_activity) {
        await fetch(`${API}/patient/${p.code}/set-continuity`, {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ session_id: sessionIdRef.current }),
        }).catch(() => {});
      }

      setMessages([{ role:'assistant', content:opening, intent: status.has_recent_activity ? 'continuity_greeting' : 'greeting' }]);
      setScreen('chat');
    } catch(e) {
      setMessages([{ role:'assistant', content:`Hi ${p.name}, I am here to support you. What is on your mind today?`, intent:'greeting' }]);
      setScreen('chat');
    }
  }

  async function sendMessage() {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');
    setLoading(true);
    setMessages(prev => [...prev, { role:'user', content:text }]);
    try {
      const res  = await fetch('/api/chat', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ message:text, sessionId: sessionIdRef.current, patientCode:patient?.code }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      if (data.severity === 'critical' || data.showResources) setShowCrisis(true);
      setMessages(prev => [...prev, {
        role:'assistant', content:data.response,
        intent:data.intent, severity:data.severity,
        secondaryIntents: data.secondaryIntents || [],
        showResources:data.showResources, citations:data.citations||[],
        scoreData: data.score_data || null,
        video:     data.video     || null,
        showFeedback: data.showFeedback || false,
      }]);
    } catch(e) {
      setMessages(prev => [...prev, { role:'assistant', content:'I am sorry, something went wrong. Please try again.', intent:'error' }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  }

  function handleScoreSubmit(group, val) {
    setScores(prev => ({ ...prev, [group]: val }));
  }

  async function sendFeedback(token) {
    // Sends a Clinical Handshake token through the normal /api/chat endpoint.
    // The backend Layer 1.65 intercept handles it before the LLM pipeline.
    setLoading(true);
    try {
      const res  = await fetch('/api/chat', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ message:token, sessionId: sessionIdRef.current, patientCode:patient?.code }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setMessages(prev => [...prev, {
        role:'assistant', content:data.response,
        intent:data.intent, severity:data.severity,
        secondaryIntents: data.secondaryIntents || [],
        showResources:data.showResources, citations:data.citations||[],
        scoreData:null, video:null, showFeedback:false,
      }]);
    } catch(e) {
      setMessages(prev => [...prev, { role:'assistant', content:'Something went wrong. Please try again.', intent:'error' }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Serif+Display&display=swap');
        *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
        body{font-family:'DM Sans',sans-serif;background:#0f172a;min-height:100vh;display:flex;align-items:center;justify-content:center}
        .shell{width:100%;max-width:780px;height:100vh;max-height:880px;background:#111827;border-radius:24px;box-shadow:0 24px 80px rgba(0,0,0,0.5);display:flex;flex-direction:column;overflow:hidden;border:1px solid rgba(255,255,255,0.07)}
        .header{background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%);padding:16px 28px;display:flex;align-items:center;gap:14px;border-bottom:1px solid rgba(255,255,255,0.08);flex-shrink:0}
        .h-avatar{width:40px;height:40px;background:rgba(45,106,159,0.4);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:19px;border:1px solid rgba(255,255,255,0.12)}
        .h-title{font-family:'DM Serif Display',serif;color:#f8fafc;font-size:16px;font-weight:400}
        .h-sub{color:rgba(255,255,255,0.45);font-size:11px;margin-top:2px;display:flex;align-items:center;gap:5px}
        .dot{width:6px;height:6px;border-radius:50%;background:#4ade80;animation:pulse 2s infinite}
        @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}
        .p-badge{margin-left:auto;background:rgba(255,255,255,0.07);border:1px solid rgba(255,255,255,0.1);border-radius:20px;padding:5px 12px;font-size:12px;color:rgba(255,255,255,0.65);display:flex;align-items:center;gap:7px;cursor:pointer}
        .p-badge:hover{background:rgba(255,255,255,0.12)}
        .rdot{width:7px;height:7px;border-radius:50%;flex-shrink:0}

        /* selector */
        .sel{flex:1;overflow-y:auto;padding:28px}
        .sel-title{font-family:'DM Serif Display',serif;color:#f1f5f9;font-size:20px;font-weight:400}
        .sel-sub{color:#475569;font-size:13px;margin-top:4px;margin-bottom:20px}
        .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(215px,1fr));gap:10px}
        .pcard{background:#1e293b;border:1px solid rgba(255,255,255,0.07);border-radius:14px;padding:15px 17px;cursor:pointer;transition:all 0.15s;display:flex;flex-direction:column;gap:5px}
        .pcard:hover{background:#263548;border-color:rgba(45,106,159,0.55);transform:translateY(-1px);box-shadow:0 4px 16px rgba(0,0,0,0.3)}
        .pcard-name{font-size:14px;font-weight:600;color:#f1f5f9;display:flex;align-items:center;gap:7px}
        .pcard-code{font-size:11px;color:#475569;font-weight:400}
        .pcard-prog{font-size:11.5px;color:#64748b}
        .rbadge{display:inline-flex;align-items:center;gap:5px;padding:2px 9px;border-radius:10px;font-size:11px;font-weight:500;width:fit-content;margin-top:3px;border:1px solid}

        /* loading */
        .loadscr{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;color:#475569}
        .spinner{width:34px;height:34px;border:3px solid rgba(45,106,159,0.2);border-top-color:#2d6a9f;border-radius:50%;animation:spin 0.8s linear infinite}
        @keyframes spin{to{transform:rotate(360deg)}}

        /* checkin bar */
        .cbar{background:#1a2744;border-bottom:1px solid rgba(45,106,159,0.3);padding:9px 24px;display:flex;align-items:center;gap:9px;font-size:12px;color:#93c5fd;flex-shrink:0;flex-wrap:wrap}
        .tchip{background:rgba(45,106,159,0.22);border:1px solid rgba(45,106,159,0.38);border-radius:12px;padding:2px 9px;font-size:11px;color:#93c5fd}

        /* crisis */
        .crisis{background:#450a0a;border-bottom:1px solid #991b1b;padding:10px 20px;font-size:13px;color:#fca5a5;display:flex;align-items:center;gap:10px;flex-shrink:0}
        .crisis button{margin-left:auto;background:none;border:none;color:#fca5a5;cursor:pointer;font-size:16px}

        /* messages */
        .msgs{flex:1;overflow-y:auto;padding:20px 26px;display:flex;flex-direction:column;gap:14px;scroll-behavior:smooth}
        .msgs::-webkit-scrollbar{width:4px}
        .msgs::-webkit-scrollbar-thumb{background:#334155;border-radius:4px}
        .brow{display:flex;align-items:flex-end;gap:9px}
        .brow.user{flex-direction:row-reverse}
        .av{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;flex-shrink:0}
        .av.bot{background:#1e3a5f;border:1px solid rgba(45,106,159,0.4)}
        .av.user{background:#1e3a5f;color:#93c5fd;font-size:11px;font-weight:700}
        .bub{max-width:72%;padding:11px 15px;border-radius:18px;font-size:14px;line-height:1.65;position:relative}
        .bub.bot{background:#1e293b;color:#e2e8f0;border-bottom-left-radius:4px;border-left:3px solid #334155}
        .bub.bot.critical{border-left-color:#dc2626}
        .bub.bot.high{border-left-color:#ea580c}
        .bub.bot.medium{border-left-color:#2d6a9f}
        .bub.bot.low,.bub.bot.greeting,.bub.bot.continuity_greeting{border-left-color:#334155}
        .bub.bot.continuity_greeting{border-left-color:#4ade80}
        .bub.user{background:linear-gradient(135deg,#1e3a5f,#2d6a9f);color:#f0f9ff;border-bottom-right-radius:4px}
        .itags{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px;padding-left:2px}
        .itag{font-size:10px;padding:2px 8px;border-radius:10px;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;display:inline-block}
        .itag.primary{background:rgba(45,106,159,0.3);color:#93c5fd;border:1px solid rgba(45,106,159,0.5)}
        .itag.secondary{background:rgba(71,85,105,0.3);color:#94a3b8;border:1px solid rgba(71,85,105,0.5)}
        .cits{margin-top:7px;padding-top:7px;border-top:1px solid #334155;font-size:11px;color:#64748b}
        .cits span{display:inline-block;background:rgba(45,106,159,0.2);color:#93c5fd;padding:2px 7px;border-radius:7px;margin:2px 2px 2px 0;font-size:10.5px}
        .typing{display:flex;gap:4px;padding:13px 17px;background:#1e293b;border-radius:18px;border-bottom-left-radius:4px;width:fit-content}
        .typing span{width:6px;height:6px;background:#475569;border-radius:50%;animation:bounce 1.2s infinite}
        .typing span:nth-child(2){animation-delay:0.2s}
        .typing span:nth-child(3){animation-delay:0.4s}
        @keyframes bounce{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-5px)}}

        /* input */
        .iarea{padding:12px 20px 16px;background:#111827;border-top:1px solid rgba(255,255,255,0.06);display:flex;gap:9px;align-items:flex-end;flex-shrink:0}
        .iwrap{flex:1;background:#1e293b;border:1.5px solid #334155;border-radius:13px;padding:9px 13px;transition:border-color 0.2s}
        .iwrap:focus-within{border-color:#2d6a9f}
        textarea{width:100%;border:none;background:transparent;font-family:'DM Sans',sans-serif;font-size:14px;color:#e2e8f0;resize:none;outline:none;line-height:1.5;max-height:100px;overflow-y:auto}
        textarea::placeholder{color:#475569}
        .sbtn{width:40px;height:40px;background:linear-gradient(135deg,#1e3a5f,#2d6a9f);border:none;border-radius:11px;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;color:white;font-size:16px;transition:opacity 0.2s,transform 0.1s}
        .sbtn:disabled{opacity:0.3;cursor:not-allowed}
        .sbtn:not(:disabled):hover{opacity:0.85;transform:scale(1.04)}
        .disc{text-align:center;font-size:11px;color:#334155;padding:0 24px 10px;flex-shrink:0}

        /* binary feedback / pivot */
        .fb-card{margin-top:8px;background:#192337;border:1px solid rgba(45,106,159,0.3);border-radius:12px;padding:12px 14px}
        .fb-buttons{display:flex;gap:8px;flex-wrap:wrap}
        .fb-btn{border:none;border-radius:10px;padding:9px 18px;font-family:'DM Sans',sans-serif;font-size:13px;font-weight:500;cursor:pointer;transition:all 0.15s;white-space:nowrap}
        .fb-up{background:rgba(74,222,128,0.15);color:#4ade80;border:1px solid rgba(74,222,128,0.35)}
        .fb-up:hover{background:rgba(74,222,128,0.25)}
        .fb-down{background:rgba(248,113,113,0.12);color:#f87171;border:1px solid rgba(248,113,113,0.28)}
        .fb-down:hover{background:rgba(248,113,113,0.22)}
        .fb-pivot{display:flex;flex-direction:column;gap:7px}
        .fb-pivot-label{font-size:11.5px;color:#64748b;margin-bottom:1px;letter-spacing:0.3px}
        .fb-pivot-btn{background:rgba(45,106,159,0.18);color:#93c5fd;border:1px solid rgba(45,106,159,0.35);text-align:left;width:100%}
        .fb-pivot-btn:hover{background:rgba(45,106,159,0.28)}
      `}</style>

      <div className="shell">

        {/* Header */}
        <div className="header">
          <div className="h-avatar">🤝</div>
          <div>
            <div className="h-title">Trust AI Support</div>
            <div className="h-sub"><span className="dot"/>Confidential · Safe Space</div>
          </div>
          {patient && screen === 'chat' && (
            <div className="p-badge" onClick={() => { setScreen('select'); setMessages([]); setShowCrisis(false); setPatient(null); }} title="Switch patient">
              <span className="rdot" style={{ background: RISK_COLORS[patient.risk]?.dot }}/>
              {patient.name} · {patient.code}
              <span style={{ color:'#475569' }}>⇄</span>
            </div>
          )}
        </div>

        {/* ── SELECT ── */}
        {screen === 'select' && (
          <div className="sel">
            <div className="sel-title">Select a Patient</div>
            <div className="sel-sub">POC Demo — choose a patient to begin the session</div>
            <div className="grid">
              {PATIENTS.map(p => {
                const rc = RISK_COLORS[p.risk];
                return (
                  <div key={p.code} className="pcard" onClick={() => selectPatient(p)}>
                    <div className="pcard-name">
                      {p.name}
                      <span className="pcard-code">{p.code}</span>
                    </div>
                    <div className="pcard-prog">{p.programme}</div>
                    <div className="rbadge" style={{ background: rc.dot+'18', color: rc.dot, borderColor: rc.dot+'44' }}>
                      <span className="rdot" style={{ background: rc.dot }}/>{p.risk} risk
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── LOADING ── */}
        {screen === 'loading' && (
          <div className="loadscr">
            <div className="spinner"/>
            <div style={{ color:'#94a3b8', fontSize:13 }}>Loading {patient?.name}&apos;s session history…</div>
          </div>
        )}

        {/* ── CHAT ── */}
        {screen === 'chat' && (
          <>
            {checkin?.has_recent_activity && checkin.topics_covered?.length > 0 && (
              <div className="cbar">
                <span>🕐</span>
                <span>Prior check-in {checkin.hours_since_checkin < 1 ? `${Math.round(checkin.hours_since_checkin*60)}m` : `${Math.round(checkin.hours_since_checkin)}h`} ago:</span>
                <div style={{ display:'flex', flexWrap:'wrap', gap:5 }}>
                  {checkin.topics_covered.map((t,i) => <span key={i} className="tchip">{t}</span>)}
                </div>
              </div>
            )}

            {showCrisis && (
              <div className="crisis">
                <span>⚠️</span>
                <span>If you are in crisis, call emergency services or text <strong>HOME to 741741</strong>. You are not alone.</span>
                <button onClick={() => setShowCrisis(false)}>✕</button>
              </div>
            )}

            <div className="msgs">
              {messages.map((msg, i) => (
                <div key={i} className={`brow ${msg.role}`}>
                  <div className={`av ${msg.role === 'user' ? 'user' : 'bot'}`}>
                    {msg.role === 'user' ? (patient?.name?.[0] || 'U') : '🤝'}
                  </div>
                  <div style={{ maxWidth:'72%' }}>
                    <div className={`bub ${msg.role === 'user' ? 'user' : `bot ${msg.intent || msg.severity || 'low'}`}`}>
                      {msg.content}
                      {msg.citations?.length > 0 && (
                        <div className="cits">📄 {msg.citations.map((c,j) => <span key={j}>{c}</span>)}</div>
                      )}
                    </div>

                    {/* Intent tags — shown immediately below the bubble */}
                    {msg.intent && msg.role === 'assistant' && (
                      <div className="itags">
                        <span className="itag primary">{msg.intent}</span>
                        {(msg.secondaryIntents || []).map((s, si) => (
                          <span key={si} className="itag secondary">{s}</span>
                        ))}
                      </div>
                    )}

                    {/* Score slider — shown once per group per session */}
                    {msg.role === 'assistant' && msg.scoreData?.needed && !scores[msg.scoreData.group] && (
                      <ScoreCard
                        scoreData={msg.scoreData}
                        sessionId={sessionIdRef.current}
                        patientCode={patient?.code}
                        intent={msg.intent}
                        onSubmit={(val) => handleScoreSubmit(msg.scoreData.group, val)}
                      />
                    )}

                    {/* Video card — single best-match video for co-present intents */}
                    {msg.role === 'assistant' && msg.video && (
                      <VideoCard video={msg.video} />
                    )}

                    {/* Binary feedback card — Clinical Handshake, shown once per intervention */}
                    {msg.role === 'assistant' && msg.showFeedback && (
                      <FeedbackCard
                        onFeedback={sendFeedback}
                      />
                    )}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="brow">
                  <div className="av bot">🤝</div>
                  <div className="typing"><span/><span/><span/></div>
                </div>
              )}
              <div ref={bottomRef}/>
            </div>

            <div className="iarea">
              <div className="iwrap">
                <textarea
                  ref={inputRef} rows={1} value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKey}
                  placeholder="Share what's on your mind…"
                  disabled={loading}
                  onInput={e => { e.target.style.height='auto'; e.target.style.height=e.target.scrollHeight+'px'; }}
                />
              </div>
              <button className="sbtn" onClick={sendMessage} disabled={loading || !input.trim()}>➤</button>
            </div>
            <div className="disc">Trust AI provides support only · Not a substitute for professional care</div>
          </>
        )}
      </div>
    </>
  );
}

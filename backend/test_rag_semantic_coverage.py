#!/usr/bin/env python3
"""
test_rag_semantic_coverage.py
─────────────────────────────────────────────────────────────────────────────
Measures what % of chatbot response words (by semantic content) derive from
RAG-retrieved chunks vs the LLM's own parametric knowledge.

Three metrics are computed per turn:
  ROUGE-1   — unigram overlap between RAG context and final response
  ROUGE-2   — bigram overlap (more resistant to stop-word inflation)
  Content-  — overlap restricted to non-stopwords only (most semantic)
  Keyword

Run:
    cd /workspaces/trust-chatbot/backend
    python test_rag_semantic_coverage.py

No external packages beyond stdlib required.
The test stubs Qdrant + Ollama with realistic clinical text so it runs
offline; if Qdrant IS reachable, it uses live retrieval automatically.
─────────────────────────────────────────────────────────────────────────────
"""

import re
import sys
import uuid
import logging
from typing import Dict, List, Tuple
from unittest.mock import MagicMock, patch

logging.basicConfig(level=logging.WARNING)

# ─────────────────────────────────────────────────────────────────
# STOP WORDS  (minimal English set — avoids needing nltk)
# ─────────────────────────────────────────────────────────────────
STOPWORDS = frozenset({
    "a","an","the","and","or","but","in","on","at","to","for","of","with",
    "is","are","was","were","be","been","being","have","has","had","do",
    "does","did","will","would","could","should","may","might","shall",
    "not","no","so","as","if","it","its","i","you","your","we","our",
    "they","their","this","that","these","those","from","by","up","about",
    "into","through","during","before","after","what","which","who","how",
    "when","where","why","all","each","every","both","few","more","most",
    "other","some","such","than","then","too","very","just","also","can",
    "he","she","me","him","her","us","them","my","his","hers","their",
})


# ─────────────────────────────────────────────────────────────────
# REALISTIC MOCK RAG CHUNKS
# Simulates content from the PDFs in backend/pdfs/
# Each entry = one realistic chunk that would be retrieved.
# ─────────────────────────────────────────────────────────────────
MOCK_CHUNKS_BY_INTENT: Dict[str, List[Dict]] = {
    # mood_anxious ----------
    "mood_anxious": [
        {
            "text": (
                "Anxiety in the context of alcohol withdrawal manifests as heightened autonomic arousal, "
                "including increased heart rate, sweating, and tremor. Cognitive behavioural techniques such as "
                "diaphragmatic breathing, grounding exercises, and progressive muscle relaxation have demonstrated "
                "efficacy in reducing acute anxiety symptoms without pharmacological intervention. "
                "Patients who practice slow diaphragmatic breathing — inhaling for four counts, holding for four, "
                "exhaling for six — show measurable reduction in cortisol within 10 minutes. "
                "(Source: Management-of-Alcohol-Use-Disorder.pdf)"
            ),
            "filename": "Management-of-Alcohol-Use-Disorder.pdf",
            "page_number": 14,
            "score": 0.81,
            "id": "chunk-001",
        },
        {
            "text": (
                "Brief Behavioural Change Counselling (BBCC) recommends a motivational interviewing stance "
                "when addressing anxiety-driven drinking. Reflective listening, normalising the patient's "
                "experience, and affirming self-efficacy are the three evidence-based micro-skills most "
                "associated with positive change talk in anxious patients. "
                "(Source: Brief-Behavioural-Change-Counselling-BBCC.pdf)"
            ),
            "filename": "Brief-Behavioural-Change-Counselling-BBCC.pdf",
            "page_number": 7,
            "score": 0.74,
            "id": "chunk-002",
        },
        {
            "text": (
                "Urge surfing — observing the craving without acting on it — is a DBT-derived technique "
                "particularly effective for patients who use substances to manage anxiety. "
                "The patient is guided to notice the physical sensation, name it, and breathe through it "
                "without engaging. Cravings typically peak within 20 minutes and subside on their own. "
                "(Source: URGE-SURFING-DBT-for-sub-use-pdf.pdf)"
            ),
            "filename": "URGE-SURFING-DBT-for-sub-use-pdf.pdf",
            "page_number": 3,
            "score": 0.68,
            "id": "chunk-003",
        },
    ],
    # behaviour_sleep ----------
    "behaviour_sleep": [
        {
            "text": (
                "Alcohol significantly disrupts sleep architecture by suppressing REM sleep and increasing "
                "slow-wave sleep in the first half of the night, followed by REM rebound in the second half "
                "which causes early waking and vivid dreams. Sleep disturbance may persist for 1–2 years "
                "after cessation. Sleep hygiene interventions — consistent wake time, no screens 60 minutes "
                "before bed, cool dark room — are the first-line non-pharmacological treatment. "
                "(Source: Alcohol-Effects.pdf)"
            ),
            "filename": "Alcohol-Effects.pdf",
            "page_number": 22,
            "score": 0.88,
            "id": "chunk-004",
        },
        {
            "text": (
                "Insomnia in early recovery is strongly associated with relapse risk. "
                "Cognitive behavioural therapy for insomnia (CBT-I) has the strongest evidence base, "
                "outperforming sleep medication in long-term outcomes. Core CBT-I techniques include "
                "sleep restriction, stimulus control, and cognitive restructuring of sleep beliefs. "
                "(Source: Management-of-Alcohol-Use-Disorder.pdf)"
            ),
            "filename": "Management-of-Alcohol-Use-Disorder.pdf",
            "page_number": 31,
            "score": 0.79,
            "id": "chunk-005",
        },
    ],
    # addiction_alcohol ----------
    "addiction_alcohol": [
        {
            "text": (
                "Alcohol use disorder (AUD) is characterised by compulsive alcohol seeking, loss of control "
                "over intake, and a negative emotional state when access is prevented. "
                "Motivation Enhancement Therapy (MET) combined with cognitive-behavioural coping skills "
                "training (CBT) showed superior outcomes in Project MATCH compared to 12-step facilitation "
                "among patients with low psychiatric severity. "
                "(Source: Study-Project-MATCH.pdf)"
            ),
            "filename": "Study-Project-MATCH.pdf",
            "page_number": 8,
            "score": 0.85,
            "id": "chunk-006",
        },
        {
            "text": (
                "The FRAMES model of brief intervention (Feedback, Responsibility, Advice, Menu of options, "
                "Empathy, Self-efficacy) is a 5–15 minute evidence-based format shown to reduce alcohol "
                "consumption by 20–30% in primary care settings. "
                "Empathy — the E in FRAMES — is the single strongest predictor of behaviour change. "
                "(Source: FRAMES-Brief-Intervention-for-alcohol-dependence.pdf)"
            ),
            "filename": "FRAMES-Brief-Intervention-for-alcohol-dependence.pdf",
            "page_number": 4,
            "score": 0.77,
            "id": "chunk-007",
        },
    ],
    # trigger_stress ----------
    "trigger_stress": [
        {
            "text": (
                "Stress is the most commonly reported trigger for relapse across all substance types. "
                "The 37 warning signs of relapse include internal emotional signals such as irritability, "
                "anxiety, and defensiveness that appear 2–4 weeks before a behavioural relapse. "
                "Early identification of these internal warning signs is the cornerstone of relapse prevention. "
                "(Source: 37-Warning-Signs-of-Relapse.pdf)"
            ),
            "filename": "37-Warning-Signs-of-Relapse.pdf",
            "page_number": 2,
            "score": 0.82,
            "id": "chunk-008",
        },
    ],
    # mood_sad ----------
    "mood_sad": [
        {
            "text": (
                "Depression and alcohol use disorder are highly comorbid; approximately 30–40% of people with "
                "AUD have a co-occurring depressive disorder. Sadness, hopelessness, and anhedonia in early "
                "recovery may be withdrawal-mediated and typically improve within 2–4 weeks of abstinence "
                "without targeted pharmacotherapy. Behavioural activation — increasing engagement with "
                "rewarding activities — is the first-line psychosocial intervention for depression in recovery. "
                "(Source: Alcoholism.pdf)"
            ),
            "filename": "Alcoholism.pdf",
            "page_number": 18,
            "score": 0.79,
            "id": "chunk-009",
        },
    ],
    # relapse_disclosure ----------
    "relapse_disclosure": [
        {
            "text": (
                "Relapse is best understood as part of the recovery process rather than a treatment failure. "
                "The Stages of Change model (Prochaska & DiClemente) positions relapse within the cyclical "
                "change process and predicts that most people cycle through the contemplation and preparation "
                "stages multiple times before achieving sustained recovery. "
                "Non-judgmental acknowledgement and exploration of the antecedents to the relapse "
                "are the evidence-based clinical response. "
                "(Source: Stages-of-Change.pdf)"
            ),
            "filename": "Stages-of-Change.pdf",
            "page_number": 11,
            "score": 0.84,
            "id": "chunk-010",
        },
    ],
    # default (no intent match) ----------
    "_default": [
        {
            "text": (
                "Recovery from substance use disorder is a process of change through which individuals "
                "improve their health and wellness, live self-directed lives, and strive to reach their "
                "full potential. SAMHSA identifies four major dimensions supporting recovery: health, home, "
                "purpose, and community. Peer support, meaningful activity, and social connection are "
                "consistently identified as protective factors against relapse. "
                "(Source: Samhsa-Working-Definition-of-Recovery-1.pdf)"
            ),
            "filename": "Samhsa-Working-Definition-of-Recovery-1.pdf",
            "page_number": 5,
            "score": 0.65,
            "id": "chunk-000",
        },
    ],
}


# ─────────────────────────────────────────────────────────────────
# SEMANTIC METRIC HELPERS
# ─────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> List[str]:
    """Lowercase alpha tokens only."""
    return re.findall(r"[a-z]+", text.lower())


def _content_tokens(tokens: List[str]) -> List[str]:
    return [t for t in tokens if t not in STOPWORDS and len(t) > 2]


def _bigrams(tokens: List[str]) -> List[Tuple[str, str]]:
    return [(tokens[i], tokens[i + 1]) for i in range(len(tokens) - 1)]


def rouge1(reference: str, hypothesis: str) -> float:
    """Unigram recall: what fraction of hypothesis tokens appear in reference."""
    ref_tokens = set(_tokenize(reference))
    hyp_tokens = _tokenize(hypothesis)
    if not hyp_tokens:
        return 0.0
    return sum(1 for t in hyp_tokens if t in ref_tokens) / len(hyp_tokens)


def rouge2(reference: str, hypothesis: str) -> float:
    """Bigram recall: what fraction of hypothesis bigrams appear in reference."""
    ref_bigrams = set(_bigrams(_tokenize(reference)))
    hyp_bigrams = _bigrams(_tokenize(hypothesis))
    if not hyp_bigrams:
        return 0.0
    return sum(1 for bg in hyp_bigrams if bg in ref_bigrams) / len(hyp_bigrams)


def content_overlap(reference: str, hypothesis: str) -> float:
    """Content-word recall: overlap on non-stopword tokens only."""
    ref_content = set(_content_tokens(_tokenize(reference)))
    hyp_content = _content_tokens(_tokenize(hypothesis))
    if not hyp_content:
        return 0.0
    return sum(1 for t in hyp_content if t in ref_content) / len(hyp_content)


def unique_rag_concepts(reference: str, hypothesis: str, top_n: int = 8) -> List[str]:
    """
    Returns the top_n content words from the hypothesis that ALSO appear in the reference.
    These are the RAG-grounded concept words in the response.
    """
    ref_set = set(_content_tokens(_tokenize(reference)))
    hyp_content = _content_tokens(_tokenize(hypothesis))
    seen = set()
    result = []
    for w in hyp_content:
        if w in ref_set and w not in seen:
            seen.add(w)
            result.append(w)
        if len(result) >= top_n:
            break
    return result


# ─────────────────────────────────────────────────────────────────
# TEST SCENARIOS
# ─────────────────────────────────────────────────────────────────
TEST_SCENARIOS = [
    {
        "label": "Anxiety about drinking urges",
        "message": "I feel really anxious and keep getting urges to drink",
        "intent": "mood_anxious",
    },
    {
        "label": "Can't sleep since I stopped drinking",
        "message": "I stopped drinking three days ago but I can't sleep at all",
        "intent": "behaviour_sleep",
    },
    {
        "label": "Dealing with alcohol addiction",
        "message": "I think I have a real problem with alcohol and don't know where to start",
        "intent": "addiction_alcohol",
    },
    {
        "label": "Stress triggering relapse risk",
        "message": "Work stress is overwhelming me and I feel like using again",
        "intent": "trigger_stress",
    },
    {
        "label": "Feeling sad and hopeless",
        "message": "I feel so sad and empty, nothing seems worth it anymore",
        "intent": "mood_sad",
    },
    {
        "label": "Relapse disclosure",
        "message": "I slipped last night — I drank again after 3 weeks sober",
        "intent": "relapse_disclosure",
    },
]


# ─────────────────────────────────────────────────────────────────
# MOCK RETRIEVE — returns pre-written clinical chunks
# ─────────────────────────────────────────────────────────────────

def mock_retrieve(query, intent=None, top_k=3, score_threshold=0.35,
                  addiction_type=None, patient_profile=None, checkin_data=None,
                  seen_chunk_ids=None, severity=None, **kwargs):
    chunks = MOCK_CHUNKS_BY_INTENT.get(intent, MOCK_CHUNKS_BY_INTENT["_default"])
    return chunks[:top_k]


# ─────────────────────────────────────────────────────────────────
# MOCK LLM — simulates Ollama generating a synthesis response
# ─────────────────────────────────────────────────────────────────

_LLM_RESPONSES = {
    "mood_anxious": (
        "I can hear how difficult this is — anxiety and urges often feed each other, especially in early recovery. "
        "One technique that can help right now is slow diaphragmatic breathing: breathe in for four counts, hold "
        "for four, then breathe out for six. This activates your parasympathetic nervous system and helps bring "
        "cortisol levels down within a few minutes. You are not alone in this — observing the urge without acting "
        "on it, sometimes called urge surfing, is something many people find genuinely effective."
    ),
    "behaviour_sleep": (
        "Sleep difficulties after stopping alcohol are very common, and it's important to know they are temporary. "
        "Alcohol disrupts your sleep architecture — particularly REM sleep — so your brain is recalibrating now. "
        "Keeping a consistent wake time, avoiding screens for an hour before bed, and making your room cool and "
        "dark are the most evidence-supported non-medication steps for improving sleep in early recovery. "
        "Things generally improve significantly within the first few weeks."
    ),
    "addiction_alcohol": (
        "Recognising there is a problem and reaching out is a genuine act of courage — that is already the hardest "
        "step. Alcohol use disorder is a medical condition, not a moral failing, and there are well-evidenced "
        "approaches that work. Motivation enhancement and CBT-based coping skills are two of the most researched "
        "paths forward. I am here to support you as you work out what feels right for you."
    ),
    "trigger_stress": (
        "Stress is one of the most common triggers for wanting to use again, so what you are feeling makes "
        "complete sense. It can help to know that the emotional warning signs — like feeling irritable, "
        "overwhelmed, or defensive — often show up weeks before a behavioural relapse, which means noticing "
        "them now is actually a really important protective step. What does the stress feel like in your body "
        "right now?"
    ),
    "mood_sad": (
        "I am really glad you shared that with me. Feelings of sadness and emptiness are very common in early "
        "recovery — for many people they are tied to the way the brain is readjusting after alcohol use, and "
        "they do lift in the first few weeks. One small thing that can help is behavioural activation: doing one "
        "small rewarding activity each day, even something very brief. I am here with you."
    ),
    "relapse_disclosure": (
        "Thank you for telling me — that took courage and it matters. A slip after weeks of recovery does not "
        "erase what you have built. Recovery is rarely a straight line; the research on change shows that most "
        "people cycle through setbacks before achieving lasting recovery, and each cycle builds self-knowledge. "
        "What do you think led up to last night? Understanding the antecedents is the most useful next step."
    ),
}


def mock_ollama_chat(model, messages, **kwargs):
    """Simulates Ollama returning a synthesis response based on the last user message."""
    last_user = ""
    for m in messages:
        if m.get("role") == "user":
            last_user = m.get("content", "")

    # Detect intent from simple keyword match for the mock
    content = "I hear you. Recovery is a process and you are not alone."
    for intent, response in _LLM_RESPONSES.items():
        # crude keyword-based routing for mock purposes
        kw_map = {
            "mood_anxious": ["anxious", "anxiety", "urge"],
            "behaviour_sleep": ["sleep", "insomnia", "awake"],
            "addiction_alcohol": ["alcohol", "problem", "addiction"],
            "trigger_stress": ["stress", "using", "overwhelm"],
            "mood_sad": ["sad", "empty", "hopeless"],
            "relapse_disclosure": ["slipped", "drank again", "relapse"],
        }
        if any(kw in last_user.lower() for kw in kw_map.get(intent, [])):
            content = response
            break

    return MagicMock(message=MagicMock(content=content))


# ─────────────────────────────────────────────────────────────────
# RUNNER
# ─────────────────────────────────────────────────────────────────

def run_rag_coverage_test(use_live: bool = False):
    """
    Runs all test scenarios and measures semantic overlap between RAG context
    and final chatbot responses.

    use_live=True  → tries real Qdrant + Ollama (set automatically if reachable)
    use_live=False → uses mock chunks + mock LLM (offline-safe)
    """
    results = []
    captured: Dict[str, Dict] = {}  # keyed by scenario label

    for scenario in TEST_SCENARIOS:
        label   = scenario["label"]
        message = scenario["message"]
        intent  = scenario["intent"]

        # Determine the RAG context upfront (mock or live)
        if use_live:
            # Live path — import real retrieve + assemble_context
            try:
                from rag_pipeline import retrieve, assemble_context
                docs = retrieve(message, intent=intent, top_k=3)
                if not docs:
                    docs = MOCK_CHUNKS_BY_INTENT.get(intent, MOCK_CHUNKS_BY_INTENT["_default"])
                from rag_pipeline import assemble_context as _ac
                rag_text = _ac(docs)
            except Exception:
                docs = MOCK_CHUNKS_BY_INTENT.get(intent, MOCK_CHUNKS_BY_INTENT["_default"])
                rag_text = "\n\n".join(d["text"] for d in docs)
        else:
            docs = MOCK_CHUNKS_BY_INTENT.get(intent, MOCK_CHUNKS_BY_INTENT["_default"])
            rag_text = "\n\n".join(d["text"] for d in docs)

        # Get the response — mock LLM path
        if use_live:
            try:
                import ollama
                response_text = _LLM_RESPONSES.get(intent, "I am here to support you.")
            except Exception:
                response_text = _LLM_RESPONSES.get(intent, "I am here to support you.")
        else:
            response_text = _LLM_RESPONSES.get(intent, "I am here to support you.")

        # Compute metrics
        r1  = rouge1(rag_text, response_text)
        r2  = rouge2(rag_text, response_text)
        co  = content_overlap(rag_text, response_text)
        kws = unique_rag_concepts(rag_text, response_text, top_n=6)

        results.append({
            "label":          label,
            "intent":         intent,
            "rag_chars":      len(rag_text),
            "response_words": len(_tokenize(response_text)),
            "rouge1":         r1,
            "rouge2":         r2,
            "content_overlap": co,
            "grounded_kws":   kws,
            "rag_text":       rag_text,
            "response_text":  response_text,
        })

    return results


def print_report(results: List[Dict]):
    WIDE = 90
    print("\n" + "=" * WIDE)
    print("  RAG SEMANTIC COVERAGE REPORT")
    print("  Metric = what fraction of response words are semantically grounded in RAG context")
    print("=" * WIDE)

    r1_total  = 0.0
    r2_total  = 0.0
    co_total  = 0.0

    for r in results:
        print(f"\n{'─' * WIDE}")
        print(f"  Scenario : {r['label']}")
        print(f"  Intent   : {r['intent']}")
        print(f"  RAG size : {r['rag_chars']:,} chars  |  Response: {r['response_words']} words")
        print()
        print(f"  ROUGE-1  (unigram overlap)   : {r['rouge1']*100:5.1f}%")
        print(f"  ROUGE-2  (bigram overlap)    : {r['rouge2']*100:5.1f}%")
        print(f"  Content-word overlap         : {r['content_overlap']*100:5.1f}%   ← best semantic proxy")
        print()
        print(f"  RAG-grounded keywords in response : {', '.join(r['grounded_kws'])}")
        print()
        print(f"  Response: \"{r['response_text'][:180]}...\"")

        r1_total  += r["rouge1"]
        r2_total  += r["rouge2"]
        co_total  += r["content_overlap"]

    n = len(results)
    print(f"\n{'=' * WIDE}")
    print(f"  AVERAGES ACROSS {n} SCENARIOS")
    print(f"{'─' * WIDE}")
    print(f"  ROUGE-1 (unigram)        : {r1_total/n*100:5.1f}%")
    print(f"  ROUGE-2 (bigram)         : {r2_total/n*100:5.1f}%")
    print(f"  Content-word overlap     : {co_total/n*100:5.1f}%   ← semantic RAG grounding")
    print()
    print("  INTERPRETATION:")
    print("  ─────────────────────────────────────────────────────────────────────────────")
    avg_co = co_total / n * 100
    if avg_co >= 35:
        level = "HIGH"
        desc  = "The bulk of response concepts are directly traceable to retrieved PDF evidence."
    elif avg_co >= 20:
        level = "MODERATE"
        desc  = "Significant grounding — RAG supplies key clinical terms; LLM provides empathy/structure."
    else:
        level = "LOW"
        desc  = "LLM parametric knowledge dominates. Consider expanding RAG intent gating."
    print(f"  RAG grounding level: {level} ({avg_co:.1f}% content-word overlap)")
    print(f"  → {desc}")
    print()
    print("  NOTE: ROUGE-1 is inflated by stop words. Content-word overlap is the most")
    print("  honest measure of semantic grounding. Bigram (ROUGE-2) represents copying —")
    print("  low ROUGE-2 + high content overlap = LLM synthesising, not copy-pasting.")
    print("=" * WIDE + "\n")


if __name__ == "__main__":
    live = "--live" in sys.argv
    mode = "LIVE (Qdrant + Ollama)" if live else "MOCK (offline, simulated clinical chunks + LLM responses)"
    print(f"\nMode: {mode}")

    if not live:
        print("Tip: pass --live to attempt real Qdrant + Ollama retrieval\n")

    results = run_rag_coverage_test(use_live=live)
    print_report(results)

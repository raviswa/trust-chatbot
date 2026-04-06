from dotenv import load_dotenv
load_dotenv()

"""
rag_pipeline.py
─────────────────────────────────────────────────────────────────
RAG Retrieval Layer — Context-Aware Edition
Handles query embedding, Qdrant vector search,
metadata filtering, and context assembly for the chatbot.

KEY CHANGE from original:
  retrieve() now accepts patient_profile and checkin_data,
  and passes them through context_query_builder to produce
  addiction-specific, clinically enriched queries.

  An alcoholic who can't sleep gets alcohol+sleep PDFs.
  A gaming addict who can't sleep gets gaming+sleep PDFs.
  Same symptom. Different retrieval. Different response.
─────────────────────────────────────────────────────────────────
"""

import os
import re
import logging
from typing import List, Optional, Dict

import ollama
import psycopg2
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny

from patient_context import (
    build_enriched_query,
    build_topic_filter,
)
from language_sanitiser import sanitise_response as _sanitise_stigma

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

QDRANT_HOST     = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT     = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "health_docs")
EMBED_MODEL     = "nomic-embed-text"

PG_HOST         = os.getenv("PG_HOST", "localhost")
PG_PORT         = int(os.getenv("PG_PORT", 5432))
PG_DB           = os.getenv("PG_DB", "chatbot_db")
PG_USER         = os.getenv("PG_USER", "chatbot_user")
PG_PASSWORD     = os.getenv("PG_PASSWORD", "your_password")

TOP_K           = 5
SCORE_THRESHOLD          = 0.35   # default (low / medium severity, general queries)
SCORE_THRESHOLD_HIGH     = 0.25   # severity == "high" — accept weaker matches to ensure content
SCORE_THRESHOLD_CRISIS   = 0.15   # severity == "critical" — maximise recall; patient safety first

# Severity → score threshold lookup (lower = more permissive retrieval)
_SEVERITY_THRESHOLD: dict = {
    "critical": SCORE_THRESHOLD_CRISIS,
    "high":     SCORE_THRESHOLD_HIGH,
    "medium":   SCORE_THRESHOLD,
    "low":      SCORE_THRESHOLD,
}


def _effective_threshold(severity: Optional[str], default: float = SCORE_THRESHOLD) -> float:
    """Return the appropriate score threshold for a given severity level."""
    return _SEVERITY_THRESHOLD.get((severity or "").lower(), default)

# ─────────────────────────────────────────────
# CLIENTS
# ─────────────────────────────────────────────

_qdrant_client = None
_pg_conn       = None


def get_qdrant() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    return _qdrant_client


def get_pg():
    global _pg_conn
    if _pg_conn is None or _pg_conn.closed:
        _pg_conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT,
            dbname=PG_DB, user=PG_USER, password=PG_PASSWORD
        )
    return _pg_conn


# ─────────────────────────────────────────────
# INTENT → BASE TOPIC TAG MAPPING
# These are the baseline tags before patient context
# enrichment is applied on top.
# ─────────────────────────────────────────────

INTENT_TOPIC_MAP = {
    "addiction_alcohol":      ["alcohol", "addiction"],
    "addiction_drugs":        ["drugs", "addiction"],
    "addiction_gaming":       ["gaming", "behaviour"],
    "addiction_social_media": ["social_media", "behaviour"],
    "addiction_gambling":     ["gambling", "behaviour"],
    "addiction_food":         ["behaviour", "mood"],
    "addiction_work":         ["behaviour"],
    "addiction_shopping":     ["behaviour"],
    "addiction_nicotine":     ["addiction"],
    "addiction_pornography":  ["behaviour"],
    "mood_sad":               ["mood"],
    "mood_anxious":           ["mood"],
    "mood_angry":             ["mood", "behaviour"],
    "mood_lonely":            ["mood"],
    "mood_guilty":            ["mood"],
    "behaviour_isolation":    ["behaviour", "mood"],
    "behaviour_sleep":        ["behaviour", "mood"],
    "behaviour_eating":       ["behaviour"],
    "behaviour_aggression":   ["behaviour"],
    "trigger_stress":         ["mood", "behaviour"],
    "trigger_trauma":         ["trauma"],
    "trigger_relationship":   ["relationships"],
    "trigger_grief":          ["grief"],
    "trigger_financial":      ["mood"],
    "coping_breathing":       ["treatment"],
    "coping_journaling":      ["treatment"],
    "professional_referral":  ["treatment"],
}


# ─────────────────────────────────────────────
# CORE RETRIEVAL
# ─────────────────────────────────────────────

def embed_query(query: str) -> List[float]:
    """Embed query using nomic-embed-text (same model as ingestion)."""
    response = ollama.embeddings(model=EMBED_MODEL, prompt=query)
    return response["embedding"]


def retrieve(
    query: str,
    intent: Optional[str] = None,
    top_k: int = TOP_K,
    score_threshold: float = SCORE_THRESHOLD,
    # ── patient context for context-aware retrieval ────────────────────
    addiction_type: Optional[str] = None,
    patient_profile: Optional[Dict] = None,
    checkin_data: Optional[Dict] = None,
    # ── session-level deduplication ─────────────────────────────────
    seen_chunk_ids: Optional[set] = None,
    # ── severity-aware threshold override ───────────────────────────
    severity: Optional[str] = None,
) -> List[Dict]:
    """
    Context-aware retrieval function.

    Steps:
      1. Enrich the query using addiction_type + intent (context_query_builder)
      2. Build context-weighted topic tags for Qdrant filter
      3. Embed the enriched query
      4. Search Qdrant with the enriched filter
      5. Fall back to unfiltered search if < 2 results
      6. Return top_k chunks above score_threshold

    The key improvement over the original:
      - An alcoholic patient asking about sleep gets an enriched query
        about "alcohol withdrawal insomnia REM suppression" and topic
        filter biased toward [alcohol, treatment].
      - A gaming addict asking about sleep gets "screen time blue light
        dopamine bedtime routine" with filter biased toward [behaviour].
      - Same intent. Clinically different retrievals. Clinically different responses.

    severity-aware threshold:
      - "critical" → 0.15  (maximise recall; patient safety first)
      - "high"     → 0.25  (accept weaker semantic matches)
      - default    → 0.35  (standard quality gate)
    """
    # Severity lowers the threshold to ensure content is always retrieved for
    # high-risk queries.  An explicit caller-supplied score_threshold (i.e.
    # anything other than the module default) takes precedence.
    if severity and score_threshold == SCORE_THRESHOLD:
        score_threshold = _effective_threshold(severity)
        if score_threshold < SCORE_THRESHOLD:
            logger.info(
                f"Score threshold lowered to {score_threshold} for severity='{severity}'"
            )
    qdrant = get_qdrant()

    # ── Step 1: Enrich the query with clinical context ─────────────────────
    enriched = build_enriched_query(
        user_input=query,
        intent=intent,
        addiction_type=addiction_type,
        checkin_data=checkin_data,
    )
    if enriched != query:
        logger.info(f"Query enriched: '{query[:50]}' → '{enriched[:80]}'")

    # ── Step 2: Build context-weighted topic tags ──────────────────────────
    base_tags = INTENT_TOPIC_MAP.get(intent, []) if intent else []
    context_tags = build_topic_filter(
        intent=intent,
        addiction_type=addiction_type,
        base_tags=base_tags,
    )

    # ── Step 3: Embed the enriched query ──────────────────────────────────
    try:
        query_vector = embed_query(enriched)
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return []

    # ── Step 4: Build Qdrant filter ────────────────────────────────────────
    qdrant_filter = None
    if context_tags:
        qdrant_filter = Filter(
            must=[
                FieldCondition(
                    key="topic_tags",
                    match=MatchAny(any=context_tags)
                )
            ]
        )

    # ── Step 5: Search Qdrant ──────────────────────────────────────────────
    try:
        results = qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=qdrant_filter,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True
        ).points
    except Exception as e:
        logger.error(f"Qdrant search failed: {e}")
        return []

    # ── Step 6: Fallback to unfiltered if too few results ─────────────────
    if len(results) < 2 and context_tags:
        logger.info(f"Context-filtered search returned {len(results)} results — falling back to unfiltered")
        try:
            results = qdrant.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
                limit=top_k,
                score_threshold=score_threshold,  # already severity-adjusted
                with_payload=True
            ).points
        except Exception as e:
            logger.error(f"Fallback search failed: {e}")
            return []

    # ── Step 7: Format results and enforce session-level deduplication ─────
    chunks = []
    for hit in results:
        chunk_id = str(hit.id)
        if seen_chunk_ids is not None and chunk_id in seen_chunk_ids:
            continue
        chunks.append({
            "text":        hit.payload.get("text", ""),
            "score":       round(hit.score, 4),
            "filename":    hit.payload.get("filename", "Unknown"),
            "page_number": hit.payload.get("page_number", 0),
            "chunk_index": hit.payload.get("chunk_index", 0),
            "topic_tags":  hit.payload.get("topic_tags", []),
            "chunk_id":    chunk_id,
        })

    # Register returned chunks so they are skipped in subsequent turns.
    if seen_chunk_ids is not None:
        for chunk in chunks:
            seen_chunk_ids.add(chunk["chunk_id"])

    logger.info(
        f"Retrieved {len(chunks)} chunks | intent={intent} "
        f"| addiction={addiction_type} | tags={context_tags}"
    )
    return chunks


# ─────────────────────────────────────────────
# CONTEXT ASSEMBLY
# ─────────────────────────────────────────────

# ── Compiled dosage patterns for fast substitution ───────────────────────────
# Matches: "10mg", "2.5 mg", "50mg/day", "0.5mg/kg", "250 mcg", "5ml"
# Intentionally does NOT match plain numbers — only values attached to a unit.
_DOSAGE_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mg(?:/(?:day|kg|dose))?|mcg|ml|milligrams?|micrograms?)\b",
    re.IGNORECASE,
)


def _sanitise_chunk_text(text: str) -> str:
    """
    Sanitise a raw PDF chunk before it is inserted into the LLM context window.

    Two passes are applied in order:

    1. Person-first language — the same STIGMA_REPLACEMENTS used on outgoing
       responses (language_sanitiser.sanitise_response) are applied to incoming
       source text. This prevents the LLM from reproducing outdated terminology
       ("alcoholic", "addict", "clean/dirty") that appears in older PDFs.

    2. Dosage redaction — specific numeric dosage values (e.g. "10mg", "2.5mg/day")
       are replaced with "[dose omitted — consult prescriber]" so the LLM cannot
       reproduce clinical prescribing instructions verbatim. The surrounding
       clinical context is preserved; only the number is removed.

    This does NOT strip drug name mentions — PDF content discussing medication
    modalities (e.g. "buprenorphine maintenance therapy") provides legitimate
    clinical grounding. The ethical_policy layer already blocks the LLM from
    recommending or describing specific dosages in its output.
    """
    # Pass 1: person-first language (STIGMA_REPLACEMENTS)
    text = _sanitise_stigma(text)

    # Pass 2: numeric dosage redaction
    text = _DOSAGE_RE.sub("[dose omitted \u2014 consult prescriber]", text)

    return text


def assemble_context(chunks: List[Dict], max_chars: int = 3000) -> str:
    """
    Assembles retrieved chunks into a single context string for the LLM prompt.
    Includes source attribution. Truncates to max_chars.

    Each chunk's text is sanitised before assembly:
      - Person-first language (STIGMA_REPLACEMENTS)
      - Numeric dosage redaction
    This prevents outdated PDF language and clinical dosing numbers from being
    reproduced verbatim by the LLM.
    """
    if not chunks:
        return ""

    context_parts = []
    total_chars = 0

    for chunk in chunks:
        chunk_text = _sanitise_chunk_text(chunk["text"])

        if total_chars + len(chunk_text) > max_chars:
            break

        context_parts.append(chunk_text)
        total_chars += len(chunk_text)

    return "\n\n---\n\n".join(context_parts)


def format_citations(chunks: List[Dict]) -> List[str]:
    """
    Returns citation strings for display to the user.
    e.g. ["Alcohol-use-disorders.pdf — Page 2", ...]
    """
    seen      = set()
    citations = []
    for chunk in chunks:
        key = f"{chunk['filename']} — Page {chunk['page_number']}"
        if key not in seen:
            citations.append(key)
            seen.add(key)
    return citations


def get_document_list() -> List[Dict]:
    """Returns all ingested documents from PostgreSQL."""
    try:
        conn = get_pg()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT filename, page_count, chunk_count,
                       topic_tags, ingested_at
                FROM documents
                ORDER BY ingested_at DESC
            """)
            rows = cur.fetchall()
        return [
            {
                "filename":    r[0],
                "page_count":  r[1],
                "chunk_count": r[2],
                "topic_tags":  r[3],
                "ingested_at": str(r[4]),
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Failed to fetch document list: {e}")
        return []

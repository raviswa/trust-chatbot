from dotenv import load_dotenv
load_dotenv()

"""
rag_pipeline.py
─────────────────────────────────────────────────────────────────
RAG Retrieval Layer
Handles query embedding, Qdrant vector search, 
metadata filtering, and context assembly for the chatbot
─────────────────────────────────────────────────────────────────
"""

import os
import logging
from typing import List, Optional, Dict

import ollama
import psycopg2
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny

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

TOP_K           = 5    # number of chunks to retrieve per query
SCORE_THRESHOLD = 0.35 # minimum cosine similarity to include a chunk

# ─────────────────────────────────────────────
# CLIENTS (lazy init — reused across calls)
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
# INTENT → TOPIC TAG MAPPING
# Maps chatbot intent tags to document topic tags
# set during ingestion. Enables pre-filtered search.
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
    """Embed user query using same model as ingestion (nomic-embed-text)."""
    response = ollama.embeddings(model=EMBED_MODEL, prompt=query)
    return response["embedding"]


def retrieve(
    query: str,
    intent: Optional[str] = None,
    top_k: int = TOP_K,
    score_threshold: float = SCORE_THRESHOLD
) -> List[Dict]:
    """
    Core retrieval function.
    
    1. Embed the query
    2. If intent maps to topic tags → filter Qdrant by topic_tags first
       (pre-filtered ANN search — faster + more relevant)
    3. Fall back to unfiltered search if filtered returns < 2 results
    4. Return top_k chunks above score_threshold

    Args:
        query:           User's raw query string
        intent:          Detected intent tag (optional, used for filtering)
        top_k:           Number of chunks to return
        score_threshold: Minimum similarity score

    Returns:
        List of chunk dicts with text, score, source metadata
    """
    qdrant = get_qdrant()

    try:
        query_vector = embed_query(query)
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return []

    # ── Build optional topic filter ───────────────────────────
    qdrant_filter = None
    topic_tags = INTENT_TOPIC_MAP.get(intent, []) if intent else []

    if topic_tags:
        qdrant_filter = Filter(
            must=[
                FieldCondition(
                    key="topic_tags",
                    match=MatchAny(any=topic_tags)
                )
            ]
        )

    # ── Search Qdrant ─────────────────────────────────────────
    try:
        results = qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=qdrant_filter,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True
        )
    except Exception as e:
        logger.error(f"Qdrant search failed: {e}")
        return []

    # ── Fallback: unfiltered search if too few results ────────
    if len(results) < 2 and topic_tags:
        logger.info("Filtered search returned < 2 results — falling back to unfiltered")
        try:
            results = qdrant.search(
                collection_name=COLLECTION_NAME,
                query_vector=query_vector,
                limit=top_k,
                score_threshold=score_threshold,
                with_payload=True
            )
        except Exception as e:
            logger.error(f"Fallback search failed: {e}")
            return []

    # ── Format results ────────────────────────────────────────
    chunks = []
    for hit in results:
        chunks.append({
            "text":        hit.payload.get("text", ""),
            "score":       round(hit.score, 4),
            "filename":    hit.payload.get("filename", "Unknown"),
            "page_number": hit.payload.get("page_number", 0),
            "chunk_index": hit.payload.get("chunk_index", 0),
            "topic_tags":  hit.payload.get("topic_tags", []),
            "chunk_id":    str(hit.id)
        })

    logger.info(f"Retrieved {len(chunks)} chunks for query (intent: {intent})")
    return chunks


def assemble_context(chunks: List[Dict], max_chars: int = 3000) -> str:
    """
    Assembles retrieved chunks into a single context string
    for the LLM prompt. Includes source attribution.
    Truncates to max_chars to stay within context window.
    """
    if not chunks:
        return ""

    context_parts = []
    total_chars = 0

    for i, chunk in enumerate(chunks):
        source = f"[Source: {chunk['filename']}, Page {chunk['page_number']}]"
        block = f"{source}\n{chunk['text']}"

        if total_chars + len(block) > max_chars:
            break

        context_parts.append(block)
        total_chars += len(block)

    return "\n\n---\n\n".join(context_parts)


def format_citations(chunks: List[Dict]) -> List[str]:
    """
    Returns a list of citation strings for display to the user.
    e.g. ["nidamed_wordsmatter.pdf, Page 2", ...]
    """
    seen = set()
    citations = []
    for chunk in chunks:
        key = f"{chunk['filename']} — Page {chunk['page_number']}"
        if key not in seen:
            citations.append(key)
            seen.add(key)
    return citations


def get_document_list() -> List[Dict]:
    """
    Returns all ingested documents from PostgreSQL.
    Useful for admin/debug endpoints.
    """
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
                "ingested_at": str(r[4])
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Failed to fetch document list: {e}")
        return []

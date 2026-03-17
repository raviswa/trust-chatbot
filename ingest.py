from dotenv import load_dotenv
load_dotenv()

"""
ingest.py
─────────────────────────────────────────────────────────────────
PDF Ingestion Pipeline
Processes local PDFs → chunks → embeds → stores in Qdrant + PostgreSQL

Usage:
    python ingest.py --pdf_dir ./pdfs
    python ingest.py --pdf_dir ./pdfs --reset   (wipe + re-ingest)

Requirements:
    pip install pymupdf qdrant-client psycopg2-binary ollama tqdm

Setup:
    - Qdrant running on localhost:6333
    - PostgreSQL running on localhost:5432
    - Ollama running with nomic-embed-text pulled
─────────────────────────────────────────────────────────────────
"""

import os
import sys
import json
import uuid
import hashlib
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

import fitz                          # pymupdf — PDF extraction
import ollama                        # nomic-embed-text embeddings
import psycopg2                      # PostgreSQL
import psycopg2.extras
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue
)
from tqdm import tqdm

# ─────────────────────────────────────────────
# CONFIG — adjust to your environment
# ─────────────────────────────────────────────

QDRANT_HOST        = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT        = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME    = os.getenv("QDRANT_COLLECTION", "health_docs")

PG_HOST            = os.getenv("PG_HOST", "localhost")
PG_PORT            = int(os.getenv("PG_PORT", 5432))
PG_DB              = os.getenv("PG_DB", "chatbot_db")
PG_USER            = os.getenv("PG_USER", "chatbot_user")
PG_PASSWORD        = os.getenv("PG_PASSWORD", "your_password")

EMBED_MODEL        = "nomic-embed-text"   # your existing embedding model
EMBED_DIMENSIONS   = 768                  # nomic-embed-text output dimensions

# Chunking config
CHUNK_SIZE         = 500    # tokens (approximate — we use word count)
CHUNK_OVERLAP      = 50     # words overlap between consecutive chunks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# DATABASE CONNECTIONS
# ─────────────────────────────────────────────

def get_qdrant_client() -> QdrantClient:
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def get_pg_conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT,
        dbname=PG_DB, user=PG_USER, password=PG_PASSWORD
    )


# ─────────────────────────────────────────────
# SETUP: Create Qdrant collection + PG tables
# ─────────────────────────────────────────────

def setup_qdrant(client: QdrantClient, reset: bool = False):
    if reset and client.collection_exists(COLLECTION_NAME):
        logger.info(f"Deleting existing collection: {COLLECTION_NAME}")
        client.delete_collection(COLLECTION_NAME)

    if not client.collection_exists(COLLECTION_NAME):
        logger.info(f"Creating Qdrant collection: {COLLECTION_NAME}")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=EMBED_DIMENSIONS,
                distance=Distance.COSINE
            )
        )
    else:
        logger.info(f"Collection already exists: {COLLECTION_NAME}")


def setup_postgres(conn, reset: bool = False):
    with conn.cursor() as cur:

        if reset:
            cur.execute("DROP TABLE IF EXISTS chunks CASCADE;")
            cur.execute("DROP TABLE IF EXISTS documents CASCADE;")
            logger.info("Dropped existing PostgreSQL tables")

        # Documents registry — one row per PDF
        cur.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                filename        TEXT NOT NULL,
                filepath        TEXT NOT NULL,
                file_hash       TEXT UNIQUE NOT NULL,
                page_count      INTEGER,
                chunk_count     INTEGER DEFAULT 0,
                topic_tags      TEXT[],
                ingested_at     TIMESTAMP DEFAULT NOW(),
                metadata        JSONB
            );
        """)

        # Chunks registry — one row per chunk stored in Qdrant
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id              UUID PRIMARY KEY,
                document_id     UUID REFERENCES documents(id) ON DELETE CASCADE,
                chunk_index     INTEGER NOT NULL,
                page_number     INTEGER,
                text            TEXT NOT NULL,
                char_count      INTEGER,
                word_count      INTEGER,
                topic_tags      TEXT[],
                created_at      TIMESTAMP DEFAULT NOW()
            );
        """)

        conn.commit()
        logger.info("PostgreSQL tables ready")


# ─────────────────────────────────────────────
# PDF EXTRACTION
# ─────────────────────────────────────────────

def extract_text_from_pdf(filepath: str) -> List[Dict]:
    """
    Extract text from PDF page by page.
    Returns list of {page_number, text} dicts.
    """
    doc = fitz.open(filepath)
    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text").strip()
        if text:
            pages.append({
                "page_number": page_num + 1,
                "text": text
            })
    doc.close()
    return pages


def file_hash(filepath: str) -> str:
    """MD5 hash of file — used to skip already-ingested files."""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ─────────────────────────────────────────────
# CHUNKING
# ─────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Splits text into overlapping chunks by word count.
    Respects paragraph boundaries where possible.
    """
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        chunk = " ".join(chunk_words)

        # Try to end at a sentence boundary
        for punct in [". ", "? ", "! ", "\n"]:
            last = chunk.rfind(punct)
            if last > len(chunk) * 0.6:  # only trim if not cutting too much
                chunk = chunk[:last + 1].strip()
                break

        if chunk:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def chunk_pages(pages: List[Dict]) -> List[Dict]:
    """
    Chunks all pages, preserving page number metadata per chunk.
    """
    all_chunks = []
    chunk_index = 0

    for page in pages:
        page_chunks = chunk_text(page["text"])
        for chunk in page_chunks:
            all_chunks.append({
                "chunk_index": chunk_index,
                "page_number": page["page_number"],
                "text": chunk,
                "char_count": len(chunk),
                "word_count": len(chunk.split())
            })
            chunk_index += 1

    return all_chunks


# ─────────────────────────────────────────────
# EMBEDDING
# ─────────────────────────────────────────────

def embed_text(text: str) -> List[float]:
    """
    Generate embedding using nomic-embed-text via Ollama.
    """
    response = ollama.embeddings(model=EMBED_MODEL, prompt=text)
    return response["embedding"]


def embed_batch(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """
    Embed a list of texts in batches to avoid memory issues.
    """
    embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        for text in batch:
            embeddings.append(embed_text(text))
    return embeddings


# ─────────────────────────────────────────────
# AUTO-TAGGING
# Assigns topic tags based on keyword presence
# Tags are stored in PostgreSQL for metadata filtering
# ─────────────────────────────────────────────

TOPIC_KEYWORDS = {
    "mood":             ["anxiety", "depression", "mood", "emotion", "mental health",
                         "sadness", "hopeless", "stress", "wellbeing"],
    "addiction":        ["addiction", "substance use", "alcohol", "drug", "opioid",
                         "recovery", "withdrawal", "dependence", "SUD"],
    "behaviour":        ["behaviour", "behavior", "habit", "pattern", "compulsive",
                         "impulsive", "trigger", "coping"],
    "gaming":           ["gaming", "video game", "screen time", "online gaming"],
    "social_media":     ["social media", "instagram", "tiktok", "facebook",
                         "scrolling", "online", "digital"],
    "gambling":         ["gambling", "betting", "casino", "wagering", "lottery"],
    "alcohol":          ["alcohol", "drinking", "beer", "wine", "spirits", "alcoholism"],
    "drugs":            ["cocaine", "heroin", "opioid", "cannabis", "marijuana",
                         "methamphetamine", "fentanyl", "benzodiazepine"],
    "trauma":           ["trauma", "PTSD", "abuse", "assault", "violence", "flashback"],
    "treatment":        ["treatment", "therapy", "counselling", "rehabilitation",
                         "medication", "clinical", "intervention"],
    "person_first":     ["person-first", "stigma", "language", "terminology",
                         "person with", "words matter"],
    "grief":            ["grief", "bereavement", "loss", "mourning", "death"],
    "relationships":    ["relationship", "family", "partner", "divorce", "domestic"],
}


def auto_tag(text: str) -> List[str]:
    """
    Assigns topic tags to a chunk based on keyword presence.
    """
    text_lower = text.lower()
    tags = []
    for tag, keywords in TOPIC_KEYWORDS.items():
        if any(kw.lower() in text_lower for kw in keywords):
            tags.append(tag)
    return tags


# ─────────────────────────────────────────────
# MAIN INGESTION PIPELINE
# ─────────────────────────────────────────────

def ingest_pdf(filepath: str, qdrant: QdrantClient, pg_conn) -> Dict:
    """
    Full pipeline for a single PDF:
    1. Check if already ingested (via hash)
    2. Extract text page by page
    3. Chunk text with overlap
    4. Auto-tag chunks
    5. Embed chunks with nomic-embed-text
    6. Store vectors in Qdrant
    7. Store metadata in PostgreSQL

    Returns: summary dict
    """
    filename = Path(filepath).name
    fhash = file_hash(filepath)

    # ── Check if already ingested ─────────────────────────────
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, filename FROM documents WHERE file_hash = %s", (fhash,))
        existing = cur.fetchone()
        if existing:
            logger.info(f"Skipping already ingested: {filename}")
            return {"status": "skipped", "filename": filename}

    logger.info(f"Ingesting: {filename}")

    # ── Extract text ──────────────────────────────────────────
    pages = extract_text_from_pdf(filepath)
    if not pages:
        logger.warning(f"No text extracted from {filename} — skipping")
        return {"status": "empty", "filename": filename}

    # ── Chunk ─────────────────────────────────────────────────
    chunks = chunk_pages(pages)
    logger.info(f"  {filename}: {len(pages)} pages → {len(chunks)} chunks")

    # ── Auto-tag document-level ───────────────────────────────
    full_text = " ".join(p["text"] for p in pages)
    doc_tags = auto_tag(full_text)

    # ── Register document in PostgreSQL ──────────────────────
    doc_id = str(uuid.uuid4())
    with pg_conn.cursor() as cur:
        cur.execute("""
            INSERT INTO documents 
                (id, filename, filepath, file_hash, page_count, chunk_count, 
                 topic_tags, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            doc_id, filename, str(filepath), fhash,
            len(pages), len(chunks),
            doc_tags,
            json.dumps({"source": "local_pdf", "ingested_by": "ingest.py"})
        ))
        pg_conn.commit()

    # ── Embed + store chunks ──────────────────────────────────
    points = []
    chunk_rows = []

    for chunk in tqdm(chunks, desc=f"  Embedding {filename}", leave=False):
        chunk_id = str(uuid.uuid4())
        chunk_tags = auto_tag(chunk["text"])

        # Embed
        try:
            vector = embed_text(chunk["text"])
        except Exception as e:
            logger.error(f"Embedding failed for chunk {chunk['chunk_index']}: {e}")
            continue

        # Qdrant point — payload carries metadata for filtered search
        points.append(PointStruct(
            id=chunk_id,
            vector=vector,
            payload={
                "document_id":  doc_id,
                "filename":     filename,
                "chunk_index":  chunk["chunk_index"],
                "page_number":  chunk["page_number"],
                "text":         chunk["text"],
                "topic_tags":   chunk_tags,
                "char_count":   chunk["char_count"],
                "word_count":   chunk["word_count"],
            }
        ))

        # PostgreSQL row
        chunk_rows.append((
            chunk_id, doc_id,
            chunk["chunk_index"], chunk["page_number"],
            chunk["text"], chunk["char_count"],
            chunk["word_count"], chunk_tags
        ))

    # ── Batch upsert to Qdrant ────────────────────────────────
    BATCH = 100
    for i in range(0, len(points), BATCH):
        qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=points[i:i + BATCH]
        )

    # ── Batch insert chunks to PostgreSQL ─────────────────────
    with pg_conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, """
            INSERT INTO chunks 
                (id, document_id, chunk_index, page_number, text,
                 char_count, word_count, topic_tags)
            VALUES %s
        """, chunk_rows)
        pg_conn.commit()

    logger.info(f"  ✓ {filename}: {len(points)} vectors stored")
    return {
        "status": "ingested",
        "filename": filename,
        "doc_id": doc_id,
        "pages": len(pages),
        "chunks": len(points),
        "tags": doc_tags
    }


def ingest_directory(pdf_dir: str, reset: bool = False):
    """
    Ingests all PDFs in a directory.
    Skips already-ingested files automatically.
    """
    pdf_dir = Path(pdf_dir)
    pdf_files = list(pdf_dir.glob("**/*.pdf"))

    if not pdf_files:
        logger.error(f"No PDF files found in: {pdf_dir}")
        sys.exit(1)

    logger.info(f"Found {len(pdf_files)} PDF files in {pdf_dir}")

    # ── Connect ───────────────────────────────────────────────
    qdrant = get_qdrant_client()
    pg_conn = get_pg_conn()

    # ── Setup ─────────────────────────────────────────────────
    setup_qdrant(qdrant, reset=reset)
    setup_postgres(pg_conn, reset=reset)

    # ── Ingest each PDF ───────────────────────────────────────
    results = []
    for pdf_path in pdf_files:
        try:
            result = ingest_pdf(str(pdf_path), qdrant, pg_conn)
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to ingest {pdf_path.name}: {e}")
            results.append({"status": "error", "filename": pdf_path.name, "error": str(e)})

    # ── Summary ───────────────────────────────────────────────
    ingested = [r for r in results if r["status"] == "ingested"]
    skipped  = [r for r in results if r["status"] == "skipped"]
    errors   = [r for r in results if r["status"] == "error"]

    logger.info("=" * 50)
    logger.info(f"Ingestion complete:")
    logger.info(f"  ✓ Ingested : {len(ingested)}")
    logger.info(f"  → Skipped  : {len(skipped)} (already in DB)")
    logger.info(f"  ✗ Errors   : {len(errors)}")
    logger.info("=" * 50)

    pg_conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest PDFs into Qdrant + PostgreSQL")
    parser.add_argument("--pdf_dir", required=True, help="Directory containing PDF files")
    parser.add_argument("--reset", action="store_true",
                        help="Wipe existing data and re-ingest everything")
    args = parser.parse_args()
    ingest_directory(args.pdf_dir, reset=args.reset)

from dotenv import load_dotenv
load_dotenv()

"""
ingest.py
─────────────────────────────────────────────────────────────────
Memory-Safe PDF Ingestion Pipeline  (Qdrant + nomic-embed-text)
Designed for constrained environments (GitHub Codespaces, low RAM VMs).

Strategy:
  - Generator-based lazy loading: one PDF processed at a time
  - RecursiveCharacterTextSplitter.from_tiktoken_encoder (cl100k_base)
    chunk_size=512 tokens, chunk_overlap=50 tokens
  - Batch embedding: 20 chunks embedded in ONE /api/embed call (~5× faster
    than one call per chunk; reduces 1,669 HTTP round-trips to ~84)
  - Qdrant upserts in strict batches of 20 to cap peak memory
  - gc.collect() after each PDF to release PyMuPDF + string buffers
  - Per-PDF error isolation: corrupt / oversized PDFs are logged and skipped

Embeddings:
  - Model:  nomic-embed-text (768-dim, cosine similarity)
  - Ollama /api/embed batch endpoint (Ollama ≥0.19) — sends a list of texts
    in one HTTP request, returns a list of vectors in one response
  - L2 normalisation applied to every vector so cosine == dot-product
    regardless of Ollama version behaviour.

Metadata stored per Qdrant point (payload):
  - text         : raw chunk text (returned at query time)
  - filename     : source PDF filename
  - page_number  : 1-based page the chunk was extracted from
  - chunk_index  : sequential chunk index within the document
  - topic_tags   : keyword-matched topic list for RAG filters

Usage:
    python ingest.py                          # ingest ./pdfs
    python ingest.py --pdf_dir /path/to/pdfs
    python ingest.py --reset                  # wipe collection first
    python ingest.py --dry_run                # stats only, no writes

Requirements:
    langchain-text-splitters>=0.3.0
    tiktoken>=0.7.0
─────────────────────────────────────────────────────────────────
"""

import gc
import math
import os
import sys
import uuid
import argparse
import logging
from pathlib import Path
from typing import Generator

import fitz                       # PyMuPDF
import requests
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

QDRANT_HOST     = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT     = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "health_docs")
EMBED_MODEL     = "nomic-embed-text"
VECTOR_DIM      = 768    # nomic-embed-text output dimension — must match collection
OLLAMA_BASE     = os.getenv("OLLAMA_HOST", "http://localhost:11434")

CHUNK_SIZE      = 512    # tokens
CHUNK_OVERLAP   = 50     # tokens
UPLOAD_BATCH    = 20     # chunks per embed+upsert batch — kept small for RAM safety

# ─────────────────────────────────────────────
# SPLITTER  — token-based via tiktoken cl100k_base
# Instantiated once; from_tiktoken_encoder sets length_function internally.
# ─────────────────────────────────────────────

_SPLITTER = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    encoding_name="cl100k_base",
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ".", " ", ""],
)

# ─────────────────────────────────────────────
# TOPIC TAG HEURISTIC  (mirrors rag_pipeline.py INTENT_TOPIC_MAP)
# ─────────────────────────────────────────────

_TOPIC_KEYWORDS = {
    "alcohol":       ["alcohol", "ethanol", "drinking", "withdrawal", "cirrhosis"],
    "drugs":         ["drug", "heroin", "cocaine", "opioid", "methamphetamine",
                      "cannabis", "marijuana", "benzodiazepine"],
    "addiction":     ["addiction", "dependence", "craving", "relapse", "recovery",
                      "sobriety", "abstinence", "twelve step", "12-step"],
    "behaviour":     ["behaviour", "behavior", "compulsion", "impulse", "gaming",
                      "gambling", "pornography", "shopping", "screen time"],
    "mood":          ["depression", "anxiety", "mood", "stress", "emotion",
                      "mental health", "wellbeing", "sleep", "insomnia"],
    "trauma":        ["trauma", "ptsd", "abuse", "neglect", "adverse childhood"],
    "relationships": ["relationship", "family", "partner", "social support", "isolation"],
    "grief":         ["grief", "loss", "bereavement", "mourning"],
    "treatment":     ["therapy", "treatment", "counselling", "counseling", "cbt",
                      "mindfulness", "naltrexone", "buprenorphine", "methadone"],
    "social_media":  ["social media", "instagram", "tiktok", "twitter", "facebook",
                      "online", "digital"],
}


def _assign_topic_tags(text: str) -> list[str]:
    lower = text.lower()
    return [tag for tag, kws in _TOPIC_KEYWORDS.items() if any(kw in lower for kw in kws)]


# ─────────────────────────────────────────────
# BATCH EMBEDDING + L2 NORMALISATION
# ─────────────────────────────────────────────

def _l2_normalise(vec: list[float]) -> list[float]:
    """Return a unit-norm copy of vec.  No-op on zero vectors."""
    norm = math.sqrt(sum(x * x for x in vec))
    return vec if norm == 0.0 else [x / norm for x in vec]


def _embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts in ONE HTTP call using Ollama's /api/embed endpoint
    (available in Ollama ≥ 0.19).  Returns a list of L2-normalised vectors.

    Batch throughput:  ~20 texts / 6 s  vs  1 text / 1.5 s individually.
    Sending 20 texts per call reduces 1,669 round-trips to ~84, cutting
    total ingestion time from ~40 min to ~8 min on CPU-only Codespace.
    """
    resp = requests.post(
        f"{OLLAMA_BASE}/api/embed",
        json={"model": EMBED_MODEL, "input": texts},
        timeout=120,
    )
    resp.raise_for_status()
    return [_l2_normalise(v) for v in resp.json()["embeddings"]]


# ─────────────────────────────────────────────
# QDRANT HELPERS
# ─────────────────────────────────────────────

def _get_qdrant() -> QdrantClient:
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def _ensure_collection(qdrant: QdrantClient, reset: bool = False) -> None:
    existing = {c.name for c in qdrant.get_collections().collections}
    if reset and COLLECTION_NAME in existing:
        logger.info(f"Deleting collection '{COLLECTION_NAME}' (--reset)")
        qdrant.delete_collection(COLLECTION_NAME)
        existing.discard(COLLECTION_NAME)
    if COLLECTION_NAME not in existing:
        logger.info(f"Creating collection '{COLLECTION_NAME}' dim={VECTOR_DIM}, cosine")
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )


# ─────────────────────────────────────────────
# GENERATOR: lazy chunk stream from a single PDF
# ─────────────────────────────────────────────

def _chunk_pdf(pdf_path: Path) -> Generator[dict, None, None]:
    """
    Lazy generator that yields one chunk dict at a time from *pdf_path*.

    Processing is per-page so page_number metadata is accurate.
    Pages with fewer than 30 characters (scanned/blank) are skipped.
    The generator holds only one page in memory at a time.

    Each yielded dict:
        text, filename, page_number (1-based), chunk_index, topic_tags
    """
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        logger.error(f"Cannot open '{pdf_path.name}': {e}")
        return

    chunk_index = 0
    try:
        for page_num, page in enumerate(doc, start=1):
            try:
                text = page.get_text("text").strip()
            except Exception as e:
                logger.warning(f"  Page {page_num} extract error in '{pdf_path.name}': {e}")
                continue

            if len(text) < 30:
                continue

            try:
                page_chunks = _SPLITTER.split_text(text)
            except Exception as e:
                logger.warning(f"  Chunk error page {page_num} in '{pdf_path.name}': {e}")
                continue

            for chunk_text in page_chunks:
                if chunk_text.strip():
                    yield {
                        "text":        chunk_text,
                        "filename":    pdf_path.name,
                        "page_number": page_num,
                        "chunk_index": chunk_index,
                        "topic_tags":  _assign_topic_tags(chunk_text),
                    }
                    chunk_index += 1
    finally:
        doc.close()


# ─────────────────────────────────────────────
# MAIN INGESTION LOOP
# ─────────────────────────────────────────────

def ingest_directory(
    pdf_dir: str,
    reset: bool = False,
    dry_run: bool = False,
) -> None:
    pdf_paths = sorted(Path(pdf_dir).glob("*.pdf"))
    if not pdf_paths:
        logger.error(f"No PDFs found in '{pdf_dir}'")
        sys.exit(1)

    logger.info(f"Found {len(pdf_paths)} PDFs in '{pdf_dir}'")

    qdrant = None
    if not dry_run:
        qdrant = _get_qdrant()
        _ensure_collection(qdrant, reset=reset)

    total_chunks  = 0
    total_vectors = 0
    failed_pdfs   = []

    for pdf_path in tqdm(pdf_paths, desc="PDFs", unit="pdf"):
        pdf_chunks  = 0
        pdf_vectors = 0
        chunk_buffer: list[dict] = []   # accumulate chunks before batch embed

        def _flush_buffer(buf: list[dict]) -> int:
            """Embed buf, upsert to Qdrant, return number of vectors stored."""
            if not buf:
                return 0
            try:
                vectors = _embed_batch([c["text"] for c in buf])
            except Exception as e:
                logger.warning(f"  Batch embed failed for '{pdf_path.name}': {e}")
                return 0
            points = [
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vectors[i],
                    payload={
                        "text":        buf[i]["text"],
                        "filename":    buf[i]["filename"],
                        "page_number": buf[i]["page_number"],
                        "chunk_index": buf[i]["chunk_index"],
                        "topic_tags":  buf[i]["topic_tags"],
                    },
                )
                for i in range(len(buf))
            ]
            qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
            return len(points)

        try:
            for chunk in _chunk_pdf(pdf_path):
                pdf_chunks += 1
                total_chunks += 1

                if dry_run:
                    continue

                chunk_buffer.append(chunk)

                # Embed + upsert when batch is full
                if len(chunk_buffer) >= UPLOAD_BATCH:
                    n = _flush_buffer(chunk_buffer)
                    pdf_vectors   += n
                    total_vectors += n
                    chunk_buffer.clear()

            # Flush remaining chunks for this PDF
            if chunk_buffer and not dry_run:
                n = _flush_buffer(chunk_buffer)
                pdf_vectors   += n
                total_vectors += n
                chunk_buffer.clear()

            if pdf_chunks == 0:
                failed_pdfs.append(pdf_path.name)

        except Exception as e:
            # Catch-all: log the PDF as failed and continue with the next one
            logger.error(f"Failed processing '{pdf_path.name}': {e}")
            failed_pdfs.append(pdf_path.name)
            chunk_buffer.clear()

        finally:
            # Release PyMuPDF page buffers and string data promptly
            gc.collect()

    # ── Summary ───────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info(f"PDFs processed : {len(pdf_paths) - len(failed_pdfs)} / {len(pdf_paths)}")
    logger.info(f"Total chunks   : {total_chunks}")
    if not dry_run:
        logger.info(f"Vectors stored : {total_vectors}")
        logger.info(f"Collection     : '{COLLECTION_NAME}' @ {QDRANT_HOST}:{QDRANT_PORT}")
    if failed_pdfs:
        logger.warning(f"Failed / empty ({len(failed_pdfs)}): {', '.join(failed_pdfs)}")
    if dry_run:
        logger.info("[DRY RUN] No writes performed.")
    logger.info("=" * 60)


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Memory-safe PDF ingestion into Qdrant (generator-based)."
    )
    parser.add_argument("--pdf_dir",  default="./pdfs",
                        help="PDF directory (default: ./pdfs)")
    parser.add_argument("--reset",    action="store_true",
                        help="Delete and recreate the Qdrant collection before ingesting.")
    parser.add_argument("--dry_run",  action="store_true",
                        help="Count chunks only — no embedding or Qdrant writes.")
    args = parser.parse_args()

    ingest_directory(pdf_dir=args.pdf_dir, reset=args.reset, dry_run=args.dry_run)

#!/usr/bin/env python3
"""
Chatbot Server Startup Script
=============================

Starts the FastAPI chatbot server on port 8000.
Automatically ensures Qdrant (Docker) and Ollama are running first.

Run with: python start_server.py
"""

import os
import sys
import time
import shutil
import subprocess
import logging

# Add workspace root to sys.path so context_query_builder.py and other
# root-level modules are importable from the backend package.
_workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace_root not in sys.path:
    sys.path.insert(0, _workspace_root)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment
from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.dirname(__file__), ".env.local")
load_dotenv(dotenv_path)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


# ─────────────────────────────────────────────────────────────
# PRE-FLIGHT: Qdrant + Ollama
# ─────────────────────────────────────────────────────────────

def _http_ok(url: str, timeout: int = 3) -> bool:
    """Return True if the URL responds with an HTTP 200."""
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def ensure_qdrant():
    """Start the 'qdrant' Docker container if it isn't already up."""
    if _http_ok("http://127.0.0.1:6333/healthz"):
        logger.info("✅ Qdrant already running on port 6333")
        return

    if not shutil.which("docker"):
        logger.warning("⚠️  docker not found — Qdrant must be started manually")
        return

    logger.info("🔄 Starting Qdrant Docker container...")
    result = subprocess.run(
        ["docker", "start", "qdrant"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        logger.warning(f"⚠️  Could not start Qdrant container: {result.stderr.strip()}")
        logger.warning("    Run: docker run -d -p 6333:6333 --name qdrant qdrant/qdrant")
        return

    # Wait up to 10 s for it to become healthy
    for _ in range(10):
        time.sleep(1)
        if _http_ok("http://127.0.0.1:6333/healthz"):
            logger.info("✅ Qdrant started successfully on port 6333")
            return

    logger.warning("⚠️  Qdrant container started but health check timed out — RAG may not work")


def ensure_ollama():
    """Start the Ollama server if it isn't already running."""
    if _http_ok("http://127.0.0.1:11434/api/tags"):
        logger.info("✅ Ollama already running on port 11434")
        return

    if not shutil.which("ollama"):
        logger.warning("⚠️  ollama not found in PATH — LLM calls will fail")
        return

    logger.info("🔄 Starting Ollama server...")
    subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait up to 15 s for it to be ready
    for _ in range(15):
        time.sleep(1)
        if _http_ok("http://127.0.0.1:11434/api/tags"):
            logger.info("✅ Ollama started successfully on port 11434")
            return

    logger.warning("⚠️  Ollama started but didn't respond in time — LLM calls may fail")

# Check environment — require a PostgreSQL connection string for CtrlS
DATABASE_URL = os.getenv("DATABASE_URL")
PG_HOST      = os.getenv("PG_HOST")

if not DATABASE_URL and not PG_HOST:
    logger.error("❌ Missing database config: set DATABASE_URL or PG_HOST/PG_DB/PG_USER/PG_PASSWORD in .env")
    sys.exit(1)

if DATABASE_URL:
    # Mask password in log output for security
    _safe_url = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
    logger.info(f"✅ Database: PostgreSQL @ {_safe_url}")
else:
    logger.info(f"✅ Database: PostgreSQL @ {PG_HOST}:{os.getenv('PG_PORT', '5432')}/{os.getenv('PG_DB', 'chatbot_db')}")

# Start server
if __name__ == "__main__":
    # ── Pre-flight: start dependencies ────────────────────────
    ensure_qdrant()
    ensure_ollama()
    import uvicorn
    
    logger.info("\n" + "="*60)
    logger.info("STARTING CHATBOT SERVER")
    logger.info("="*60)
    logger.info("Server will be available at: http://localhost:8000")
    logger.info("API docs available at:      http://localhost:8000/docs")
    logger.info("="*60 + "\n")
    
    uvicorn.run(
        "chatbot_engine:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )

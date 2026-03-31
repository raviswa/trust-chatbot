#!/usr/bin/env python3
"""
Chatbot Server Startup Script
=============================

Starts the FastAPI chatbot server on port 8000.

Run with: python start_server.py
"""

import os
import sys
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

# Check environment
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("❌ Missing SUPABASE_URL or SUPABASE_KEY in environment")
    sys.exit(1)

logger.info("✅ Environment loaded")
logger.info(f"   SUPABASE_URL: {SUPABASE_URL}")
logger.info(f"   SUPABASE_KEY: {SUPABASE_KEY[:20]}...")

# Start server
if __name__ == "__main__":
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
        reload=True,
        log_level="info"
    )

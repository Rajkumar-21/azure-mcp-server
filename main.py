# main.py (Corrected)
import uvicorn
import logging
import os
from dotenv import load_dotenv

# Load .env for local Uvicorn run
load_dotenv()

# Import the FastMCP instance from server.py
# Rename the import for clarity to avoid confusion with the final asgi_app
from server import mcp as mcp_instance

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Get the actual ASGI application for SSE ---
# This is the key change: call .sse_app() on the FastMCP instance
asgi_app = mcp_instance.sse_app()
# ---------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1") # Use 0.0.0.0 for containers

    logger.info(f"Starting Uvicorn ASGI server on {host}:{port}")
    uvicorn.run(
        asgi_app,          # <-- Pass the result of .sse_app() here
        host=host,
        port=port,
        log_level="info"
    )
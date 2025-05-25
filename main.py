# azure_mcp_server/main.py (With Import Debugging)
import uvicorn
import logging
import os
import sys # Import sys
from dotenv import load_dotenv

# --- Basic Logging Setup (Early) ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.info("main.py: Starting execution/import...")

# Load .env for local Uvicorn run
try:
    logger.info("main.py: Attempting to load .env...")
    load_dotenv()
    logger.info("main.py: .env loaded (if found).")
except Exception as e:
    logger.error(f"main.py: Error loading .env: {e}", exc_info=True)

# --- Import Starlette ---
try:
    logger.info("main.py: Importing Starlette...")
    from starlette.applications import Starlette
    from starlette.routing import Mount
    logger.info("main.py: Starlette imported successfully.")
except ImportError as e:
    logger.critical(f"main.py: FAILED to import Starlette: {e}", exc_info=True)
    sys.exit("Critical import failed: Starlette")

# --- Import the MCP instance from server.py ---
try:
    logger.info("main.py: Importing MCP instance from server...")
    from server import mcp as mcp_instance # Ensure 'server.py' is in Python path
    logger.info("main.py: MCP instance imported successfully from server.")
except ImportError as e:
    logger.critical(f"main.py: FAILED to import from server.py: {e}", exc_info=True)
    sys.exit("Critical import failed: server module")
except Exception as e:
    logger.critical(f"main.py: UNEXPECTED error importing from server.py: {e}", exc_info=True)
    sys.exit("Unexpected error during server import")


# --- Create the Starlette app instance ---
try:
    logger.info("main.py: Creating Starlette app instance...")
    app = Starlette(routes=[
        Mount('/', app=mcp_instance.sse_app()) # Use the imported mcp_instance
    ])
    logger.info("main.py: Starlette app instance created successfully.")
except Exception as e:
     logger.critical(f"main.py: FAILED to create Starlette app instance: {e}", exc_info=True)
     sys.exit("Failed to initialize Starlette app")

if __name__ == "__main__":
    logger.info("main.py: Running in __main__ block (direct execution)...")
    port = int(os.getenv("PORT", 8080)) # Default to 8080 if not set
    host = os.getenv("HOST", "127.0.0.1") # Default to 127.0.0.1; use "0.0.0.0" for containers

    logger.info(f"Starting Uvicorn ASGI server via __main__ on {host}:{port}")
    uvicorn.run(
        app, # Pass the app object directly
        host=host,
        port=port,
        log_level="info"
    )
else:
    logger.info("main.py: Imported as a module (likely by Uvicorn). 'app' object should be defined.")
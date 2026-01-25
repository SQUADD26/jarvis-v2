"""FastAPI server for Jarvis voice client API.

Run with: uvicorn jarvis.api.server:app --host 0.0.0.0 --port 8000
Or: uv run python -m jarvis.api
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from jarvis.config import get_settings
from jarvis.core.orchestrator import process_message
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="Jarvis API",
    description="API for Jarvis voice client",
    version="1.0.0",
)


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    message: str
    user_id: str = "voice_local"
    history: list[dict] | None = None


class ChatResponse(BaseModel):
    """Response body for chat endpoint."""
    response: str
    user_id: str


async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    """Verify the API key from request header."""
    settings = get_settings()
    if not settings.jarvis_api_key:
        logger.warning("JARVIS_API_KEY not configured on server")
        raise HTTPException(status_code=500, detail="API key not configured")

    if x_api_key != settings.jarvis_api_key:
        logger.warning(f"Invalid API key attempt")
        raise HTTPException(status_code=401, detail="Invalid API key")

    return x_api_key


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "jarvis-api"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    _api_key: str = Depends(verify_api_key)
):
    """
    Process a chat message through the orchestrator.

    Requires X-API-Key header for authentication.
    """
    logger.info(f"API chat request from {request.user_id}: {request.message[:50]}...")

    try:
        # Process through orchestrator
        response = await process_message(
            user_id=request.user_id,
            message=request.message,
            history=request.history or []
        )

        logger.info(f"API response generated: {len(response)} chars")

        return ChatResponse(
            response=response,
            user_id=request.user_id
        )

    except Exception as e:
        logger.error(f"API chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event():
    """Log startup."""
    logger.info("Jarvis API server starting...")


@app.on_event("shutdown")
async def shutdown_event():
    """Log shutdown."""
    logger.info("Jarvis API server shutting down...")

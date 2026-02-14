"""FastAPI server for Jarvis API.

Run with: uvicorn jarvis.api.server:app --host 0.0.0.0 --port 8001
Or: uv run python -m jarvis.api
"""

import os
import json
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from jarvis.config import get_settings
from jarvis.core.orchestrator import process_message
from jarvis.integrations.gemini import gemini
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="Jarvis API",
    description="API for Jarvis AI assistant",
    version="2.0.0",
)

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth ──────────────────────────────────────────────────

async def verify_auth(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> dict:
    """Dual auth: API key (Telegram/programmatic) or Supabase JWT (web)."""
    settings = get_settings()

    # API Key auth
    if x_api_key:
        if not settings.jarvis_api_key:
            raise HTTPException(status_code=500, detail="API key not configured")
        if x_api_key != settings.jarvis_api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return {"user_id": "api_user", "auth_type": "api_key"}

    # Supabase JWT auth
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        try:
            from jarvis.db.supabase_client import get_supabase_client
            supabase = get_supabase_client()
            user_response = supabase.auth.get_user(token)
            if user_response and user_response.user:
                return {
                    "user_id": str(user_response.user.id),
                    "auth_type": "jwt",
                    "email": user_response.user.email,
                }
        except Exception as e:
            logger.warning(f"JWT verification failed: {e}")
            raise HTTPException(status_code=401, detail="Invalid token")

    raise HTTPException(status_code=401, detail="Authentication required")


# ── Models ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    user_id: str = "web_user"
    conversation_id: Optional[str] = None
    history: list[dict] | None = None


class ChatResponse(BaseModel):
    response: str
    user_id: str
    conversation_id: Optional[str] = None


# ── Health ────────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "jarvis-api"}


# ── Chat ──────────────────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    auth: dict = Depends(verify_auth),
):
    """Process a chat message through the orchestrator."""
    user_id = auth.get("user_id", request.user_id)
    logger.info(f"Chat request from {user_id}: {request.message[:50]}...")

    try:
        response = await process_message(
            user_id=user_id,
            message=request.message,
            history=request.history or [],
        )
        return ChatResponse(
            response=response,
            user_id=user_id,
            conversation_id=request.conversation_id,
        )
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/stream")
async def chat_stream(
    request: ChatRequest,
    auth: dict = Depends(verify_auth),
):
    """Stream chat response via SSE."""
    user_id = auth.get("user_id", request.user_id)
    logger.info(f"Stream request from {user_id}: {request.message[:50]}...")

    async def event_generator():
        try:
            # Process through orchestrator to get agent data first
            response = await process_message(
                user_id=user_id,
                message=request.message,
                history=request.history or [],
            )

            # Stream the response in chunks
            chunk_size = 20
            for i in range(0, len(response), chunk_size):
                chunk = response[i:i + chunk_size]
                yield f"data: {json.dumps({'text': chunk})}\n\n"

            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Stats ─────────────────────────────────────────────────

@app.get("/api/stats/costs")
async def get_costs(
    days: int = 30,
    auth: dict = Depends(verify_auth),
):
    """Get LLM cost statistics."""
    try:
        from jarvis.db.supabase_client import get_supabase_client
        supabase = get_supabase_client()
        result = supabase.table("llm_stats_daily").select("*").order(
            "date", desc=True
        ).limit(days).execute()
        return {"stats": result.data}
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/integrations/status")
async def integrations_status(auth: dict = Depends(verify_auth)):
    """Return connection status for each OAuth provider."""
    user_id = auth.get("user_id")
    if not user_id or user_id == "api_user":
        raise HTTPException(status_code=400, detail="JWT auth required")

    try:
        from jarvis.db.supabase_client import get_supabase_client
        supabase = get_supabase_client()

        providers = {
            "gmail": "gmail_accounts",
            "google_calendar": "google_calendar_accounts",
            "notion": "notion_accounts",
            "fathom": "fathom_oauth_tokens",
        }

        result = {}
        for provider, table in providers.items():
            row = supabase.table(table).select("id, updated_at").eq(
                "user_id", user_id
            ).limit(1).execute()
            result[provider] = {
                "connected": len(row.data) > 0,
                "updated_at": row.data[0]["updated_at"] if row.data else None,
            }

        # Telegram: check user_profiles
        profile = supabase.table("user_profiles").select("telegram_id").eq(
            "id", user_id
        ).maybe_single().execute()
        result["telegram"] = {
            "connected": bool(profile.data and profile.data.get("telegram_id")),
        }

        return {"integrations": result}
    except Exception as e:
        logger.error(f"Integrations status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Static files (production) ─────────────────────────────

frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "dist")
frontend_dir = os.path.abspath(frontend_dir)

if os.path.exists(frontend_dir):
    assets_dir = os.path.join(frontend_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="static-assets")

    @app.get("/{path:path}")
    async def spa(path: str):
        """Serve SPA for all non-API routes."""
        file_path = os.path.join(frontend_dir, path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dir, "index.html"))


# ── Lifecycle ─────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    logger.info("Jarvis API server starting...")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Jarvis API server shutting down...")

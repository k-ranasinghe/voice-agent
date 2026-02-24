"""
Main FastAPI application.
Entry point for the Bank ABC Voice Agent backend.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.config import settings
from src.database import init_db, close_db
from src.cache import init_redis, close_redis
from src.observability import setup_logging, init_langfuse, get_logger
from src.api.routes import health, admin
from src.api.websocket import handle_websocket_text
from src.api.voice_websocket import handle_voice_websocket


# Setup logging
setup_logging()
logger = get_logger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - startup and shutdown events."""
    
    # Startup
    logger.info("🚀 Starting Bank ABC Voice Agent...")
    logger.info(f"Environment: {settings.environment}")
    
    try:
        # Initialize database
        logger.info("Connecting to PostgreSQL...")
        await init_db()
        logger.info("✅ PostgreSQL connected")
        
        # Initialize Redis
        logger.info("Connecting to Redis...")
        await init_redis()
        logger.info("✅ Redis connected")
        
        # Initialize LangFuse
        logger.info("Initializing LangFuse...")
        init_langfuse()
        logger.info("✅ LangFuse initialized")
        
        logger.info("✨ Application ready to accept requests")
        
        yield
        
    finally:
        # Shutdown
        logger.info("🛑 Shutting down...")
        await close_db()
        await close_redis()
        logger.info("✅ Cleanup complete")


# Create FastAPI app
app = FastAPI(
    title="Bank ABC Voice Agent API",
    description="Conversational AI platform for banking customer service",
    version="0.1.0",
    lifespan=lifespan,
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(admin.router, tags=["Admin"])


# WebSocket endpoint for text-based testing
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for text-based agent conversation."""
    await handle_websocket_text(websocket)


# WebSocket endpoint for voice streaming
@app.websocket("/ws/voice")
async def voice_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for voice-based agent conversation with STT/TTS."""
    await handle_voice_websocket(websocket)


@app.get("/")

async def root():
    """Root endpoint - API information."""
    return {
        "name": "Bank ABC Voice Agent API",
        "version": "0.1.0",
        "status": "operational",
        "environment": settings.environment,
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )

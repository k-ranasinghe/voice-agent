"""
Health check endpoint with dependency verification.
Checks database, Redis, and external API connectivity.
"""
from fastapi import APIRouter, status
from datetime import datetime
from sqlalchemy import text
import httpx

from src.database import get_db, engine
from src.cache import get_redis
from src.config import settings
from src.observability import get_logger


router = APIRouter()
logger = get_logger(__name__)


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check endpoint - verifies all dependencies.
    Used by Railway/deployment platforms for readiness checks.
    """
    
    checks = {
        "database": await check_database(),
        "redis": await check_redis(),
        "deepgram": await check_deepgram(),
        "elevenlabs": await check_elevenlabs(),
        "openai": await check_openai(),
    }
    
    all_healthy = all(checks.values())
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.environment,
        "checks": checks,
    }


async def check_database() -> bool:
    """Verify PostgreSQL connectivity."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


async def check_redis() -> bool:
    """Verify Redis connectivity."""
    try:
        redis = get_redis()
        await redis.ping()
        return True
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return False


async def check_deepgram() -> bool:
    """Verify Deepgram API accessibility."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://api.deepgram.com/v1/projects",
                headers={"Authorization": f"Token {settings.deepgram_api_key}"},
            )
            return response.status_code in [200, 401]  # 401 means API is reachable
    except Exception as e:
        logger.error(f"Deepgram health check failed: {e}")
        return False


async def check_elevenlabs() -> bool:
    """Verify ElevenLabs API accessibility."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": settings.elevenlabs_api_key},
            )
            return response.status_code == 200
    except Exception as e:
        logger.error(f"ElevenLabs health check failed: {e}")
        return False


async def check_openai() -> bool:
    """Verify OpenAI API accessibility."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            )
            return response.status_code == 200
    except Exception as e:
        logger.error(f"OpenAI health check failed: {e}")
        return False

"""
Admin API endpoints - for monitoring and configuration.
Serves the frontend AdminDashboard with active calls, configurations, and call history.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime, timedelta

from src.database import get_db
from src.database.models import CallSession, Transcript, AgentAction, Configuration
from src.observability import get_logger


router = APIRouter(prefix="/api/admin", tags=["Admin"])
logger = get_logger(__name__)


# ==================== Active Calls ====================

@router.get("/active-calls")
async def get_active_calls(db: AsyncSession = Depends(get_db)):
    """
    List active / recent call sessions (last 24 hours).
    Response shape matches frontend `api.getActiveCalls()`.
    """
    cutoff = datetime.utcnow() - timedelta(hours=24)

    result = await db.execute(
        select(CallSession)
        .where(CallSession.started_at >= cutoff)
        .order_by(desc(CallSession.started_at))
        .limit(50)
    )

    sessions = result.scalars().all()

    return {
        "active_sessions": [
            {
                "session_id": str(s.session_id),
                "customer_id": s.customer_id,
                "intent": s.intent,
                "authenticated": s.authenticated,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "duration": s.duration_seconds,
            }
            for s in sessions
        ]
    }


# ==================== Configurations ====================

class ConfigUpdateBody(BaseModel):
    key: str
    value: str


@router.get("/configurations")
async def get_configurations(db: AsyncSession = Depends(get_db)):
    """
    List all configuration entries.
    Response shape matches frontend `api.getConfigurations()`.
    """
    result = await db.execute(select(Configuration))
    configs = result.scalars().all()

    return {
        "configurations": [
            {
                "id": c.key,  # primary key = key
                "key": c.key,
                "value": str(c.value) if c.value is not None else "",
                "category": c.description or "general",
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in configs
        ]
    }


@router.put("/configurations")
async def update_configuration(body: ConfigUpdateBody, db: AsyncSession = Depends(get_db)):
    """
    Update a single configuration entry by key.
    """
    result = await db.execute(
        select(Configuration).where(Configuration.key == body.key)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail=f"Configuration '{body.key}' not found")

    config.value = body.value
    config.updated_at = datetime.utcnow()
    await db.commit()

    logger.info(f"Configuration updated: {body.key}")

    return {"status": "updated"}


# ==================== Call History ====================

@router.get("/call-history")
async def get_call_history(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """
    List recent call sessions (most recent first).
    Response shape matches frontend `api.getCallHistory()`.
    """
    result = await db.execute(
        select(CallSession)
        .order_by(desc(CallSession.started_at))
        .limit(limit)
    )

    sessions = result.scalars().all()

    return {
        "sessions": [
            {
                "session_id": str(s.session_id),
                "customer_id": s.customer_id,
                "intent": s.intent,
                "authenticated": s.authenticated,
                "escalated": s.escalated,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "duration": s.duration_seconds,
            }
            for s in sessions
        ]
    }


# ==================== Legacy / Analytics Endpoints ====================

@router.get("/calls")
async def list_calls(db: AsyncSession = Depends(get_db)):
    """Legacy: list active call sessions (alias for active-calls)."""
    return await get_active_calls(db)


@router.get("/call/{session_id}/transcript")
async def get_call_transcript(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get full transcript for a call session."""

    result = await db.execute(
        select(Transcript)
        .where(Transcript.session_id == session_id)
        .order_by(Transcript.timestamp)
    )

    transcripts = result.scalars().all()

    if not transcripts:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "messages": [
            {
                "speaker": t.speaker,
                "content": t.content,
                "pii_detected": t.pii_detected,
                "timestamp": t.timestamp.isoformat(),
            }
            for t in transcripts
        ]
    }


@router.get("/call/{session_id}/actions")
async def get_call_actions(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get all agent actions/tool calls for a session."""

    result = await db.execute(
        select(AgentAction)
        .where(AgentAction.session_id == session_id)
        .order_by(AgentAction.timestamp)
    )

    actions = result.scalars().all()

    return {
        "session_id": session_id,
        "actions": [
            {
                "action_type": a.action_type,
                "tool_name": a.tool_name,
                "tool_input": a.tool_input,
                "tool_output": a.tool_output,
                "error": a.error,
                "timestamp": a.timestamp.isoformat(),
            }
            for a in actions
        ]
    }


@router.get("/analytics/intent-distribution")
async def get_intent_distribution(db: AsyncSession = Depends(get_db)):
    """Get distribution of intents over last 7 days."""

    cutoff = datetime.utcnow() - timedelta(days=7)

    result = await db.execute(
        select(
            CallSession.intent,
            func.count(CallSession.session_id).label("count")
        )
        .where(CallSession.started_at >= cutoff)
        .where(CallSession.intent.isnot(None))
        .group_by(CallSession.intent)
    )

    rows = result.all()

    return {
        "period_days": 7,
        "intents": [
            {"intent": row.intent, "count": row.count}
            for row in rows
        ]
    }


@router.get("/analytics/summary")
async def get_analytics_summary(db: AsyncSession = Depends(get_db)):
    """Get overall analytics summary."""

    cutoff = datetime.utcnow() - timedelta(days=7)

    # Total calls
    total_result = await db.execute(
        select(func.count(CallSession.session_id))
        .where(CallSession.started_at >= cutoff)
    )
    total_calls = total_result.scalar()

    # Escalation rate
    escalated_result = await db.execute(
        select(func.count(CallSession.session_id))
        .where(CallSession.started_at >= cutoff)
        .where(CallSession.escalated == True)
    )
    escalated_calls = escalated_result.scalar()

    # Average duration
    duration_result = await db.execute(
        select(func.avg(CallSession.duration_seconds))
        .where(CallSession.started_at >= cutoff)
        .where(CallSession.duration_seconds.isnot(None))
    )
    avg_duration = duration_result.scalar() or 0

    # Auth success rate
    auth_success_result = await db.execute(
        select(func.count(CallSession.session_id))
        .where(CallSession.started_at >= cutoff)
        .where(CallSession.authenticated == True)
    )
    auth_success = auth_success_result.scalar()

    escalation_rate = (escalated_calls / total_calls * 100) if total_calls > 0 else 0
    auth_success_rate = (auth_success / total_calls * 100) if total_calls > 0 else 0

    return {
        "period_days": 7,
        "total_calls": total_calls,
        "escalation_rate": round(escalation_rate, 2),
        "auth_success_rate": round(auth_success_rate, 2),
        "average_duration_seconds": round(avg_duration, 1),
    }

"""
Audit Logging System - Tracks all agent actions and tool calls.
Provides immutable append-only logging to database.
"""
from datetime import datetime
from typing import Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import async_session
from src.database.models import AgentAction, Transcript, CallSession
from src.security.pii_redactor import redact_pii, detect_pii_types
from src.observability import get_logger


logger = get_logger(__name__)


async def log_tool_call(
    session_id: str,
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_output: Dict[str, Any] | None = None,
    error: str | None = None
) -> None:
    """
    Log a tool call to the database audit trail.
    
    Args:
        session_id: UUID of the call session
        tool_name: Name of the tool being called
        tool_input: Input parameters (will be sanitized)
        tool_output: Output result (will be sanitized)
        error: Error message if tool failed
    """
    
    async with async_session() as session:
        action = AgentAction(
            session_id=session_id,
            action_type="tool_call",
            tool_name=tool_name,
            tool_input=tool_input,  # JSONB field
            tool_output=tool_output,
            error=error,
            timestamp=datetime.utcnow(),
        )
        
        session.add(action)
        await session.commit()
        
        logger.info(f"📝 Logged tool call: {tool_name} | Session: {session_id}")


async def log_transcript(
    session_id: str,
    speaker: str,
    content: str
) -> None:
    """
    Log a conversation turn to transcripts table.
    Detects and redacts PII before storing.
    
    Args:
        session_id: UUID of the call session
        speaker: 'user' or 'agent'
        content: Message content
    """
    
    # Detect PII (don't redact, just flag)
    pii_types = detect_pii_types(content)
    
    # Redact PII for storage
    redacted_content, _ = redact_pii(content, strict_mode=False)
    
    async with async_session() as session:
        transcript = Transcript(
            session_id=session_id,
            speaker=speaker,
            content=redacted_content,
            pii_detected=pii_types if pii_types else None,
            timestamp=datetime.utcnow(),
        )
        
        session.add(transcript)
        await session.commit()
        
        if pii_types:
            logger.warning(f"Transcript logged with PII detection: {', '.join(pii_types)}")


async def update_session(
    session_id: str,
    **updates
) -> None:
    """
    Update call session metadata.
    
    Args:
        session_id: Session UUID
        **updates: Fields to update (customer_id, intent, authenticated, etc.)
    """
    
    from sqlalchemy import update
    
    async with async_session() as session:
        await session.execute(
            update(CallSession)
            .where(CallSession.session_id == session_id)
            .values(**updates)
        )
        await session.commit()
        
        logger.debug(f"Session updated: {session_id} | Fields: {list(updates.keys())}")


async def close_session(session_id: str, duration_seconds: int) -> None:
    """
    Close a call session and record duration.
    
    Args:
        session_id: Session UUID
        duration_seconds: Call duration in seconds
    """
    
    await update_session(
        session_id=session_id,
        ended_at=datetime.utcnow(),
        duration_seconds=duration_seconds,
    )
    
    logger.info(f"Session closed: {session_id} | Duration: {duration_seconds}s")

"""
SQLAlchemy ORM models for the banking voice agent.
Defines all database tables as per the schema in agents.md.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String, Integer, Numeric, Boolean, Text, TIMESTAMP, ARRAY,
    ForeignKey, Index, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import uuid


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Customer(Base):
    """Customer table - contains customer information and hashed PINs."""
    __tablename__ = "customers"
    
    customer_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(100))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    pin_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, 
        server_default=func.now()
    )
    
    # Relationships
    accounts: Mapped[list["Account"]] = relationship(back_populates="customer")
    call_sessions: Mapped[list["CallSession"]] = relationship(back_populates="customer")


class Account(Base):
    """Account table - customer bank accounts."""
    __tablename__ = "accounts"
    
    account_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("customers.customer_id"),
        nullable=False
    )
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)  # checking, savings
    balance: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=func.now()
    )
    
    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="accounts")
    cards: Mapped[list["Card"]] = relationship(back_populates="account")


class Card(Base):
    """Card table - debit/credit cards linked to accounts."""
    __tablename__ = "cards"
    
    card_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("accounts.account_id"),
        nullable=False
    )
    card_number_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, blocked, expired
    blocked_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)
    blocked_reason: Mapped[Optional[str]] = mapped_column(Text)
    expiration_date: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=func.now()
    )
    
    # Relationships
    account: Mapped["Account"] = relationship(back_populates="cards")


class CallSession(Base):
    """Call session table - tracks each voice call session."""
    __tablename__ = "call_sessions"
    
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    customer_id: Mapped[Optional[str]] = mapped_column(
        String(20),
        ForeignKey("customers.customer_id")
    )
    intent: Mapped[Optional[str]] = mapped_column(String(50))
    authenticated: Mapped[bool] = mapped_column(Boolean, default=False)
    authentication_method: Mapped[Optional[str]] = mapped_column(String(20))
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    escalation_reason: Mapped[Optional[str]] = mapped_column(Text)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=func.now()
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)
    
    # Relationships
    customer: Mapped[Optional["Customer"]] = relationship(back_populates="call_sessions")
    transcripts: Mapped[list["Transcript"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan"
    )
    agent_actions: Mapped[list["AgentAction"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_sessions_customer", "customer_id"),
        Index("idx_sessions_started", "started_at"),
    )


class Transcript(Base):
    """Transcript table - conversation logs for each session."""
    __tablename__ = "transcripts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("call_sessions.session_id"),
        nullable=False
    )
    speaker: Mapped[str] = mapped_column(String(10), nullable=False)  # user or agent
    content: Mapped[str] = mapped_column(Text, nullable=False)
    pii_detected: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String(100)))
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=func.now()
    )
    
    # Relationships
    session: Mapped["CallSession"] = relationship(back_populates="transcripts")
    
    # Indexes
    __table_args__ = (
        Index("idx_transcripts_session", "session_id"),
    )


class AgentAction(Base):
    """Agent action table - audit trail for all tool calls and actions."""
    __tablename__ = "agent_actions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("call_sessions.session_id"),
        nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)  # tool_call, escalation, etc.
    tool_name: Mapped[Optional[str]] = mapped_column(String(50))
    tool_input: Mapped[Optional[dict]] = mapped_column(JSONB)
    tool_output: Mapped[Optional[dict]] = mapped_column(JSONB)
    error: Mapped[Optional[str]] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=func.now()
    )
    
    # Relationships
    session: Mapped["CallSession"] = relationship(back_populates="agent_actions")
    
    # Indexes
    __table_args__ = (
        Index("idx_actions_session", "session_id"),
        Index("idx_actions_tool", "tool_name"),
    )


class Configuration(Base):
    """Configuration table - stores system prompts and settings."""
    __tablename__ = "configurations"
    
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    updated_by: Mapped[Optional[str]] = mapped_column(String(50))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now()
    )

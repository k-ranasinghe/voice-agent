"""
AgentState TypedDict schema for LangGraph workflow.
Defines all state fields tracked throughout the agent conversation.
"""
from typing import TypedDict, Annotated, Sequence, Literal
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """
    Complete state schema for banking voice agent.
    
    This state is persisted via PostgreSQL checkpointer and passed
    through all nodes in the LangGraph workflow.
    """
    
    # === Conversation Thread ===
    messages: Annotated[Sequence[BaseMessage], add_messages]
    """Conversation messages with automatic deduplication"""
    
    # === User Context ===
    customer_id: str | None
    """Verified customer ID (e.g., CUST00001)"""
    
    authenticated: bool
    """Whether user has passed identity verification"""
    
    authentication_method: Literal["pin", "otp", "voice"] | None
    """Method used for authentication (POC uses PIN only)"""
    
    verification_attempts: int
    """Number of failed verification attempts (max 3)"""
    
    # === Conversation Metadata ===
    session_id: str
    """UUID for this call session"""
    
    intent: Literal[
        "card_atm",
        "account_servicing",
        "account_opening",
        "digital_support",
        "transfer_payment",
        "account_closure",
        "general_inquiry"
    ] | None
    """Classified user intent"""
    
    intent_confidence: float | None
    """Confidence score for intent classification (0.0-1.0)"""
    
    flow_stage: str | None
    """Current stage within the flow (e.g., 'card_blocked', 'awaiting_confirmation')"""
    
    needs_user_input: bool
    """When True, graph should END to return control to the user for input"""
    
    resume_node: str | None
    """When set, intent_router skips re-classification and routes directly to this node"""
    
    escalation_requested: bool
    """True if user requests human or agent gives up"""
    
    escalation_reason: str | None
    """Why escalation was triggered"""
    
    # === Tool Results Cache (avoid redundant calls) ===
    last_tool_output: dict | None
    """Most recent tool execution result"""
    
    account_balance: float | None
    """Cached account balance after get_account_balance()"""
    
    recent_transactions: list[dict] | None
    """Cached transactions after get_recent_transactions()"""
    
    card_details: dict | None
    """Cached card info after checking card status"""
    
    # === Security & Compliance ===
    pii_detected: list[str]
    """Types of PII detected (SSN, CREDIT_CARD, etc.)"""
    
    suspicious_activity: bool
    """Fraud detection flag"""
    
    critical_actions_taken: list[str]
    """Irreversible actions like block_card()"""
    
    # === Metrics ===
    turn_count: int
    """Number of conversation turns"""
    
    start_time: float
    """Unix timestamp when session started"""

"""
Security Check Node - Handles customer authentication via PIN verification.
Enforces 3-attempt limit and extracts customer ID from conversation.
"""
import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field
import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.state import AgentState
from src.config import settings
from src.database.models import Customer
from src.database.connection import async_session
from src.observability import get_logger


logger = get_logger(__name__)


class IdentityExtraction(BaseModel):
    """Structured output for extracting customer ID and PIN from conversation."""
    
    customer_id: str | None = Field(
        description="Customer ID mentioned by user (format: CUST##### or similar)"
    )
    pin: str | None = Field(
        description="4-digit PIN mentioned by user"
    )
    has_identity_info: bool = Field(
        description="True if customer provided either ID or PIN"
    )


IDENTITY_EXTRACTION_PROMPT = """You are an identity extraction expert for Bank ABC.

Analyze the conversation and extract:
1. **Customer ID**: Usually in format "CUST00001" or similar
2. **PIN**: A 4-digit number mentioned as password/PIN

**Important Rules:**
- Only extract if EXPLICITLY mentioned by the user
- Do NOT invent or guess IDs
- PINs are exactly 4 digits
- If user says "my ID is CUST00001" → extract "CUST00001"
- If user says "my PIN is 1234" → extract "1234"
- If user says "I don't know my ID" → return None

Look only at the most recent messages for new information.
"""


async def verify_pin(customer_id: str, pin: str) -> bool:
    """
    Verify customer PIN against database.
    
    Args:
        customer_id: Customer ID
        pin: Provided PIN
        
    Returns:
        True if PIN matches, False otherwise
    """
    async with async_session() as session:
        result = await session.execute(
            select(Customer).where(Customer.customer_id == customer_id)
        )
        customer = result.scalar_one_or_none()
        
        if not customer:
            logger.warning(f"Customer {customer_id} not found")
            return False
        
        # Verify PIN with bcrypt
        pin_bytes = pin.encode('utf-8')
        hash_bytes = customer.pin_hash.encode('utf-8')
        
        return bcrypt.checkpw(pin_bytes, hash_bytes)


async def security_check_node(state: AgentState) -> AgentState:
    """
    Security Check Node - Authenticates customer before sensitive operations.
    
    Flow:
    1. Check if already authenticated → skip
    2. Extract customer ID and PIN from conversation
    3. Verify credentials
    4. Update authentication status
    5. Track failed attempts (max 3)
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with authentication status
    """
    
    # Already authenticated?
    if state.get("authenticated"):
        logger.info("Customer already authenticated, skipping verification")
        return state
    
    # Max attempts reached?
    verification_attempts = state.get("verification_attempts", 0)
    if verification_attempts >= 3:
        logger.warning("Max verification attempts reached, escalating")
        return {
            **state,
            "escalation_requested": True,
            "escalation_reason": "Failed authentication after 3 attempts",
            "messages": state["messages"] + [
                AIMessage(content=(
                    "I'm sorry, but for your security, I need to transfer you "
                    "to a representative after multiple failed verification attempts. "
                    "Please hold while I connect you."
                ))
            ]
        }
    
    # Extract identity information from conversation
    llm = ChatOpenAI(
        model="gpt-4.1-mini",
        temperature=0.0,
        api_key=settings.openai_api_key,
    ).with_structured_output(IdentityExtraction)
    
    # Build conversation context
    conversation_text = "\n".join([
        f"{msg.type}: {msg.content}"
        for msg in state["messages"][-5:]  # Last 5 messages for context
    ])
    
    try:
        extraction: IdentityExtraction = llm.invoke([
            SystemMessage(content=IDENTITY_EXTRACTION_PROMPT),
            HumanMessage(content=conversation_text),
        ])
        
        logger.info(f"Extracted - ID: {extraction.customer_id}, Has PIN: {extraction.pin is not None}")
        
        # If no identity info provided yet, ask for it
        if not extraction.has_identity_info:
            logger.info("No identity info provided, requesting from user")
            
            # Determine what to ask for
            if not state.get("customer_id"):
                prompt = (
                    "For security purposes, I'll need to verify your identity. "
                    "Could you please provide your Customer ID? "
                    "It should be in the format CUST followed by numbers, like CUST00001."
                )
            else:
                prompt = (
                    f"Thank you. Now, could you please provide your 4-digit PIN "
                    f"to verify your identity?"
                )
            
            return {
                **state,
                "needs_user_input": True,
                "resume_node": "security_check",
                "messages": state["messages"] + [AIMessage(content=prompt)]
            }
        
        # Update customer ID if provided
        if extraction.customer_id:
            state = {**state, "customer_id": extraction.customer_id}
        
        # If we have both ID and PIN, verify
        if extraction.customer_id and extraction.pin:
            is_valid = await verify_pin(extraction.customer_id, extraction.pin)
            
            if is_valid:
                logger.info(f"Authentication successful for {extraction.customer_id}")
                
                return {
                    **state,
                    "authenticated": True,
                    "authentication_method": "pin",
                    "customer_id": extraction.customer_id,
                    "needs_user_input": False,
                    "resume_node": None,
                    "messages": state["messages"] + [
                        AIMessage(content=(
                            "Thank you for verifying your identity. "
                            "How can I assist you today?"
                        ))
                    ]
                }
            else:
                logger.warning(f"Authentication failed for {extraction.customer_id}")
                
                new_attempts = verification_attempts + 1
                remaining_attempts = 3 - new_attempts
                
                if remaining_attempts > 0:
                    message = (
                        f"I'm sorry, but that PIN doesn't match our records. "
                        f"You have {remaining_attempts} attempt(s) remaining. "
                        f"Please try again."
                    )
                else:
                    message = (
                        "I'm sorry, but I need to transfer you to a representative "
                        "for security reasons. Please hold."
                    )
                
                return {
                    **state,
                    "verification_attempts": new_attempts,
                    "needs_user_input": True,
                    "resume_node": "security_check",
                    "messages": state["messages"] + [AIMessage(content=message)]
                }
        
        # Have customer ID but still need PIN — ask for it
        if extraction.customer_id and not extraction.pin:
            return {
                **state,
                "customer_id": extraction.customer_id,
                "needs_user_input": True,
                "resume_node": "security_check",
                "messages": state["messages"] + [
                    AIMessage(content=(
                        f"Thank you. Now, could you please provide your "
                        f"4-digit PIN to verify your identity?"
                    ))
                ]
            }
        
        # Shouldn't reach here, but ask for credentials as fallback
        return {
            **state,
            "needs_user_input": True,
            "resume_node": "security_check",
            "messages": state["messages"] + [
                AIMessage(content="Could you please provide your Customer ID and PIN?")
            ]
        }
        
    except Exception as e:
        logger.error(f"Security check failed: {e}", exc_info=True)
        
        # On error, ask for credentials manually
        return {
            **state,
            "needs_user_input": True,
            "resume_node": "security_check",
            "messages": state["messages"] + [
                AIMessage(content=(
                    "I apologize, but I'm having trouble verifying your identity. "
                    "Could you please provide your Customer ID and PIN?"
                ))
            ]
        }


def check_auth_status(state: AgentState) -> str:
    """
    Conditional edge - Routes based on authentication status.
    
    Returns:
        Next node name based on auth status and intent
    """
    
    if state.get("escalation_requested"):
        return "escalation"
    
    # If the node asked a question and needs user input, end the graph
    # so the WebSocket handler can wait for the user's next message
    if state.get("needs_user_input"):
        return "__end__"
    
    if not state.get("authenticated"):
        return "security_check"  # Loop back for more auth attempts
    
    # Authenticated - route to appropriate flow
    intent = state.get("intent")
    
    intent_to_node = {
        "card_atm": "card_atm_agent",
        "account_servicing": "account_servicing_agent",
        "transfer_payment": "transfer_agent",
        "account_closure": "closure_agent",
    }
    
    return intent_to_node.get(intent, "escalation")

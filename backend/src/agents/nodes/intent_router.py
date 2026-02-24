"""
Intent Router Node - Classifies user intent using LLM structured output.
This is the entry point for the LangGraph workflow.
"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from typing import Literal

from src.agents.state import AgentState
from src.config import settings
from src.observability import get_logger


logger = get_logger(__name__)


class IntentClassification(BaseModel):
    """Structured output schema for intent classification."""
    
    intent: Literal[
        "card_atm",
        "account_servicing",
        "account_opening",
        "digital_support",
        "transfer_payment",
        "account_closure",
        "general_inquiry"
    ] = Field(description="The primary intent of the user's query")
    
    confidence: float = Field(
        description="Confidence score between 0.0 and 1.0",
        ge=0.0,
        le=1.0
    )
    
    reasoning: str = Field(
        description="Brief explanation of why this intent was chosen"
    )


# System prompt for intent classification
INTENT_SYSTEM_PROMPT = """You are an intent classification expert for Bank ABC's voice assistant.

Analyze the customer's message and classify it into ONE of these categories:

1. **card_atm**: Lost/stolen cards, ATM issues, card declined, cash not dispensed, card fraud
2. **account_servicing**: Statement requests, profile updates (address, phone, email), balance inquiries
3. **account_opening**: New account inquiries, eligibility, appointment booking, lead capture
4. **digital_support**: App issues, login problems, OTP not received, device change, app crashes
5. **transfer_payment**: Failed/pending transfers, beneficiary management, bill payment issues
6. **account_closure**: Account closure requests, retention attempts
7. **general_inquiry**: Hours, locations, product information, general questions

**Classification Guidelines:**
- If the user mentions "card" with a problem → card_atm
- If the user wants to update their information → account_servicing
- If the user can't access the app → digital_support
- If the user wants to close their account → account_closure
- If unclear or multiple intents → general_inquiry

**Important:**
- Only classify based on the user's MOST RECENT message
- Set confidence < 0.6 if uncertain
- Provide clear reasoning for your choice
"""


def route_intent_node(state: AgentState) -> AgentState:
    """
    Intent Router Node - Entry point of the LangGraph workflow.
    
    Classifies user intent using GPT-4 with structured output.
    Updates state with intent and confidence score.
    
    If `resume_node` is set (mid-flow resumption), skips re-classification
    and preserves the existing intent so `route_to_flow` can route directly.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with intent and confidence
    """
    
    # Mid-flow resumption: skip intent re-classification if we're
    # resuming a flow that was waiting for user input
    if state.get("resume_node"):
        logger.info(
            f"Resuming mid-flow at '{state['resume_node']}', "
            f"skipping intent re-classification (intent={state.get('intent')})"
        )
        return state
    
    # Get the last user message
    user_messages = [msg for msg in state["messages"] if msg.type == "human"]
    
    if not user_messages:
        logger.warning("No user messages found for intent classification")
        return {
            **state,
            "intent": "general_inquiry",
            "intent_confidence": 0.5,
        }
    
    last_user_message = user_messages[-1].content
    
    logger.info(f"Classifying intent for: '{last_user_message[:100]}...'")
    
    # Initialize LLM with structured output
    llm = ChatOpenAI(
        model="gpt-4.1-mini",
        temperature=0.0,
        api_key=settings.openai_api_key,
    ).with_structured_output(IntentClassification)
    
    # Invoke LLM
    try:
        result: IntentClassification = llm.invoke([
            SystemMessage(content=INTENT_SYSTEM_PROMPT),
            HumanMessage(content=last_user_message),
        ])
        
        logger.info(
            f"Intent classified: {result.intent} "
            f"(confidence: {result.confidence:.2f}, "
            f"reasoning: {result.reasoning})"
        )
        
        # Update state
        return {
            **state,
            "intent": result.intent,
            "intent_confidence": result.confidence,
        }
        
    except Exception as e:
        logger.error(f"Intent classification failed: {e}", exc_info=True)
        
        # Fallback to general_inquiry
        return {
            **state,
            "intent": "general_inquiry",
            "intent_confidence": 0.3,
        }


def route_to_flow(state: AgentState) -> str:
    """
    Conditional edge function - Routes to appropriate agent based on intent.
    
    If `resume_node` is set, routes directly to that node for mid-flow
    resumption (e.g., returning to security_check after user provides credentials).
    
    Returns next node name.
    """
    
    # Mid-flow resumption: route directly to the node that was waiting
    resume = state.get("resume_node")
    if resume:
        logger.info(f"Mid-flow resumption: routing directly to '{resume}'")
        return resume
    
    intent = state.get("intent")
    confidence = state.get("intent_confidence", 0.0)
    
    # If intent unclear, go to general inquiry handler
    if confidence < 0.5:
        logger.info("Low confidence, routing to general inquiry")
        return "general_inquiry_node"
    
    # Map intents to node names
    intent_to_node = {
        "card_atm": "security_check",
        "account_servicing": "security_check",
        "transfer_payment": "security_check",
        "account_closure": "security_check",
        "account_opening": "opening_agent",
        "digital_support": "digital_agent",
        "general_inquiry": "general_inquiry_node",
    }
    
    next_node = intent_to_node.get(intent, "general_inquiry_node")
    logger.info(f"Routing to: {next_node}")
    
    return next_node

"""
Card & ATM Agent Node - Deep Logic Implementation.
Handles lost/stolen cards, card blocking, ATM issues, and declined payments.
"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field
from typing import Literal

from src.agents.state import AgentState
from src.tools.banking import block_card, get_card_details
from src.config import settings
from src.observability import get_logger


logger = get_logger(__name__)


class CardAction(BaseModel):
    """Structured output for card agent decisions."""
    
    action: Literal[
        "block_card",
        "check_status",
        "gather_info",
        "complete",
        "escalate"
    ] = Field(description="Next action to take")
    
    card_id: str | None = Field(
        description="Card ID if mentioned (e.g., CARD00001)"
    )
    
    reason: str | None = Field(
        description="Reason for card block (Lost, Stolen, Fraud, Damaged)"
    )
    
    confirmation_needed: bool = Field(
        description="True if need to confirm card block with user"
    )
    
    response: str = Field(
        description="Response message to user"
    )


CARD_AGENT_PROMPT = """You are a specialized agent for Bank ABC handling card and ATM issues.

**Your Capabilities:**
- Help with lost/stolen cards
- Block cards (requires explicit user confirmation)
-Check card status
- Report ATM issues (cash not dispensed, card stuck)
- Help with declined payments

**Conversation Flow for Lost/Stolen Card:**
1. Ask which card (if customer has multiple)
2. Confirm they want to block it (REQUIRED before blocking)
3. Block the card using the tool
4. Provide reference number and explain next steps (replacement card)

**Important Rules:**
- NEVER block a card without explicit confirmation from the user
- If user says "my card was stolen" → ask "To protect your account, would you like me to block this card?"
- After blocking, tell them: "Card blocked successfully. Reference: {{reference_id}}. A replacement will arrive in 5-7 business days."
- For ATM issues (cash not dispensed), create a dispute case
- Stay focused on card/ATM issues only

**Current State:**
- Customer ID: {customer_id}
- Authenticated: {authenticated}

Analyze the conversation and decide the next action.
"""


async def card_atm_agent_node(state: AgentState) -> AgentState:
    """
    Card & ATM Agent - Handles card-related issues with deep logic.
    
    Flow:
    1. Understand issue (lost/stolen/ATM/declined)
    2. If block needed → get confirmation
    3. Execute block_card() tool
    4. Provide reference ID and next steps
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with agent response
    """
    
    customer_id = state.get("customer_id")
    
    # Build conversation context
    conversation_history = "\n".join([
        f"{msg.type}: {msg.content}"
        for msg in state["messages"][-10:]  # Last 10 messages
    ])
    
    # Prepare prompt with state context
    system_prompt = CARD_AGENT_PROMPT.format(
        customer_id=customer_id,
        authenticated=state.get("authenticated", False)
    )
    
    # Initialize LLM with structured output
    llm = ChatOpenAI(
        model="gpt-4.1-mini",
        temperature=0.0,
        api_key=settings.openai_api_key,
    ).with_structured_output(CardAction)
    
    try:
        decision: CardAction = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Conversation:\n{conversation_history}")
        ])
        
        logger.info(f"Card agent action: {decision.action}")
        
        # Execute action
        if decision.action == "block_card":
            if not decision.confirmation_needed:
                # User confirmed, execute block
                if decision.card_id:
                    result = await block_card(
                        state,
                        card_id=decision.card_id,
                        reason=decision.reason or "Customer request"
                    )
                    
                    if result["success"]:
                        response = (
                            f"Your card ending in {result.get('last_4', 'XXXX')} has been blocked successfully. "
                            f"Reference number: {result['reference_id']}. "
                            f"A replacement card will be mailed to your address on file within 5-7 business days. "
                            f"Is there anything else I can help you with?"
                        )
                        
                        # Mark flow as complete
                        return {
                            **state,
                            "flow_stage": "card_blocked",
                            "messages": state["messages"] + [AIMessage(content=response)]
                        }
                    else:
                        response = f"I encountered an issue: {result.get('error')}. Let me transfer you to a specialist."
                        return {
                            **state,
                            "escalation_requested": True,
                            "escalation_reason": f"Card block failed: {result.get('error')}",
                            "messages": state["messages"] + [AIMessage(content=response)]
                        }
                else:
                    # Need card ID
                    return {
                        **state,
                        "needs_user_input": True,
                        "resume_node": "card_atm_agent",
                        "messages": state["messages"] + [
                            AIMessage(content="Could you provide your card number or the last 4 digits?")
                        ]
                    }
            else:
                # Need confirmation first
                return {
                    **state,
                    "flow_stage": "awaiting_confirmation",
                    "needs_user_input": True,
                    "resume_node": "card_atm_agent",
                    "messages": state["messages"] + [AIMessage(content=decision.response)]
                }
        
        elif decision.action == "check_status":
            if decision.card_id:
                card_info = await get_card_details(state, decision.card_id)
                
                if card_info["success"]:
                    status = card_info["status"]
                    response = f"Your card ending in {card_info['last_4']} is currently {status}."
                    if status == "blocked":
                        response += f" It was blocked on {card_info['blocked_at']} due to: {card_info['blocked_reason']}."
                else:
                    response = "I couldn't find that card in our system. Could you verify the card number?"
                
                return {
                    **state,
                    "messages": state["messages"] + [AIMessage(content=response)]
                }
        
        elif decision.action == "escalate":
            return {
                **state,
                "escalation_requested": True,
                "escalation_reason": "Card issue requires specialist",
                "messages": state["messages"] + [AIMessage(content=decision.response)]
            }
        
        elif decision.action == "complete":
            return {
                **state,
                "flow_stage": "complete",
                "messages": state["messages"] + [AIMessage(content=decision.response)]
            }
        
        else:  # gather_info or default
            return {
                **state,
                "needs_user_input": True,
                "resume_node": "card_atm_agent",
                "messages": state["messages"] + [AIMessage(content=decision.response)]
            }
    
    except Exception as e:
        logger.error(f"Card agent error: {e}", exc_info=True)
        
        return {
            **state,
            "escalation_requested": True,
            "escalation_reason": f"Agent error: {str(e)}",
            "messages": state["messages"] + [
                AIMessage(content="I'm having trouble processing your request. Let me connect you with a specialist.")
            ]
        }


def check_card_flow_completion(state: AgentState) -> str:
    """Check if card flow is complete."""
    
    if state.get("escalation_requested"):
        return "escalation"
    
    if state.get("needs_user_input"):
        return "__end__"
    
    if state.get("flow_stage") in ["card_blocked", "complete"]:
        return "complete"
    
    # Continue in card agent
    return "card_atm_agent"

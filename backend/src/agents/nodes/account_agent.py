"""
Account Servicing Agent Node - Deep Logic Implementation.
Handles statement requests, profile updates, and balance inquiries.
"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field
from typing import Literal

from src.agents.state import AgentState
from src.tools.banking import (
    get_account_balance,
    request_statement,
    update_profile
)
from src.config import settings
from src.observability import get_logger


logger = get_logger(__name__)


class AccountServiceAction(BaseModel):
    """Structured output for account servicing decisions."""
    
    action: Literal[
        "get_balance",
        "request_statement",
        "update_profile",
        "gather_info",
        "complete",
        "escalate"
    ] = Field(description="Next action to take")
    
    statement_period: Literal["monthly", "quarterly", "annual"] | None = Field(
        description="Statement period if requesting statement"
    )
    
    profile_updates: dict | None = Field(
        description="Profile fields to update (email, phone)"
    )
    
    response: str = Field(
        description="Response message to user"
    )


ACCOUNT_SERVICING_PROMPT = """You are a specialized agent for Bank ABC handling account servicing requests.

**Your Capabilities:**
- Provide account balance
- Request account statements (monthly, quarterly, annual)
- Update profile information (email, phone)
- Answer account-related questions

**Conversation Flow Examples:**

**Balance Inquiry:**
User: "What's my balance?"
Action: get_balance → Tell them total and per account

**Statement Request:**
User: "I need a statement"
Action: gather_info (which period?) → request_statement → Confirm it will be emailed

**Profile Update:**
User: "Update my email to john@example.com"
Action: update_profile → Confirm update successful

**Important Rules:**
- For balance, show both total and breakdown by account
- For statements, confirm period (monthly/quarterly/annual) before requesting
- For profile updates, only allow email and phone changes
- Stay focused on account servicing only

**Current State:**
- Customer ID: {customer_id}
- Authenticated: {authenticated}

Analyze the conversation and decide the next action.
"""


async def account_servicing_agent_node(state: AgentState) -> AgentState:
    """
    Account Servicing Agent - Handles account-related requests with deep logic.
    
    Flow:
    1. Understand request (balance/statement/profile update)
    2. Gather any missing information
    3. Execute appropriate tool
    4. Confirm completion
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with agent response
    """
    
    customer_id = state.get("customer_id")
    
    # Build conversation context
    conversation_history = "\n".join([
        f"{msg.type}: {msg.content}"
        for msg in state["messages"][-10:]
    ])
    
    # Prepare prompt
    system_prompt = ACCOUNT_SERVICING_PROMPT.format(
        customer_id=customer_id,
        authenticated=state.get("authenticated", False)
    )
    
    # Initialize LLM
    llm = ChatOpenAI(
        model="gpt-4.1-mini",
        temperature=0.0,
        api_key=settings.openai_api_key,
    ).with_structured_output(AccountServiceAction)
    
    try:
        decision: AccountServiceAction = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Conversation:\n{conversation_history}")
        ])
        
        logger.info(f"Account servicing action: {decision.action}")
        
        # Execute action
        if decision.action == "get_balance":
            result = await get_account_balance(state, customer_id)
            
            if result["success"]:
                accounts_text = "\n".join([
                    f"- {acc['account_type'].title()}: ${acc['balance']:,.2f}"
                    for acc in result["accounts"]
                ])
                
                response = (
                    f"Here are your account balances:\n{accounts_text}\n"
                    f"Total: ${result['total_balance']:,.2f}\n"
                    f"Is there anything else I can help you with?"
                )
                
                return {
                    **state,
                    "account_balance": result["total_balance"],
                    "flow_stage": "complete",
                    "messages": state["messages"] + [AIMessage(content=response)]
                }
            else:
                response = f"I couldn't retrieve your balance: {result.get('error')}"
                return {
                    **state,
                    "messages": state["messages"] + [AIMessage(content=response)]
                }
        
        elif decision.action == "request_statement":
            period = decision.statement_period or "monthly"
            
            result = await request_statement(state, customer_id, period)
            
            if result["success"]:
                response = (
                    f"Your {period} statement has been requested. "
                    f"Reference number: {result['reference_id']}. "
                    f"{result['message']}"
                )
                
                return {
                    **state,
                    "flow_stage": "complete",
                    "messages": state["messages"] + [AIMessage(content=response)]
                }
        
        elif decision.action == "update_profile":
            if decision.profile_updates:
                result = await update_profile(state, customer_id, decision.profile_updates)
                
                if result["success"]:
                    updated = ", ".join(result["updated_fields"])
                    response = f"Your {updated} has been updated successfully."
                    
                    return {
                        **state,
                        "flow_stage": "complete",
                        "messages": state["messages"] + [AIMessage(content=response)]
                    }
                else:
                    response = f"Update failed: {result.get('error')}"
                    return {
                        **state,
                        "messages": state["messages"] + [AIMessage(content=response)]
                    }
        
        elif decision.action == "escalate":
            return {
                **state,
                "escalation_requested": True,
                "escalation_reason": "Account servicing requires specialist",
                "messages": state["messages"] + [AIMessage(content=decision.response)]
            }
        
        elif decision.action == "complete":
            return {
                **state,
                "flow_stage": "complete",
                "messages": state["messages"] + [AIMessage(content=decision.response)]
            }
        
        else:  # gather_info
            return {
                **state,
                "needs_user_input": True,
                "resume_node": "account_servicing_agent",
                "messages": state["messages"] + [AIMessage(content=decision.response)]
            }
    
    except Exception as e:
        logger.error(f"Account servicing error: {e}", exc_info=True)
        
        return {
            **state,
            "escalation_requested": True,
            "escalation_reason": f"Agent error: {str(e)}",
            "messages": state["messages"] + [
                AIMessage(content="I'm having trouble. Let me connect you with a specialist.")
            ]
        }


def check_account_flow_completion(state: AgentState) -> str:
    """Check if account servicing flow is complete."""
    
    if state.get("escalation_requested"):
        return "escalation"
    
    if state.get("needs_user_input"):
        return "__end__"
    
    if state.get("flow_stage") == "complete":
        return "complete"
    
    return "account_servicing_agent"

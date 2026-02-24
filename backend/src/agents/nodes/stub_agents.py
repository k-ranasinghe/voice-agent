"""
Stub Agents - Simple routing for flows without deep logic.
These agents provide basic responses and escalate to human specialists.
"""
from langchain_core.messages import AIMessage
from src.agents.state import AgentState
from src.tools.banking import create_lead
from src.observability import get_logger


logger = get_logger(__name__)


# ==================== ACCOUNT OPENING ====================

async def account_opening_agent_node(state: AgentState) -> AgentState:
    """
    Account Opening Agent (Stub) - Captures lead and escalates.
    
    Flow:
    1. Gather basic info (name, email, phone, account type)
    2. Create lead
    3. Inform user a representative will contact them
    """
    
    logger.info("Account opening agent activated")
    
    # For POC, just capture intent and create lead
    response = (
        "Thank you for your interest in opening an account with Bank ABC! "
        "Our account specialists can help you choose the right account for your needs. "
        "May I have your name, email, and phone number to have someone contact you?"
    )
    
    # Check if we have enough info to create lead
    messages_content = " ".join([msg.content for msg in state["messages"] if msg.type == "human"])
    
    # Simple check for email pattern (very basic for POC)
    import re
    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', messages_content)
    
    if email_match:
        # Create lead with extracted info
        lead_data = {
            "name": "Prospective Customer",  # In production, extract properly
            "email": email_match.group(),
            "phone": "TBD",
            "account_type": "checking"
        }
        
        result = await create_lead(state, lead_data)
        
        response = (
            f"Thank you! I've created a reference for you: {result['reference_id']}. "
            f"{result['message']}"
        )
        
        return {
            **state,
            "flow_stage": "complete",
            "messages": state["messages"] + [AIMessage(content=response)]
        }
    
    return {
        **state,
        "needs_user_input": True,
        "resume_node": "opening_agent",
        "messages": state["messages"] + [AIMessage(content=response)]
    }


# ==================== DIGITAL SUPPORT ====================

async def digital_support_agent_node(state: AgentState) -> AgentState:
    """
    Digital Support Agent (Stub) - Escalates app/online banking issues.
    
    Digital issues require screen sharing and technical troubleshooting,
    so we escalate to human support.
    """
    
    logger.info("Digital support agent activated")
    
    response = (
        "I understand you're having trouble with our digital banking services. "
        "Our technical support team is best equipped to help you with app and online banking issues. "
        "Let me connect you with a digital banking specialist who can assist you right away."
    )
    
    return {
        **state,
        "escalation_requested": True,
        "escalation_reason": "Digital support - requires technical specialist",
        "messages": state["messages"] + [AIMessage(content=response)]
    }


# ==================== TRANSFER & PAYMENT ====================

async def transfer_payment_agent_node(state: AgentState) -> AgentState:
    """
    Transfer & Payment Agent (Stub) - Escalates to specialist.
    
    Transfer issues require security verification and transaction investigation,
    so we escalate to human support.
    """
    
    logger.info("Transfer/payment agent activated")
    
    response = (
        "I can help connect you with our payments team. "
        "Transfer and payment issues require detailed investigation. "
        "Let me transfer you to a specialist who can review your transaction and resolve this for you."
    )
    
    return {
        **state,
        "escalation_requested": True,
        "escalation_reason": "Transfer/payment issue - requires specialist",
        "messages": state["messages"] + [AIMessage(content=response)]
    }


# ==================== ACCOUNT CLOSURE ====================

async def account_closure_agent_node(state: AgentState) -> AgentState:
    """
    Account Closure Agent (Stub) - Retention attempt + escalation.
    
    Flow:
    1. Ask reason for closure
    2. Attempt basic retention (e.g., offer to waive fees)
    3. Escalate to retention specialist
    """
    
    logger.info("Account closure agent activated")
    
    # Check if user already stated reason
    user_messages = [msg.content.lower() for msg in state["messages"] if msg.type == "human"]
    
    # Simple retention attempt
    if not state.get("flow_stage"):
        response = (
            "I'm sorry to hear you're considering closing your account. "
            "May I ask what's prompting this decision? "
            "Perhaps there's something we can do to address your concerns."
        )
        
        return {
            **state,
            "flow_stage": "retention_attempt",
            "needs_user_input": True,
            "resume_node": "closure_agent",
            "messages": state["messages"] + [AIMessage(content=response)]
        }
    else:
        # After retention attempt, escalate
        response = (
            "I appreciate you sharing that with me. "
            "Our customer retention team would like to discuss options with you personally. "
            "Let me connect you with a specialist who can help."
        )
        
        return {
            **state,
            "escalation_requested": True,
            "escalation_reason": "Account closure - retention specialist needed",
            "messages": state["messages"] + [AIMessage(content=response)]
        }


# ==================== GENERAL INQUIRY ====================

async def general_inquiry_agent_node(state: AgentState) -> AgentState:
    """
    General Inquiry Agent - Handles generic questions.

    Provides basic information and routes to specialists as needed.
    """

    logger.info("General inquiry agent activated")

    response = (
        "I'm Bank ABC's virtual assistant. I can help you with:\n"
        "- Card issues (lost/stolen, blocked cards)\n"
        "- Account servicing (balance, statements, profile updates)\n"
        "- Account opening inquiries\n"
        "- Digital banking support\n"
        "\nWhat can I help you with today?"
    )

    return {
        **state,
        "flow_stage": "complete",
        "messages": state["messages"] + [AIMessage(content=response)]
    }


# ==================== ESCALATION ====================

async def human_escalation_node(state: AgentState) -> AgentState:
    """
    Human Escalation Node - Final node for transferring to human agent.
    
    Preserves conversation context and reason for escalation.
    """
    
    escalation_reason = state.get("escalation_reason", "User request")
    logger.critical(f"Escalating to human: {escalation_reason}")
    
    response = (
        "Thank you for your patience. I'm connecting you with a specialist "
        "who can better assist you. Please hold while I transfer your call."
    )
    
    # In production, this would trigger actual call transfer
    # For POC, we just mark the session as escalated
    
    return {
        **state,
        "flow_stage": "escalated",
        "messages": state["messages"] + [AIMessage(content=response)]
    }


# ==================== COMPLETION CHECK ====================

def check_flow_completion(state: AgentState) -> str:
    """Generic flow completion check for stub agents."""
    
    if state.get("escalation_requested"):
        return "escalation"
    
    if state.get("needs_user_input"):
        return "__end__"
    
    if state.get("flow_stage") == "complete":
        return "complete"
    
    # For stub agents, usually escalate after capturing intent
    return state.get("intent", "general_inquiry") + "_agent"

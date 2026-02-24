"""
LangGraph Workflow - Main agent orchestration graph.
Ties together all nodes with conditional routing and state persistence.
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver

from src.agents.state import AgentState
from src.agents.nodes.intent_router import route_intent_node, route_to_flow
from src.agents.nodes.security_check import security_check_node, check_auth_status
from src.agents.nodes.card_agent import card_atm_agent_node, check_card_flow_completion
from src.agents.nodes.account_agent import account_servicing_agent_node, check_account_flow_completion
from src.agents.nodes.stub_agents import (
    account_opening_agent_node,
    digital_support_agent_node,
    transfer_payment_agent_node,
    account_closure_agent_node,
    general_inquiry_agent_node,
    human_escalation_node,
    check_flow_completion
)
from src.config import settings
from src.observability import get_logger


logger = get_logger(__name__)


def create_agent_graph() -> StateGraph:
    """
    Create the complete LangGraph workflow for the banking voice agent.
    
    Graph Flow:
    1. START → intent_router (classify intent)
    2. intent_router → [security_check | opening_agent | digital_agent | general_inquiry]
    3. security_check → [card_agent | account_agent | transfer_agent | closure_agent | security_check (retry)]
    4. Each agent → [complete | escalation | continue_in_agent]
    5. escalation → END
    6. complete → END
    
    Returns:
        Compiled StateGraph with PostgreSQL checkpointer
    """
    
    logger.info("Building LangGraph workflow...")
    
    # Create graph
    workflow = StateGraph(AgentState)
    
    # ==================== ADD NODES ====================
    
    # Entry point - intent classification
    workflow.add_node("intent_router", route_intent_node)
    
    # Security/authentication
    workflow.add_node("security_check", security_check_node)
    
    # Deep logic agents
    workflow.add_node("card_atm_agent", card_atm_agent_node)
    workflow.add_node("account_servicing_agent", account_servicing_agent_node)
    
    # Stub agents
    workflow.add_node("opening_agent", account_opening_agent_node)
    workflow.add_node("digital_agent", digital_support_agent_node)
    workflow.add_node("transfer_agent", transfer_payment_agent_node)
    workflow.add_node("closure_agent", account_closure_agent_node)
    workflow.add_node("general_inquiry_node", general_inquiry_agent_node)
    
    # Escalation
    workflow.add_node("escalation", human_escalation_node)
    
    # ==================== SET ENTRY POINT ====================
    
    workflow.set_entry_point("intent_router")
    
    # ==================== CONDITIONAL EDGES ====================
    
    # From intent_router, route to appropriate next node
    workflow.add_conditional_edges(
        "intent_router",
        route_to_flow,
        {
            # Normal intent routing targets
            "security_check": "security_check",
            "opening_agent": "opening_agent",
            "digital_agent": "digital_agent",
            "general_inquiry_node": "general_inquiry_node",
            # Mid-flow resume targets (resume_node routes directly here)
            "card_atm_agent": "card_atm_agent",
            "account_servicing_agent": "account_servicing_agent",
            "transfer_agent": "transfer_agent",
            "closure_agent": "closure_agent",
        }
    )
    
    # From security_check, route based on auth status and intent
    workflow.add_conditional_edges(
        "security_check",
        check_auth_status,
        {
            "card_atm_agent": "card_atm_agent",
            "account_servicing_agent": "account_servicing_agent",
            "transfer_agent": "transfer_agent",
            "closure_agent": "closure_agent",
            "security_check": "security_check",  # Retry authentication
            "escalation": "escalation",
            "__end__": END,  # Needs user input
        }
    )
    
    # From card_atm_agent, check completion
    workflow.add_conditional_edges(
        "card_atm_agent",
        check_card_flow_completion,
        {
            "card_atm_agent": "card_atm_agent",  # Continue conversation
            "escalation": "escalation",
            "complete": END,
            "__end__": END,  # Needs user input
        }
    )
    
    # From account_servicing_agent, check completion
    workflow.add_conditional_edges(
        "account_servicing_agent",
        check_account_flow_completion,
        {
            "account_servicing_agent": "account_servicing_agent",  # Continue
            "escalation": "escalation",
            "complete": END,
            "__end__": END,  # Needs user input
        }
    )
    
    # Stub agents - most escalate immediately
    for agent_name in ["opening_agent", "digital_agent", "transfer_agent", "closure_agent"]:
        workflow.add_conditional_edges(
            agent_name,
            check_flow_completion,
            {
                f"{agent_name}": agent_name,  # Continue if needed
                "escalation": "escalation",
                "complete": END,
                "__end__": END,  # Needs user input
            }
        )
    
    # General inquiry loops or ends
    workflow.add_conditional_edges(
        "general_inquiry_node",
        lambda state: "complete" if state.get("flow_stage") == "complete" else "general_inquiry_node",
        {
            "general_inquiry_node": "general_inquiry_node",
            "complete": END,
        }
    )
    
    # Escalation always ends
    workflow.add_edge("escalation", END)
    
    logger.info("✅ LangGraph workflow built successfully")
    
    return workflow


def compile_agent_graph() -> StateGraph:
    """
    Compile the agent graph with state persistence checkpointer.
    
    Uses InMemorySaver for POC. For production, replace with
    properly initialized AsyncPostgresSaver.
    
    Returns:
        Compiled graph ready for invocation
    """
    
    workflow = create_agent_graph()
    
    # Use InMemorySaver for POC (PostgresSaver.from_conn_string() returns
    # a context manager in langgraph-checkpoint-postgres v3+, which is not
    # compatible with long-lived graph instances)
    checkpointer = InMemorySaver()
    
    # Compile with checkpointer
    app = workflow.compile(checkpointer=checkpointer)
    
    logger.info("✅ Agent graph compiled with InMemorySaver checkpointer")
    
    return app


# Global compiled graph instance
agent_graph = None


def get_agent_graph():
    """Get or create the compiled agent graph."""
    global agent_graph
    
    if agent_graph is None:
        agent_graph = compile_agent_graph()
    
    return agent_graph

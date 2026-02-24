"""
Pytest configuration and shared fixtures.
"""
import sys
import os
import pytest

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def mock_agent_state():
    """Create a minimal AgentState dict for testing tools."""
    return {
        "messages": [],
        "customer_id": None,
        "authenticated": False,
        "authentication_method": None,
        "verification_attempts": 0,
        "session_id": "test-session-001",
        "intent": None,
        "intent_confidence": None,
        "flow_stage": None,
        "needs_user_input": False,
        "resume_node": None,
        "escalation_requested": False,
        "escalation_reason": None,
        "last_tool_output": None,
        "account_balance": None,
        "recent_transactions": None,
        "card_details": None,
        "pii_detected": [],
        "suspicious_activity": False,
        "critical_actions_taken": [],
        "turn_count": 0,
        "start_time": 0.0,
    }


@pytest.fixture
def authenticated_state(mock_agent_state):
    """AgentState with authentication already passed."""
    return {
        **mock_agent_state,
        "authenticated": True,
        "customer_id": "CUST00001",
        "authentication_method": "pin",
    }

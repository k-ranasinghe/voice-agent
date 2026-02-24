"""
Tests for Intent Router Node.
"""
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage

from src.agents.nodes.intent_router import (
    route_intent_node,
    route_to_flow,
    IntentClassification,
)


class TestRouteToFlow:
    """Test deterministic routing table."""

    def test_card_atm_goes_to_security(self, mock_agent_state):
        state = {**mock_agent_state, "intent": "card_atm", "intent_confidence": 0.9}
        assert route_to_flow(state) == "security_check"

    def test_account_servicing_goes_to_security(self, mock_agent_state):
        state = {**mock_agent_state, "intent": "account_servicing", "intent_confidence": 0.8}
        assert route_to_flow(state) == "security_check"

    def test_account_opening_goes_to_opening(self, mock_agent_state):
        state = {**mock_agent_state, "intent": "account_opening", "intent_confidence": 0.9}
        assert route_to_flow(state) == "opening_agent"

    def test_digital_support_goes_to_digital(self, mock_agent_state):
        state = {**mock_agent_state, "intent": "digital_support", "intent_confidence": 0.9}
        assert route_to_flow(state) == "digital_agent"

    def test_general_inquiry_goes_to_general(self, mock_agent_state):
        state = {**mock_agent_state, "intent": "general_inquiry", "intent_confidence": 0.9}
        assert route_to_flow(state) == "general_inquiry_node"

    def test_low_confidence_goes_to_general(self, mock_agent_state):
        state = {**mock_agent_state, "intent": "card_atm", "intent_confidence": 0.3}
        assert route_to_flow(state) == "general_inquiry_node"

    def test_transfer_goes_to_security(self, mock_agent_state):
        state = {**mock_agent_state, "intent": "transfer_payment", "intent_confidence": 0.9}
        assert route_to_flow(state) == "security_check"

    def test_closure_goes_to_security(self, mock_agent_state):
        state = {**mock_agent_state, "intent": "account_closure", "intent_confidence": 0.9}
        assert route_to_flow(state) == "security_check"


class TestRouteIntentNode:
    """Test intent router node behavior."""

    def test_no_messages_fallback(self, mock_agent_state):
        """With no messages, should default to general_inquiry."""
        state = {**mock_agent_state, "messages": []}
        result = route_intent_node(state)
        assert result["intent"] == "general_inquiry"
        assert result["intent_confidence"] == 0.5

    @patch("src.agents.nodes.intent_router.ChatOpenAI")
    def test_successful_classification(self, mock_llm_class, mock_agent_state):
        """Should classify intent using LLM and update state."""
        # Mock the LLM chain
        mock_classification = IntentClassification(
            intent="card_atm",
            confidence=0.95,
            reasoning="User mentioned lost card"
        )
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_classification
        mock_llm_instance = MagicMock()
        mock_llm_instance.with_structured_output.return_value = mock_chain
        mock_llm_class.return_value = mock_llm_instance

        state = {
            **mock_agent_state,
            "messages": [HumanMessage(content="I lost my card")],
        }

        result = route_intent_node(state)
        assert result["intent"] == "card_atm"
        assert result["intent_confidence"] == 0.95

    @patch("src.agents.nodes.intent_router.ChatOpenAI")
    def test_llm_failure_fallback(self, mock_llm_class, mock_agent_state):
        """If LLM fails, should fallback to general_inquiry with low confidence."""
        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = Exception("API Error")
        mock_llm_instance = MagicMock()
        mock_llm_instance.with_structured_output.return_value = mock_chain
        mock_llm_class.return_value = mock_llm_instance

        state = {
            **mock_agent_state,
            "messages": [HumanMessage(content="Hello")],
        }

        result = route_intent_node(state)
        assert result["intent"] == "general_inquiry"
        assert result["intent_confidence"] == 0.3


class TestIntentClassificationSchema:
    """Test the Pydantic model validates correctly."""

    def test_valid_intent(self):
        c = IntentClassification(
            intent="card_atm",
            confidence=0.9,
            reasoning="Card related"
        )
        assert c.intent == "card_atm"

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            IntentClassification(intent="card_atm", confidence=1.5, reasoning="test")

        with pytest.raises(Exception):
            IntentClassification(intent="card_atm", confidence=-0.1, reasoning="test")

    def test_invalid_intent_type(self):
        with pytest.raises(Exception):
            IntentClassification(intent="unknown_type", confidence=0.5, reasoning="test")

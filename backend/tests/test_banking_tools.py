"""
Tests for Banking Tools — authentication enforcement and tool behavior.
"""
import pytest


def _import_tools():
    """Lazy import to avoid circular dependency at collection time."""
    from src.tools.banking import (
        get_account_balance,
        get_recent_transactions,
        block_card,
        get_card_details,
        create_lead,
        request_statement,
        update_profile,
    )
    from src.tools.decorators import AuthenticationRequired
    return {
        "get_account_balance": get_account_balance,
        "get_recent_transactions": get_recent_transactions,
        "block_card": block_card,
        "get_card_details": get_card_details,
        "create_lead": create_lead,
        "request_statement": request_statement,
        "update_profile": update_profile,
        "AuthenticationRequired": AuthenticationRequired,
    }


class TestRequiresAuthDecorator:
    """Test @requires_auth enforcement on banking tools."""

    @pytest.mark.asyncio
    async def test_unauthenticated_balance_raises(self, mock_agent_state):
        tools = _import_tools()
        with pytest.raises(tools["AuthenticationRequired"]):
            await tools["get_account_balance"](mock_agent_state, "CUST00001")

    @pytest.mark.asyncio
    async def test_authenticated_balance_succeeds(self, authenticated_state):
        tools = _import_tools()
        result = await tools["get_account_balance"](authenticated_state, "CUST00001")
        assert isinstance(result, dict)
        assert "success" in result

    @pytest.mark.asyncio
    async def test_unauthenticated_transactions_raises(self, mock_agent_state):
        tools = _import_tools()
        with pytest.raises(tools["AuthenticationRequired"]):
            await tools["get_recent_transactions"](mock_agent_state, "CUST00001")

    @pytest.mark.asyncio
    async def test_unauthenticated_block_card_raises(self, mock_agent_state):
        tools = _import_tools()
        with pytest.raises(tools["AuthenticationRequired"]):
            await tools["block_card"](mock_agent_state, "CARD001", "Lost")

    @pytest.mark.asyncio
    async def test_unauthenticated_update_profile_raises(self, mock_agent_state):
        tools = _import_tools()
        with pytest.raises(tools["AuthenticationRequired"]):
            await tools["update_profile"](mock_agent_state, "CUST00001", {"email": "new@test.com"})

    @pytest.mark.asyncio
    async def test_unauthenticated_statement_raises(self, mock_agent_state):
        tools = _import_tools()
        with pytest.raises(tools["AuthenticationRequired"]):
            await tools["request_statement"](mock_agent_state, "CUST00001")


class TestToolsOutput:
    """Test that tool functions return expected output structures."""

    @pytest.mark.asyncio
    async def test_get_card_details_no_auth_required(self, mock_agent_state):
        tools = _import_tools()
        result = await tools["get_card_details"](mock_agent_state, "CARD001")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_create_lead_no_auth_required(self, mock_agent_state):
        tools = _import_tools()
        result = await tools["create_lead"](mock_agent_state, {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "555-1234",
            "account_type": "savings",
        })
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_block_card_with_auth(self, authenticated_state):
        tools = _import_tools()
        result = await tools["block_card"](authenticated_state, "CARD001", "Lost")
        assert isinstance(result, dict)
        assert "success" in result

    @pytest.mark.asyncio
    async def test_recent_transactions_with_auth(self, authenticated_state):
        tools = _import_tools()
        result = await tools["get_recent_transactions"](authenticated_state, "CUST00001")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_update_profile_with_auth(self, authenticated_state):
        tools = _import_tools()
        result = await tools["update_profile"](authenticated_state, "CUST00001", {
            "email": "newemail@bank.com"
        })
        assert isinstance(result, dict)

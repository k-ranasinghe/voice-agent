"""
Mock Banking API Tools.
Simulates core banking system operations with database queries.
All sensitive tools require authentication via @requires_auth decorator.
"""
from datetime import datetime, timedelta
from typing import Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.state import AgentState
from src.database.connection import async_session
from src.database.models import Customer, Account, Card
from src.tools.decorators import requires_auth, log_critical_action
from src.observability import get_logger


logger = get_logger(__name__)


# ==================== AUTHENTICATION ====================

async def verify_identity(state: AgentState, customer_id: str, pin: str) -> dict:
    """
    Verify customer identity via PIN.
    
    NOTE: This is handled by security_check_node in the graph.
    This function is for explicit verification in other contexts.
    
    Args:
        state: Agent state
        customer_id: Customer ID
        pin: Provided PIN
        
    Returns:
        Verification result with status
    """
    import bcrypt
    
    async with async_session() as session:
        result = await session.execute(
            select(Customer).where(Customer.customer_id == customer_id)
        )
        customer = result.scalar_one_or_none()
        
        if not customer:
            logger.warning(f"verify_identity: Customer {customer_id} not found")
            return {
                "success": False,
                "error": "Customer not found"
            }
        
        # Verify PIN
        pin_bytes = pin.encode('utf-8')
        hash_bytes = customer.pin_hash.encode('utf-8')
        
        is_valid = bcrypt.checkpw(pin_bytes, hash_bytes)
        
        if is_valid:
            logger.info(f"verify_identity: Success for {customer_id}")
            return {
                "success": True,
                "customer_id": customer_id,
                "customer_name": customer.name,
            }
        else:
            logger.warning(f"verify_identity: Failed for {customer_id}")
            return {
                "success": False,
                "error": "Invalid PIN"
            }


# ==================== BALANCE & TRANSACTIONS ====================

@requires_auth
async def get_account_balance(state: AgentState, customer_id: str) -> dict:
    """
    Get account balance for customer.
    **Requires authentication**.
    
    Args:
        state: Agent state (must be authenticated)
        customer_id: Customer ID
        
    Returns:
        Account balance details
    """
    async with async_session() as session:
        result = await session.execute(
            select(Account).where(Account.customer_id == customer_id)
        )
        accounts = result.scalars().all()
        
        if not accounts:
            return {
                "success": False,
                "error": "No accounts found for customer"
            }
        
        account_balances = [
            {
                "account_id": acc.account_id,
                "account_type": acc.account_type,
                "balance": float(acc.balance),
                "currency": acc.currency,
            }
            for acc in accounts
        ]
        
        total_balance = sum(acc["balance"] for acc in account_balances)
        
        logger.info(f"get_account_balance: {customer_id} - Total: ${total_balance:,.2f}")
        
        return {
            "success": True,
            "total_balance": total_balance,
            "accounts": account_balances,
        }


@requires_auth
async def get_recent_transactions(
    state: AgentState,
    customer_id: str,
    count: int = 5
) -> dict:
    """
    Get recent transactions for customer.
    **Requires authentication**.
    
    NOTE: For POC, we generate mock transactions.
    In production, this would query actual transaction table.
    
    Args:
        state: Agent state (must be authenticated)
        customer_id: Customer ID
        count: Number of recent transactions
        
    Returns:
        List of recent transactions
    """
    # Mock transaction data for POC
    mock_transactions = [
        {
            "date": (datetime.now() - timedelta(days=i)).isoformat(),
            "description": f"Transaction {i+1}",
            "amount": -50.00 * (i + 1),
            "category": "Grocery" if i % 2 == 0 else "Dining",
        }
        for i in range(count)
    ]
    
    logger.info(f"get_recent_transactions: {customer_id} - {count} transactions")
    
    return {
        "success": True,
        "transactions": mock_transactions,
        "count": len(mock_transactions),
    }


# ==================== CARD MANAGEMENT ====================

async def get_card_details(state: AgentState, card_id: str) -> dict:
    """
    Get card status and details.
    Does not require auth (for checking if card already blocked).
    
    Args:
        state: Agent state
        card_id: Card ID
        
    Returns:
        Card details
    """
    async with async_session() as session:
        result = await session.execute(
            select(Card).where(Card.card_id == card_id)
        )
        card = result.scalar_one_or_none()
        
        if not card:
            return {
                "success": False,
                "error": "Card not found"
            }
        
        return {
            "success": True,
            "card_id": card.card_id,
            "last_4": card.card_number_last4,
            "status": card.status,
            "expiration": card.expiration_date.isoformat() if card.expiration_date else None,
            "blocked_at": card.blocked_at.isoformat() if card.blocked_at else None,
            "blocked_reason": card.blocked_reason,
        }


@requires_auth
@log_critical_action("CARD_BLOCKED")
async def block_card(state: AgentState, card_id: str, reason: str) -> dict:
    """
    Block a card (IRREVERSIBLE ACTION).
    **Requires authentication**.
    **Logs as critical action**.
    
    Args:
        state: Agent state (must be authenticated)
        card_id: Card ID to block
        reason: Reason for blocking (e.g., "Lost", "Stolen", "Fraud")
        
    Returns:
        Block confirmation with reference ID
    """
    async with async_session() as session:
        # Check if card exists
        result = await session.execute(
            select(Card).where(Card.card_id == card_id)
        )
        card = result.scalar_one_or_none()
        
        if not card:
            return {
                "success": False,
                "error": "Card not found"
            }
        
        if card.status == "blocked":
            logger.warning(f"block_card: Card {card_id} already blocked")
            return {
                "success": False,
                "error": "Card is already blocked",
                "blocked_at": card.blocked_at.isoformat(),
                "blocked_reason": card.blocked_reason,
            }
        
        # Block the card
        await session.execute(
            update(Card)
            .where(Card.card_id == card_id)
            .values(
                status="blocked",
                blocked_at=datetime.utcnow(),
                blocked_reason=reason,
            )
        )
        await session.commit()
        
        reference_id = f"BLK-{card_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        logger.critical(f"🚨 CARD BLOCKED: {card_id} | Reason: {reason} | Ref: {reference_id}")
        
        return {
            "success": True,
            "card_id": card_id,
            "reference_id": reference_id,
            "blocked_at": datetime.utcnow().isoformat(),
            "message": f"Card ending in {card.card_number_last4} has been blocked successfully.",
        }


# ==================== PROFILE MANAGEMENT ====================

@requires_auth
async def update_profile(state: AgentState, customer_id: str, updates: dict) -> dict:
    """
    Update customer profile information.
    **Requires authentication**.
    
    Args:
        state: Agent state (must be authenticated)
        customer_id: Customer ID
        updates: Dict with fields to update (email, phone, address, etc.)
        
    Returns:
        Update confirmation
    """
    allowed_fields = {"email", "phone"}
    
    # Filter to allowed fields only
    filtered_updates = {
        k: v for k, v in updates.items() if k in allowed_fields
    }
    
    if not filtered_updates:
        return {
            "success": False,
            "error": "No valid fields to update"
        }
    
    async with async_session() as session:
        await session.execute(
            update(Customer)
            .where(Customer.customer_id == customer_id)
            .values(**filtered_updates)
        )
        await session.commit()
        
        logger.info(f"update_profile: {customer_id} - Updated: {list(filtered_updates.keys())}")
        
        return {
            "success": True,
            "updated_fields": list(filtered_updates.keys()),
            "message": "Profile updated successfully",
        }


# ==================== STATEMENTS ====================

@requires_auth
async def request_statement(state: AgentState, customer_id: str, period: str = "monthly") -> dict:
    """
    Request account statement.
    **Requires authentication**.
    
    Args:
        state: Agent state (must be authenticated)
        customer_id: Customer ID
        period: Statement period ("monthly", "quarterly", "annual")
        
    Returns:
        Statement request confirmation
    """
    # In production, this would generate PDF and email it
    reference_id = f"STMT-{customer_id}-{datetime.now().strftime('%Y%m%d')}"
    
    logger.info(f"request_statement: {customer_id} - Period: {period} - Ref: {reference_id}")
    
    return {
        "success": True,
        "reference_id": reference_id,
        "period": period,
        "message": f"Your {period} statement will be emailed within 24 hours.",
    }


# ==================== ACCOUNT OPENING (LEAD CAPTURE) ====================

async def create_lead(state: AgentState, customer_data: dict) -> dict:
    """
    Create lead for account opening.
    Does not require authentication (new customers).
    
    Args:
        state: Agent state
        customer_data: Dict with name, email, phone, account_type
        
    Returns:
        Lead creation confirmation
    """
    # In production, this would create a lead in CRM system
    reference_id = f"LEAD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    logger.info(f"create_lead: {customer_data.get('name')} - Ref: {reference_id}")
    
    return {
        "success": True,
        "reference_id": reference_id,
        "message": "Thank you! A representative will contact you within 2 business days.",
    }

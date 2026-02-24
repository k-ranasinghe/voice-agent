"""
Security decorators for banking tools.
Enforces authentication before sensitive operations.
"""
from functools import wraps
from typing import Callable, Any
from src.agents.state import AgentState
from src.observability import get_logger


logger = get_logger(__name__)


class AuthenticationRequired(Exception):
    """Raised when a tool requires authentication but user is not authenticated."""
    pass


def requires_auth(func: Callable) -> Callable:
    """
    Decorator to enforce authentication before tool execution.
    
    Usage:
        @requires_auth
        async def get_account_balance(state: AgentState, customer_id: str):
            ...
    
    Args:
        func: Tool function to wrap
        
    Returns:
        Wrapped function that checks authentication
        
    Raises:
        AuthenticationRequired: If state["authenticated"] is False
    """
    
    @wraps(func)
    async def wrapper(state: AgentState, *args, **kwargs) -> Any:
        if not state.get("authenticated", False):
            error_msg = f"{func.__name__} requires authentication"
            logger.error(error_msg)
            raise AuthenticationRequired(error_msg)
        
        logger.info(f"✓ Auth check passed for {func.__name__}")
        return await func(state, *args, **kwargs)
    
    return wrapper


def log_critical_action(action_type: str):
    """
    Decorator to log critical/irreversible actions.
    
    Usage:
        @log_critical_action("CARD_BLOCKED")
        async def block_card(...):
            ...
    
    Args:
        action_type: Type of critical action for audit log
    """
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(state: AgentState, *args, **kwargs) -> Any:
            result = await func(state, *args, **kwargs)
            
            # Add to critical actions list
            critical_actions = state.get("critical_actions_taken", [])
            critical_actions.append(action_type)
            
            logger.critical(
                f"🚨 CRITICAL ACTION: {action_type} | "
                f"Customer: {state.get('customer_id')} | "
                f"Session: {state.get('session_id')}"
            )
            
            return result
        
        return wrapper
    
    return decorator

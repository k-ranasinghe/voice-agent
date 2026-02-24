"""
Fraud Detection Module - Identifies suspicious activity patterns.
Uses keyword analysis and conversation context.
"""
from typing import Dict, List
from langchain_core.messages import BaseMessage
from src.agents.state import AgentState
from src.observability import get_logger


logger = get_logger(__name__)


# Suspicious keywords and phrases
SUSPICIOUS_KEYWORDS = [
    "transfer everything",
    "withdraw all",
    "close account immediately",
    "send money to",
    "urgent transfer",
    "wire transfer now",
    "empty account",
    "maximum withdrawal",
    "change beneficiary to",
    "add new beneficiary",
]

COERCION_INDICATORS = [
    "someone told me",
    "they said i must",
    "i'm being forced",
    "threatened",
    "or else",
    "time sensitive",
    "right now or",
]


def detect_suspicious_activity(state: AgentState) -> Dict[str, any]:
    """
    Detect suspicious activity patterns in conversation.
    
    Checks for:
    - Suspicious keywords (urgent large transfers, account emptying)
    - Multiple failed authentication attempts
    - Unusual request patterns
    - Coercion indicators
    
    Args:
        state: Current agent state
        
    Returns:
        Dict with suspicious flag and details
    """
    
    flags = []
    
    # Check failed authentication attempts
    verification_attempts = state.get("verification_attempts", 0)
    if verification_attempts >= 2:
        flags.append({
            "type": "FAILED_AUTH",
            "severity": "HIGH",
            "description": f"Multiple failed authentication attempts ({verification_attempts})"
        })
    
    # Analyze conversation for suspicious keywords
    recent_messages = state.get("messages", [])[-10:]  # Last 10 messages
    user_messages = [
        msg.content.lower() 
        for msg in recent_messages 
        if msg.type == "human"
    ]
    
    conversation_text = " ".join(user_messages)
    
    # Check for suspicious keywords
    for keyword in SUSPICIOUS_KEYWORDS:
        if keyword in conversation_text:
            flags.append({
                "type": "SUSPICIOUS_KEYWORD",
                "severity": "MEDIUM",
                "description": f"Detected suspicious phrase: '{keyword}'"
            })
            logger.warning(f"🚨 Suspicious keyword detected: {keyword}")
    
    # Check for coercion indicators
    for indicator in COERCION_INDICATORS:
        if indicator in conversation_text:
            flags.append({
                "type": "COERCION_INDICATOR",
                "severity": "CRITICAL",
                "description": f"Possible coercion detected: '{indicator}'"
            })
            logger.critical(f"⚠️ COERCION INDICATOR: {indicator}")
    
    # Check for rapid succession of high-value requests
    critical_actions = state.get("critical_actions_taken", [])
    if len(critical_actions) > 2:
        flags.append({
            "type": "RAPID_CRITICAL_ACTIONS",
            "severity": "HIGH",
            "description": f"Multiple critical actions in single session: {len(critical_actions)}"
        })
    
    # Determine if conversation is suspicious
    is_suspicious = len(flags) > 0
    has_critical_flags = any(f["severity"] == "CRITICAL" for f in flags)
    
    if is_suspicious:
        logger.warning(f"Suspicious activity detected - {len(flags)} flag(s)")
    
    return {
        "is_suspicious": is_suspicious,
        "requires_immediate_escalation": has_critical_flags,
        "flags": flags,
        "flag_count": len(flags),
    }


def should_escalate_for_fraud(state: AgentState) -> bool:
    """
    Determine if conversation should be escalated due to fraud concerns.
    
    Args:
        state: Current agent state
        
    Returns:
        True if should escalate immediately
    """
    
    result = detect_suspicious_activity(state)
    
    if result["requires_immediate_escalation"]:
        logger.critical(
            f"🚨 IMMEDIATE ESCALATION: Fraud/coercion suspected | "
            f"Session: {state.get('session_id')} | "
            f"Flags: {result['flag_count']}"
        )
        return True
    
    return False

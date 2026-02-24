"""
PII Redaction Module - Detects and redacts sensitive information.
Prevents PII leakage in logs, traces, and database transcripts.
"""
import re
from typing import Tuple
from src.observability import get_logger


logger = get_logger(__name__)


# PII Pattern Definitions
PII_PATTERNS = {
    "SSN": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    "SSN_NO_DASH": re.compile(r'\b\d{9}\b'),
    "CREDIT_CARD": re.compile(r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b'),
    "PHONE": re.compile(r'\b(\+?1[-.]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
    "EMAIL": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    "PIN": re.compile(r'\bPIN\s*:?\s*\d{4}\b', re.IGNORECASE),
    "PASSWORD": re.compile(r'\bpassword\s*:?\s*\S+\b', re.IGNORECASE),
}


def redact_pii(text: str, strict_mode: bool = False) -> Tuple[str, list[str]]:
    """
    Redact PII from text.
    
    Args:
        text: Input text potentially containing PII
        strict_mode: If True, redact emails and phones as well
        
    Returns:
        Tuple of (redacted_text, detected_types)
    """
    
    detected = []
    redacted = text
    
    #Always redact critical PII
    critical_patterns = ["SSN", "SSN_NO_DASH", "CREDIT_CARD", "PIN", "PASSWORD"]
    
    for pii_type, pattern in PII_PATTERNS.items():
        # Only process critical patterns or all patterns in strict mode
        if pii_type in critical_patterns or strict_mode:
            matches = pattern.findall(text)
            
            if matches:
                detected.append(pii_type)
                
                # Redact with pattern name
                redacted = pattern.sub(f"[{pii_type}_REDACTED]", redacted)
                
                logger.warning(f"PII detected and redacted: {pii_type} ({len(matches)} occurrence(s))")
    
    return redacted, detected


def redact_partial_card(text: str) -> str:
    """
    Redact credit card numbers but keep last 4 digits.
    
    Example: "4532 1234 5678 9010" → "XXXX XXXX XXXX 9010"
    
    Args:
        text: Input text
        
    Returns:
        Text with partial card redaction
    """
    
    # Pattern to match card numbers
    card_pattern = re.compile(r'\b(\d{4})[- ]?(\d{4})[- ]?(\d{4})[- ]?(\d{4})\b')
    
    def replace_card(match):
        """Replace all but last 4 digits."""
        last_4 = match.group(4)
        return f"XXXX XXXX XXXX {last_4}"
    
    return card_pattern.sub(replace_card, text)


def sanitize_for_logging(text: str) -> str:
    """
    Sanitize text for safe logging.
    Removes all critical PII with strict redaction.
    
    Args:
        text: Input text
        
    Returns:
        Sanitized text safe for logging
    """
    
    sanitized, detected = redact_pii(text, strict_mode=False)
    
    if detected:
        logger.info(f"Sanitized log entry - removed: {', '.join(detected)}")
    
    return sanitized


def detect_pii_types(text: str) -> list[str]:
    """
    Detect PII types without redacting.
    Useful for flagging conversations containing sensitive data.
    
    Args:
        text: Input text
        
    Returns:
        List of detected PII types
    """
    
    detected = []
    
    for pii_type, pattern in PII_PATTERNS.items():
        if pattern.search(text):
            detected.append(pii_type)
    
    return detected

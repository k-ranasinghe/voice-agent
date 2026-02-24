"""
LangFuse observability client initialization.
Provides tracing for LangGraph agent execution.
"""
from langfuse import Langfuse
from src.config import settings


# Global LangFuse client
langfuse_client: Langfuse | None = None


def init_langfuse() -> Langfuse:
    """Initialize LangFuse client and callback handler."""
    global langfuse_client
    
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )


def get_langfuse_client() -> Langfuse:
    """Get LangFuse client instance."""
    if langfuse_client is None:
        init_langfuse()
    return langfuse_client

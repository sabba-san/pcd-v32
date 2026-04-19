# ai_client.py
import os
from groq import Groq

_client = None  # singleton


def _get_sanitized_api_key() -> str:
    raw_value = os.getenv("GROQ_API_KEY", "")
    api_key = raw_value.strip().strip('"').strip("'").strip()
    return api_key


def get_ai_client():
    """
    Get Groq AI client
    """
    global _client

    if _client is not None:
        return _client

    api_key = _get_sanitized_api_key()

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY not set. Please define it in environment variables."
        )

    _client = Groq(api_key=api_key)
    return _client


# Keep backward compatibility
def get_openai_client():
    """Deprecated: Use get_ai_client() instead"""
    return get_ai_client()

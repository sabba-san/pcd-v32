# ai_client.py
import os
from groq import Groq

_clients = {}


def _sanitize_api_key(raw_value: str) -> str:
    return (raw_value or "").strip().strip('"').strip("'").strip()


def _get_api_key_for_scope(scope: str = "report") -> str:
    if scope == "chatbot":
        return _sanitize_api_key(
            os.getenv("GROQ_API_KEY_CHATBOT") or os.getenv("GROQ_API_KEY")
        )
    if scope == "report":
        return _sanitize_api_key(
            os.getenv("GROQ_API_KEY_REPORT") or os.getenv("GROQ_API_KEY")
        )
    return _sanitize_api_key(os.getenv("GROQ_API_KEY"))


def get_ai_client(scope: str = "report"):
    """
    Get Groq AI client for a specific scope.
    scope:
    - report: report generation + module3 AI helpers
    - chatbot: chatbot-specific calls
    - default: generic fallback only
    """
    cache_key = scope or "report"
    if cache_key in _clients:
        return _clients[cache_key]

    api_key = _get_api_key_for_scope(cache_key)

    if not api_key:
        raise RuntimeError(
            "Groq API key not set. Define GROQ_API_KEY_REPORT/GROQ_API_KEY_CHATBOT or fallback GROQ_API_KEY."
        )

    _clients[cache_key] = Groq(api_key=api_key)
    return _clients[cache_key]


# Keep backward compatibility
def get_openai_client():
    """Deprecated: Use get_ai_client() instead"""
    return get_ai_client()

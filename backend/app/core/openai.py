"""
OpenAI Agents SDK bootstrap configuration.

Centralizes SDK configuration so agent modules do not depend on environment
variables being implicitly exported to the operating system.

Imported by:
- agent execution service before running agents.
"""

from agents import set_default_openai_key

from app.core.config import get_ai_settings

settings = get_ai_settings()

set_default_openai_key(settings.openai_api_key)

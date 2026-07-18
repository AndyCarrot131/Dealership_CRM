"""Default Gemini runtime configuration.

The application uses Gemini's OpenAI-compatible endpoint so the shared LLM
client can continue to serve every agent, including multimodal deal extraction.
"""

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
GEMINI_MODEL = "gemini-3.5-flash"
GEMINI_API_KEY_REF = "env:GEMINI_API_KEY"

__all__ = ["GEMINI_API_KEY_REF", "GEMINI_BASE_URL", "GEMINI_MODEL"]

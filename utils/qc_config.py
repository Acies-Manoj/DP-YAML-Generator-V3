"""
utils/qc_config.py — Re-exports LLM settings from the shared description engine config.
Single source of truth: edit utils/description_engine/config.py to change provider/key/model.
"""

from utils.description_engine.config import (
    PROVIDER,
    GROQ_API_KEY,
    DEFAULT_GROQ_MODEL   as GROQ_DEFAULT_MODEL,
    OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL as OLLAMA_DEFAULT_MODEL,
)
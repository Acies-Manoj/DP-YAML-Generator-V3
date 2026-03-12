"""
config.py — Central configuration for the Description Engine.

SET YOUR PROVIDER AND API KEY HERE.
This is the only place you need to change when switching providers or rotating keys.
Do not enter keys in the Streamlit UI — they are read from here.
"""

# ── Provider ──────────────────────────────────────────────────────────────────
# Options: "groq" or "ollama"
import os

from dotenv import load_dotenv
load_dotenv()   
    
PROVIDER = "groq"

# ── Groq Settings (used when PROVIDER = "groq") ───────────────────────────────
# Get your free API key at: https://console.groq.com
# Sign up → API Keys → Create Key → paste below
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Available Groq models (free tier):
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
]
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"

# ── Ollama Settings (used when PROVIDER = "ollama") ───────────────────────────
# Ollama must be running locally: https://ollama.com
# Run: ollama pull mistral  (one-time model download)
OLLAMA_BASE_URL = "http://localhost:11434"

OLLAMA_MODELS = [
    "mistral",
    "llama3",
    "gemma2",
    "phi3",
]

# ── Common Settings ───────────────────────────────────────────────────────────
# Default model shown selected in the UI dropdown
# DEFAULT_GROQ_MODEL   = "llama3-8b-8192"
DEFAULT_OLLAMA_MODEL = "mistral"
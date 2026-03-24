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
    "openai/gpt-oss-120b", 
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
]

# ── Active model — change this line to switch models ─────────────────────────
# Use "llama-3.1-8b-instant" if you hit the 70b daily token limit (100k TPD)
# Use "llama-3.3-70b-versatile" for best quality when limit resets
DEFAULT_GROQ_MODEL   = "llama-3.3-70b-versatile"   # ← change here to switch
GROQ_DEFAULT_MODEL   = DEFAULT_GROQ_MODEL        # alias used by llm_checks.py

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

DEFAULT_OLLAMA_MODEL = "mistral"
OLLAMA_DEFAULT_MODEL = DEFAULT_OLLAMA_MODEL      # alias used by llm_checks.py

# ── Common Settings ───────────────────────────────────────────────────────────
# To switch back to 70b after limit resets, change DEFAULT_GROQ_MODEL above to:
# DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
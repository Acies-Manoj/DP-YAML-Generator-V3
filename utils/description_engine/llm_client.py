"""
llm_client.py — LLM API client supporting multiple free providers.

Supported providers:
  - groq:   Free cloud API via console.groq.com (recommended)
  - ollama: Local free inference via ollama.com

model_config examples:
  Groq:   {"provider": "groq",   "api_key": "gsk_...", "model": "llama3-8b-8192"}
  Ollama: {"provider": "ollama", "model": "mistral",   "base_url": "http://localhost:11434"}
"""

import json
import time


# ── Groq recommended free models ─────────────────────────────────────────────
GROQ_MODELS = [
    "llama3-8b-8192",
    "llama-3.3-70b-versatile",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]

OLLAMA_MODELS = [
    "mistral",
    "llama3",
    "gemma2",
    "phi3",
]

SYSTEM_PROMPT = (
    "You are a a senior data analyst documenting this table for a business intelligence team."
    "Always respond with valid JSON only. "
    "No markdown formatting, no code fences, no explanation. "
    "Pure JSON only."
)


def _validate_response(data: dict) -> dict:
    """Validate that LLM response has required keys."""
    if "table_description" not in data:
        raise ValueError("LLM response missing 'table_description' key")
    if "columns" not in data or not isinstance(data["columns"], list):
        raise ValueError("LLM response missing or invalid 'columns' key")
    return data


def _parse_json_response(raw: str) -> dict:
    """
    Parse JSON from LLM response, handling common issues like
    markdown fences that some models add despite instructions.
    """
    text = raw.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(
            l for l in lines if not l.strip().startswith("```")
        ).strip()
    return json.loads(text)


def _call_groq(prompt: str, model_config: dict) -> dict:
    """Call Groq cloud API (free tier)."""
    try:
        from groq import Groq
    except ImportError:
        raise ImportError(
            "groq package not installed. Run: pip install groq"
        )

    api_key = model_config.get("api_key", "")
    if not api_key:
        raise ValueError("Groq API key is required. Get one free at console.groq.com")

    model   = model_config.get("model", "llama3-8b-8192")
    client  = Groq(api_key=api_key)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=2000,
        temperature=0.1,  # Low temp = more consistent JSON output
    )

    raw = response.choices[0].message.content
    return _parse_json_response(raw)


def _call_ollama(prompt: str, model_config: dict) -> dict:
    """Call local Ollama instance."""
    try:
        import requests
    except ImportError:
        raise ImportError("requests package not installed. Run: pip install requests")

    base_url = model_config.get("base_url", "http://localhost:11434")
    model    = model_config.get("model", "mistral")
    url      = f"{base_url}/api/generate"

    full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"

    payload = {
        "model":  model,
        "prompt": full_prompt,
        "stream": False,
        "format": "json",  # Ollama JSON mode
        "options": {"temperature": 0.1},
    }

    resp = requests.post(url, json=payload, timeout=120)
    resp.raise_for_status()

    raw = resp.json().get("response", "")
    return _parse_json_response(raw)


def call_llm(prompt: str, model_config: dict, retries: int = 1) -> dict:
    """
    Call LLM with the given prompt using the configured provider.

    Args:
        prompt:       Full prompt string from prompt_builder.
        model_config: Dict with provider + credentials. See module docstring.
        retries:      Number of retry attempts on JSON parse failure.

    Returns:
        Validated dict: {"table_description": str, "columns": [...]}

    Raises:
        ValueError:   If JSON parsing fails after retries.
        RuntimeError: If API call itself fails.
    """
    provider = model_config.get("provider", "groq").lower()

    for attempt in range(retries + 1):
        try:
            if provider == "groq":
                data = _call_groq(prompt, model_config)
            elif provider == "ollama":
                data = _call_ollama(prompt, model_config)
            else:
                raise ValueError(
                    f"Unsupported provider: '{provider}'. Use 'groq' or 'ollama'."
                )
            return _validate_response(data)

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            if attempt < retries:
                time.sleep(1)
                continue
            raise ValueError(
                f"LLM returned invalid JSON after {retries + 1} attempt(s). "
                f"Error: {e}"
            )
        except Exception as e:
            raise RuntimeError(f"LLM API call failed ({provider}): {e}") from e

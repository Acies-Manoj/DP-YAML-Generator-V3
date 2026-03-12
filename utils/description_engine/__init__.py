"""
utils/description_engine — Metadata Intelligence Module

Public API:
    from utils.description_engine import generate_descriptions
    from utils.description_engine import generate_descriptions_multi
    from utils.description_engine import clear_cache

UI helper (used in pages/1_CADP.py only):
    from utils.description_engine.description_ui import render_description_panel
"""

from .description_generator import (
    generate_descriptions,
    generate_descriptions_multi,
    clear_cache,
)

__all__ = [
    "generate_descriptions",
    "generate_descriptions_multi",
    "clear_cache",
]
"""
StockMinds Core Computational Substrate.
Contains pure in-memory rate limiting, Pydantic schemas, configuration, and token-budgeted prompt assemblers.
"""

from core.config import Settings, settings

__all__ = ["Settings", "settings"]

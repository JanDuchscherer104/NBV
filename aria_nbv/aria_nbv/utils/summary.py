"""Compatibility import for the former tensor-summary module.

This module exports the canonical :func:`aria_nbv.utils.summarize` under its
historical direct-import path. New code should use the package-level export;
the compatibility surface adds no second implementation.
"""

from .rich_summary import summarize

__all__ = ["summarize"]

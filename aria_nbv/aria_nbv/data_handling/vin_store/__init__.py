"""Immutable VIN offline-store contracts, adapters, and actor views.

Import specialized manifest, reader, writer, and batch contracts from their
leaf modules; this package root intentionally exports only the stable snippet
view predicates.
"""

from .views import VinSnippetView, is_vin_snippet_view_instance

__all__ = ["VinSnippetView", "is_vin_snippet_view_instance"]

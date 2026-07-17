"""Normalize EFM semantic-id metadata for data and visualization consumers.

This module provides tolerant normalization of sparse mappings or legacy dense
name sequences and a single class-name lookup with a numeric fallback. It owns
presentation-facing canonicalization only; it does not remap stored semantic
ids, infer categories, or define the dataset ontology.

Sparse mappings and legacy dense sequences are converted to one integer-keyed
representation without treating unknown numeric ids as meaningful labels.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypeAlias

SemanticNameMap: TypeAlias = dict[int, str]
"""Sparse mapping from EFM semantic id to human-readable class name."""


def normalize_semantic_name_map(value: Mapping[object, object] | Sequence[object] | None) -> SemanticNameMap | None:
    """Normalize raw EFM semantic-name metadata into a sparse id map.

    Args:
        value: Raw semantic metadata from EFM, msgpack, or legacy dense lists.

    Returns:
        Sparse ``{semantic_id: class_name}`` mapping, or ``None`` when missing.
    """

    if value is None:
        return None
    if isinstance(value, Mapping):
        return {int(key): str(item) for key, item in value.items()}
    if isinstance(value, (str, bytes)):
        raise TypeError("Semantic-name metadata must be a mapping or sequence of names, not a string.")
    return {index: str(item) for index, item in enumerate(value)}


def semantic_class_name(sem_id: int | float, sem_id_to_name: Mapping[int, str] | Sequence[str] | None) -> str:
    """Return a display class name for one EFM semantic id."""

    index = int(sem_id)
    mapping = normalize_semantic_name_map(sem_id_to_name)
    if mapping is None:
        return "<unknown>"
    name = str(mapping.get(index, ""))
    if not name or name == str(index):
        return "<unknown>"
    return name

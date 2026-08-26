"""Extract source-owned inline documentation for config and datamodel fields.

The extractor reads Python syntax only. It never imports a model's runtime
target, evaluates annotations, or instantiates configuration objects, which
makes it safe for metadata-only configuration inspection.
"""

from __future__ import annotations

import ast
from functools import cache
from inspect import cleandoc, getsource
from textwrap import dedent


@cache
def field_docstrings(model: type) -> dict[str, str]:
    """Return inline string literals immediately following annotated fields.

    Args:
        model: Dataclass or Pydantic model class whose source is inspectable.

    Returns:
        Field-name to cleaned documentation mapping. Dynamically generated or
        source-unavailable classes return an empty mapping.

    Notes:
        Only a literal string expression directly after an ``AnnAssign`` is a
        field docstring. Comments, computed strings, and inherited fields are
        intentionally excluded; callers may walk the model MRO when needed.
    """

    try:
        tree = ast.parse(dedent(getsource(model)))
    except (OSError, TypeError, SyntaxError, IndentationError):
        return {}
    class_node = next((node for node in tree.body if isinstance(node, ast.ClassDef)), None)
    if class_node is None:
        return {}
    docs: dict[str, str] = {}
    body = class_node.body
    for index, node in enumerate(body[:-1]):
        if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
            continue
        following = body[index + 1]
        if not isinstance(following, ast.Expr):
            continue
        value = following.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            docs[node.target.id] = cleandoc(value.value)
    return docs


def inherited_field_docstring(model: type, field_name: str) -> str | None:
    """Resolve one field docstring from the nearest class in the model MRO."""

    for owner in model.__mro__:
        if owner is object:
            continue
        if doc := field_docstrings(owner).get(field_name):
            return doc
    return None


__all__ = ["field_docstrings", "inherited_field_docstring"]

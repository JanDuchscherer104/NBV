"""Compact tensor summaries and Rich trees for diagnostics.

This module owns both the structured summary dictionaries used by model and
dataset diagnostics and their optional Rich rendering. It inspects
EFM3D tensor wrappers without mutating or moving their underlying tensors;
callers retain device and lifetime ownership.
"""

from dataclasses import fields, is_dataclass
from typing import Any, cast

import torch
from efm3d.aria.camera import CameraTW
from efm3d.aria.obb import ObbTW
from efm3d.aria.pose import PoseTW
from efm3d.aria.tensor_wrapper import TensorWrapper
from rich.text import Text
from rich.tree import Tree
from torch import Tensor


def summarize(val: Any, *, include_stats: bool = False) -> Any:
    """Describe tensor-like values without copying their payloads.

    Tensor wrappers are reduced to shape, dtype, and device metadata. Floating
    statistics are computed over finite elements only when `include_stats` is
    true; lists are represented by length and all other values pass through.
    """
    if val is None:
        return None
    if isinstance(val, list):
        return {"len": len(val)}

    tensor = _extract_tensor(val)
    if tensor is not None:
        return _tensor_summary(tensor, include_stats=include_stats)
    return val


def _extract_tensor(val: Any) -> Tensor | None:
    """Return the storage tensor exposed by a supported EFM3D wrapper."""
    if isinstance(val, Tensor):
        return val
    if isinstance(val, (TensorWrapper, PoseTW, CameraTW, ObbTW)):
        tensor = val.tensor() if callable(getattr(val, "tensor", None)) else val.tensor
        return cast(Tensor, tensor)
    return None


def _tensor_summary(tensor: Tensor, *, include_stats: bool = False) -> dict[str, Any]:
    """Build JSON-compatible metadata for one tensor."""
    summary: dict[str, Any] = {
        "shape": tuple(tensor.shape),
        "dtype": str(tensor.dtype),
        "device": str(tensor.device),
    }
    if tensor.numel() and torch.is_floating_point(tensor) and include_stats:
        finite = tensor[torch.isfinite(tensor)]
        if finite.numel():
            summary["min"] = float(finite.min())
            summary["max"] = float(finite.max())
            summary["mean"] = float(finite.mean())
    return summary


def summarize_shape(value: Any) -> str:
    """Render tensor shape, dtype, and device as one compact status string."""
    summary = summarize(value)
    if summary is None:
        return "None"
    if isinstance(summary, dict):
        if "shape" in summary:
            parts = [str(summary["shape"])]
            if "dtype" in summary:
                parts.append(str(summary["dtype"]).replace("torch.", ""))
            if "device" in summary:
                parts.append(str(summary["device"]))
            return " ".join(parts)
        if "len" in summary:
            return f"list(len={summary['len']})"
        return str(summary)
    return type(summary).__name__


def _list_desc(items: list[Any]) -> str:
    elem_type = type(items[0]).__name__ if items else "unknown"
    parts = [f"len: {len(items)}", f"elem_type: {elem_type}"]
    if items and not isinstance(items[0], (dict, list, tuple, torch.Tensor)):
        parts.append(f"first: {items[0]}")
        parts.append(f"last: {items[-1]}")
    return "{" + ", ".join(parts) + "}"


def _render_rich_summary(
    node: Tree,
    key: str | None,
    value: Any,
    path: tuple[str, ...],
    *,
    path_map: dict[tuple[str, ...], str],
    show_only_sample: set[str],
    include_stats: bool,
) -> None:
    lookup_path = path[1:] if path and path[0] == "data" else path
    flat_note = f" [flat: {path_map.get(lookup_path)}]" if lookup_path in path_map else ""
    label = f"{key} <{type(value).__name__}>{flat_note}" if key is not None else None
    current = node if label is None else node.add(Text(label, style="config.field"))

    tensor = _extract_tensor(value)
    if tensor is not None:
        current.add(
            Text(
                _format_tensor_summary(_tensor_summary(tensor, include_stats=include_stats)),
                style="config.value",
            )
        )
        return

    if isinstance(value, dict) and _is_tensor_summary(value):
        current.add(Text(_format_tensor_summary(value), style="config.value"))
        return

    if isinstance(value, dict):
        if not value:
            current.add(Text("{}", style="config.value"))
            return
        items = list(value.items())
        if key in show_only_sample and len(items) > 2:
            items = [items[0], items[-1]]
        for k, v in items:
            _render_rich_summary(
                current,
                k,
                v,
                path + (k,),
                path_map=path_map,
                show_only_sample=show_only_sample,
                include_stats=include_stats,
            )
        return

    if is_dataclass(value) and not isinstance(value, type):
        for field in fields(value):
            _render_rich_summary(
                current,
                field.name,
                getattr(value, field.name),
                path + (field.name,),
                path_map=path_map,
                show_only_sample=show_only_sample,
                include_stats=include_stats,
            )
        return

    if isinstance(value, (list, tuple)):
        current.add(Text(_list_desc(list(value)), style="config.value"))
        return

    current.add(Text(str(value), style="config.value"))


def _is_tensor_summary(value: dict[str, Any]) -> bool:
    if "shape" not in value or "dtype" not in value:
        return False
    allowed = {"shape", "dtype", "device", "min", "max", "mean"}
    return set(value.keys()).issubset(allowed)


def _format_tensor_summary(value: dict[str, Any]) -> str:
    shape = value.get("shape")
    dtype = value.get("dtype")
    device = value.get("device")
    parts = [f"Tensor{shape}", str(dtype).replace("torch.", "")]
    if device is not None:
        parts.append(str(device))
    stats = []
    for key in ("min", "max", "mean"):
        if key in value:
            stats.append(f"{key}={value[key]:.4g}")
    if stats:
        parts.append("{" + ", ".join(stats) + "}")
    return " ".join(parts)


def rich_summary(
    tree_dict: dict[str, Any],
    *,
    path_map: dict[tuple[str, ...], str] | None = None,
    include_stats: bool = False,
    show_only_sample: list[str] | None = None,
    root_label: str = "",
    is_print: bool = True,
) -> Tree:
    """Build and return a rich Tree from a flattened sample dict.

    - Dataclasses and dictionaries are traversed recursively, preserving the
      composition of typed dataset items and batches.
    - Tensors and EFM tensor wrappers show shape, dtype, and device; finite
      floating-point statistics are included when ``include_stats`` is true.
    - Lists show length/element type (+ first/last for primitive elements).
    - Dicts are traversed recursively; keys listed in ``show_only_sample`` are
      truncated to first/last items.
    - The original flat key is appended to the node label when available.
    """

    root = Tree(Text(root_label, style="config.name"))
    summary_data = tree_dict or {}
    resolved_path_map = path_map or {}
    sample_only = set(show_only_sample or [])

    for k, v in summary_data.items():
        _render_rich_summary(
            root,
            k,
            v,
            (k,),
            path_map=resolved_path_map,
            show_only_sample=sample_only,
            include_stats=include_stats,
        )

    if is_print:
        from .console import Console

        Console().print(root, soft_wrap=False, highlight=True, markup=True, emoji=False)  # type: ignore[no-untyped-call]
    return root


def capture_tree(tree: Tree) -> str:
    """Render a Rich tree as ANSI-free plain text for logs and web UIs."""
    from .console import Console

    console = Console(force_terminal=False, color_system=None, width=240)  # type: ignore[no-untyped-call]
    with console.capture() as capture:
        console.print(
            tree,
            soft_wrap=False,
            highlight=True,
            markup=True,
            emoji=False,
        )
    return capture.get().rstrip()


def capture_tree_html(tree: Tree) -> str:
    """Render a Rich tree as self-contained HTML while preserving its styles."""

    from .console import Console

    console = Console(
        record=True,
        force_terminal=True,
        color_system="truecolor",
        width=240,
    )  # type: ignore[no-untyped-call]
    console.print(tree, soft_wrap=False, highlight=True, markup=True, emoji=False)
    return console.export_html(
        code_format=(
            '<pre style="margin:0; overflow-x:auto; color:inherit; background:transparent; '
            'font-family:Menlo,\'DejaVu Sans Mono\',consolas,\'Courier New\',monospace">{code}</pre>'
        ),
        inline_styles=True,
    )


def build_nested(
    flat_sample: dict[str, Any], show_semidense: bool = True, show_gt: bool = True
) -> tuple[dict[str, Any], dict[tuple[str, ...], str]]:
    """Expand EFM `#`/`+` flat keys into a diagnostic-only nested mapping.

    Returns both the nested values and a reverse path map to the original flat
    keys. Optional filters hide semi-dense or oracle GT branches from display;
    they do not alter the source sample.
    """
    nested: dict[str, Any] = {}
    path_to_flat: dict[tuple[str, ...], str] = {}
    for k, v in flat_sample.items():
        if not show_semidense and k.startswith("msdpd#"):
            continue
        if not show_gt and k.startswith("gt_data"):
            continue

        parts: list[str] = []
        if "#" in k:
            a, rest = k.split("#", 1)
            parts.append(a)
            if "+" in rest:
                b, c = rest.split("+", 1)
                parts.extend([b, c])
            else:
                parts.append(rest)
        else:
            parts.append(k)

        cursor = nested
        for p in parts[:-1]:
            cursor = cursor.setdefault(p, {})
        cursor[parts[-1]] = v
        path_to_flat[tuple(parts)] = k

    return nested, path_to_flat

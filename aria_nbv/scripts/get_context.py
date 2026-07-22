"""Print contract-style classes and config fields from ``aria_nbv`` source.

The inspector uses Python's AST only, performs no imports or execution, and
writes the bounded contract view to stdout.
"""

from __future__ import annotations

import argparse
import ast
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

EXCLUDE_PATHS: list[str] = ["__init__.py"]
CONTRACT_SUFFIXES: tuple[str, ...] = (
    "View",
    "Output",
    "Prediction",
    "Batch",
    "Config",
    "Diagnostics",
    "Spec",
    "State",
    "Metadata",
)


@dataclass
class FunctionInfo:
    name: str
    signature: str
    doc: str | None = None


@dataclass
class FieldInfo:
    name: str
    annotation: str | None = None


@dataclass
class ClassInfo:
    name: str
    doc: str | None = None
    methods: list[FunctionInfo] = field(default_factory=list)
    fields: list[FieldInfo] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)
    category: str | None = None


@dataclass
class ModuleInfo:
    module: str
    path: Path
    doc: str | None
    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    constants: list[str] = field(default_factory=list)


def _is_constant_name(name: str) -> bool:
    return name.isupper() and name.replace("_", "").isalpha()


def _first_paragraph(text: str | None) -> str | None:
    if not text:
        return None
    stripped = text.strip()
    parts = [part.strip() for part in stripped.split("\n\n") if part.strip()]
    return parts[0] if parts else stripped


def _unparse(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def _base_name(expr: ast.expr) -> str:
    value = _unparse(expr)
    return value or "<unknown>"


def _format_signature(fn_node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args: list[str] = []
    positional = [*fn_node.args.posonlyargs, *fn_node.args.args]
    defaults = [None] * (len(positional) - len(fn_node.args.defaults)) + list(fn_node.args.defaults)

    for index, arg in enumerate(positional):
        if arg.arg == "self":
            continue
        name = arg.arg
        if index < len(fn_node.args.posonlyargs):
            name = f"{name} /"
        if defaults[index] is not None:
            name = f"{name}=..."
        args.append(name)

    if fn_node.args.vararg:
        args.append(f"*{fn_node.args.vararg.arg}")
    elif fn_node.args.kwonlyargs:
        args.append("*")

    for kw_arg, kw_default in zip(fn_node.args.kwonlyargs, fn_node.args.kw_defaults, strict=True):
        name = kw_arg.arg
        if kw_default is not None:
            name = f"{name}=..."
        args.append(name)

    if fn_node.args.kwarg:
        args.append(f"**{fn_node.args.kwarg.arg}")

    return f"({', '.join(args)})"


def _is_dataclass(class_node: ast.ClassDef) -> bool:
    for decorator in class_node.decorator_list:
        name = _unparse(decorator) or ""
        if name.endswith("dataclass"):
            return True
    return False


def _class_fields(class_node: ast.ClassDef) -> list[FieldInfo]:
    fields: list[FieldInfo] = []
    for stmt in class_node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            if stmt.target.id.startswith("_"):
                continue
            fields.append(FieldInfo(stmt.target.id, _unparse(stmt.annotation)))
        elif isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_") and not _is_constant_name(target.id):
                    fields.append(FieldInfo(target.id, None))
    dedup: dict[str, FieldInfo] = {}
    for item in fields:
        dedup[item.name] = item
    return list(dedup.values())


def _categorize_class(class_node: ast.ClassDef, bases: list[str]) -> str | None:
    base_set = set(bases)
    if any(base.endswith("TypedDict") for base in base_set):
        return "typed-dict"
    if any(base.endswith("BaseConfig") for base in base_set):
        return "config"
    if any(base.endswith("BaseModel") for base in base_set):
        return "pydantic-model"
    if any(base.endswith("BaseSettings") for base in base_set):
        return "settings-model"
    if _is_dataclass(class_node):
        return "dataclass"
    if class_node.name.endswith(CONTRACT_SUFFIXES):
        return "named-contract"
    return None


def parse_module(py_path: Path, root: Path) -> ModuleInfo | None:
    try:
        text = py_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        node = ast.parse(text, filename=str(py_path))
    except SyntaxError:
        return None

    mod_doc = ast.get_docstring(node)
    classes: list[ClassInfo] = []
    functions: list[FunctionInfo] = []
    constants: list[str] = []

    for stmt in node.body:
        if isinstance(stmt, ast.ClassDef):
            methods: list[FunctionInfo] = []
            for class_stmt in stmt.body:
                if isinstance(class_stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and not class_stmt.name.startswith(
                    "_"
                ):
                    methods.append(
                        FunctionInfo(
                            name=class_stmt.name,
                            signature=_format_signature(class_stmt),
                            doc=ast.get_docstring(class_stmt),
                        )
                    )
            bases = [_base_name(base) for base in stmt.bases]
            classes.append(
                ClassInfo(
                    name=stmt.name,
                    doc=ast.get_docstring(stmt),
                    methods=methods,
                    fields=_class_fields(stmt),
                    bases=bases,
                    category=_categorize_class(stmt, bases),
                )
            )
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and not stmt.name.startswith("_"):
            functions.append(
                FunctionInfo(
                    name=stmt.name,
                    signature=_format_signature(stmt),
                    doc=ast.get_docstring(stmt),
                )
            )
        elif isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and _is_constant_name(target.id):
                    constants.append(target.id)

    rel = py_path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    module_name = ".".join(parts)
    return ModuleInfo(
        module=module_name,
        path=py_path,
        doc=mod_doc,
        classes=classes,
        functions=functions,
        constants=constants,
    )


def scan_root(root: Path) -> list[ModuleInfo]:
    modules: list[ModuleInfo] = []
    for py_path in root.rglob("*.py"):
        if "__pycache__" in py_path.parts:
            continue
        if py_path.name == "__init__.py":
            continue
        rel_path = py_path.relative_to(root).as_posix()
        if rel_path in EXCLUDE_PATHS:
            continue
        info = parse_module(py_path, root)
        if info and info.module:
            modules.append(info)
    modules.sort(key=lambda module: module.module)
    return modules


def print_contracts(mods: list[ModuleInfo], root: Path, max_doc: int) -> None:
    print("# Data Contracts\n")
    for module in mods:
        contract_classes = [class_info for class_info in module.classes if class_info.category is not None]
        if not contract_classes:
            continue
        for class_info in contract_classes:
            rel_path = module.path.relative_to(root).as_posix()
            doc = _first_paragraph(class_info.doc) or "—"
            if len(doc) > max_doc:
                doc = doc[: max_doc - 1] + "..."
            print(f"## {module.module}.{class_info.name}")
            print(f"- Category: {class_info.category}")
            print(f"- File: {rel_path}")
            if class_info.bases:
                print(f"- Bases: {', '.join(class_info.bases)}")
            print(doc)
            if class_info.fields:
                print("\nFields:")
                for field_info in class_info.fields:
                    if field_info.annotation:
                        print(f"- `{field_info.name}: {field_info.annotation}`")
                    else:
                        print(f"- `{field_info.name}`")
            print()


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1] / "aria_nbv"),
        help="Root package directory",
    )
    parser.add_argument("--max-doc", type=int, default=240, help="Max characters for doc summaries")
    args = parser.parse_args(list(argv) if argv is not None else None)

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"error: root directory not found: {root}", file=sys.stderr)
        return 2
    modules = scan_root(root)
    print_contracts(modules, root, args.max_doc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

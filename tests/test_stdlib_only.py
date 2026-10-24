"""The backend must run with the Python standard library alone."""

import ast
import pathlib
import sys

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "marine_guard"


def test_marine_guard_imports_only_standard_library():
    for path in PACKAGE.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module]
            else:
                continue
            for name in names:
                root = name.split(".")[0]
                assert root in sys.stdlib_module_names, f"{path.name} imports {name}"


def test_marine_guard_has_no_print_calls():
    for path in PACKAGE.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "print":
                raise AssertionError(f"print() in {path.name}")


WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                    *(f"lpt{i}" for i in range(1, 10))}


def test_no_file_names_that_windows_cannot_create():
    root = PACKAGE.parent
    for path in root.rglob("*"):
        if ".git" in path.parts:
            continue
        assert path.name.split(".")[0].lower() not in WINDOWS_RESERVED, path

"""Static import and ground-truth boundary checks for production code."""
import ast
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {"faultctl", "tests", ".venv", ".build", ".git", ".specs", "__pycache__", "runs"}


def violations(source):
    tree = ast.parse(source)
    hits = []
    def static_text(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = static_text(node.left), static_text(node.right)
            if left is not None and right is not None:
                return left + right
        return None
    for node in ast.walk(tree):
        literal = static_text(node)
        if literal and "injected.json" in literal.lower():
            hits.append("ground truth string")
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] == "faultctl" for alias in node.names):
                hits.append("faultctl import")
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "faultctl":
            hits.append("faultctl import")
        elif isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            if name in {"__import__", "import_module"} and node.args:
                arg = static_text(node.args[0])
                if arg and arg.split(".")[0] == "faultctl":
                    hits.append("dynamic faultctl import")
    # Catch path construction in stages as well as a complete path literal.
    if re.search(r"injected[.]json|loop[.]pid|faultctl[/\\]([.]state|[.]pristine)", source, re.I):
        hits.append("ground truth reference")
    return hits


def test_agent_isolation():
    hits = []
    for path in ROOT.rglob("*.py"):
        if any(part in EXCLUDED for part in path.relative_to(ROOT).parts):
            continue
        hits.extend(f"{path.relative_to(ROOT)}: {hit}" for hit in violations(path.read_text(encoding="utf-8")))
    assert not hits, "\n".join(hits)


def test_boundary_checker_rejects_import_and_path_forms():
    for source in ("import faultctl", "from faultctl.core import inject", "__import__('faultctl.core')", "importlib.import_module('faultctl')", "p = root / 'injected.json'", "__import__('fault'+'ctl')", "p = 'injected' + '.json'"):
        assert violations(source)
    assert not violations("from tools import get_metrics")

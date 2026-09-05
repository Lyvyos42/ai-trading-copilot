"""Source-level rules for the signal path.

Some failure modes cannot be caught by running the code, because they only
appear when a specific agent abstains on a specific symbol with a specific
data source down - a combination no reachable unit test enumerates. Those are
asserted against the source instead.

Imported by scripts/test_agent_integrity.py.
"""
import ast
import glob
import io
import os

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")

_DEFAULTS = ("''", '""', "[]", "{}", "0", "0.0")


def _py_files(root: str):
    return sorted(glob.glob(os.path.join(root, "**", "*.py"), recursive=True))


def find_rng(root: str = APP) -> list[str]:
    """Executable references to random/rng. AST, so comments and docstrings pass."""
    out = []
    for path in _py_files(root):
        tree = ast.parse(io.open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                    and node.value.id in ("rng", "random")):
                out.append(f"{os.path.basename(path)}:{node.lineno}")
    return out


def find_get_then_index(root: str = APP) -> list[str]:
    """`d.get(key, default)` that is then indexed or sliced.

    `.get(key, default)` returns the default only when the key is ABSENT.
    Since agents began abstaining, keys are PRESENT with value None - so the
    default never fires and the following index raises. This exact trap has
    produced four separate production failures:

        quant.py      market_data.get("atr", close * 0.012)
        trader.py     fund.get("earnings_momentum", 0) > 0.2
        trader.py     CURRENT PRICE: {current_price:{_pfmt}}
        signals.py    final.get("bull_case", "")[:200]   <- the BTC-USD 500

    The safe idiom is `(d.get(k) or default)`, which handles absent AND None.

    Detected on the AST so f-strings and nesting are covered: a Subscript whose
    value is a Call to `.get` with two arguments.
    """
    out = []
    for path in _py_files(root):
        tree = ast.parse(io.open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Subscript):
                continue
            call = node.value
            if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "get" and len(call.args) == 2):
                out.append(f"{os.path.basename(path)}:{node.lineno}")
    return out


def find_eager_arithmetic_default(root: str = APP) -> list[str]:
    """`d.get(key, <arithmetic>)` — the default is evaluated eagerly.

    `market_data.get("atr", close * 0.012)` computes `close * 0.012` BEFORE the
    lookup, so it raises when close is None even though the key exists. Use
    nz(d, key, default) or guard the operand.
    """
    out = []
    for path in _py_files(root):
        tree = ast.parse(io.open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get" and len(node.args) == 2):
                continue
            if isinstance(node.args[1], ast.BinOp):
                out.append(f"{os.path.basename(path)}:{node.lineno}")
    return out

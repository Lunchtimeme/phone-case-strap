"""Read the Human Kit's strap parameters from its OpenSCAD file.

The SCAD models and this package's analytic B-rep builder must never disagree
about a dimension, so neither of them owns a copy: this module evaluates
`strap_system_parameters.scad` itself, including the simple arithmetic it uses to
derive ear spacing, track spacing and window width from the band width.

Only numeric literals, names and + - * / % ** are accepted. Anything else raises,
rather than silently producing a wrong dimension.
"""

import ast
import os
import re
from pathlib import Path

PARAMETER_FILE_NAME = "strap_system_parameters.scad"


def search_dirs():
    """Places to look for the parameter file, without relying on __file__.

    FreeCADCmd does not always define __file__ for the script it runs.
    """
    dirs = []
    try:
        dirs.append(Path(__file__).resolve().parent)
    except NameError:
        pass
    dirs.append(Path.cwd())
    dirs.append(Path.cwd() / "modules")
    return dirs


def find_parameters_file(extra_dirs=()):
    env = os.environ.get("STRAP_PARAMETERS")
    if env:
        p = Path(env)
        if not p.is_file():
            raise FileNotFoundError(f"STRAP_PARAMETERS points at {p}, which does not exist")
        return p.resolve()

    tried = []
    for d in list(extra_dirs) + search_dirs():
        for c in (d / PARAMETER_FILE_NAME,
                  d / "human_kit" / PARAMETER_FILE_NAME,
                  d.parent / "human_kit" / PARAMETER_FILE_NAME,
                  d.parent / "Human_Kit" / PARAMETER_FILE_NAME,
                  d.parent.parent / "Human_Kit" / PARAMETER_FILE_NAME):
            tried.append(c)
            if c.is_file():
                return c.resolve()
    raise FileNotFoundError(
        f"cannot find {PARAMETER_FILE_NAME}. Looked in:\n"
        + "\n".join(f"  {c}" for c in tried)
        + "\nSet STRAP_PARAMETERS to its path."
    )


def _eval(expr, env):
    node = ast.parse(expr.strip(), mode="eval").body

    def ev(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.Name):
            if n.id not in env:
                raise KeyError(n.id)
            return env[n.id]
        if isinstance(n, ast.UnaryOp):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else +v
        if isinstance(n, ast.BinOp):
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Add):
                return a + b
            if isinstance(n.op, ast.Sub):
                return a - b
            if isinstance(n.op, ast.Mult):
                return a * b
            if isinstance(n.op, ast.Div):
                return a / b
            if isinstance(n.op, ast.Mod):
                return a % b
            if isinstance(n.op, ast.Pow):
                return a ** b
        raise ValueError(f"unsupported expression: {expr.strip()}")

    return ev(node)


def read_parameters(path):
    """Return (values, unresolved_names) from a SCAD parameter file."""
    text = Path(path).read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    pending = dict(re.findall(r"^\s*([A-Za-z_]\w*)\s*=\s*([^;]+);", text, flags=re.M))

    values = {}
    for _ in range(len(pending) + 1):
        progressed = False
        for name in list(pending):
            try:
                values[name] = _eval(pending[name], values)
            except (KeyError, ValueError, SyntaxError, ZeroDivisionError):
                continue
            del pending[name]
            progressed = True
        if not progressed:
            break
    return values, sorted(pending)


class Parameters:
    """Resolved parameter set with a clear error for anything missing."""

    def __init__(self, path=None, extra_dirs=()):
        self.path = Path(path) if path else find_parameters_file(extra_dirs)
        self.values, self.unresolved = read_parameters(self.path)

    def __getitem__(self, name):
        if name not in self.values:
            raise KeyError(
                f"{self.path}: cannot use '{name}' - it is missing or uses an "
                "expression this loader does not handle."
            )
        return self.values[name]

    def get(self, name, default=None):
        return self.values.get(name, default)

    def require(self, names):
        missing = [n for n in names if n not in self.values]
        if missing:
            raise KeyError(f"{self.path}: missing parameters: {', '.join(missing)}")
        return {n: self.values[n] for n in names}

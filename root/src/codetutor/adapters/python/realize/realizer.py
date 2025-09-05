from __future__ import annotations
import json, importlib
from pathlib import Path
from typing import Any, Dict, List, Tuple
from codetutor.core.dsl.loader import IR

FIXTURE_DIR = Path("data/fixtures")  # expects: data/fixtures/<language>/<library>/fixtures.json

def _value_code(v: Any) -> str:
    if isinstance(v, str):
        return json.dumps(v)
    if isinstance(v, list):
        return "[" + ",".join(_value_code(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ",".join(f"{_value_code(k)}:{_value_code(val)}" for k, val in v.items()) + "}"
    return repr(v)

def _load_fixture_map(language: str, library: str) -> Dict[str, Dict[str, Any]]:
    p = FIXTURE_DIR / language / library / "fixtures.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Empty means: no imports/setup hints; we will still try best-effort generic fallback
    return {}

def _initial_setup(language: str, library: str, accept_label: str, fixture_map: Dict[str, Dict[str, Any]]) -> Tuple[str, str, str]:
    """
    Returns (imports_code, setup_code, serializer_hint)
    Fixture schema (JSON) per type label, e.g.:
    {
      "DataFrame": {
         "imports": ["import pandas as pd"],
         "setup": "curr = pd.DataFrame({'A':[1,2,3],'B':[10,20,30]})",
         "serializer": "csv"
      }
    }
    """
    info = fixture_map.get(accept_label, {})
    imports = "\n".join(info.get("imports", [])) + ("\n" if info.get("imports") else "")
    setup = info.get("setup", "")
    serializer = (info.get("serializer") or "").lower()
    return imports, setup, serializer

def _call_snippet(qual: str, kwargs: Dict[str, Any]) -> str:
    """
    Generic call:
      - Try bound method getattr(curr, name)
      - Else import module and call free function f(curr, **kwargs)
    """
    name = qual.split(".")[-1]
    args_code = ", ".join(f"{k}={_value_code(v)}" for k, v in kwargs.items())
    mod_path = qual.rsplit(".", 1)[0]
    return (
        f"__m = getattr(curr, {json.dumps(name)}, None)\n"
        f"if callable(__m):\n"
        f"    __res = __m({args_code})\n"
        f"else:\n"
        f"    __f = __import__({json.dumps(mod_path)}, fromlist=['*']).{name}\n"
        f"    __res = __f(curr, {args_code})\n"
        f"curr = curr if __res is None else __res\n"
    )

def _serialize_snippet(serializer_hint: str) -> str:
    """
    Try hint, then fallbacks: to_csv / to_json / to_dict / tolist / numpy / repr
    """
    lines = ["import sys"]
    if serializer_hint == "csv":
        lines += [
            "if hasattr(curr, 'to_csv'): sys.stdout.write(curr.to_csv(index=False))",
            "elif hasattr(curr, 'to_json'): sys.stdout.write(curr.to_json())",
            "else: sys.stdout.write(str(curr))",
        ]
    elif serializer_hint == "json":
        lines += [
            "if hasattr(curr, 'to_json'): sys.stdout.write(curr.to_json())",
            "elif hasattr(curr, 'to_dict'): import json as _j; sys.stdout.write(_j.dumps(curr.to_dict()))",
            "else: sys.stdout.write(str(curr))",
        ]
    else:
        lines += [
            "if hasattr(curr, 'to_csv'): sys.stdout.write(curr.to_csv(index=False))",
            "elif hasattr(curr, 'to_json'): sys.stdout.write(curr.to_json())",
            "elif hasattr(curr, 'to_dict'): import json as _j; sys.stdout.write(_j.dumps(curr.to_dict()))",
            "elif hasattr(curr, 'tolist'): import json as _j; sys.stdout.write(_j.dumps(curr.tolist()))",
            "elif hasattr(curr, 'numpy'): import json as _j; sys.stdout.write(_j.dumps(curr.numpy().tolist()))",
            "else: sys.stdout.write(str(curr))",
        ]
    return "\n".join(lines) + "\n"

def realize_program(language: str, library: str, ir: IR, plan: List[int], kwarg_list: List[Dict[str, Any]]) -> str:
    """
    Purely generic: relies on cards for qualnames and type labels, and on a data-driven fixture map.
    """
    first = ir.cards[plan[0]]
    accept_label = str(first.pre.get("accepts") or "")
    if not accept_label:
        # last resort: let user supply fixtures for their library; fail loudly if none
        raise ValueError("First card lacks pre.accepts; cannot choose an initial fixture.")

    fixture_map = _load_fixture_map(language, library)
    imports, setup, serializer_hint = _initial_setup(language, library, accept_label, fixture_map)

    if not setup:
        # Best-effort generic placeholder (keeps universality; user can add fixtures.json to improve)
        setup = "curr = None  # TODO: provide a fixture in data/fixtures/{}/{}/fixtures.json\n".format(language, library)

    body = []
    for step_idx, idx in enumerate(plan):
        qual = ir.cards[idx].qualname
        body.append(_call_snippet(qual, kwarg_list[step_idx]))

    return imports + setup + "".join(body) + _serialize_snippet(serializer_hint)

from __future__ import annotations
import importlib, json
from typing import Any, Dict, List, Tuple
from codetutor.core.dsl.loader import IR, Card

def value_code(v: Any) -> str:
    if isinstance(v, str): return json.dumps(v)
    if isinstance(v, list): return "[" + ",".join(value_code(x) for x in v) + "]"
    if isinstance(v, dict): return "{" + ",".join(f"{value_code(k)}:{value_code(val)}" for k,val in v.items()) + "}"
    return repr(v)

def qual_to_obj(qual: str):
    parts = qual.split(".")
    for i in range(len(parts), 0, -1):
        try:
            mod = importlib.import_module(".".join(parts[:i]))
            obj = mod
            for p in parts[i:]:
                obj = getattr(obj, p)
            return obj
        except Exception:
            continue
    raise ImportError(f"cannot import {qual}")

def initial_fixture(lib: str, accept_label: str) -> Tuple[str, str]:
    if lib == "pandas":
        if accept_label == "DataFrame":
            head = "import pandas as pd\n"
            data = "df = pd.DataFrame({'A':[1,2,3,4],'B':[10,20,30,40],'C':[5,6,7,8]})\n"
            return head, data + "curr = df\n"
        if accept_label == "Series":
            head = "import pandas as pd\n"
            data = "curr = pd.Series([1,2,3,4])\n"
            return head, data
    raise ValueError(f"No fixture for {lib}:{accept_label}")

def call_line(qual: str, kwargs: Dict[str,Any]) -> str:
    name = qual.split(".")[-1]
    args_code = ", ".join(f"{k}={value_code(v)}" for k,v in kwargs.items())
    # Try bound method first; fallback to function(curr, ...)
    return (
        f"__m = getattr(curr, {value_code(name)}, None)\n"
        f"if callable(__m):\n"
        f"    __res = __m({args_code})\n"
        f"else:\n"
        f"    __f = __import__('{qual.rsplit('.',1)[0]}', fromlist=['*']).{name}\n"
        f"    __res = __f(curr, {args_code})\n"
        f"curr = curr if __res is None else __res\n"
    )

def realize_program(lib: str, ir: IR, plan: List[int], kwarg_list: List[Dict[str,Any]]) -> str:
    first = ir.cards[plan[0]]
    acc = first.pre.get("accepts") or "DataFrame"
    head, setup = initial_fixture(lib, str(acc))
    body = []
    for step_idx, card_idx in enumerate(plan):
        qual = ir.cards[card_idx].qualname
        body.append(call_line(qual, kwarg_list[step_idx]))
    tail = (
        "import sys\n"
        "try:\n"
        "    import pandas as pd\n"
        "    if hasattr(curr,'to_csv'):\n"
        "        sys.stdout.write(curr.to_csv(index=False))\n"
        "    else:\n"
        "        sys.stdout.write(str(curr))\n"
        "except Exception:\n"
        "    sys.stdout.write(str(curr))\n"
    )
    return head + setup + "".join(body) + tail
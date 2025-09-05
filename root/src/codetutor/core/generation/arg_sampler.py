from __future__ import annotations
import random
from typing import Any, Dict, List, Tuple

# params schema: list of (name:str, domain:str, required:bool, default:Optional[str])
def sample_kwargs(params: List[Tuple[str,str,bool,object]], env: Dict[str,Any]) -> Dict[str,Any]:
    kwargs: Dict[str,Any] = {}
    for name, dom, required, default in params:
        if default is not None and not required:
            # often safest to omit optionals; include sometimes
            if random.random() < 0.2: kwargs[name] = coerce(default)
            continue
        if not required:
            # include some optional args randomly
            if random.random() < 0.3:
                kwargs[name] = sample_value(dom, env)
            continue
        kwargs[name] = sample_value(dom, env)
    return kwargs

def coerce(v):
    # defaults are strings from DB; try to interpret
    if isinstance(v, (int, float, bool)): return v
    s = str(v)
    if s.lower() in ("true","false"): return s.lower() == "true"
    try: return int(s)
    except: pass
    try: return float(s)
    except: pass
    return s

def sample_value(domain: str, env: Dict[str,Any]):
    d = domain or "any"
    if "bool" in d: return random.choice([True, False])
    if "int" in d: return random.randint(1,3)
    if "float" in d: return round(random.uniform(0.1, 3.0), 2)
    if "enum[" in d:
        inside = d[d.find("[")+1:d.find("]")]
        items = [x.strip() for x in inside.split("|") if x.strip()]
        return items[0] if items else "enumval"
    if "str|list[str]" in d:
        col = (env.get("columns") or ["A"])[0]
        return random.choice([col, [col]])
    if "list" in d: return []
    if "dict" in d: return {}
    if "str" in d:
        return (env.get("columns") or ["A"])[0]
    return 1  # any

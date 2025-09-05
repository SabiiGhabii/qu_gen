from __future__ import annotations
import csv, io, json, hashlib
from typing import Any, Dict, Tuple, Literal

def fingerprint(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]

def detect_format(stdout: str) -> Literal["csv","json","text"]:
    s = stdout.strip()
    if not s: return "text"
    # try CSV quickly
    try:
        _ = list(csv.reader(io.StringIO(s)))
        if len(_) >= 1 and len(_[0]) >= 1:
            return "csv"
    except Exception:
        pass
    # try JSON
    try:
        json.loads(s)
        return "json"
    except Exception:
        return "text"

def summarize(stdout: str) -> Dict[str, Any]:
    kind = detect_format(stdout)
    if kind == "csv":
        rows = list(csv.reader(io.StringIO(stdout)))
        return {"format":"csv", "rows": len(rows)-1 if rows else 0, "cols": len(rows[0]) if rows else 0,
                "header": rows[0] if rows else [], "preview": "\n".join("\t".join(r) for r in rows[:5])}
    if kind == "json":
        try:
            obj = json.loads(stdout)
        except Exception:
            obj = None
        return {"format":"json", "type": type(obj).__name__ if obj is not None else "invalid",
                "preview": stdout[:800]}
    return {"format":"text", "len": len(stdout), "preview": stdout[:800]}

def validate_nonempty(stdout: str) -> Tuple[bool, str]:
    ok = bool(stdout.strip())
    return ok, "nonempty output" if ok else "empty output"

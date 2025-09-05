from __future__ import annotations
import importlib, inspect, json, sqlite3, sys, math
from pathlib import Path
from typing import Any
from blake3 import blake3
from griffe import load
from docstring_parser import parse as parse_doc

def _connect(db_path: str) -> sqlite3.Connection:
    p = Path(db_path); p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p))
    con.execute("PRAGMA foreign_keys=ON;")
    return con

def _ensure_schema(con: sqlite3.Connection, schema_path: str | None = None) -> None:
    if schema_path is None:
        schema_path = Path(__file__).with_name("schema.sql")
    sql = Path(schema_path).read_text(encoding="utf-8")
    con.executescript(sql)

def _hash(s: str | None) -> str | None:
    return blake3(s.encode("utf-8")).hexdigest() if s else None

def _get_or_insert_library(con: sqlite3.Connection, name: str, version: str | None) -> int:
    row = con.execute(
        "SELECT id FROM libraries WHERE name=? AND IFNULL(version,'')=IFNULL(?, '')",
        (name, version),
    ).fetchone()
    if row: return row[0]
    cur = con.execute(
        "INSERT INTO libraries(name,version,hash) VALUES(?,?,?)",
        (name, version, _hash(f"{name}:{version or ''}"))
    )
    return cur.lastrowid

def _import_qualname(qn: str) -> Any | None:
    parts = qn.split(".")
    for i in range(len(parts), 0, -1):
        try:
            obj = importlib.import_module(".".join(parts[:i]))
            for p in parts[i:]:
                obj = getattr(obj, p)
            return obj
        except Exception:
            continue
    return None

def _insert_symbol(con: sqlite3.Connection, lib_id: int, *, qualname: str,
                   objtype: str, module: str, owner: str | None,
                   is_public: int, doc_hash: str | None, sig_hash: str | None) -> int:
    con.execute(
        "INSERT OR IGNORE INTO symbols(library_id,qualname,objtype,module,owner,is_public,doc_hash,sig_hash) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (lib_id, qualname, objtype, module, owner, is_public, doc_hash, sig_hash),
    )
    row = con.execute(
        "SELECT id FROM symbols WHERE library_id=? AND qualname=?",
        (lib_id, qualname),
    ).fetchone()
    return row[0]

def _insert_signature(con: sqlite3.Connection, symbol_id: int,
                      signature: str | None, params_json: str | None,
                      returns_text: str | None) -> None:
    if not (signature or params_json or returns_text): return
    con.execute(
        "INSERT INTO signatures(symbol_id,signature,params_json,returns_text) VALUES(?,?,?,?)",
        (symbol_id, signature, params_json, returns_text),
    )

def _insert_docstring(con: sqlite3.Connection, symbol_id: int, *,
                      summary: str | None, params_json: str | None,
                      returns_json: str | None, raw: str | None) -> None:
    if not raw: return
    con.execute(
        "INSERT INTO docstrings(symbol_id,summary,params_json,returns_json,raw) VALUES(?,?,?,?,?)",
        (symbol_id, summary, params_json, returns_json, raw),
    )

def scan_library(lib_name: str, db_path: str = "data/db/api_index.db",
                 schema_path: str | None = None, depth: str = "full") -> None:
    """
    depth:
      - 'light' -> only direct children of root module (e.g., pandas.*), no recursion
      - 'mid'   -> recurse one submodule level (e.g., pandas.core, pandas.tests), not deeper
      - 'full'  -> no limit
    """
    con = _connect(db_path)
    _ensure_schema(con, schema_path)

    mod = importlib.import_module(lib_name)
    version = getattr(mod, "__version__", None)
    lib_id = _get_or_insert_library(con, lib_name, version)

    model = load(lib_name)
    base_depth = len(lib_name.split("."))
    max_mod_depth = {
        "light": base_depth,          # only root's direct members
        "mid":   base_depth + 1,      # one level of submodules
        "full":  math.inf,            # unlimited
    }.get(depth, math.inf)

    def walk(m) -> None:
        # Skip aliases to avoid alias resolution crashes (e.g., pandas.annotations -> __future__.annotations)
        if getattr(m, "kind", None) and getattr(m.kind, "value", None) == "alias":
            return

        path = getattr(m, "path", lib_name)
        d = len(path.split("."))

        if getattr(m, "kind", None) and m.kind.value in {"module", "package"}:
            if d > max_mod_depth:
                return
            for child in getattr(m, "members", {}).values():
                walk(child)
            return

        qualname = path
        objtype = m.kind.value
        module = getattr(getattr(m, "module", None), "path", lib_name)
        owner = getattr(getattr(m, "parent", None), "path", None)
        is_public = 0 if any(part.startswith("_") for part in qualname.split(".")) else 1

        pyobj = _import_qualname(qualname)

        sig_txt = params_json = returns_text = None
        try:
            if pyobj and (inspect.isfunction(pyobj) or inspect.ismethod(pyobj) or inspect.isclass(pyobj)):
                sig = inspect.signature(pyobj)
                sig_txt = str(sig)
                params_json = json.dumps([
                    {
                        "name": p.name, "kind": str(p.kind),
                        "default": None if p.default is inspect._empty else repr(p.default),
                        "annotation": None if p.annotation is inspect._empty else repr(p.annotation),
                    } for p in sig.parameters.values()
                ])
                returns_text = None if sig.return_annotation is inspect._empty else repr(sig.return_annotation)
        except Exception:
            pass

        raw_doc = None
        try:
            raw_doc = inspect.getdoc(pyobj) if pyobj else (m.docstring.value if m.docstring else None)
        except Exception:
            raw_doc = None

        summary = params_doc_json = returns_doc_json = None
        if raw_doc:
            try:
                parsed = parse_doc(raw_doc)
                summary = (parsed.short_description or "")[:2048]
                params_doc_json = json.dumps([
                    {"arg": p.arg_name, "type": p.type_name, "desc": p.description}
                    for p in parsed.params
                ])
                returns_doc_json = json.dumps({
                    "type": getattr(parsed.returns, "type_name", None),
                    "desc": getattr(parsed.returns, "description", None),
                })
            except Exception:
                pass

        sym_id = _insert_symbol(
            con, lib_id,
            qualname=qualname, objtype=objtype, module=module, owner=owner,
            is_public=is_public, doc_hash=_hash(raw_doc), sig_hash=_hash(sig_txt),
        )
        _insert_signature(con, sym_id, sig_txt, params_json, returns_text)
        _insert_docstring(con, sym_id, summary=summary, params_json=params_doc_json,
                          returns_json=returns_doc_json, raw=raw_doc)

    for member in model.members.values():
        walk(member)

    con.commit()
    con.close()

if __name__ == "__main__":
    # Usage: python -m codetutor.adapters.python.scan.scan <library> [--depth light|mid|full]
    import argparse
    ap = argparse.ArgumentParser(prog="scan", add_help=True, description=None)
    ap.add_argument("library", help="Import name, e.g., pandas")
    ap.add_argument("--depth", choices=["light", "mid", "full"], default="full")
    args = ap.parse_args()
    scan_library(args.library, depth=args.depth)

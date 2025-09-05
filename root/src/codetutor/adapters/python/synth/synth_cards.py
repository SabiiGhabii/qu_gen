# FILE: src/codetutor/ctdsl/synth_cards.py
# usage: python -m codetutor.ctdsl.synth_cards pandas --db data/db/api_index.db --limit 50
from __future__ import annotations
import argparse, json, re, sqlite3, sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---- tiny helpers ----
def q(s: Optional[str]) -> str:
    return json.dumps(s) if s is not None else "null"  # robust string quoting, no custom escaper

def last_id_part(qual: Optional[str]) -> Optional[str]:
    if not qual: return None
    parts = qual.split(".")
    return parts[-1] if parts else None

def normalize_type(text: Optional[str]) -> Optional[str]:
    """Pick a simple type label from annotation/returns text (library-agnostic)."""
    if not text: return None
    toks = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)
    return toks[0] if toks else None

def infer_params(params_json: Optional[str]) -> List[Tuple[str,str,bool,Optional[str]]]:
    """Return (name, domain, required, default) tuples; domains are coarse but generic."""
    if not params_json: return []
    try:
        params = json.loads(params_json)
    except Exception:
        return []
    out = []
    for p in params:
        name = p.get("name") or ""
        ann  = (p.get("annotation") or "")
        default_raw = p.get("default", None)
        default = None if default_raw in (None, "inspect._empty") else str(default_raw)
        kind = str(p.get("kind", ""))
        required = default is None and ("POSITIONAL" in kind or "KEYWORD" in kind)
        # very broad, library-agnostic domain guesses
        dom = "any"
        ann_norm = ann.lower()
        if "bool" in ann_norm or name in {"inplace","ascending"}: dom = "bool"
        elif "int" in ann_norm: dom = "int"
        elif "float" in ann_norm: dom = "float"
        elif "str" in ann_norm or name in {"by","on","columns","subset","keys"}: dom = "str|list[str]"
        elif "list" in ann_norm or "sequence" in ann_norm or "iterable" in ann_norm: dom = "list[any]"
        elif "dict" in ann_norm or "mapping" in ann_norm: dom = "dict"
        elif "axis" in name.lower(): dom = "enum[axis]"
        out.append((name, dom, bool(required), default))
    return out

def infer_accepts(owner: Optional[str]) -> Optional[str]:
    """Use the owner’s last identifier as an accepted input type label."""
    return last_id_part(owner)

def infer_returns(qualname: str, owner: Optional[str], returns_text: Optional[str]) -> Optional[str]:
    """Prefer explicit return annotation; otherwise fall back to owner-as-container."""
    t = normalize_type(returns_text)
    if t: return t
    return last_id_part(owner)

def infer_is_stop(qualname: str, returns_label: Optional[str]) -> bool:
    """Stop if we return a concrete container-like type and not an obvious intermediate."""
    if not returns_label: return False
    # generic heuristic: names containing 'GroupBy'/'Iterator'/'Generator' are intermediate
    interm = re.search(r"(GroupBy|Iterator|Generator|Cursor|Builder)$", returns_label)
    if interm: return False
    # also treat obvious chaining ops (e.g., endswith '.groupby') as non-stop
    if qualname.split(".")[-1].lower() in {"groupby","builder","cursor"}: return False
    return True

def infer_mutates(params: List[Tuple[str,str,bool,Optional[str]]]) -> Optional[bool]:
    """Library-agnostic: presence of 'inplace' param suggests default non-mutating."""
    if any(n == "inplace" for n, *_ in params): return False
    return None  # unknown

# ---- DB access (expects your scan schema: libraries, symbols, signatures, docstrings) ----
SQL = """
SELECT s.qualname, s.objtype, s.owner, s.is_public,
       sig.signature, sig.params_json, sig.returns_text,
       d.raw as doc_raw
FROM symbols s
LEFT JOIN signatures sig ON sig.symbol_id = s.id
LEFT JOIN docstrings d   ON d.symbol_id = s.id
WHERE s.library_id = (SELECT id FROM libraries WHERE name = ?)
  AND s.is_public = 1
ORDER BY s.qualname
"""

def rows_for_library(db_path: str, lib: str, limit: Optional[int]) -> List[sqlite3.Row]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.execute(SQL, (lib,))
    rows = cur.fetchmany(limit) if limit else cur.fetchall()
    con.close()
    return rows

# ---- Card synthesis ----
def card_block(qualname: str,
               profile: str,
               accepts: Optional[str],
               params: List[Tuple[str,str,bool,Optional[str]]],
               returns: Optional[str],
               mutates: Optional[bool],
               is_stop: bool) -> str:
    lines = [f"card {qualname} : {profile} {{"]

    if accepts:
        lines.append(f"  pre.accepts = {q(accepts)};")

    if params:
        items = ", ".join(
            f"({q(n)},{q(dom)},{str(req).lower()},{q(d) if d is not None else 'null'})"
            for (n, dom, req, d) in params
        )
        lines.append(f"  pre.args = [ {items} ];")

    if returns:
        lines.append(f"  post.returns = {q(returns)};")

    if mutates is not None:
        lines.append(f"  post.mutates_input = {'true' if mutates else 'false'};")

    lines.append(f"  post.is_valid_stop = {'true' if is_stop else 'false'};")
    lines.append("}\n")
    return "\n".join(lines)

def synth_cards(db_path: str, lib: str, outdir: str, limit: int) -> Path:
    rows = rows_for_library(db_path, lib, limit)
    if not rows:
        sys.exit(f"No public symbols found for library '{lib}' in {db_path}")

    # ensure output dir: data/cards/{library}
    out_dir = Path(outdir) if outdir else Path("data") / "cards" / lib
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "cards.ctdsl"

    blocks: List[str] = []
    for r in rows:
        qual = r["qualname"]
        owner = r["owner"]
        params = infer_params(r["params_json"])
        accepts = infer_accepts(owner)
        returns = infer_returns(qual, owner, r["returns_text"])
        mutates = infer_mutates(params)
        is_stop = infer_is_stop(qual, returns)
        blocks.append(
            card_block(qual, profile="auto", accepts=accepts, params=params,
                       returns=returns, mutates=mutates, is_stop=is_stop)
        )

    out_path.write_text("".join(blocks), encoding="utf-8")
    print(f"Wrote {len(blocks)} cards → {out_path}")
    return out_path

# ---- CLI (minimal) ----
def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("library", help="Library name as scanned (e.g., pandas)")
    ap.add_argument("--db", default="data/db/api_index.db")
    ap.add_argument(
        "--outdir",
        default="data/cards/python/{library}",
        help="Override output dir (default data/cards/python/{library})"
    )
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()
    args.outdir = args.outdir.format(library=args.library)

    synth_cards(args.db, args.library, args.outdir, args.limit)

#usage: python -m codetutor.adapters.python.synth.synth_cards pandas --db data/db/api_index.db --limit 50

if __name__ == "__main__":
    main()

from __future__ import annotations
from typing import Set, Tuple
from codetutor.core.dsl.loader import IR

def build_compat(ir: IR) -> tuple[Set[tuple[int, int]], set[int]]:
    pairs: Set[tuple[int, int]] = set()
    stops: set[int] = set()

    for i, ci in enumerate(ir.cards):
        if bool(ci.post.get("is_valid_stop")):
            stops.add(i)

        for j, cj in enumerate(ir.cards):
            ret = str(ci.post.get("returns") or "")
            acc = str(cj.pre.get("accepts") or "")
            if not (ret and acc):  # must have types on both sides
                continue

            ok = (ret == acc)

            # Optional gates if present in your cards (no-ops if absent)
            # Axis compatibility: e.g., "rows"/"cols"
            out_axis = ci.post.get("produces_axis")
            req_axis = cj.pre.get("accepts_axis")
            if ok and (req_axis is not None and out_axis is not None):
                ok = (str(out_axis) == str(req_axis))

            # Dtype/domain compatibility
            out_dtype = ci.post.get("produces_dtype")
            req_dtype = cj.pre.get("accepts_dtype")
            if ok and (req_dtype is not None and out_dtype is not None):
                ok = (str(out_dtype) == str(req_dtype))

            if ok:
                pairs.add((i, j))

    return pairs, stops

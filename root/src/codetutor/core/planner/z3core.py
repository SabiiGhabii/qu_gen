from __future__ import annotations
from typing import Iterable, List, Sequence, Set, Tuple
from z3 import Solver, Int, Bool, Or, And, Distinct, Not, BoolVal, sat

# Pairs are 0-based indices into cards
def choose_plan(a1_idx: int,
                n_cards: int,
                compat_pairs: Set[Tuple[int,int]],
                stop_set: Set[int]) -> List[int] | None:
    s = Solver()
    x1, x2, x3 = Int("x1"), Int("x2"), Int("x3")
    use3 = Bool("use3")
    s.add(x1 == a1_idx, x2 >= 0, x2 < n_cards, x3 >= 0, x3 < n_cards)
    s.add(Distinct(x1, x2, x3))

    # A1 -> A2
    allowed_from_a1 = [j for (i,j) in compat_pairs if i == a1_idx]
    if not allowed_from_a1: return None
    s.add(Or([x2 == j for j in allowed_from_a1]))

    # (A2 -> A3) or stop(A2)
    allowed_any = Or([And(x2 == i, x3 == j) for (i,j) in compat_pairs]) if compat_pairs else BoolVal(False)
    stop2 = Or([x2 == k for k in stop_set]) if stop_set else BoolVal(False)
    stop3 = Or([x3 == k for k in stop_set]) if stop_set else BoolVal(False)
    s.add( Or( And(Not(use3), stop2),
               And(use3, allowed_any, stop3) ) )

    if s.check() != sat: return None
    m = s.model()
    return [m[x1].as_long(), m[x2].as_long()] if not m[use3] else [m[x1].as_long(), m[x2].as_long(), m[x3].as_long()]
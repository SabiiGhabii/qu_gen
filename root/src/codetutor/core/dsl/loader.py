from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from lark import Lark, Transformer, Token, Tree

GRAMMAR_PATH = Path(__file__).with_name("ctdsl.lark")

@dataclass
class Card:
    qualname: str
    profile: str
    pre: Dict[str, Any] = field(default_factory=dict)
    post: Dict[str, Any] = field(default_factory=dict)
    links: List[Tuple[str, Any]] = field(default_factory=list)  # (rel, target)

@dataclass
class IR:
    cards: List[Card]
    index: Dict[str, int]

class _ToPython(Transformer):
    def SIGNED_NUMBER(self, t: Token):
        s = str(t)
        return int(s) if s.lstrip("-").isdigit() else float(s)
    def ESCAPED_STRING(self, t: Token):
        return t[1:-1]
    def true(self, _):  return True
    def false(self, _): return False
    def tuple(self, items): return tuple(items)
    def list(self, items):  return list(items)

class _BuildIR(Transformer):
    def __init__(self):
        self.cards: List[Card] = []
        self._vp = _ToPython()

    def card(self, items):
        qual = items[0]; profile = items[1]
        c = Card(qualname=qual, profile=profile)
        for it in items[2:]:
            if isinstance(it, tuple) and len(it) == 3 and it[0] in ("pre","post"):
                ns, key, val = it
                (c.pre if ns=="pre" else c.post)[key] = val
            elif isinstance(it, tuple) and len(it) == 2:
                c.links.append(it)
        self.cards.append(c)

    def fact(self, items):
        ns = str(items[0]); key = str(items[1]); val = self._vp.transform(Tree("value", items[2:3]))
        return (ns, key, val)

    def modal_fact(self, items):
        # treat like a normal fact for now; modal semantics handled later
        _modal = str(items[0]); ns = str(items[1]); key = str(items[2]); val = self._vp.transform(Tree("value", items[3:4]))
        return (ns, key, val)

    def link(self, items):
        rel = str(items[0]); tgt = str(items[1])
        return (rel, tgt)

    def QUALNAME(self, t): return str(t)
    def CNAME(self, t):    return str(t)

def load_cards(path: str | Path) -> IR:
    text = Path(path).read_text(encoding="utf-8")
    parser = Lark.open(GRAMMAR_PATH.as_posix(), parser="lalr")
    tree = parser.parse(text)
    tx = _BuildIR(); tx.transform(tree)
    return IR(cards=tx.cards, index={c.qualname:i for i,c in enumerate(tx.cards)})

from __future__ import annotations
import json, argparse
from pathlib import Path
from typing import Dict, Any, Set
from codetutor.core.dsl.loader import load_cards, IR

# Optionally supply a trait pack with fixture hints:
# adapters/<language>/<library>/traits/<library>_pack.yaml (fixtures section)
try:
    import yaml  # optional; only used if a pack exists
except Exception:
    yaml = None

def collect_type_labels(ir: IR) -> Set[str]:
    labels: Set[str] = set()
    for c in ir.cards:
        a = c.pre.get("accepts"); r = c.post.get("returns")
        if isinstance(a, str) and a: labels.add(a)
        if isinstance(r, str) and r: labels.add(r)
    return labels

def load_pack(language: str, library: str) -> Dict[str, Any]:
    p = Path("src")/ "codetutor" / "adapters" / language / "traits" / f"{library}_pack.yaml"
    if p.exists() and yaml:
        try:
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}
    return {}

def materialize_fixtures(language: str, library: str, labels: Set[str], pack: Dict[str, Any]) -> Dict[str, Any]:
    fixtures_from_pack = (pack.get("fixtures") or {}) if isinstance(pack, dict) else {}
    out: Dict[str, Any] = {}
    for lbl in sorted(labels):
        if lbl in fixtures_from_pack:
            out[lbl] = fixtures_from_pack[lbl]
            continue
        # Generic, safe placeholder; user can enhance later or pack can provide specifics.
        out[lbl] = {
            "imports": [],                                     # none → universal realizer still works
            "setup": f"curr = None  # TODO: provide fixture for type '{lbl}'",
            "serializer": "repr"
        }
    return out

def write_fixtures(language: str, library: str, fixtures: Dict[str, Any]) -> Path:
    out_dir = Path("data") / "fixtures" / language / library
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "fixtures.json"
    out_path.write_text(json.dumps(fixtures, indent=2), encoding="utf-8")
    return out_path

def auto_fixtures(language: str, library: str, cards_path: str) -> Path:
    ir = load_cards(cards_path)
    labels = collect_type_labels(ir)
    pack = load_pack(language, library)
    fixtures = materialize_fixtures(language, library, labels, pack)
    return write_fixtures(language, library, fixtures)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("language")
    ap.add_argument("library")
    ap.add_argument("--cards", default=None, help="Path to cards.ctdsl")
    args = ap.parse_args()
    cards = args.cards or f"data/cards/{args.language}/{args.library}/cards.ctdsl"
    p = auto_fixtures(args.language, args.library, cards)
    print(f"Wrote {p}")

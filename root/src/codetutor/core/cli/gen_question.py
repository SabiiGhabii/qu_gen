from __future__ import annotations
import json, os, random, sys, time
from pathlib import Path
from typing import Dict, List, Optional

from codetutor.core.dsl.loader import load_cards, IR
from codetutor.core.planner.compat import build_compat
from codetutor.core.planner.z3core import choose_plan
from codetutor.core.generation.arg_sampler import sample_kwargs
from codetutor.core.generation.realize_universal import realize_program
from codetutor.core.generation.text import render_question
from codetutor.core.sandbox.runner import run_code
from codetutor.core.sandbox.inspectors import fingerprint

# ---------- core search ----------
def pick_start_indices(ir: IR) -> List[int]:
    starts = [i for i,c in enumerate(ir.cards) if str(c.pre.get("accepts")) in {"DataFrame","Series"}]
    return starts if starts else list(range(len(ir.cards)))

def try_one_plan(language: str, library: str, ir: IR,
                 plan: List[int],
                 arg_resamples: int,
                 env: Dict[str, object]) -> Optional[Dict]:
    # multiple arg resamples per plan
    for _ in range(max(1, arg_resamples)):
        kwarg_list = [sample_kwargs(ir.cards[i].pre.get("args") or [], env) for i in plan]
        try:
            code = realize_program(language, library, ir, plan, kwarg_list)
        except Exception:
            continue  # realization failed (e.g., missing fixture) → resample args/plan

        res = run_code(code, timeout=float(os.getenv("CT_TIMEOUT", "8.0")), allowed_imports=[library])
        if not res.ok:
            continue

        out_preview = "\n".join(res.stdout.splitlines()[:5])
        return {
            "apis": [ir.cards[i].qualname for i in plan],
            "kwargs": kwarg_list,
            "program": code,
            "stdout": res.stdout,
            "preview": out_preview,
        }
    return None

def generate_question_multi(library: str,
                            language: str = "python",
                            cards_path: Optional[str] = None,
                            max_plans: int = 200,
                            arg_resamples: int = 3) -> Dict:
    cards_path = cards_path or f"data/cards/{language}/{library}/cards.ctdsl"
    ir: IR = load_cards(cards_path)

    compat_pairs, stop_set = build_compat(ir)
    if not compat_pairs:
        raise SystemExit("No compatible pairs; regenerate cards with a higher limit or improve traits.")

    starts = pick_start_indices(ir)
    env = {"columns": ["A","B","C"]}  # generic sampler hint

    # Plan attempts; vary start node to diversify search
    for attempt in range(1, max_plans + 1):
        a1_idx = random.choice(starts)
        plan = choose_plan(a1_idx, len(ir.cards), compat_pairs, stop_set)
        if not plan:
            continue

        pack = try_one_plan(language, library, ir, plan, arg_resamples, env)
        if pack:
            # success → package as a question artifact
            fp = fingerprint(pack["stdout"])
            out_dir = Path("data") / "questions" / language / library
            out_dir.mkdir(parents=True, exist_ok=True)

            # Minimal QG (template; FLAN optional if installed)
            qg = render_question(
                apis=pack["apis"],
                output_preview=pack["preview"],
                inputs_hint=None,
                requirements=[]
            )
            doc = {
                "library": library,
                "apis": pack["apis"],
                "kwargs": pack["kwargs"],
                "program": pack["program"],
                "output_preview": pack["preview"],
                "fingerprint": fp,
                "question_text": qg["question_text"],
                "created_at": int(time.time()),
                "attempt": attempt,
            }
            (out_dir / f"q_{fp}.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
            return doc

    raise SystemExit(f"Failed to produce a valid snippet after {max_plans} plan attempts "
                     f"× {arg_resamples} arg resamples per plan.")

# ---------- tiny CLI (keep args minimal) ----------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m codetutor.core.cli.gen_question <library> [<max_plans> [<arg_resamples>]]")
        sys.exit(2)
    lib = sys.argv[1]
    max_plans = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.getenv("CT_MAX_PLANS", "200"))
    arg_resamples = int(sys.argv[3]) if len(sys.argv) > 3 else int(os.getenv("CT_ARG_RESAMPLES", "3"))
    q = generate_question_multi(lib, "python", None, max_plans=max_plans, arg_resamples=arg_resamples)
    print(json.dumps(q, indent=2))

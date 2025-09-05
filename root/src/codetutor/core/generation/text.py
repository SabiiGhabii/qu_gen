from __future__ import annotations
import importlib
from typing import Dict, List, Optional

def _template_question(apis: List[str], output_preview: str, requirements: List[str], inputs_hint: str|None=None) -> str:
    req = ("; ".join(requirements)) if requirements else "Follow the API requirements exactly."
    apis_txt = ", ".join(apis)
    inputs_line = f" Inputs: {inputs_hint}." if inputs_hint else ""
    return (f"Use exactly these APIs: {apis_txt} to produce an output matching the preview below."
            f"{inputs_line} Requirements: {req} Output preview:\n{output_preview.strip()[:800]}")

def _try_load_flan(model_name: str):
    try:
        transformers = importlib.import_module("transformers")
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        tok = AutoTokenizer.from_pretrained(model_name)
        mdl = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        return tok, mdl
    except Exception:
        return None, None

def _paraphrase_with_flan(prompt: str, model_name: str = "google/flan-t5-small", max_new_tokens: int = 96) -> Optional[str]:
    tok, mdl = _try_load_flan(model_name)
    if not tok or not mdl:
        return None
    inputs = tok(prompt, return_tensors="pt")
    out = mdl.generate(**inputs, max_new_tokens=max_new_tokens, num_beams=1)
    text = tok.decode(out[0], skip_special_tokens=True)
    return text

def render_question(apis: List[str],
                    output_preview: str,
                    inputs_hint: str|None = None,
                    requirements: Optional[List[str]] = None,
                    model_name: Optional[str] = None) -> Dict:
    base = _template_question(apis, output_preview, requirements or [], inputs_hint)
    if model_name:
        paraphrased = _paraphrase_with_flan(
            f"Rewrite as a concise coding exercise without revealing solution code:\n{base}",
            model_name=model_name
        )
        text = paraphrased or base
    else:
        text = base
    return {"question_text": text, "requirements": requirements or []}

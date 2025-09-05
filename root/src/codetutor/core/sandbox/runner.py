from __future__ import annotations
import os, subprocess, sys, textwrap
from dataclasses import dataclass
from typing import Iterable, Optional

@dataclass
class SandboxResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool

def _import_guard_prelude(allowed: Iterable[str]) -> str:
    base = {m.split('.')[0] for m in allowed}
    base |= {"builtins"}  # always allowed
    # Lightweight import guard; no effect if allowed is empty.
    return textwrap.dedent(f"""
    import sys
    class _Guard:
        def find_spec(self, fullname, path=None, target=None):
            base = fullname.split('.')[0]
            if base in {sorted(base)!r}:
                return None
            raise ImportError(f"Module {{fullname}} not allowed in sandbox")
    if {bool(base)!r}:
        sys.meta_path.insert(0, _Guard())
    """)

def run_code(code: str,
             timeout: float = 6.0,
             allowed_imports: Optional[Iterable[str]] = None) -> SandboxResult:
    prelude = _import_guard_prelude(allowed_imports or [])
    payload = prelude + "\n" + code
    env = os.environ.copy()
    env.setdefault("PYTHONHASHSEED", "0")  # determinism
    try:
        p = subprocess.run(
            [sys.executable, "-c", payload],
            capture_output=True, text=True, timeout=timeout, env=env
        )
        ok = (p.returncode == 0 and bool(p.stdout.strip()))
        return SandboxResult(ok=ok, returncode=p.returncode, stdout=p.stdout, stderr=p.stderr, timed_out=False)
    except subprocess.TimeoutExpired as e:
        return SandboxResult(ok=False, returncode=-1, stdout=e.stdout or "", stderr=(e.stderr or "") + "\nTIMEOUT", timed_out=True)

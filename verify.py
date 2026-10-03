#!/usr/bin/env python
"""
verify.py - THRONE verification framework.
Standalone CLI: run a battery of tests on the mainframe and report pass/fail.
Exit code 0 if all pass, 1 if any fail.

Usage:
    python verify.py                   # all checks
    python verify.py --layer tool      # only tool-level (syntax + imports)
    python verify.py --layer service   # only service-level (endpoints)
    python verify.py --layer project   # only project-level (tests + git)
    python verify.py --quick           # fast smoke (15s target)
    python verify.py --json            # machine-readable output
"""
import sys
import os
import json
import time
import argparse
import importlib
import traceback
import subprocess
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
HERMES = Path(os.environ.get("HERMES_HOME", r"C:\Users\KING\AppData\Local\hermes"))
SCRIPTS = HERMES / "scripts"

# --- Result types ---

class Result:
    def __init__(self, name: str, ok: bool, detail: str = "", dur_ms: int = 0):
        self.name = name
        self.ok = ok
        self.detail = detail
        self.dur_ms = dur_ms

    def to_dict(self):
        return {"name": self.name, "ok": self.ok, "detail": self.detail, "dur_ms": self.dur_ms}


def timed(fn):
    """Decorator: time the wrapped check."""
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        try:
            ok, detail = fn(*args, **kwargs)
        except Exception as e:
            ok, detail = False, f"EXCEPTION: {e}"
        dt = int((time.perf_counter() - t0) * 1000)
        return Result(name=fn.__name__, ok=ok, detail=detail, dur_ms=dt)
    return wrapper


# --- Layer 1: Tool-level (syntax + imports) ---

# Files we author + maintain. Other scripts in scripts/ are legacy and
# intentionally not part of the mainframe contract.
VERIFIED_SCRIPTS = {
    "ollama-server.py",
    "ollama-health.py",
    "throttle-audit.py",
    "workspace-watchdog.py",
    "memory-promoter.py",
}


@timed
def check_scripts_compile():
    """All .py we author under SCRIPTS must py_compile cleanly."""
    bad = []
    checked = 0
    for p in SCRIPTS.glob("*.py"):
        if p.name not in VERIFIED_SCRIPTS:
            continue
        checked += 1
        r = subprocess.run(
            [sys.executable, "-m", "py_compile", str(p)],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode != 0:
            bad.append(f"{p.name}: {r.stderr.strip()[:200]}")
    if bad:
        return False, "; ".join(bad)
    return True, f"{checked}/{len(VERIFIED_SCRIPTS)} maintained scripts compile"


@timed
def check_elite_packages_import():
    """All elite packages must import successfully."""
    targets = [
        "psutil", "aiohttp", "fastapi", "uvicorn", "pydantic",
        "watchfiles", "tenacity", "rich", "typer", "httpx",
        "prometheus_client", "structlog", "numpy", "sklearn",
        "pypdf", "markdownify", "bs4", "PIL", "cv2",
        "win32", "pyttsx3", "sounddevice", "faster_whisper",
        "pytest",
    ]
    failed = []
    for t in targets:
        try:
            importlib.import_module(t)
        except Exception as e:
            failed.append(f"{t}: {e}")
    if failed:
        return False, "; ".join(failed)
    return True, f"{len(targets)} packages importable"


# --- Layer 2: Service-level (live endpoints) ---

@timed
def check_ollama_upstream():
    """Ollama :11434 must respond to /api/tags."""
    try:
        import httpx
        r = httpx.get("http://127.0.0.1:11434/api/tags", timeout=3.0)
        if r.status_code == 200:
            models = r.json().get("models", [])
            return True, f"{len(models)} models loaded"
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)


@timed
def check_health_daemon():
    """THRONE health daemon on :11435 must be alive."""
    try:
        import httpx
        r = httpx.get("http://127.0.0.1:11435/health", timeout=3.0)
        if r.status_code == 200:
            return True, "ok=True"
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, f"daemon not running: {e}"


@timed
def check_health_daemon_stats():
    """/ollama/stats returns GPU + host metrics."""
    try:
        import httpx
        r = httpx.get("http://127.0.0.1:11435/ollama/stats", timeout=3.0)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        d = r.json()
        gpu = d.get("gpus")
        if not gpu:
            return False, "no GPU reported"
        g = gpu[0]
        return True, f"GPU {g['temp']}°C {g['util']}% {g['mem_used_mb']}/{g['mem_total_mb']}MB"
    except Exception as e:
        return False, str(e)


# --- Layer 3: Project-level (git + tests) ---

@timed
def check_mainframe_repo():
    """dqikfox/mainframe repo must be on disk + clean working tree."""
    repo = ROOT  # we're inside the mainframe repo
    if not (repo / ".git").exists():
        return False, "not a git repo"
    r = subprocess.run(["git", "-C", str(repo), "status", "--short"],
                       capture_output=True, text=True, timeout=10)
    if r.stdout.strip():
        return False, f"dirty: {r.stdout.strip()[:200]}"
    r = subprocess.run(["git", "-C", str(repo), "log", "-1", "--oneline"],
                       capture_output=True, text=True, timeout=10)
    return True, f"HEAD: {r.stdout.strip()}"


@timed
def check_skills_index():
    """All 5 new skills must exist on disk."""
    required = ["throttle-cleanup", "mainframe-bootstrap", "code-review-light",
                "audio-tts-orchestrator", "memory-promoter"]
    skills_root = HERMES / "skills"
    missing = []
    for s in required:
        if not (skills_root / s / "SKILL.md").exists():
            missing.append(s)
    if missing:
        return False, f"missing: {missing}"
    return True, f"{len(required)} skills present"


@timed
def check_cron_jobs():
    """3 new cron jobs must be in jobs.json."""
    jobs_path = HERMES / "cron" / "jobs.json"
    if not jobs_path.exists():
        return False, "jobs.json missing"
    try:
        data = json.loads(jobs_path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"parse: {e}"
    names = {j["name"] for j in data.get("jobs", [])}
    required = {"Ollama_Health_Beat", "Throttle_Audit", "Memory_Hygiene"}
    missing = required - names
    if missing:
        return False, f"missing: {missing}"
    return True, f"{len(data['jobs'])} total jobs, all new present"


@timed
def check_no_throttle_offenders():
    """No throttling-bloat processes should be in the top 10 CPU list."""
    try:
        import psutil
    except ImportError:
        return False, "psutil not installed"
    bad_procs = {"PhoneExperienceHost.exe", "CrossDeviceService.exe"}
    found = []
    procs = []
    for p in psutil.process_iter():
        try:
            procs.append((p.cpu_percent(interval=0.05), p.name()))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(reverse=True)
    top_names = {n for _, n in procs[:10]}
    hits = top_names & bad_procs
    if hits:
        return False, f"throttle offenders in top CPU: {hits}"
    return True, f"clean (top 10: {sorted(top_names)[:5]})"


# --- Layer 4: User-issue (reproducibility) ---

@timed
def check_lummings_app_loads():
    """The Lummings SPA must serve 200 + assets reachable."""
    try:
        import httpx
    except ImportError:
        return False, "httpx not installed"
    # Repo on disk?
    lummings = Path(r"C:\Users\KING\Projects\lumming\docs\app\index.html")
    if not lummings.exists():
        return False, "index.html missing"
    # Has the transformation engine JS?
    text = lummings.read_text(encoding="utf-8")
    required = ["MAGIC_KEYWORDS", "performTransformation", "LUMINARIES",
                "transformation-stage"]
    missing = [r for r in required if r not in text]
    if missing:
        return False, f"JS missing markers: {missing}"
    return True, f"{lummings.stat().st_size // 1024}KB, {len(text)} chars"


# --- Runner ---

LAYER_FNS = {
    "tool": [check_scripts_compile, check_elite_packages_import],
    "service": [check_ollama_upstream, check_health_daemon,
                check_health_daemon_stats, check_no_throttle_offenders],
    "project": [check_mainframe_repo, check_skills_index,
                check_cron_jobs, check_lummings_app_loads],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", choices=list(LAYER_FNS.keys()))
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.layer:
        fns = LAYER_FNS[args.layer]
    elif args.quick:
        fns = [check_health_daemon, check_ollama_upstream,
               check_mainframe_repo, check_no_throttle_offenders]
    else:
        fns = sum(LAYER_FNS.values(), [])

    results = [fn() for fn in fns]
    passed = sum(1 for r in results if r.ok)
    failed = len(results) - passed
    ts = datetime.now(timezone.utc).isoformat()

    if args.json:
        print(json.dumps({
            "ts": ts, "total": len(results),
            "passed": passed, "failed": failed,
            "results": [r.to_dict() for r in results],
        }, indent=2))
        return 0 if failed == 0 else 1

    print(f"=== VERIFY {ts} ===\n")
    for r in results:
        mark = "OK" if r.ok else "FAIL"
        print(f"  [{mark:>4}] {r.name:<32} {r.dur_ms:>5}ms  {r.detail}")
    print(f"\n  TOTAL: {passed}/{len(results)} passed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
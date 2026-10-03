"""
post-edit-verify.py - Run after every code edit.
Exits 0 if all tests pass, non-zero otherwise. Designed to be invoked by
cron, by hand, or as a hook in the agent skill loop.

Behavior:
    - Runs pytest on tests/ if --pytest
    - Runs verify.py --quick if --verify
    - Runs both if no flag (default)
    - Logs to C:/Users/KING/AppData/Local/hermes/audit/post-edit.log
    - On failure, prints the failing test/check + suggested fix

Usage:
    python post-edit-verify.py
    python post-edit-verify.py --pytest
    python post-edit-verify.py --verify
    python post-edit-verify.py --json
"""
import sys
import os
import json
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
LOG = Path(r"C:\Users\KING\AppData\Local\hermes\audit\post-edit.log")
LOG.parent.mkdir(parents=True, exist_ok=True)


def log(line: str) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    out = f"{ts} {line}"
    print(out)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(out + "\n")


def run_pytest() -> tuple[bool, str]:
    t0 = time.perf_counter()
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--tb=short", "-q"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
    )
    dt = time.perf_counter() - t0
    ok = r.returncode == 0
    summary = f"pytest exit={r.returncode} dt={dt:.1f}s"
    if not ok:
        summary += f"\n--- stderr ---\n{r.stderr[:500]}\n--- stdout tail ---\n{r.stdout[-500:]}"
    return ok, summary


def run_verify() -> tuple[bool, str]:
    t0 = time.perf_counter()
    r = subprocess.run(
        [sys.executable, "verify.py", "--quick"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=120,
    )
    dt = time.perf_counter() - t0
    ok = r.returncode == 0
    summary = f"verify exit={r.returncode} dt={dt:.1f}s"
    if not ok:
        # extract just the FAIL lines
        tail = "\n".join([
            l for l in r.stdout.splitlines() if "FAIL" in l or "TOTAL" in l
        ])
        summary += f"\n{tail}"
    return ok, summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pytest", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    do_pytest = args.pytest or (not args.pytest and not args.verify)
    do_verify = args.verify or (not args.pytest and not args.verify)

    report = {"ts": datetime.now().isoformat(), "checks": {}}
    overall_ok = True

    if do_pytest:
        log("running pytest...")
        ok, detail = run_pytest()
        report["checks"]["pytest"] = {"ok": ok, "detail": detail[:1000]}
        overall_ok = overall_ok and ok

    if do_verify:
        log("running verify.py --quick...")
        ok, detail = run_verify()
        report["checks"]["verify"] = {"ok": ok, "detail": detail[:1000]}
        overall_ok = overall_ok and ok

    report["overall_ok"] = overall_ok

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        if overall_ok:
            log("ALL CHECKS PASSED")
        else:
            log(f"FAIL — {[(k, v['ok']) for k, v in report['checks'].items()]}")

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
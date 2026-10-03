"""
tests/test_mainframe.py - pytest suite for the mainframe.
Covers Layer 1-4 verification.

Run:
    pytest tests/test_mainframe.py -v
    pytest tests/test_mainframe.py -v --tb=short
"""
import os
import sys
import time
import json
import subprocess
from pathlib import Path

import pytest

MAINFRAME_ROOT = Path(__file__).resolve().parent.parent
HERMES = Path(os.environ.get("HERMES_HOME",
                              r"C:\Users\KING\AppData\Local\hermes"))
SCRIPTS = HERMES / "scripts"

# Add verify.py to path so we can import its helpers
sys.path.insert(0, str(MAINFRAME_ROOT))


# --- Layer 1: tool ---

@pytest.mark.layer_tool
def test_maintained_scripts_compile():
    """All 5 scripts the mainframe owns must compile."""
    maintained = {
        "ollama-server.py", "ollama-health.py",
        "throttle-audit.py", "workspace-watchdog.py",
        "memory-promoter.py",
    }
    failures = []
    for name in maintained:
        p = SCRIPTS / name
        if not p.exists():
            failures.append(f"{name}: not found")
            continue
        r = subprocess.run(
            [sys.executable, "-m", "py_compile", str(p)],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            failures.append(f"{name}: {r.stderr.strip()[:100]}")
    assert not failures, f"compile failures: {failures}"


@pytest.mark.layer_tool
def test_elite_packages_importable():
    """The 24-package elite baseline must all import."""
    targets = [
        "psutil", "aiohttp", "fastapi", "uvicorn", "pydantic",
        "watchfiles", "tenacity", "rich", "typer", "httpx",
        "prometheus_client", "structlog", "numpy", "sklearn",
        "pypdf", "markdownify", "bs4", "PIL", "cv2",
        "win32", "pyttsx3", "sounddevice", "faster_whisper",
        "pytest",
    ]
    failures = []
    for t in targets:
        try:
            __import__(t)
        except Exception as e:
            failures.append((t, str(e)[:80]))
    assert not failures, f"import failures: {failures}"


@pytest.mark.layer_tool
def test_verify_py_imports():
    """verify.py must be importable (no syntax errors at module level)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("verify", MAINFRAME_ROOT / "verify.py")
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "main")
    assert hasattr(mod, "Result")
    assert hasattr(mod, "LAYER_FNS")


# --- Layer 2: service ---

@pytest.mark.layer_service
def test_ollama_upstream_reachable():
    import httpx
    r = httpx.get("http://127.0.0.1:11434/api/tags", timeout=3.0)
    assert r.status_code == 200, f"Ollama HTTP {r.status_code}"
    data = r.json()
    assert "models" in data


@pytest.mark.layer_service
def test_health_daemon_alive():
    """If the health daemon is down, try to skip with xfail or fail loud."""
    import httpx
    try:
        r = httpx.get("http://127.0.0.1:11435/health", timeout=3.0)
    except httpx.ConnectError:
        pytest.skip("health daemon not running on :11435 - expected to be started by start.cmd")
    assert r.status_code == 200
    assert r.json().get("ok") is True


@pytest.mark.layer_service
@pytest.mark.skipif(not Path(r"C:\Program Files\NVIDIA Corporation").exists(),
                    reason="no NVIDIA drivers")
def test_health_daemon_reports_gpu():
    import httpx
    try:
        r = httpx.get("http://127.0.0.1:11435/ollama/stats", timeout=3.0)
    except httpx.ConnectError:
        pytest.skip("health daemon not running")
    if r.status_code != 200:
        pytest.skip(f"health daemon returned {r.status_code}")
    d = r.json()
    assert d.get("gpus"), "expected at least one GPU"
    g = d["gpus"][0]
    assert 0 <= g["temp"] <= 110, f"GPU temp out of range: {g['temp']}"
    assert 0 <= g["util"] <= 100, f"GPU util out of range: {g['util']}"


# --- Layer 3: project ---

@pytest.mark.layer_project
def test_mainframe_repo_clean():
    repo = MAINFRAME_ROOT
    if not (repo / ".git").exists():
        pytest.skip("not in a git repo")
    r = subprocess.run(
        ["git", "-C", str(repo), "status", "--short"],
        capture_output=True, text=True, timeout=10,
    )
    assert not r.stdout.strip(), f"dirty tree: {r.stdout.strip()}"


@pytest.mark.layer_project
def test_all_skills_have_skill_md():
    required = ["throttle-cleanup", "mainframe-bootstrap", "code-review-light",
                "audio-tts-orchestrator", "memory-promoter"]
    skills_root = HERMES / "skills"
    missing = [s for s in required if not (skills_root / s / "SKILL.md").exists()]
    assert not missing, f"missing skills: {missing}"


@pytest.mark.layer_project
def test_cron_jobs_present():
    jobs_path = HERMES / "cron" / "jobs.json"
    if not jobs_path.exists():
        pytest.skip("jobs.json missing")
    data = json.loads(jobs_path.read_text(encoding="utf-8"))
    names = {j["name"] for j in data.get("jobs", [])}
    required = {"Ollama_Health_Beat", "Throttle_Audit", "Memory_Hygiene"}
    missing = required - names
    assert not missing, f"missing cron jobs: {missing}"


@pytest.mark.layer_project
def test_no_throttle_bloat_running():
    """PhoneExperienceHost / CrossDeviceService must not be running."""
    import psutil
    bad = {"PhoneExperienceHost.exe", "CrossDeviceService.exe"}
    found = set()
    for p in psutil.process_iter():
        try:
            if p.name() in bad:
                found.add(p.name())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    assert not found, f"throttling bloat active: {found}"


# --- Layer 4: user-issue reproducer ---

@pytest.mark.layer_user
def test_lummings_spa_serves_correctly():
    """The Lummings SPA must exist with all transformation engine hooks."""
    path = Path(r"C:\Users\KING\Projects\lumming\docs\app\index.html")
    if not path.exists():
        pytest.skip("Lummings SPA not built")
    text = path.read_text(encoding="utf-8")
    # Required JavaScript hooks for the transformation feature
    required_markers = [
        "MAGIC_KEYWORDS",
        "performTransformation",
        "LUMINARIES",
        "transformation-stage",
        "openChat",
        "startSceneryMode",
    ]
    missing = [m for m in required_markers if m not in text]
    assert not missing, f"SPA missing hooks: {missing}"
    # Must reference asset paths
    assert "/assets/portraits/" in text, "SPA does not reference portraits path"


@pytest.mark.layer_user
def test_lummings_spa_reachable_via_local_server():
    """Spin up a quick http.server in a thread and confirm /app/ serves 200."""
    import http.server
    import socketserver
    import threading
    import httpx
    docs = Path(r"C:\Users\KING\Projects\lumming\docs")
    if not (docs / "app" / "index.html").exists():
        pytest.skip("Lummings SPA not built")

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(docs), **kw)
        def log_message(self, *a, **kw):
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        r = httpx.get(f"http://127.0.0.1:{port}/app/", timeout=3.0)
        assert r.status_code == 200, f"HTTP {r.status_code}"
        assert "Lummings" in r.text or "LUMO" in r.text, "expected Lummings brand in body"
    finally:
        httpd.shutdown()


@pytest.mark.layer_user
def test_chronological_repro():
    """Reproduce the original bug report: 'nothing was throttling' was wrong.
    Verify the throttle fix worked by confirming the bad processes are dead.
    """
    import psutil
    bad = {"PhoneExperienceHost.exe", "CrossDeviceService.exe"}
    victims = []
    for p in psutil.process_iter():
        try:
            if p.name() in bad:
                victims.append(p.name())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    assert not victims, (
        f"REGRESSION: throttling bloat is back: {victims}. "
        "Run throttle-audit.py --kill-safe"
    )
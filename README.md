# THRONE Mainframe (elite agent toolkit)

Scripts under `scripts/` provide production tooling for the THRONE host.

## Layout

```
scripts/
  ollama-server.py       FastAPI daemon :11435, proxies :11434 + host stats
  ollama-health.py       Cron-friendly Ollama probe (exit 0/1/2)
  throttle-audit.py      Process audit + safe-kill whitelist
  workspace-watchdog.py  File watcher for C:/Users/KING/Projects/
  memory-promoter.py     Stale-entry scanner for USER.md / MEMORY.md
```

## Skills

- `throttle-cleanup` — diagnose + kill Windows throttling processes
- `mainframe-bootstrap` — install baseline + lay down scripts/
- `code-review-light` — pre-commit secrets/syntax/tests
- `audio-tts-orchestrator` — Edge/OpenAI/ElevenLabs/pyttsx3 fallback
- `memory-promoter` — promote stable, demote dated, delete stale

## Cron jobs

| Name | Schedule | Script |
|---|---|---|
| Ollama_Health_Beat | every 5m | ollama-health.py |
| Throttle_Audit | every 15m | throttle-audit.py |
| Memory_Hygiene | daily | memory-promoter.py |

## Endpoints

- `http://127.0.0.1:11434` — Ollama (upstream)
- `http://127.0.0.1:11435/health` — Health daemon
- `http://127.0.0.1:11435/ollama/tags` — model list proxy
- `http://127.0.0.1:11435/ollama/stats` — host metrics incl. GPU

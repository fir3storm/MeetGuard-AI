# Changelog

## v0.2.0 (2026-06-21)

### Added
- **CLI** — `meetguard` command with 11 options: `--config`, `--dry-run`, `--headless`,
  `--setup-audio`, `--list-audio-devices`, `--enroll`, `--verbose`, `--version`
- **Config validation** — 8 checks at startup (weight sums, thresholds, FPS, sample rate, model paths)
- **Signal handling** — graceful `SIGINT`/`SIGTERM` shutdown
- **Session lifecycle** — proper `create_session`/`end_session` with SQLite tracking
- **Audio setup wizard** — `meetguard --setup-audio` detects loopback devices, tests recording
- **Webhook alerts** — Slack, Discord, and Email backends
- **LLM fallback** — local Ollama (or HuggingFace) disambiguates borderline NLP scores
- **REST API** — `GET /status`, `/risk`, `/alerts`, `/sessions`, `/voiceprints`, `/start`, `/stop`
- **Dashboard auto-refresh** — Gradio updates every 2 seconds (no manual refresh)
- **Pipeline backpressure** — frame dropping with warnings when buffer is full
- **Voiceprint encryption** — Fernet AES encryption for biometric data at rest
- **`pyproject.toml`** — full metadata, entry points, optional extras, tool config
- **CI pipeline** — GitHub Actions (ruff + black + mypy + pytest)
- **Comprehensive tests** — 15 test files covering config, detectors, fusion, capture, webhooks

### Changed
- `config/default.yaml` — documented every setting with inline comments; added webhooks + LLM sections
- `main.py` — full rewrite with CLI dispatch, signal handlers, session lifecycle, WebSocket wiring
- `gradio_app.py` — auto-polling via `every=2.0` instead of manual refresh button
- `frame_buffer.py` — added `push_with_backpressure()`, `fill_ratio` property
- `voiceprint_db.py` — encryption layer, key auto-generation

### Fixed
- `DashboardServer` (FastAPI+WebSocket) was imported but never started — now wired into engine
- Sessions table stayed empty — `create_session()`/`end_session()` added
- No graceful shutdown on Ctrl+C — signal handlers registered
- Missing config validation — `validate_config()` runs at startup

## v0.1.0 (2026-06-21)

### Added
- Initial pipeline: capture → process → detect → fuse → alert
- 5 detectors: deepfake face (3DCNN), voice mismatch (ECAPA-TDNN), lip-sync (SyncNet),
  suspicious NLP (regex + Sentence-BERT), urgency language
- Screen capture (MSS, 5 FPS), audio loopback (sounddevice, 16kHz)
- Fusion engine with weighted risk scoring
- Desktop notifications (plyer), sound alerts, meeting clip recording
- Gradio dashboard (manual refresh)
- SQLite storage for voiceprints and session logs
- Voiceprint enrollment CLI
- Ring buffer with thread safety

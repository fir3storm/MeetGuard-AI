# Changelog

## v0.3.0 (2026-06-21)

**Branding:** MeetGuard AI by Abhirup Guha — Info Security Solution

### Added
- **Speaker diarization** — `AudioSplitter` wired into pipeline: isolates speakers before voice
  comparison, per-speaker scoring. Enabled via `diarization.enabled: true` in config.
  Graceful fallback if pyannote-audio not installed.
- **CLI subcommands** — `meetguard status` (engine PID + session summary),
  `meetguard alerts` (alert history with `--json`), `meetguard report` (structured session
  report with alert timeline). All offline — read SQLite directly.
- **Performance metrics tab** — collapsible accordion in Gradio dashboard showing actual
  FPS, frame buffer %, audio buffer %, mean tick time, uptime, pipeline ticks.
- **Configuration profiles** — `--profile high-security` (15 FPS, tight thresholds 0.10/0.30/0.60,
  enables LLM + diarization), `--profile balanced` (defaults),
  `--profile low-resource` (3 FPS, disables lip-sync, higher thresholds, 120s cooldown).
- **`measured_fps` property** on screen capture — tracks actual frame rate from timestamps.
- **PID file** at `~/.meetguard/engine.pid` for `meetguard status` detection.
- **Assets** — SVG logo and branding materials.
- **34 new tests** — CLI commands, profiles, diarization config, screen FPS.
  Total: 53 passing tests.

### Changed
- `config/default.yaml` — added `diarization` section with `enabled` and `hf_token`.
- `meetguard/config.py` — `load()` accepts `profile` parameter, imports `meetguard.profiles`.
- `meetguard/main.py` — diarization init + tick logic, CLI subparsers, perf metrics
  collection and push to dashboard, `--profile` flag, PID file management.
- `meetguard/ui/gradio_app.py` — `update_perf()`, `_get_perf_data()`, collapsible accordion
  with auto-refreshing performance metrics.
- `meetguard/capture/screen_capture.py` — `measured_fps` property with rolling frame times.
- `meetguard/profiles.py` — **moved** from `meetguard/config/profiles.py` to fix import shadowing.
- `pyproject.toml` — added author (`Abhirup Guha`) and maintainer (`Info Security Solution`).

### Fixed
- `AudioSplitter` was dead code — instantiated but never called. Now wired into pipeline.
- Config fixture in tests — `diarization` key was nested under `capture` instead of top-level.

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

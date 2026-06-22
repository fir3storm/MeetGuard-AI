<p align="center">
  <img src="https://img.shields.io/badge/version-0.2.0-blue" alt="Version">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/status-alpha-yellow" alt="Status">
</p>

# 🛡️ MeetGuard AI

**Real-time deepfake and social engineering detection for video meetings.**

MeetGuard AI is a live security assistant that monitors Zoom, Microsoft Teams, and Google Meet calls. It captures the meeting's audio and video (via screen capture + audio loopback) and runs five parallel detectors every 3 seconds, flagging executive impersonation attempts in real time.

---

## What it detects

| Threat | Detector | What it catches |
|---|---|---|
| **Synthetic faces** | Deepfake Face (3DCNN) | Frame-by-frame deepfake generation — e.g. a real-time face swap of the CEO |
| **Voice impersonation** | Voice Mismatch (ECAPA-TDNN) | Speaker doesn't match enrolled voiceprints — e.g. an impostor using a different voice |
| **Desynced audio/video** | Lip-Sync (SyncNet) | Audio doesn't match lip movements — common in low-quality deepfakes |
| **Fraud instructions** | Suspicious NLP (regex + Sentence-BERT) | "Change the vendor account to this new routing number" |
| **Pressure tactics** | Urgency Language (weighted keywords) | "Transfer now — don't tell anyone — this is confidential" |

### Use cases

- **CFO fraud** — impersonator posing as the CEO requests an urgent wire transfer
- **Vendor payment redirection** — fake vendor asks to update payment details
- **Executive whaling** — socially engineered pressure to bypass approval processes

---

## Quick start

### 1. Audio loopback (required once)

MeetGuard captures the **speaker output** (what you hear), not your microphone. You need a virtual audio device:

| OS | Tool | Setup |
|---|---|---|
| **Windows** | [VB-Cable](https://vb-audio.com/Cable/) | Install → set "CABLE Input" as your meeting app's speaker output |
| **macOS** | [BlackHole](https://github.com/ExistentialAudio/BlackHole) | `brew install blackhole-2ch` → create Multi-Output Device in Audio MIDI Setup |
| **Linux** | PulseAudio monitor | `pactl load-module module-loopback` |

Run the setup wizard to verify:
```bash
meetguard --setup-audio
```

### 2. Install

```bash
pip install -r requirements/base.txt
```

Optional: GPU support for faster inference:
```bash
pip install -r requirements/gpu.txt
```

### 3. Download models

```bash
python scripts/download_models.py
```

### 4. Enrol an executive's voiceprint

Record a ~30 second sample of the executive speaking normally:

```bash
# From a WAV file
meetguard --enroll CEO ceo_voice.wav

# Using the interactive CLI
python scripts/enroll_executive.py --name "CFO" --record 30
```

Repeat for each person you want to protect (CEO, CFO, etc.).

### 5. Run

```bash
# Start your meeting, then:
meetguard
```

The dashboard opens at **http://127.0.0.1:7860**. On critical detections, you get a desktop notification, an audible alert, and a 30-second video/audio clip saved to `~/.meetguard/sessions/`.

---

## CLI reference

```bash
meetguard [options]

Options:
  -c, --config FILE        Path to YAML config file
  -v, --verbose            Debug logging level
  --dry-run                Validate config + check dependencies, then exit
  --headless               Run without Gradio dashboard
  --setup-audio            Interactive audio loopback setup wizard
  --list-audio-devices     List available audio input devices
  --enroll NAME FILE       Enrol a voiceprint from a WAV file
  --version                Print version and exit
```

### Example: validate before running

```bash
meetguard --dry-run -c my-config.yaml
```

### Example: run headless (no GUI)

```bash
meetguard --headless
```

### Example: list audio devices

```bash
meetguard --list-audio-devices
```

---

## Configuration

All thresholds and weights are in `config/default.yaml`:

```yaml
fusion:
  weights:
    face: 0.30    # 30% weight in total risk score
    voice: 0.25
    lip: 0.15
    nlp: 0.20
    urgency: 0.10
  thresholds:
    monitor: 0.20
    suspicious: 0.45
    critical: 0.75    # ≥ 0.75 triggers desktop alert + clip + webhooks
```

Webhook integration (Slack / Discord / Email):

```yaml
alerting:
  webhooks:
    slack_url: "https://hooks.slack.com/services/..."
    discord_url: "https://discord.com/api/webhooks/..."
    email:
      smtp_host: "smtp.gmail.com"
      from_addr: "meetguard@example.com"
      to_addrs: ["security@example.com"]
```

---

## How it works

```
Every 200ms:  screen grab (5 FPS) + audio loopback (16kHz)
                 │
                 ▼  Every 3 seconds
         ┌─────────────────┐
         │   5 Detectors   │
         │  • Face (3DCNN) │──→ deepfake score
         │  • Voice (ECAPA)│──→ mismatch score
         │  • Lip (SyncNet)│──→ drift score
         │  • NLP (BERT)   │──→ suspicious score
         │  • Urgency (RE) │──→ pressure score
         └────────┬────────┘
                  ▼
         ┌─────────────────┐
         │   Fusion Engine │──→ total_risk (weighted sum)
         │   Classifier    │──→ SAFE / MONITOR / SUSPICIOUS / CRITICAL
         └────────┬────────┘
                  ▼
         ┌─────────────────┐
         │     Alerting    │
         │  • Desktop popup│
         │  • Sound alert  │
         │  • Save 30s clip│
         │  • Webhooks     │
         │  • SQLite log   │
         └─────────────────┘
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for a detailed data flow diagram.

---

## API

When running, MeetGuard serves a REST API on port 8573:

```bash
curl http://127.0.0.1:8573/api/v1/status
curl http://127.0.0.1:8573/api/v1/status/risk
curl http://127.0.0.1:8573/api/v1/alerts?limit=10
curl http://127.0.0.1:8573/api/v1/sessions
curl http://127.0.0.1:8573/api/v1/voiceprints
```

WebSocket at `ws://127.0.0.1:8573/ws` streams real-time updates.

---

## Project structure

```
meetguard/
├── capture/          # Screen + audio capture, ring buffers
├── processing/       # Face extraction, voiceprint, transcription
├── detectors/        # 5 detection modules + LLM fallback
├── fusion/           # Risk aggregation, classification, alert rules
├── alerting/         # Notifications, webhooks, recording, dashboard server
├── api/              # REST API (FastAPI router)
├── storage/          # SQLite voiceprints + session logs
├── ui/               # Gradio dashboard
├── utils/            # Data models, logging
├── config.py         # YAML config loader + validator
└── main.py           # Entry point, engine, CLI
```

---

## Development

```bash
make dev          # Install dev dependencies
make test         # Run all tests
make test-cov     # With coverage report
make lint         # ruff + black
make format       # auto-format code
make dry-run      # Validate config
```

---

## Roadmap

- [ ] **Diarization integration** — isolate speakers before voice comparison
- [ ] **Prosodic urgency detection** — detect stress from speech rate / pitch
- [ ] **Performance dashboard** — FPS, buffer fill, inference times
- [ ] **Configuration profiles** — high-security / balanced / low-resource presets
- [ ] **Configuration UI** — in-dashboard settings editor
- [ ] **Windows installer** — PyInstaller + NSIS

---

## License

MIT — see [LICENSE](LICENSE).

Built by [Abhirup Guha](https://github.com/fir3storm).

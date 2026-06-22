"""MeetGuard AI — entry point with CLI.

Usage:
    meetguard                          # Start with GUI
    meetguard status                   # Engine status + last session
    meetguard alerts                   # Recent alerts
    meetguard report                   # Session report
    meetguard --headless               # No dashboard
    meetguard --profile high-security  # Use a config profile
    meetguard --dry-run                # Validate + exit
    meetguard --setup-audio            # Audio loopback wizard
    meetguard --version                # Print version
"""

from __future__ import annotations

import argparse
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np

from meetguard.alerting.dashboard_server import DashboardServer
from meetguard.alerting.desktop_notify import notify
from meetguard.alerting.meeting_recorder import MeetingRecorder
from meetguard.alerting.sound_alert import play_alert
from meetguard.alerting.webhooks import build_webhook_backends
from meetguard.capture.audio_capture import AudioCapture, AudioConfig
from meetguard.capture.audio_wizard import run_audio_wizard
from meetguard.capture.frame_buffer import RingBuffer
from meetguard.capture.screen_capture import ScreenCapture, CaptureConfig
from meetguard.capture.window_selector import find_meeting_window
from meetguard.config import ConfigError, load as load_config, validate_config
from meetguard.detectors.deepfake_face import DeepfakeFaceDetector
from meetguard.detectors.lip_sync import LipSyncDetector
from meetguard.detectors.suspicious_nlp import SuspiciousNLPDectector
from meetguard.detectors.urgency_language import UrgencyLanguageDetector
from meetguard.detectors.voice_mismatch import VoiceMismatchDetector
from meetguard.fusion.alert_rules import AlertRules
from meetguard.fusion.risk_aggregator import RiskAggregator
from meetguard.fusion.threat_classifier import ThreatClassifier
from meetguard.processing.face_extractor import FaceExtractor
from meetguard.processing.transcriber import Transcriber
from meetguard.processing.voiceprint_manager import VoiceprintManager
from meetguard.storage.session_log import SessionLog
from meetguard.ui.gradio_app import GradioDashboard
from meetguard.utils.logger import get_logger
from meetguard.utils.models import AlertLevel, DetectorScores, FusionResult

VERSION = "0.3.0"


class MeetGuardEngine:
    """Core engine that orchestrates the detection pipeline."""

    def __init__(self, config_path: str | Path | None = None, headless: bool = False,
                 profile: str | None = None):
        self.cfg = load_config(config_path, profile=profile)
        self.log = get_logger("engine")

        fps = self.cfg["capture"]["fps"]
        buf_sec = self.cfg["capture"]["buffer_seconds"]
        self.frame_buffer = RingBuffer[np.ndarray](maxlen=fps * buf_sec)
        self.audio_buffer = RingBuffer[np.ndarray](maxlen=5 * buf_sec)

        # Capture
        self.screen_cap = ScreenCapture(CaptureConfig(fps=fps))
        self.audio_cap = AudioCapture(AudioConfig(
            sample_rate=self.cfg["capture"]["audio_sample_rate"],
        ))

        # Processing
        self.face_extractor = FaceExtractor()
        self.vp_manager = VoiceprintManager()
        self.transcriber = Transcriber()

        # Diarization (optional)
        diar_cfg = self.cfg.get("diarization", {})
        if diar_cfg.get("enabled", False):
            try:
                from meetguard.processing.audio_splitter import AudioSplitter
                self.audio_splitter = AudioSplitter(hf_token=diar_cfg.get("hf_token"))
                self._diarize_enabled = True
                self.log.info("Speaker diarization enabled")
            except (ImportError, RuntimeError) as e:
                self.audio_splitter = None
                self._diarize_enabled = False
                self.log.warning("Diarization disabled: %s", e)
        else:
            self.audio_splitter = None
            self._diarize_enabled = False

        # Detectors
        dc = self.cfg["detectors"]
        self.deepfake_detector = DeepfakeFaceDetector(
            model_path=dc["deepfake_face"]["model_path"],
            window_frames=dc["deepfake_face"]["window_frames"],
            threshold_suspicious=dc["deepfake_face"]["threshold_suspicious"],
            threshold_critical=dc["deepfake_face"]["threshold_critical"],
        )
        self.voice_detector = VoiceMismatchDetector(
            self.vp_manager,
            similarity_threshold=dc["voice_mismatch"]["similarity_threshold"],
        )
        self.lip_detector = LipSyncDetector(
            confidence_threshold=dc["lip_sync"]["confidence_threshold"],
            window_seconds=dc["lip_sync"]["window_seconds"],
        )
        self.nlp_detector = SuspiciousNLPDectector(
            model_name=dc["suspicious_nlp"]["model"],
            enable_llm_fallback=dc["suspicious_nlp"]["enable_llm_fallback"],
        )
        self.urgency_detector = UrgencyLanguageDetector(
            threshold=dc["urgency_language"]["threshold"],
        )

        # Fusion
        fc = self.cfg["fusion"]
        self.aggregator = RiskAggregator(weights=fc["weights"])
        self.classifier = ThreatClassifier(thresholds=fc["thresholds"])
        self.alert_rules = AlertRules(cooldown_seconds=fc["cooldown_seconds"])

        # Alerting
        self.recorder = MeetingRecorder(
            Path.home() / ".meetguard" / "sessions",
            clip_length_seconds=self.cfg["alerting"]["clip_length_seconds"],
        )
        self.recorder.set_buffers(self.frame_buffer, self.audio_buffer)
        self.session_log = SessionLog()
        self.webhook_backends = build_webhook_backends(self.cfg)

        # Dashboard
        self.headless = headless
        self.dashboard = GradioDashboard()
        self.dashboard_server = DashboardServer() if not headless else None

        # State
        self._running = threading.Event()
        self._session_id: str = ""
        self._transcript_buffer: list[str] = []
        self._face_crops: list = []
        self._start_time: float = 0.0
        self._tick_count: int = 0
        self._tick_warning_threshold: float = 5.0
        self._tick_times: list[float] = []

    # ── callbacks ──────────────────────────────────────────────────────

    def _on_frame(self, frame: np.ndarray) -> None:
        pushed = self.frame_buffer.push_with_backpressure(frame)
        if not pushed and self._tick_count % 10 == 0:
            self.log.warning("Frame buffer full — dropping frames")

    def _on_audio(self, chunk: np.ndarray) -> None:
        self.audio_buffer.push(chunk)

    # ── pipeline tick ──────────────────────────────────────────────────

    def _tick(self) -> Optional[FusionResult]:
        t0 = time.perf_counter()
        frames = self.frame_buffer.get_last(16)
        audio = self.audio_buffer.get_all()

        if not frames or not audio:
            return None

        scores = DetectorScores()
        sample_rate = self.cfg["capture"]["audio_sample_rate"]
        concat = np.concatenate(audio).astype(np.float32)

        # 1. Face extraction + deepfake detection
        face_crops: list[np.ndarray] = []
        for f in frames:
            crop = self.face_extractor.detect_largest(f)
            if crop is not None:
                face_crops.append(crop)
        if face_crops:
            scores.face = self.deepfake_detector.predict_sliding(face_crops)

        # 2. Voice mismatch (per-speaker if diarization enabled)
        if self._diarize_enabled and self.audio_splitter is not None:
            try:
                speakers = self.audio_splitter.diarize(concat, sample_rate=sample_rate)
                if speakers:
                    per_speaker = []
                    for label, seg in speakers.items():
                        if len(seg) > sample_rate * 0.5:  # min 0.5s
                            per_speaker.append(self.voice_detector.predict(seg))
                    scores.voice = max(per_speaker) if per_speaker else 0.0
                else:
                    scores.voice = self.voice_detector.predict(concat)
            except Exception as e:
                self.log.warning("Diarization failed, falling back: %s", e)
                scores.voice = self.voice_detector.predict(concat)
        else:
            scores.voice = self.voice_detector.predict(concat)

        # 3. Lip-sync
        if face_crops:
            try:
                scores.lip = self.lip_detector.predict(face_crops[0], concat)
            except Exception:
                pass

        # 4. Transcription + NLP
        text = self.transcriber.transcribe(concat)
        if text:
            scores.nlp = self.nlp_detector.predict(text)
            scores.urgency = self.urgency_detector.predict(text)

        # 5. Fusion
        total_risk = self.aggregator.aggregate(scores)
        level = self.classifier.classify(total_risk)

        elapsed = time.perf_counter() - t0
        if elapsed > self._tick_warning_threshold:
            self.log.warning("Pipeline tick took %.1fs (threshold: %.1fs)", elapsed, self._tick_warning_threshold)

        return FusionResult(
            scores=scores, total_risk=total_risk, level=level,
            meeting_active=self._running.is_set(), session_id=self._session_id,
        )

    # ── lifecycle ──────────────────────────────────────────────────────

    def start(self) -> None:
        self._start_time = time.time()
        self.log.info("MeetGuard AI v%s starting...", VERSION)

        meeting_title = find_meeting_window(self.cfg["capture"]["window_title_patterns"])
        if meeting_title:
            self.log.info("Meeting window detected: %s", meeting_title)
        else:
            self.log.info("No meeting window found — monitoring in passive mode")

        self._session_id = self.session_log.create_session(meeting_window=meeting_title or "")
        self.log.info("Session created: %s", self._session_id)

        # Write PID file for `meetguard status`
        pid_dir = Path.home() / ".meetguard"
        pid_dir.mkdir(parents=True, exist_ok=True)
        pid_dir.joinpath("engine.pid").write_text(str(threading.get_native_id()))

        self.screen_cap.start(self._on_frame)
        self.audio_cap.start(self._on_audio)

        if self.dashboard_server:
            self.dashboard_server.start()

        if not self.headless:
            threading.Thread(target=self.dashboard.launch, daemon=True).start()

        self._running.set()
        self.log.info("Engine started — detection loop running (tick every 3s)")

        try:
            while self._running.is_set():
                result = self._tick()
                if result is not None:
                    self.dashboard.update(result)
                    if self.dashboard_server:
                        self.dashboard_server.update(result)
                    self._push_perf()
                    self._handle_alert(result)
                self._tick_count += 1
                time.sleep(3.0)
        except KeyboardInterrupt:
            self.log.info("Keyboard interrupt received")
        finally:
            self.stop()

    def stop(self) -> None:
        if not self._running.is_set():
            return
        self._running.clear()
        duration = time.time() - self._start_time

        # Clean up PID file
        pid_file = Path.home() / ".meetguard" / "engine.pid"
        if pid_file.exists():
            pid_file.unlink()

        self.screen_cap.stop()
        self.audio_cap.stop()
        self.session_log.end_session(self._session_id)
        self.session_log.close()
        self.log.info("MeetGuard AI stopped (ran for %.1fs, %d ticks)", duration, self._tick_count)

    # ── performance metrics ────────────────────────────────────────────

    def _push_perf(self) -> None:
        fps = self.cfg["capture"]["fps"]
        buf_max = fps * self.cfg["capture"]["buffer_seconds"]
        audio_buf_max = 5 * buf_max
        tick_ms = float(np.mean(self._tick_times)) if self._tick_times else 0.0

        self.dashboard.update_perf({
            "fps": getattr(self.screen_cap, "measured_fps", float(fps)),
            "buffer_fill_pct": (len(self.frame_buffer) / max(buf_max, 1)) * 100,
            "audio_buffer_fill_pct": (len(self.audio_buffer) / max(audio_buf_max, 1)) * 100,
            "tick_time_ms": tick_ms,
            "uptime_seconds": int(time.time() - self._start_time),
            "tick_count": self._tick_count,
        })

    # ── alert handling ────────────────────────────────────────────────

    def _handle_alert(self, result: FusionResult) -> None:
        if result.level == AlertLevel.SAFE:
            return

        self.session_log.save_alert(result)

        if result.level == AlertLevel.CRITICAL:
            if not self.alert_rules.should_alert(result.level):
                return
            notify(result.level, "Deepfake Risk Detected",
                   f"Total risk: {result.total_risk:.2f}")
            play_alert()
            self.recorder.save_clip(reason=f"critical_{result.total_risk:.2f}")
            for backend in self.webhook_backends:
                try:
                    backend.send(result)
                except Exception as e:
                    self.log.error("Webhook send failed: %s", e)
            self.log.warning("CRITICAL alert fired (risk=%.2f)", result.total_risk)
        elif result.level == AlertLevel.SUSPICIOUS:
            for backend in self.webhook_backends:
                try:
                    backend.send(result)
                except Exception:
                    pass


# ── CLI ──────────────────────────────────────────────────────────────────

_shutdown_requested = threading.Event()


def _signal_handler(signum: int, _frame) -> None:
    sig_name = signal.Signals(signum).name
    get_logger("engine").warning("Received %s — shutting down...", sig_name)
    _shutdown_requested.set()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="meetguard", description="MeetGuard AI — live deepfake detection")
    sub = parser.add_subparsers(dest="command")

    # ── subcommands ──
    sub.add_parser("status", help="Show engine status and last session summary")
    p_alerts = sub.add_parser("alerts", help="List recent alerts")
    p_alerts.add_argument("--limit", type=int, default=10)
    p_alerts.add_argument("--json", action="store_true", help="Output as JSON")
    p_report = sub.add_parser("report", help="Generate session report")
    p_report.add_argument("--session", help="Session ID (default: latest)")
    p_report.add_argument("-o", "--output", help="Write JSON report to file")

    # ── flat flags ──
    parser.add_argument("-c", "--config", help="Path to YAML config file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    parser.add_argument("--profile", choices=["high-security", "balanced", "low-resource"],
                        help="Configuration profile (overrides YAML)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate config + check dependencies, then exit")
    parser.add_argument("--headless", action="store_true", help="Run without Gradio dashboard")
    parser.add_argument("--setup-audio", action="store_true", help="Audio loopback setup wizard")
    parser.add_argument("--list-audio-devices", action="store_true", help="List audio devices")
    parser.add_argument("--enroll", nargs=2, metavar=("NAME", "FILE"),
                        help="Enrol voiceprint from WAV file")
    parser.add_argument("--version", action="store_true", help="Print version")
    return parser


def cli() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # ── dispatch subcommands ──
    if args.command == "status":
        from meetguard.cli.commands import cmd_status
        cmd_status()
        sys.exit(0)
    if args.command == "alerts":
        from meetguard.cli.commands import cmd_alerts
        cmd_alerts(limit=args.limit, json_output=args.json)
        sys.exit(0)
    if args.command == "report":
        from meetguard.cli.commands import cmd_report
        cmd_report(session_id=args.session, output=args.output)
        sys.exit(0)

    # ── quick actions ──
    if args.version:
        print(f"MeetGuard AI v{VERSION}")
        sys.exit(0)
    if args.list_audio_devices:
        AudioCapture().list_devices()
        print(AudioCapture().list_devices())
        sys.exit(0)
    if args.setup_audio:
        run_audio_wizard()
        sys.exit(0)
    if args.enroll:
        _run_enroll(*args.enroll)
        sys.exit(0)

    # ── config validation ──
    try:
        cfg = load_config(args.config, profile=args.profile)
    except ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Profile error: {e}", file=sys.stderr)
        sys.exit(1)

    for w in validate_config(cfg):
        print(f"  ⚠ {w}", file=sys.stderr)

    if args.dry_run:
        dets = cfg.get("detectors", {})
        enabled = sum(1 for d in dets.values() if isinstance(d, dict) and d.get("enabled"))
        print(f"✓ Config valid")
        print(f"  Profile:   {args.profile or 'default'}")
        print(f"  Capture:   {cfg['capture']['fps']} FPS, {cfg['capture']['buffer_seconds']}s buffer")
        print(f"  Detectors: {enabled} enabled")
        print(f"  Fusion:    weights={cfg['fusion']['weights']}  thresholds={cfg['fusion']['thresholds']}")
        sys.exit(0)

    # ── run ──
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    engine = MeetGuardEngine(config_path=args.config, headless=args.headless, profile=args.profile)
    engine.start()
    _shutdown_requested.wait()
    engine.stop()


def _run_enroll(name: str, filepath: str) -> None:
    import soundfile as sf
    from meetguard.processing.voiceprint_manager import VoiceprintManager
    audio, sr = sf.read(filepath)
    if sr != 16000:
        import scipy.signal
        audio = scipy.signal.resample(audio, int(len(audio) * 16000 / sr))
    mgr = VoiceprintManager()
    record = mgr.enroll(name, audio.astype(np.float32))
    print(f"✓ Enrolled '{name}' ({len(audio) / 16000:.1f}s)")


if __name__ == "__main__":
    cli()

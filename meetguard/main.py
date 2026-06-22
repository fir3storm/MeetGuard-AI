"""MeetGuard AI — entry point with CLI.

Usage:
    meetguard                          # Start with GUI
    meetguard --headless               # No dashboard
    meetguard --dry-run                # Validate + exit
    meetguard -c path/to/config.yaml   # Custom config
    meetguard --setup-audio            # Audio loopback wizard
    meetguard --list-audio-devices     # Show audio devices
    meetguard --enroll CEO voice.wav   # Enrol voiceprint
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

VERSION = "0.2.0"


class MeetGuardEngine:
    """Core engine that orchestrates the detection pipeline."""

    def __init__(self, config_path: str | Path | None = None, headless: bool = False):
        self.cfg = load_config(config_path)
        self.log = get_logger("engine")

        # Buffers
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

    # ── callbacks ──────────────────────────────────────────────────────

    def _on_frame(self, frame: np.ndarray) -> None:
        pushed = self.frame_buffer.push_with_backpressure(frame)
        if not pushed and self._tick_count % 10 == 0:
            self.log.warning("Frame buffer full — dropping frames")

    def _on_audio(self, chunk: np.ndarray) -> None:
        self.audio_buffer.push(chunk)

    def _on_transcript(self, text: str) -> None:
        self._transcript_buffer.append(text)

    # ── pipeline tick ──────────────────────────────────────────────────

    def _tick(self) -> Optional[FusionResult]:
        """Execute one full pipeline cycle (~every 3s)."""
        t0 = time.perf_counter()

        frames = self.frame_buffer.get_last(16)
        audio = self.audio_buffer.get_all()

        if not frames:
            return None
        if not audio:
            return None

        scores = DetectorScores()

        # 1. Face extraction + deepfake detection
        face_crops: list[np.ndarray] = []
        for f in frames:
            crop = self.face_extractor.detect_largest(f)
            if crop is not None:
                face_crops.append(crop)
        if face_crops:
            scores.face = self.deepfake_detector.predict_sliding(face_crops)

        # 2. Voice mismatch
        if audio:
            concat = np.concatenate(audio)
            scores.voice = self.voice_detector.predict(concat)

        # 3. Lip-sync (if we have both face + audio)
        if face_crops and audio:
            try:
                scores.lip = self.lip_detector.predict(face_crops[0], concat)
            except Exception:
                pass

        # 4. Transcription + NLP
        if audio:
            concat = np.concatenate(audio)
            text = self.transcriber.transcribe(concat)
            if text:
                scores.nlp = self.nlp_detector.predict(text)
                scores.urgency = self.urgency_detector.predict(text)

        # 5. Fusion
        total_risk = self.aggregator.aggregate(scores)
        level = self.classifier.classify(total_risk)

        result = FusionResult(
            scores=scores,
            total_risk=total_risk,
            level=level,
            meeting_active=self._running.is_set(),
            session_id=self._session_id,
        )

        # Backpressure: warn if tick takes too long
        elapsed = time.perf_counter() - t0
        if elapsed > self._tick_warning_threshold:
            self.log.warning("Pipeline tick took %.1fs (threshold: %.1fs)", elapsed, self._tick_warning_threshold)

        return result

    # ── lifecycle ──────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the detection pipeline."""
        self._start_time = time.time()
        self.log.info("MeetGuard AI v%s starting...", VERSION)

        # Find meeting window
        meeting_title = find_meeting_window(self.cfg["capture"]["window_title_patterns"])
        if meeting_title:
            self.log.info("Meeting window detected: %s", meeting_title)
        else:
            self.log.info("No meeting window found — monitoring in passive mode")

        # Create session
        self._session_id = self.session_log.create_session(meeting_window=meeting_title or "")
        self.log.info("Session created: %s", self._session_id)

        # Start capture
        self.screen_cap.start(self._on_frame)
        self.audio_cap.start(self._on_audio)

        # Start dashboard server (FastAPI + WebSocket)
        if self.dashboard_server:
            self.dashboard_server.start()
            self.log.info("Dashboard server started on http://127.0.0.1:%d", self.dashboard_server.port)

        # Start Gradio dashboard
        if not self.headless:
            dash_thread = threading.Thread(target=self.dashboard.launch, daemon=True)
            dash_thread.start()
            self.log.info("Gradio dashboard launching...")

        self._running.set()
        self.log.info("Engine started — detection loop running (tick every 3s)")

        # Pipeline loop
        try:
            while self._running.is_set():
                result = self._tick()
                if result is not None:
                    self.dashboard.update(result)
                    if self.dashboard_server:
                        self.dashboard_server.update(result)
                    self._handle_alert(result)
                self._tick_count += 1
                time.sleep(3.0)
        except KeyboardInterrupt:
            self.log.info("Keyboard interrupt received")
        finally:
            self.stop()

    def stop(self) -> None:
        """Gracefully stop the pipeline."""
        if not self._running.is_set():
            return
        self._running.clear()
        duration = time.time() - self._start_time

        self.screen_cap.stop()
        self.audio_cap.stop()
        self.session_log.end_session(self._session_id)
        self.session_log.close()

        self.log.info("MeetGuard AI stopped (ran for %.1fs, %d ticks)", duration, self._tick_count)

    # ── alert handling ────────────────────────────────────────────────

    def _handle_alert(self, result: FusionResult) -> None:
        if result.level == AlertLevel.SAFE:
            return

        self.session_log.save_alert(result)

        if result.level == AlertLevel.CRITICAL:
            if not self.alert_rules.should_alert(result.level):
                return
            notify(result.level, "Deepfake Risk Detected",
                   f"Total risk: {result.total_risk:.2f} — face:{result.scores.face:.2f} "
                   f"voice:{result.scores.voice:.2f} lip:{result.scores.lip:.2f} "
                   f"nlp:{result.scores.nlp:.2f} urgency:{result.scores.urgency:.2f}")
            play_alert()
            self.recorder.save_clip(reason=f"critical_{result.total_risk:.2f}")
            # Webhooks
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
            self.log.info("SUSPICIOUS (risk=%.2f): f=%s v=%s l=%s n=%s u=%s",
                          result.total_risk,
                          f"{result.scores.face:.2f}", f"{result.scores.voice:.2f}",
                          f"{result.scores.lip:.2f}", f"{result.scores.nlp:.2f}",
                          f"{result.scores.urgency:.2f}")


# ── CLI ──────────────────────────────────────────────────────────────────

_shutdown_requested = threading.Event()


def _signal_handler(signum: int, _frame) -> None:
    sig_name = signal.Signals(signum).name
    log = get_logger("engine")
    log.warning("Received %s — shutting down...", sig_name)
    _shutdown_requested.set()


def cli() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="meetguard",
        description="MeetGuard AI — live deepfake detection for video meetings",
    )
    parser.add_argument("-c", "--config", help="Path to YAML config file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    parser.add_argument("--dry-run", action="store_true", help="Validate config + check dependencies, then exit")
    parser.add_argument("--headless", action="store_true", help="Run without Gradio dashboard")
    parser.add_argument("--setup-audio", action="store_true", help="Run audio loopback setup wizard")
    parser.add_argument("--list-audio-devices", action="store_true", help="List available audio devices and exit")
    parser.add_argument("--enroll", nargs=2, metavar=("NAME", "FILE"), help="Enrol voiceprint from WAV file")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    args = parser.parse_args()

    # ── quick actions ──────────────────────────────────────────────
    if args.version:
        print(f"MeetGuard AI v{VERSION}")
        sys.exit(0)

    if args.list_audio_devices:
        cap = AudioCapture()
        print(cap.list_devices())
        sys.exit(0)

    if args.setup_audio:
        run_audio_wizard()
        sys.exit(0)

    if args.enroll:
        name, filepath = args.enroll
        _run_enroll(name, filepath)
        sys.exit(0)

    # ── config validation ──────────────────────────────────────────
    try:
        cfg = load_config(args.config)
    except ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        sys.exit(1)

    warnings = validate_config(cfg)
    if warnings:
        for w in warnings:
            print(f"  ⚠ {w}", file=sys.stderr)

    if args.dry_run:
        print("✓ Config valid")
        print(f"  Capture: {cfg['capture']['fps']} FPS, {cfg['capture']['buffer_seconds']}s buffer")
        print(f"  Detectors: {sum(1 for d in cfg['detectors'].values() if isinstance(d, dict) and d.get('enabled'))} enabled")
        print(f"  Fusion weights: {cfg['fusion']['weights']}")
        print(f"  Thresholds: {cfg['fusion']['thresholds']}")
        print("✓ Dry run complete — exiting")
        sys.exit(0)

    # ── normal run ────────────────────────────────────────────────
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    engine = MeetGuardEngine(config_path=args.config, headless=args.headless)
    engine.start()
    # Wait for shutdown signal
    _shutdown_requested.wait()
    engine.stop()


def _run_enroll(name: str, filepath: str) -> None:
    """Enrol a voiceprint from a WAV file."""
    import soundfile as sf
    from meetguard.processing.voiceprint_manager import VoiceprintManager
    audio, sr = sf.read(filepath)
    if sr != 16000:
        import scipy.signal
        audio = scipy.signal.resample(audio, int(len(audio) * 16000 / sr))
    audio = audio.astype(np.float32)
    mgr = VoiceprintManager()
    record = mgr.enroll(name, audio)
    print(f"✓ Enrolled '{name}' ({len(audio) / 16000:.1f}s, embedding: {len(record.embedding_bytes)} bytes)")


def serve(config_path: str | Path | None = None) -> None:
    """Legacy entry point for backward compatibility."""
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    engine = MeetGuardEngine(config_path=config_path)
    engine.start()
    _shutdown_requested.wait()
    engine.stop()


if __name__ == "__main__":
    cli()

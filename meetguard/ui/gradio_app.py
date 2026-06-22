"""Gradio-based MVP dashboard for MeetGuard AI — with auto-refresh."""

from __future__ import annotations

import threading
from typing import Any, Optional

import numpy as np

from meetguard.utils.models import AlertLevel, DetectorScores, FusionResult

try:
    import gradio as gr
except ImportError:
    gr = None  # type: ignore[assignment]


class GradioDashboard:
    """Real-time dashboard with live risk scores, timeline, and controls.

    Auto-refreshes every 2 seconds via Gradio's built-in `every` parameter.
    """

    def __init__(self):
        self._latest: Optional[FusionResult] = None
        self._history: list[FusionResult] = []
        self._running = threading.Event()
        self._lock = threading.Lock()

    def update(self, result: FusionResult) -> None:
        with self._lock:
            self._latest = result
            self._history.append(result)
            if len(self._history) > 200:
                self._history = self._history[-200:]

    def _get_data(self) -> tuple:
        """Return current data for all UI components."""
        with self._lock:
            r = self._latest
            hist = list(self._history)

        if r is None:
            return "⏸️ Idle", 0.0, 0, 0, 0, 0, 0, 0, "Waiting for data..."

        hist_risk = [h.total_risk for h in hist[-60:]] if hist else [0]
        avg = float(np.mean(hist_risk)) if hist_risk else 0

        if r.level == AlertLevel.CRITICAL:
            alert = f"🚨 CRITICAL: Risk {r.total_risk:.2f} at {r.timestamp.strftime('%H:%M:%S')}"
        elif r.level == AlertLevel.SUSPICIOUS:
            alert = f"⚠️ SUSPICIOUS: Risk {r.total_risk:.2f}"
        else:
            alert = ""

        status = "🟢 Monitoring" if r.meeting_active else "⏸️ Idle"
        return (
            status, r.total_risk,
            r.scores.face, r.scores.voice, r.scores.lip,
            r.scores.nlp, r.scores.urgency,
            avg, alert,
        )

    def _build_ui(self) -> Any:
        if gr is None:
            return None

        with gr.Blocks(title="MeetGuard AI", theme=gr.themes.Soft()) as demo:
            gr.Markdown("# 🛡️ MeetGuard AI — Live Deepfake Detection")

            with gr.Row():
                status_box = gr.Textbox(label="Status", interactive=False)
                risk_box = gr.Number(label="Total Risk", interactive=False)
                timeline = gr.Slider(label="Avg Risk (60s)", minimum=0, maximum=1.0,
                                     interactive=False)

            with gr.Row():
                face_bar = gr.Number(label="🫵 Face Deepfake")
                voice_bar = gr.Number(label="🗣️ Voice Mismatch")
                lip_bar = gr.Number(label="👄 Lip-Sync")
                nlp_bar = gr.Number(label="📝 Suspicious NLP")
                urgency_bar = gr.Number(label="⚠️ Urgency")

            alert_box = gr.Textbox(label="Latest Alert", interactive=False, lines=2)

            # Auto-refresh every 2 seconds
            demo.load(
                fn=self._get_data,
                outputs=[status_box, risk_box, face_bar, voice_bar, lip_bar,
                         nlp_bar, urgency_bar, timeline, alert_box],
                every=2.0,
            )

        return demo

    def launch(self, share: bool = False) -> None:
        """Launch the Gradio dashboard."""
        demo = self._build_ui()
        if demo is None:
            print("Gradio not installed — skipping UI")
            return
        demo.queue(default_concurrency_limit=5)
        demo.launch(share=share, inbrowser=True)

"""Gradio-based MVP dashboard for MeetGuard AI — with auto-refresh and perf panel."""

from __future__ import annotations

import threading
from typing import Any, Optional

import numpy as np

from meetguard.utils.models import AlertLevel, FusionResult

try:
    import gradio as gr
except ImportError:
    gr = None  # type: ignore[assignment]


class GradioDashboard:
    """Real-time dashboard with live risk scores, timeline, and performance metrics.

    Auto-refreshes every 2 seconds via Gradio's built-in `every` parameter.
    """

    def __init__(self):
        self._latest: Optional[FusionResult] = None
        self._history: list[FusionResult] = []
        self._lock = threading.Lock()
        self._perf_metrics: dict[str, Any] = {
            "fps": 0.0, "buffer_fill_pct": 0.0, "audio_buffer_fill_pct": 0.0,
            "tick_time_ms": 0.0, "uptime_seconds": 0, "tick_count": 0,
        }

    def update(self, result: FusionResult) -> None:
        with self._lock:
            self._latest = result
            self._history.append(result)
            if len(self._history) > 200:
                self._history = self._history[-200:]

    def update_perf(self, metrics: dict) -> None:
        with self._lock:
            self._perf_metrics.update(metrics)

    # ── callbacks ──────────────────────────────────────────────────────

    def _get_data(self) -> tuple:
        with self._lock:
            r = self._latest
            hist = list(self._history)
        if r is None:
            return "⏸️ Idle", 0.0, 0, 0, 0, 0, 0, 0, "Waiting for data..."

        avg = float(np.mean([h.total_risk for h in hist[-60:] or [0]]))
        alert = ""
        if r.level == AlertLevel.CRITICAL:
            alert = f"🚨 CRITICAL: Risk {r.total_risk:.2f} at {r.timestamp.strftime('%H:%M:%S')}"
        elif r.level == AlertLevel.SUSPICIOUS:
            alert = f"⚠️ SUSPICIOUS: Risk {r.total_risk:.2f}"
        return (
            "🟢 Monitoring" if r.meeting_active else "⏸️ Idle",
            r.total_risk, r.scores.face, r.scores.voice, r.scores.lip,
            r.scores.nlp, r.scores.urgency, avg, alert,
        )

    def _get_perf_data(self) -> tuple:
        with self._lock:
            p = dict(self._perf_metrics)
        ups = p["uptime_seconds"]
        return (
            f"{p['fps']:.1f}", f"{p['buffer_fill_pct']:.0f}%", f"{p['audio_buffer_fill_pct']:.0f}%",
            f"{p['tick_time_ms']:.0f}ms", f"{ups // 60}m {ups % 60}s", p["tick_count"],
        )

    # ── UI ─────────────────────────────────────────────────────────────

    def _build_ui(self) -> Any:
        if gr is None:
            return None

        with gr.Blocks(title="MeetGuard AI", theme=gr.themes.Soft()) as demo:
            gr.Markdown("# 🛡️ MeetGuard AI — Live Deepfake Detection")

            # ── Risk Panel ──
            with gr.Row():
                status_box = gr.Textbox(label="Status", interactive=False)
                risk_box = gr.Number(label="Total Risk", interactive=False)
                timeline = gr.Slider(label="Avg Risk (60s)", minimum=0, maximum=1.0, interactive=False)

            with gr.Row():
                face_bar = gr.Number(label="🫵 Face Deepfake")
                voice_bar = gr.Number(label="🗣️ Voice Mismatch")
                lip_bar = gr.Number(label="👄 Lip-Sync")
                nlp_bar = gr.Number(label="📝 Suspicious NLP")
                urgency_bar = gr.Number(label="⚠️ Urgency")

            alert_box = gr.Textbox(label="Latest Alert", interactive=False, lines=2)

            # ── Performance Panel ──
            with gr.Accordion("⚙️ Performance Metrics", open=False):
                with gr.Row():
                    fps_box = gr.Textbox(label="Actual FPS", interactive=False)
                    buf_box = gr.Textbox(label="Frame Buffer", interactive=False)
                    audio_buf_box = gr.Textbox(label="Audio Buffer", interactive=False)
                with gr.Row():
                    tick_box = gr.Textbox(label="Avg Tick Time", interactive=False)
                    uptime_box = gr.Textbox(label="Uptime", interactive=False)
                    tick_count_box = gr.Number(label="Pipeline Ticks", interactive=False)

            # ── auto-refresh both panels ──
            demo.load(fn=self._get_data, every=2.0,
                      outputs=[status_box, risk_box, face_bar, voice_bar, lip_bar,
                               nlp_bar, urgency_bar, timeline, alert_box])
            demo.load(fn=self._get_perf_data, every=2.0,
                      outputs=[fps_box, buf_box, audio_buf_box, tick_box, uptime_box, tick_count_box])

        return demo

    def launch(self, share: bool = False) -> None:
        demo = self._build_ui()
        if demo is None:
            return
        demo.queue(default_concurrency_limit=5)
        demo.launch(share=share, inbrowser=True)

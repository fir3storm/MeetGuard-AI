#!/usr/bin/env python3
"""CLI to enrol an executive's voiceprint.

Usage:
    python scripts/enroll_executive.py --name "CEO" --file ceo_voice.wav
    python scripts/enroll_executive.py --name "CFO" --record 30
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrol a voiceprint for MeetGuard AI")
    parser.add_argument("--name", required=True, help="Executive's name")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to WAV file (at least 10s)")
    group.add_argument("--record", type=int, metavar="SECONDS",
                       help="Record N seconds from microphone")
    args = parser.parse_args()

    try:
        from meetguard.processing.voiceprint_manager import VoiceprintManager
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from meetguard.processing.voiceprint_manager import VoiceprintManager

    if args.file:
        import soundfile as sf  # type: ignore[import-untyped]
        audio, sr = sf.read(args.file)
        if sr != 16000:
            import scipy.signal  # type: ignore[import-untyped]
            audio = scipy.signal.resample(audio, int(len(audio) * 16000 / sr))
        audio = audio.astype(np.float32)
        print(f"Loaded {args.file} — {len(audio) / 16000:.1f}s at 16kHz")
    else:
        import sounddevice as sd  # type: ignore[import-untyped]
        print(f"Recording for {args.record}s — speak clearly...")
        audio = sd.rec(int(args.record * 16000), samplerate=16000, channels=1, dtype=np.float32)
        sd.wait()
        audio = audio.flatten()
        print(f"Recorded {len(audio) / 16000:.1f}s")

    mgr = VoiceprintManager()
    record = mgr.enroll(args.name, audio)
    print(f"✓ Enrolled voiceprint for '{args.name}' (embedding: {len(record.embedding_bytes)} bytes)")


if __name__ == "__main__":
    main()

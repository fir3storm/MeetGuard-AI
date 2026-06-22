"""Audio loopback setup wizard.

Guides the user through installing and configuring a virtual audio device
(VB-Cable on Windows, BlackHole on macOS) so MeetGuard can capture
system audio (the meeting speaker output), not the microphone.
"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

try:
    import sounddevice as sd
except ImportError:
    sd = None  # type: ignore[assignment]


INSTALL_URLS = {
    "win32": "https://vb-audio.com/Cable/",
    "darwin": "https://github.com/ExistentialAudio/BlackHole",
    "linux": "https://wiki.archlinux.org/title/PulseAudio/Examples#Loopback",
}

SETUP_GUIDES = {
    "win32": """
  Windows Setup (VB-Cable):
  1. Download and install from https://vb-audio.com/Cable/
  2. Restart your computer
  3. Open Sound Settings → Sound Control Panel → Playback
  4. Set 'CABLE Input' as the default playback device
  5. Open your meeting app (Zoom/Teams/Meet)
  6. Set the app's speaker output to 'CABLE Input'
  7. In MeetGuard, select 'CABLE Output' as the audio input device
""",
    "darwin": """
  macOS Setup (BlackHole):
  1. Install: brew install blackhole-2ch
  2. Open Audio MIDI Setup (Applications/Utilities)
  3. Create a Multi-Output Device: BlackHole + your speakers
  4. Set the Multi-Output Device as your system output
  5. In MeetGuard, select 'BlackHole 2ch' as the audio input device
""",
    "linux": """
  Linux Setup (PulseAudio loopback):
  1. Load the loopback module:
     pactl load-module module-loopback latency_msec=20
  2. Set your meeting app's output to the loopback target
  3. In MeetGuard, select the monitor source as the audio input device
""",
}


def _detect_loopback_device() -> int | None:
    """Auto-detect a loopback device (VB-Cable / BlackHole / monitor)."""
    if sd is None:
        return None
    keywords = ["cable", "blackhole", "monitor", "loopback", "virtual"]
    for idx, dev in enumerate(sd.query_devices()):
        name: str = dev["name"].lower()
        if any(kw in name for kw in keywords) and dev["max_input_channels"] > 0:
            return idx
    return None


def run_audio_wizard() -> None:
    """Interactive audio setup wizard."""
    print("\n=== MeetGuard AI — Audio Loopback Setup ===\n")
    platform = sys.platform
    print(f"Detected platform: {platform}")

    # Step 1: list devices
    if sd is not None:
        print("\nAvailable audio input devices:")
        for idx, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                marker = " ← LOOPBACK DETECTED" if _detect_loopback_device() == idx else ""
                print(f"  [{idx}] {dev['name']}{marker}")

    # Step 2: check for loopback
    loopback_idx = _detect_loopback_device()
    if loopback_idx is not None:
        dev_name = sd.query_devices()[loopback_idx]["name"] if sd else "Unknown"
        print(f"\n✓ Loopback device detected: '{dev_name}' (index {loopback_idx})")
        print("  You can use this with MeetGuard.")
    else:
        print("\n✗ No loopback device detected.")
        guide = SETUP_GUIDES.get(platform, "See the documentation for audio setup.")
        print(guide)
        url = INSTALL_URLS.get(platform)
        if url:
            print(f"\n  Opening {url} in your browser...")
            webbrowser.open(url)

    # Step 3: test
    if sd is not None:
        print("\n  Testing loopback: recording 2s of audio...")
        try:
            import numpy as np
            device = loopback_idx if loopback_idx is not None else sd.default.device[0]
            recording = sd.rec(int(2 * 16000), samplerate=16000, channels=1,
                               device=device, dtype=np.float32)
            sd.wait()
            energy = float(np.sqrt(np.mean(recording ** 2)))
            if energy > 0.01:
                print(f"  ✓ Audio detected (energy: {energy:.4f}) — loopback is working!")
            else:
                print(f"  ⚠ Low or no audio (energy: {energy:.4f}) — make sure your meeting app is playing audio")
        except Exception as e:
            print(f"  ✗ Test failed: {e}")

    # Step 4: save config
    if loopback_idx is not None:
        config_dir = Path.home() / ".meetguard"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "audio_config.json"
        import json
        config_path.write_text(json.dumps({"audio_device": loopback_idx}, indent=2))
        print(f"\n✓ Saved audio device config to {config_path}")

    print("\nSetup complete. Run 'meetguard' to start detection.\n")


if __name__ == "__main__":
    run_audio_wizard()

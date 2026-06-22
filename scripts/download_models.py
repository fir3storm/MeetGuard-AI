"""Download all pretrained model weights for MeetGuard detectors."""

from __future__ import annotations

import sys
from pathlib import Path

MODELS_DIR = Path.home() / ".meetguard" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

MODELS = {
    "deepfake_3dcnn.pth": {
        "url": "https://github.com/selimsef/dfdc_deepfake_challenge/releases/download/v1.0/xception_best.pth",
        "description": "XceptionNet deepfake detector (DFDC challenge)",
    },
    # Add more model URLs here as they become available
}


def download(url: str, dest: Path) -> None:
    """Download a file with progress indicator."""
    import requests
    from tqdm import tqdm

    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))

    with open(dest, "wb") as f, tqdm(
        desc=dest.name, total=total, unit="B", unit_scale=True,
    ) as pbar:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            pbar.update(len(chunk))


def main() -> None:
    """Download all models."""
    print(f"Downloading models to {MODELS_DIR}...")
    for filename, info in MODELS.items():
        dest = MODELS_DIR / filename
        if dest.exists():
            print(f"  ✓ {filename} already exists, skipping")
            continue
        try:
            print(f"  → Downloading {filename}...")
            print(f"    ({info['description']})")
            download(info["url"], dest)
            print(f"  ✓ {filename} downloaded ({dest.stat().st_size / 1024 / 1024:.1f} MB)")
        except Exception as e:
            print(f"  ✗ Failed to download {filename}: {e}", file=sys.stderr)

    print("\nDone. Models are ready.")


if __name__ == "__main__":
    main()

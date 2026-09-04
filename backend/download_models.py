#!/usr/bin/env python3
"""Download ONNX models required for IBVAP AI pipeline.
Called during Docker build to ensure models are available on Render."""

import os
import sys
import urllib.request

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")

MODELS = {
    "face_detection_yunet_2023mar.onnx": {
        "url": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "size_hint": "232 KB",
    },
    "face_recognition_sface_2021dec.onnx": {
        "url": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "size_hint": "37 MB",
    },
    "license_plate_detection_lpd_yunet_2023mar.onnx": {
        "url": "https://github.com/opencv/opencv_zoo/raw/main/models/license_plate_detection_lpd_yunet/license_plate_detection_lpd_yunet_2023mar.onnx",
        "size_hint": "4 MB",
    },
}


def download_models():
    os.makedirs(MODELS_DIR, exist_ok=True)
    for filename, info in MODELS.items():
        dest = os.path.join(MODELS_DIR, filename)
        if os.path.exists(dest) and os.path.getsize(dest) > 1000:
            print(f"  ✓ {filename} already exists ({os.path.getsize(dest)} bytes), skipping.")
            continue
        print(f"  ⬇ Downloading {filename} ({info['size_hint']}) ...")
        try:
            urllib.request.urlretrieve(info["url"], dest)
            print(f"  ✓ Downloaded {filename} ({os.path.getsize(dest)} bytes)")
        except Exception as e:
            print(f"  ✗ FAILED to download {filename}: {e}", file=sys.stderr)
            # Don't abort — the backend has safe fallback for missing models
    print("Model download complete.")


if __name__ == "__main__":
    download_models()

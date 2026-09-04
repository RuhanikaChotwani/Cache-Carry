"""Static plate detection diagnostic test using FastALPR.
Accepts an explicit video path (or image path) as a required command-line argument.
Passes saved extracted image PATH to alpr.predict() and prints exact object attributes.
"""

import os
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

import cv2

SNAPSHOTS_DIR = BACKEND_DIR / "data" / "snapshots"
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def run_test():
    print("=" * 60)
    print("FASTALPR STATIC DIAGNOSTIC TEST")
    print("=" * 60)

    if len(sys.argv) < 2:
        print("ERROR: Video/image path is required.")
        print("Usage:")
        print("  backend\\.venv\\Scripts\\python.exe backend\\test_plate_debug.py <path_to_video.mp4>")
        sys.exit(1)

    target_input = sys.argv[1].strip().strip('"').strip("'")
    target_path = Path(target_input)
    if not target_path.is_absolute():
        if not target_path.exists():
            target_path = (BACKEND_DIR.parent / target_input).resolve()
        if not target_path.exists():
            target_path = (BACKEND_DIR / target_input).resolve()

    if not target_path.exists() or not target_path.is_file():
        print(f"ERROR: Specified video file not found: {target_input}")
        print(f"Resolved absolute path: {target_path}")
        sys.exit(1)

    print(f"Target Video File: {target_path.name}")
    print(f"Target Full Path: {target_path}")
    print(f"File Size: {target_path.stat().st_size / (1024*1024):.2f} MB")

    # 1. Initialize FastALPR
    print("\n--- 1. Initializing FastALPR (ONNX CPU) ---")
    try:
        from fast_alpr import ALPR

        t_init0 = time.time()
        alpr = ALPR(
            detector_model="yolo-v9-t-384-license-plate-end2end",
            ocr_model="cct-xs-v2-global-model",
            detector_providers=["CPUExecutionProvider"],
            ocr_providers=["CPUExecutionProvider"],
        )
        t_init = (time.time() - t_init0) * 1000
        print(f"[OK] FastALPR initialized in {t_init:.1f} ms")
    except ImportError as e:
        print(f"[FATAL] FastALPR import failed: {e}")
        print("Run: backend\\.venv\\Scripts\\python.exe -m pip install --upgrade \"fast-alpr[onnx]\"")
        sys.exit(1)
    except Exception as e:
        print(f"[FATAL] FastALPR initialization error: {e}")
        sys.exit(1)

    # 2. Extract frame from video and save to disk
    print("\n--- 2. Extracting sample frame ---")
    cap = cv2.VideoCapture(str(target_path))
    if not cap.isOpened():
        print(f"[FATAL] OpenCV could not open video file: {target_path}")
        sys.exit(1)

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    print(f"Video Info: {w}x{h} @ {fps:.1f} FPS | Total frames: {total_frames}")

    # Extract frame at 1 second (frame 25-30) where car plate is clearly visible
    extract_idx = min(30, max(1, total_frames // 2))
    cap.set(cv2.CAP_PROP_POS_FRAMES, extract_idx)
    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        print(f"[FATAL] Could not read frame {extract_idx} from video.")
        sys.exit(1)

    raw_path = SNAPSHOTS_DIR / f"test_extracted_frame_{extract_idx}.jpg"
    cv2.imwrite(str(raw_path), frame)
    print(f"Saved extracted frame image to: {raw_path}")

    # 3. Run prediction by passing the saved image PATH to FastALPR
    print("\n--- 3. Running FastALPR on image path ---")
    t0 = time.time()
    results = alpr.predict(str(raw_path))
    dur = (time.time() - t0) * 1000
    print(f"Prediction completed in {dur:.1f} ms")

    count = len(results) if results is not None else 0
    print(f"\nFastALPR result count: {count}")
    print(f"repr(results): {repr(results)}")

    if results and count > 0:
        first = results[0]
        try:
            print(f"vars(results[0]): {vars(first)}")
        except Exception:
            print(f"dir(results[0]): {dir(first)}")

        # Extract values
        det_target = getattr(first, "detection", first)
        bb = getattr(det_target, "bounding_box", None) or getattr(det_target, "bbox", None) or getattr(first, "bounding_box", None)
        det_conf = getattr(det_target, "confidence", 0.0) or getattr(first, "confidence", 0.0)

        ocr_obj = getattr(first, "ocr", None) or getattr(det_target, "ocr", None)
        plate_text = getattr(ocr_obj, "text", "") if ocr_obj else getattr(first, "text", "")
        ocr_conf = getattr(ocr_obj, "confidence", 0.0) if ocr_obj else 0.0

        print(f"\ndetected plate text: {plate_text}")
        print(f"OCR confidence: {ocr_conf}")
        print(f"detector confidence: {det_conf}")
        print(f"bounding-box field/value: {bb}")

    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    run_test()

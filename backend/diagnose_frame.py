"""Diagnostic script to inspect actual uploaded video frames, inference times,
LPD-YuNet detection raw outputs, and global plate fallback detection.
"""

import sys
import time
from pathlib import Path

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import cv2
import numpy as np

MODELS_DIR = Path(__file__).resolve().parent / "models"
UPLOADS_DIR = Path(__file__).resolve().parent / "runtime_uploads"

YUNET_PATH = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
SFACE_PATH = MODELS_DIR / "face_recognition_sface_2021dec.onnx"
LPD_PATH = MODELS_DIR / "license_plate_detection_lpd_yunet_2023mar.onnx"

def diagnose_videos():
    print("=== 1. DIAGNOSING UPLOADED VIDEOS ===")
    video_files = list(UPLOADS_DIR.glob("*.mp4"))
    if not video_files:
        print("No uploaded videos found in runtime_uploads.")
        return

    for vf in video_files:
        cap = cv2.VideoCapture(str(vf))
        if not cap.isOpened():
            print(f"Could not open {vf.name}")
            continue

        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f"File: {vf.name} | Res: {width}x{height} | FPS: {fps:.2f} | Total Frames: {total_frames}")

        # Read middle frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, min(30, total_frames // 2))
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            print("  Could not read sample frame.")
            continue

        print(f"  Sample frame shape: {frame.shape}, dtype: {frame.dtype}")

        # Test LPD YuNet on this frame
        test_lpd_on_frame(frame, vf.name)

def test_lpd_on_frame(frame, source_name):
    print(f"\n--- Testing LPD-YuNet on {source_name} ---")
    h, w = frame.shape[:2]

    if not LPD_PATH.exists():
        print("LPD model file does not exist!")
        return

    # 1. Test at various score thresholds: 0.50, 0.30, 0.15, 0.05
    for score_thresh in [0.50, 0.30, 0.15, 0.05]:
        try:
            detector = cv2.FaceDetectorYN_create(
                model=str(LPD_PATH),
                config="",
                input_size=(w, h),
                score_threshold=score_thresh,
                nms_threshold=0.30,
                top_k=500
            )
            t0 = time.time()
            _, detections = detector.detect(frame)
            dur = (time.time() - t0) * 1000

            count = len(detections) if detections is not None else 0
            print(f"  LPD-YuNet @ threshold {score_thresh:.2f} ({w}x{h}): {count} detections (Inference time: {dur:.1f}ms)")
            if detections is not None:
                for idx, row in enumerate(detections):
                    score = float(row[14]) if len(row) > 14 else 0.0
                    bx, by, bw, bh = int(row[0]), int(row[1]), int(row[2]), int(row[3])
                    print(f"    Raw Candidate #{idx+1}: Box=[{bx}, {by}, {bw}, {bh}], Aspect={bw/max(1,bh):.2f}, Score={score:.4f}")
        except Exception as e:
            print(f"  LPD-YuNet error: {e}")

    # 2. Test Global / Morphological Aspect-Ratio Plate Locator (Fallback for UK/EU/US rectangular plates)
    print("\n--- Testing Global Rectangular Plate Locator (Fallback) ---")
    t0 = time.time()
    fallback_plates = detect_plates_fallback(frame)
    dur = (time.time() - t0) * 1000
    print(f"  Fallback Detector: {len(fallback_plates)} candidate(s) (Time: {dur:.1f}ms)")
    for idx, p in enumerate(fallback_plates):
        print(f"    Candidate #{idx+1}: Box={p['bbox']}, Aspect={p['aspect']:.2f}, Conf={p['confidence']:.2f}")

def detect_plates_fallback(frame):
    """Detects high-contrast rectangular plate candidates with standard vehicle plate aspect ratio (2.0 to 5.5)."""
    h, w = frame.shape[:2]
    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Blur & Sobel gradient to find vertical edge densities
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    sobelx = cv2.Sobel(blurred, cv2.CV_8U, 1, 0, ksize=3)

    # Threshold with Otsu
    _, thresh = cv2.threshold(sobelx, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Morphological closing with horizontal rectangular kernel to connect character edges
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 3))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    # Find contours
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    min_area = (w * h) * 0.0005   # at least 0.05% of frame
    max_area = (w * h) * 0.15     # at most 15% of frame

    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        area = bw * bh
        if area < min_area or area > max_area:
            continue

        aspect = float(bw) / float(max(1, bh))
        # Standard worldwide plate aspect ratios range from 2.0 to 5.5 (UK/EU standard: 520x110 mm => 4.7)
        if 2.0 <= aspect <= 5.8:
            # Check edge density in candidate crop
            crop = gray[y:y+bh, x:x+bw]
            if crop.size == 0:
                continue
            edges = cv2.Canny(crop, 50, 150)
            edge_density = float(np.count_nonzero(edges)) / float(crop.size)

            if edge_density > 0.08:
                candidates.append({
                    "bbox": [x, y, x + bw, y + bh],
                    "aspect": aspect,
                    "confidence": min(0.95, round(0.55 + edge_density * 0.8, 2)),
                    "detector": "global_plate_detector"
                })

    # Sort by confidence descending, keep top 3 non-overlapping
    candidates.sort(key=lambda c: c["confidence"], reverse=True)
    return candidates[:3]

if __name__ == "__main__":
    diagnose_videos()

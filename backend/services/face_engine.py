"""Face Engine for IBVAP: OpenCV Zoo YuNet Detector + SFace Recognizer.
Exact Model Paths:
- backend/models/face_detection_yunet_2023mar.onnx
- backend/models/face_recognition_sface_2021dec.onnx
"""

import os, io, math, time, uuid
from pathlib import Path
import cv2
import numpy as np

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
YUNET_PATH = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
SFACE_PATH = MODELS_DIR / "face_recognition_sface_2021dec.onnx"

_yunet_detector = None
_sface_recognizer = None

_status = {
    "yunet_path": str(YUNET_PATH),
    "yunet_file_exists": False,
    "yunet_loaded": False,
    "yunet_error": None,
    "sface_path": str(SFACE_PATH),
    "sface_file_exists": False,
    "sface_loaded": False,
    "sface_error": None,
}


def load_face_engine():
    """Initializes OpenCV YuNet and SFace models from backend/models/."""
    global _yunet_detector, _sface_recognizer, _status

    _status["yunet_file_exists"] = YUNET_PATH.exists()
    _status["sface_file_exists"] = SFACE_PATH.exists()

    # 1. Load YuNet Face Detector
    if YUNET_PATH.exists():
        try:
            if hasattr(cv2, "FaceDetectorYN_create"):
                detector = cv2.FaceDetectorYN_create(
                    model=str(YUNET_PATH),
                    config="",
                    input_size=(640, 480),
                    score_threshold=0.60,
                    nms_threshold=0.30,
                    top_k=5000,
                    backend_id=cv2.dnn.DNN_BACKEND_OPENCV,
                    target_id=cv2.dnn.DNN_TARGET_CPU
                )
            elif hasattr(cv2, "FaceDetectorYN") and hasattr(cv2.FaceDetectorYN, "create"):
                detector = cv2.FaceDetectorYN.create(
                    model=str(YUNET_PATH),
                    config="",
                    input_size=(640, 480),
                    score_threshold=0.60,
                    nms_threshold=0.30,
                    top_k=5000,
                    backend_id=cv2.dnn.DNN_BACKEND_OPENCV,
                    target_id=cv2.dnn.DNN_TARGET_CPU
                )
            else:
                raise AttributeError("OpenCV build does not have cv2.FaceDetectorYN")

            _yunet_detector = detector
            _status["yunet_loaded"] = True
            _status["yunet_error"] = None
        except Exception as e:
            _status["yunet_loaded"] = False
            _status["yunet_error"] = str(e)
    else:
        _status["yunet_loaded"] = False
        _status["yunet_error"] = f"File not found: {YUNET_PATH}"

    # 2. Load SFace Face Recognizer
    if SFACE_PATH.exists():
        try:
            if hasattr(cv2, "FaceRecognizerSF_create"):
                recognizer = cv2.FaceRecognizerSF_create(
                    model=str(SFACE_PATH),
                    config="",
                    backend_id=cv2.dnn.DNN_BACKEND_OPENCV,
                    target_id=cv2.dnn.DNN_TARGET_CPU
                )
            elif hasattr(cv2, "FaceRecognizerSF") and hasattr(cv2.FaceRecognizerSF, "create"):
                recognizer = cv2.FaceRecognizerSF.create(
                    model=str(SFACE_PATH),
                    config="",
                    backend_id=cv2.dnn.DNN_BACKEND_OPENCV,
                    target_id=cv2.dnn.DNN_TARGET_CPU
                )
            else:
                raise AttributeError("OpenCV build does not have cv2.FaceRecognizerSF")

            _sface_recognizer = recognizer
            _status["sface_loaded"] = True
            _status["sface_error"] = None
        except Exception as e:
            _status["sface_loaded"] = False
            _status["sface_error"] = str(e)
    else:
        _status["sface_loaded"] = False
        _status["sface_error"] = f"File not found: {SFACE_PATH}"


def get_face_engine_status():
    return dict(_status)


def detect_faces(frame):
    """Detects faces in the given frame using YuNet.
    Returns: list of dicts: [
        {"bbox": [x1, y1, x2, y2], "confidence": float, "raw_row": np.ndarray, "embedding": list}
    ]
    """
    accepted, _, _, _ = detect_faces_debug(frame)
    return accepted


def detect_faces_debug(frame):
    """Runs YuNet detection with detailed diagnostics for debug frames."""
    if frame is None or _yunet_detector is None:
        return [], [], [], "yunet_unloaded"

    h, w = frame.shape[:2]
    frame_area = float(w * h)
    raw_candidates = []
    rejected_candidates = []
    accepted_faces = []

    try:
        _yunet_detector.setInputSize((w, h))
        _, faces = _yunet_detector.detect(frame)

        if faces is not None:
            for face_row in faces:
                x = int(face_row[0])
                y = int(face_row[1])
                width = int(face_row[2])
                height = int(face_row[3])
                score = float(face_row[14])

                x1 = x
                y1 = y
                x2 = x + width
                y2 = y + height

                raw_candidates.append([x1, y1, x2, y2, score, "yunet"])

                # Validation
                valid, reason = _validate_face_bbox(x1, y1, x2, y2, w, h, frame_area, score)
                if valid:
                    emb = extract_embedding(frame, face_row)
                    accepted_faces.append({
                        "bbox": [x1, y1, x2, y2],
                        "confidence": round(score, 2),
                        "raw_row": face_row,
                        "embedding": emb,
                        "detector": "yunet"
                    })
                else:
                    rejected_candidates.append({
                        "bbox": [x1, y1, x2, y2],
                        "reason": reason,
                        "detector": "yunet"
                    })

        return accepted_faces, raw_candidates, rejected_candidates, "yunet"
    except Exception as e:
        return [], [], [{"bbox": [0, 0, w, h], "reason": f"YuNet error: {str(e)}", "detector": "yunet"}], "yunet_error"


def _validate_face_bbox(x1, y1, x2, y2, frame_w, frame_h, frame_area, confidence):
    """Balanced validation: rejects walls/texture while accepting real faces."""
    # Clamp slightly to frame boundaries
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(frame_w, x2)
    y2 = min(frame_h, y2)

    if x2 <= x1 or y2 <= y1:
        return False, "inverted bbox"

    box_w = x2 - x1
    box_h = y2 - y1
    box_area = float(box_w * box_h)

    # 1. Area ratio: 0.1% to 65% of frame
    area_ratio = box_area / frame_area
    if area_ratio < 0.001:
        return False, f"area too small ({area_ratio*100:.2f}%)"
    if area_ratio > 0.65:
        return False, f"area too large ({area_ratio*100:.1f}%)"

    # 2. Aspect ratio (face width/height)
    aspect = box_h / float(box_w)
    if aspect < 0.50 or aspect > 2.2:
        return False, f"aspect ratio ({aspect:.2f})"

    # 3. Confidence threshold >= 0.40
    if confidence < 0.40:
        return False, f"confidence ({confidence:.2f} < 0.40)"

    return True, "valid"


def extract_embedding(frame, face_row):
    """Extracts 128-dimensional L2-normalized feature vector using SFace."""
    if _sface_recognizer is None or frame is None or face_row is None:
        return [0.0] * 128

    try:
        aligned_face = _sface_recognizer.alignCrop(frame, face_row)
        feature = _sface_recognizer.feature(aligned_face)
        feat_flat = feature.flatten()
        norm = np.linalg.norm(feat_flat)
        if norm > 0:
            feat_flat = feat_flat / norm
        return feat_flat.tolist()
    except Exception:
        # Fallback spatial embedding from crop if SFace align fails
        try:
            x, y, w_box, h_box = [int(v) for v in face_row[:4]]
            crop = frame[max(0, y):max(0, y) + max(10, h_box), max(0, x):max(0, x) + max(10, w_box)]
            resized = cv2.resize(crop, (112, 112))
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
            hist = cv2.calcHist([gray], [0], None, [128], [0, 256]).flatten()
            norm = np.linalg.norm(hist)
            if norm > 0:
                hist = hist / norm
            return hist.tolist()
        except Exception:
            return [0.0] * 128


def compare_embedding(embedding, watchlist, threshold=0.45):
    """Calculates cosine similarity against all enrolled subjects in the watchlist.
    Returns: (best_match_dict_or_None, max_similarity, is_match)
    """
    if not watchlist or not embedding:
        return None, 0.0, False

    emb_arr = np.array(embedding, dtype=np.float32)
    norm_a = np.linalg.norm(emb_arr)
    if norm_a == 0:
        return None, 0.0, False
    emb_arr = emb_arr / norm_a

    best_match = None
    max_sim = 0.0

    for item in watchlist:
        target_emb = item.get("embedding")
        if not target_emb:
            continue
        t_arr = np.array(target_emb, dtype=np.float32)
        norm_b = np.linalg.norm(t_arr)
        if norm_b == 0:
            continue
        t_arr = t_arr / norm_b

        # Cosine similarity
        sim = float(np.dot(emb_arr, t_arr))
        if sim > max_sim:
            max_sim = sim
            best_match = item

    is_match = (max_sim >= threshold) and (best_match is not None)
    return best_match, round(max_sim, 3), is_match


# Auto-load on module import
load_face_engine()

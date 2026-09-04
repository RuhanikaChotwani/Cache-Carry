"""Strict ANPR Engine for IBVAP using FastALPR (ONNX CPU Backend).
Uses FastALPR for plate detection (yolo-v9-t-384-license-plate-end2end) and
global OCR recognition (cct-xs-v2-global-model).
Legacy LPD-YuNet runtime calls are completely removed.
No fake plate boxes, fake OCR strings, or placeholder records.

Three internal levels:
A. raw_candidates: FastALPR model output only, diagnostics only, never shown in normal UI.
B. validated_candidates: Filtered by confidence and valid alphanumeric text. Diagnostics only.
C. confirmed_plates: Validated candidate track persists >= 3 frames with consensus OCR text.
   Only confirmed plates appear in the normal live UI, trigger alerts, and are persisted to disk.
"""

import time
import logging
from collections import Counter
from typing import List, Dict, Optional, Tuple

import cv2
import numpy as np

from services import anpr_store

logger = logging.getLogger("ibvap.anpr")

_alpr = None
_anpr_enabled = True
_alpr_initialized = False

_status = {
    "engine": "FastALPR (ONNX CPU)",
    "primary_detector": "FastALPR (yolo-v9-t-384-license-plate-end2end)",
    "ocr_engine": "FastALPR (cct-xs-v2-global-model ONNX)",
    "alpr_loaded": False,
    "alpr_error": None,
    "model_loaded": False,
    "exact_error": None,
    "anpr_enabled": True,
    "ocr_available": False,
    "ocr_error": None,
    "input_width": 0,
    "input_height": 0,
    "inference_width": 0,
    "inference_height": 0,
    "detection_ms": 0.0,
    "ocr_ms": 0.0,
    "display_fps": 0.0,
    "raw_candidates_count": 0,
    "validated_candidates_count": 0,
    "confirmed_plates_count": 0,
}

# Tracking state for temporal persistence
# track_id -> { bbox, hits, det_conf, ocr_history, ocr_confs, last_seen, last_saved_time, detector }
_plate_tracks: Dict[str, dict] = {}
_track_counter = 0


def _to_float(val, default: float = 0.0) -> float:
    """Safely converts any scalar, single-element container, or string to float without throwing."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, (list, tuple, np.ndarray)):
        if len(val) == 0:
            return default
        return _to_float(val[0], default)
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _to_int(val, default: int = 0) -> int:
    """Safely converts any scalar, single-element container, or string to int without throwing."""
    if val is None:
        return default
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    if isinstance(val, (list, tuple, np.ndarray)):
        if len(val) == 0:
            return default
        return _to_int(val[0], default)
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def _to_str(val, default: str = "") -> str:
    """Safely converts any scalar or container to string."""
    if val is None:
        return default
    if isinstance(val, str):
        return val
    if isinstance(val, (list, tuple, np.ndarray)):
        if len(val) == 0:
            return default
        if len(val) > 0 and isinstance(val[0], str):
            return str(val[0])
        return str(val)
    return str(val)


def load_anpr_engine():
    """Initializes FastALPR once on CPU and logs startup status explicitly."""
    global _alpr, _status, _alpr_initialized

    if _alpr_initialized:
        return

    print("[ANPR] Initializing FastALPR (ONNX CPU)...")
    try:
        from fast_alpr import ALPR

        _alpr = ALPR(
            detector_model="yolo-v9-t-384-license-plate-end2end",
            ocr_model="cct-xs-v2-global-model",
            detector_providers=["CPUExecutionProvider"],
            ocr_providers=["CPUExecutionProvider"],
        )
        _status["alpr_loaded"] = True
        _status["alpr_error"] = None
        _status["model_loaded"] = True
        _status["exact_error"] = None
        _status["ocr_available"] = True
        _status["ocr_error"] = None
        print("[ANPR] FastALPR initialized successfully on CPU execution provider.")
        logger.info("FastALPR initialized successfully on CPU execution provider.")
    except ImportError as e:
        _alpr = None
        err_msg = f"FastALPR package is not installed: {e}"
        _status["alpr_loaded"] = False
        _status["alpr_error"] = err_msg
        _status["model_loaded"] = False
        _status["exact_error"] = err_msg
        _status["ocr_available"] = False
        _status["ocr_error"] = err_msg
        print(f"[ANPR] FastALPR initialization failed: {err_msg}")
        logger.error(f"FastALPR initialization failed: {err_msg}")
    except Exception as e:
        _alpr = None
        err_msg = f"FastALPR initialization exception: {e}"
        _status["alpr_loaded"] = False
        _status["alpr_error"] = err_msg
        _status["model_loaded"] = False
        _status["exact_error"] = err_msg
        _status["ocr_available"] = False
        _status["ocr_error"] = err_msg
        print(f"[ANPR] FastALPR initialization failed: {err_msg}")
        logger.error(f"FastALPR initialization failed: {err_msg}")

    _alpr_initialized = True


def set_anpr_enabled(enabled: bool):
    global _anpr_enabled, _status
    _anpr_enabled = bool(enabled)
    _status["anpr_enabled"] = _anpr_enabled


def is_anpr_enabled() -> bool:
    return _anpr_enabled


def get_status() -> dict:
    return dict(_status)


def get_latest_anpr() -> dict:
    """Returns latest confirmed plates and diagnostics."""
    return {
        "confirmed_plates_count": _status["confirmed_plates_count"],
        "raw_candidates_count": _status["raw_candidates_count"],
        "validated_candidates_count": _status["validated_candidates_count"],
        "model_loaded": _status["alpr_loaded"],
        "ocr_available": _status["ocr_available"],
    }


def get_diagnostics() -> dict:
    return {
        "engine": _status["engine"],
        "model_loaded": _status["alpr_loaded"],
        "exact_error": _status["exact_error"] or _status["alpr_error"],
        "primary_detector": _status["primary_detector"],
        "anpr_enabled": _anpr_enabled,
        "ocr_available": _status["ocr_available"],
        "ocr_engine": _status["ocr_engine"],
        "ocr_error": _status.get("ocr_error"),
        "input_dimensions": f"{_status['input_width']}x{_status['input_height']}",
        "inference_dimensions": f"{_status['inference_width']}x{_status['inference_height']}",
        "detection_ms": round(_status["detection_ms"], 1),
        "ocr_ms": round(_status["ocr_ms"], 1),
        "display_fps": round(_status["display_fps"], 1),
        "raw_candidates_count": _status["raw_candidates_count"],
        "validated_candidates_count": _status["validated_candidates_count"],
        "confirmed_plates_count": _status["confirmed_plates_count"],
        "active_tracks_count": len(_plate_tracks),
    }


def update_fps_metric(fps: float):
    _status["display_fps"] = _to_float(fps, 0.0)


def _extract_alpr_item(item, iw: int, ih: int) -> Tuple[Optional[List[int]], float, str, float]:
    """Extracts bounding box, detector confidence, normalized plate text, and OCR confidence
    from any FastALPR result object, dictionary, or list without raising TypeErrors.
    """
    bbox = None
    det_conf = 0.0
    ocr_text = ""
    ocr_conf = 0.0

    if item is None:
        return None, 0.0, "", 0.0

    # 1. Inspect detection object or direct attributes
    detection_target = getattr(item, "detection", None) or getattr(item, "plate", None) or item

    # Confidence extraction
    conf_raw = (
        getattr(detection_target, "confidence", None)
        or getattr(detection_target, "conf", None)
        or getattr(item, "confidence", None)
        or getattr(item, "conf", None)
    )
    if conf_raw is None and isinstance(item, dict):
        conf_raw = item.get("confidence") or item.get("conf") or item.get("score")
    det_conf = _to_float(conf_raw, 0.0)

    # Bounding Box extraction
    bb_raw = (
        getattr(detection_target, "bounding_box", None)
        or getattr(detection_target, "bbox", None)
        or getattr(detection_target, "box", None)
        or getattr(item, "bounding_box", None)
        or getattr(item, "bbox", None)
        or getattr(item, "box", None)
    )
    if bb_raw is None and isinstance(item, dict):
        bb_raw = item.get("bounding_box") or item.get("bbox") or item.get("box")

    if bb_raw is not None:
        # Object with x1, y1, x2, y2 or left, top, right, bottom
        x1 = getattr(bb_raw, "x1", None) or getattr(bb_raw, "left", None) or getattr(bb_raw, "xmin", None)
        y1 = getattr(bb_raw, "y1", None) or getattr(bb_raw, "top", None) or getattr(bb_raw, "ymin", None)
        x2 = getattr(bb_raw, "x2", None) or getattr(bb_raw, "right", None) or getattr(bb_raw, "xmax", None)
        y2 = getattr(bb_raw, "y2", None) or getattr(bb_raw, "bottom", None) or getattr(bb_raw, "ymax", None)

        if x1 is not None and y1 is not None and x2 is not None and y2 is not None:
            ix1, iy1 = _to_int(x1), _to_int(y1)
            ix2, iy2 = _to_int(x2), _to_int(y2)
            bbox = [
                max(0, min(iw - 1, ix1)),
                max(0, min(ih - 1, iy1)),
                max(ix1 + 1, min(iw, ix2)),
                max(iy1 + 1, min(ih, iy2)),
            ]
        elif isinstance(bb_raw, (list, tuple, np.ndarray)) and len(bb_raw) >= 4:
            ix1 = _to_int(bb_raw[0])
            iy1 = _to_int(bb_raw[1])
            ix2 = _to_int(bb_raw[2])
            iy2 = _to_int(bb_raw[3])
            bbox = [
                max(0, min(iw - 1, ix1)),
                max(0, min(ih - 1, iy1)),
                max(ix1 + 1, min(iw, ix2)),
                max(iy1 + 1, min(ih, iy2)),
            ]

    # If item itself is a list/tuple of elements (e.g. [box, conf, text, ocr_conf])
    if bbox is None and isinstance(item, (list, tuple, np.ndarray)):
        if len(item) >= 4 and all(isinstance(x, (int, float, str)) for x in item[:4]):
            ix1, iy1 = _to_int(item[0]), _to_int(item[1])
            ix2, iy2 = _to_int(item[2]), _to_int(item[3])
            bbox = [
                max(0, min(iw - 1, ix1)),
                max(0, min(ih - 1, iy1)),
                max(ix1 + 1, min(iw, ix2)),
                max(iy1 + 1, min(ih, iy2)),
            ]
            if len(item) >= 5:
                det_conf = _to_float(item[4], 0.0)
            if len(item) >= 6:
                ocr_text = _to_str(item[5])
            if len(item) >= 7:
                ocr_conf = _to_float(item[6], det_conf)
        elif len(item) >= 2 and isinstance(item[0], (list, tuple, np.ndarray)) and len(item[0]) >= 4:
            box_sub = item[0]
            ix1, iy1 = _to_int(box_sub[0]), _to_int(box_sub[1])
            ix2, iy2 = _to_int(box_sub[2]), _to_int(box_sub[3])
            bbox = [
                max(0, min(iw - 1, ix1)),
                max(0, min(ih - 1, iy1)),
                max(ix1 + 1, min(iw, ix2)),
                max(iy1 + 1, min(ih, iy2)),
            ]
            det_conf = _to_float(item[1], 0.0)
            if len(item) >= 3:
                ocr_text = _to_str(item[2])
            if len(item) >= 4:
                ocr_conf = _to_float(item[3], det_conf)

    # 2. Inspect OCR object
    if not ocr_text:
        ocr_obj = getattr(item, "ocr", None) or getattr(detection_target, "ocr", None)
        if ocr_obj is not None:
            if hasattr(ocr_obj, "text"):
                ocr_text = _to_str(getattr(ocr_obj, "text", ""))
            elif isinstance(ocr_obj, str):
                ocr_text = ocr_obj
            elif isinstance(ocr_obj, (list, tuple)) and len(ocr_obj) > 0:
                ocr_text = _to_str(ocr_obj[0])
                if len(ocr_obj) > 1:
                    ocr_conf = _to_float(ocr_obj[1], det_conf)

            if hasattr(ocr_obj, "confidence"):
                ocr_conf = _to_float(getattr(ocr_obj, "confidence", 0.0), det_conf)
            elif hasattr(ocr_obj, "conf"):
                ocr_conf = _to_float(getattr(ocr_obj, "conf", 0.0), det_conf)
        elif hasattr(item, "text"):
            ocr_text = _to_str(getattr(item, "text", ""))
            ocr_conf = det_conf
        elif isinstance(item, dict) and "text" in item:
            ocr_text = _to_str(item.get("text"))
            ocr_conf = _to_float(item.get("ocr_confidence") or item.get("confidence"), det_conf)

    clean_text = "".join(c for c in ocr_text.upper() if c.isalnum())
    if ocr_conf == 0.0 and det_conf > 0.0 and clean_text:
        ocr_conf = det_conf

    return bbox, det_conf, clean_text, ocr_conf


def process_anpr_frame(
    infer_frame,
    source_name: str = "Surveillance Feed",
    orig_w: int = 640,
    orig_h: int = 480,
    frame_counter: int = 1,
) -> Dict[str, List[dict]]:
    """Processes infer_frame using FastALPR.
    Separates output strictly into raw_candidates, validated_candidates, and confirmed_plates.
    """
    global _status, _plate_tracks, _track_counter

    empty_result = {"raw_candidates": [], "validated_candidates": [], "confirmed_plates": []}

    if infer_frame is None or not _anpr_enabled:
        _status["raw_candidates_count"] = 0
        _status["validated_candidates_count"] = 0
        _status["confirmed_plates_count"] = 0
        return empty_result

    ih, iw = infer_frame.shape[:2]
    _status["input_width"] = orig_w
    _status["input_height"] = orig_h
    _status["inference_width"] = iw
    _status["inference_height"] = ih

    if _alpr is None or not _status["alpr_loaded"]:
        _status["raw_candidates_count"] = 0
        _status["validated_candidates_count"] = 0
        _status["confirmed_plates_count"] = 0
        return empty_result

    t0 = time.time()
    raw_candidates = []
    validated_candidates = []
    confirmed_plates = []

    try:
        results = _alpr.predict(infer_frame)
        t_dur = (time.time() - t0) * 1000
        _status["detection_ms"] = float(t_dur)
        _status["ocr_ms"] = float(t_dur)

        if results is not None:
            for item in results:
                bbox, det_conf, clean_text, ocr_conf = _extract_alpr_item(item, iw, ih)
                if bbox is None:
                    continue

                raw_candidates.append({
                    "bbox": bbox,
                    "confidence": round(det_conf, 3),
                    "detector": "fast_alpr",
                    "text": clean_text,
                    "ocr_confidence": round(ocr_conf, 3),
                })

                # Tier B Validation: valid text and confidence
                if len(clean_text) >= 4 and ocr_conf >= 0.35 and det_conf >= 0.30:
                    validated_candidates.append({
                        "bbox": bbox,
                        "confidence": round(det_conf, 3),
                        "detector": "fast_alpr",
                        "plate_text": clean_text,
                        "ocr_confidence": round(ocr_conf, 3),
                    })

    except Exception as e:
        _status["alpr_error"] = str(e)
        _status["exact_error"] = str(e)
        logger.error(f"FastALPR prediction error: {e}")
        return empty_result

    # --- Tier C: Temporal Consensus for Confirmed Plates ---
    now_t = time.time()
    matched_track_ids = set()

    for val in validated_candidates:
        v_box = val["bbox"]
        best_match_id = None
        best_iou = 0.0

        for t_id, track in _plate_tracks.items():
            if t_id in matched_track_ids:
                continue
            iou = _compute_iou(v_box, track["bbox"])
            if iou > 0.25 and iou > best_iou:
                best_iou = iou
                best_match_id = t_id

        if best_match_id is not None:
            tr = _plate_tracks[best_match_id]
            tr["bbox"] = v_box
            tr["hits"] += 1
            tr["det_conf"] = max(tr["det_conf"], val["confidence"])
            tr["last_seen"] = now_t
            tr["ocr_history"].append(val["plate_text"])
            tr["ocr_confs"].append(val["ocr_confidence"])
            matched_track_ids.add(best_match_id)
            target_track_id = best_match_id
        else:
            _track_counter += 1
            new_id = f"plate-track-{_track_counter}"
            _plate_tracks[new_id] = {
                "bbox": v_box,
                "hits": 1,
                "det_conf": val["confidence"],
                "detector": "fast_alpr",
                "ocr_history": [val["plate_text"]],
                "ocr_confs": [val["ocr_confidence"]],
                "last_saved_time": 0.0,
                "last_seen": now_t,
            }
            matched_track_ids.add(new_id)
            target_track_id = new_id

        tr = _plate_tracks[target_track_id]

        # Consensus: >= 3 readings with matching text
        if tr["hits"] >= 3 and len(tr["ocr_history"]) >= 3:
            counts = Counter(tr["ocr_history"])
            most_common_text, vote_count = counts.most_common(1)[0]
            if vote_count >= 3 and 4 <= len(most_common_text) <= 12:
                matching_confs = [
                    _to_float(c, 0.0)
                    for t, c in zip(tr["ocr_history"], tr["ocr_confs"])
                    if t == most_common_text
                ]
                avg_ocr_conf = float(np.mean(matching_confs)) if len(matching_confs) > 0 else 0.0

                confirmed_plates.append({
                    "id": target_track_id,
                    "bbox": tr["bbox"],
                    "confidence": tr["det_conf"],
                    "ocr_confidence": round(avg_ocr_conf, 2),
                    "plate_text": most_common_text,
                    "detector": "fast_alpr",
                    "status": "confirmed",
                })

                # Persist to store (rate-limited: max 1 per 30s per unique plate)
                if now_t - tr.get("last_saved_time", 0.0) >= 30.0:
                    tr["last_saved_time"] = now_t
                    anpr_store.add_record(
                        plate_text=most_common_text,
                        detector_confidence=tr["det_conf"],
                        ocr_confidence=avg_ocr_conf,
                        source_name=source_name,
                        bbox=tr["bbox"],
                        frame_sequence=frame_counter,
                    )

    # Cleanup stale tracks (> 3.0 seconds inactive)
    stale_ids = [t_id for t_id, tr in _plate_tracks.items() if now_t - tr["last_seen"] > 3.0]
    for s_id in stale_ids:
        del _plate_tracks[s_id]

    _status["raw_candidates_count"] = len(raw_candidates)
    _status["validated_candidates_count"] = len(validated_candidates)
    _status["confirmed_plates_count"] = len(confirmed_plates)

    return {
        "raw_candidates": raw_candidates,
        "validated_candidates": validated_candidates,
        "confirmed_plates": confirmed_plates,
    }


def _compute_iou(boxA: list, boxB: list) -> float:
    """Computes Intersection-over-Union safely for any coordinate representation."""
    try:
        xA = max(_to_float(boxA[0]), _to_float(boxB[0]))
        yA = max(_to_float(boxA[1]), _to_float(boxB[1]))
        xB = min(_to_float(boxA[2]), _to_float(boxB[2]))
        yB = min(_to_float(boxA[3]), _to_float(boxB[3]))
        inter = max(0.0, xB - xA) * max(0.0, yB - yA)
        areaA = max(1.0, (_to_float(boxA[2]) - _to_float(boxA[0])) * (_to_float(boxA[3]) - _to_float(boxA[1])))
        areaB = max(1.0, (_to_float(boxB[2]) - _to_float(boxB[0])) * (_to_float(boxB[3]) - _to_float(boxB[1])))
        return float(inter) / float(areaA + areaB - inter)
    except Exception:
        return 0.0


# Initialize on module load
load_anpr_engine()

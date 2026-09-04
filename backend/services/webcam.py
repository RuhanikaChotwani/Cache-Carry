"""Webcam and Video Capture Service for IBVAP.
Handles atomic source lifecycle, 4K downscaling, interleaved AI inference,
per-frame tamper-evidence hashing, and strict ANPR output separation.
"""

import os
import time
import threading
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Union, List, Dict

from services import face_engine, fcr_watchlist, anpr_engine, alert_store, ledger, video_manager

logger = logging.getLogger("ibvap.webcam")
logging.basicConfig(level=logging.INFO)

_has_cv2 = False
_has_np = False

try:
    import cv2
    import numpy as np
    _has_cv2 = True
    _has_np = True
except Exception:
    pass

# --- Global atomic lifecycle state ---
_lifecycle_lock = threading.Lock()
_stream_session_id = 0
_frame_session_id = 0

_cap = None
_running = False
_camera_error: Optional[str] = None
_last_frame_error: Optional[str] = None
_stop_event = threading.Event()
_analysis_thread: Optional[threading.Thread] = None

_frames_published = 0
_last_valid_frame_at = 0.0

# Source metadata
_source_type = "webcam"
_source_name = "Laptop Webcam 0"
_source_path: Union[int, str] = 0
_loop_enabled = True
_source_finished = False
_current_frame_number = 0
_total_frames = 0
_video_fps = 30.0

# FPS telemetry
_displayed_fps = 0.0
_inference_fps = 0.0

# Frame and detection cache
_latest_raw_frame: Optional[bytes] = None
_latest_annotated_frame: Optional[bytes] = None
_latest_debug_frame: Optional[bytes] = None
_latest_faces: List[dict] = []
_latest_confirmed_plates: List[dict] = []

_frame_width = 640
_frame_height = 480
_frame_lock = threading.Lock()
_detection_lock = threading.Lock()

_last_alert_time: Dict[str, float] = {}


def get_status() -> dict:
    global _running, _cap, _has_cv2, _camera_error, _last_frame_error
    global _frames_published, _last_valid_frame_at, _stream_session_id
    global _source_name, _source_type, _source_finished, _loop_enabled
    global _current_frame_number, _total_frames, _displayed_fps, _inference_fps
    global _frame_width, _frame_height

    is_open = False
    if _cap is not None and _has_cv2:
        try:
            is_open = bool(_cap.isOpened())
        except Exception:
            pass

    now = time.time()
    is_feed_active = (
        _running
        and is_open
        and _frames_published > 0
        and _last_valid_frame_at > 0
        and (now - _last_valid_frame_at < 2.0)
    )

    f_status = face_engine.get_face_engine_status() or {}
    a_status = anpr_engine.get_status() or {}

    yunet_loaded = bool(f_status.get("yunet_loaded", False))
    sface_loaded = bool(f_status.get("sface_loaded", False))
    alpr_loaded = bool(a_status.get("alpr_loaded", False))

    with _detection_lock:
        faces_count = len(_latest_faces) if is_feed_active else 0
        plates_count = len(_latest_confirmed_plates) if is_feed_active else 0

    return {
        "running": is_feed_active,
        "feed_active": is_feed_active,
        "is_camera_open": is_open,
        "session_id": _stream_session_id,
        "camera_error": _camera_error or _last_frame_error,
        "last_frame_error": _last_frame_error,
        "frames_published": _frames_published,
        "last_valid_frame_at": _last_valid_frame_at if _last_valid_frame_at > 0 else None,
        "source": _source_name if is_feed_active else (_camera_error or f"Connecting to {_source_name}..."),
        "source_type": _source_type,
        "source_name": _source_name,
        "source_finished": _source_finished,
        "loop_enabled": _loop_enabled,
        "frame_number": _current_frame_number,
        "total_frames": _total_frames if _total_frames > 0 else None,
        "displayed_fps": round(_displayed_fps, 1) if is_feed_active else 0.0,
        "inference_fps": round(_inference_fps, 1) if is_feed_active else 0.0,
        "face_count": faces_count,
        "plate_count": plates_count,
        "current_frame_width": _frame_width,
        "current_frame_height": _frame_height,
        "face_detector_name": "YuNet Face Detector (2023mar)",
        "watchlist_count": len(fcr_watchlist.get_watchlist()),
        "model_loading_state": {
            "yunet": yunet_loaded,
            "sface": sface_loaded,
            "fast_alpr": alpr_loaded,
        },
        "models": {
            "yunet": {"loaded": yunet_loaded, "error": f_status.get("yunet_error")},
            "sface": {"loaded": sface_loaded, "error": f_status.get("sface_error")},
            "fast_alpr": {"loaded": alpr_loaded, "error": a_status.get("alpr_error")},
        },
    }


def start(
    source: Union[int, str] = 0,
    source_type: str = "webcam",
    source_id: Optional[str] = None,
    source_name: Optional[str] = None,
    loop: bool = True,
) -> dict:
    """Atomic start of a video capture session."""
    global _cap, _running, _camera_error, _last_frame_error, _stop_event, _analysis_thread
    global _source_type, _source_name, _source_path, _loop_enabled, _source_finished
    global _current_frame_number, _total_frames, _video_fps, _stream_session_id, _frame_session_id
    global _frame_width, _frame_height, _displayed_fps, _inference_fps
    global _frames_published, _last_valid_frame_at
    global _latest_raw_frame, _latest_annotated_frame, _latest_debug_frame
    global _latest_faces, _latest_confirmed_plates

    with _lifecycle_lock:
        # 1. Signal and stop previous capture cleanly
        _stop_event.set()
        _running = False

        if _analysis_thread is not None and _analysis_thread.is_alive():
            if _analysis_thread != threading.current_thread():
                _analysis_thread.join(timeout=2.0)
            _analysis_thread = None

        if _cap is not None:
            try:
                _cap.release()
            except Exception:
                pass
            _cap = None

        # Stop frame chain writer from previous session
        ledger.stop_frame_chain()

        # 2. Increment session ID and reset all state
        _stream_session_id += 1
        current_session = _stream_session_id
        _frame_session_id = 0
        _stop_event.clear()
        _camera_error = None
        _last_frame_error = None
        _source_finished = False
        _current_frame_number = 0
        _total_frames = 0
        _video_fps = 30.0
        _displayed_fps = 0.0
        _inference_fps = 0.0
        _frames_published = 0
        _last_valid_frame_at = 0.0

        with _frame_lock:
            _latest_raw_frame = None
            _latest_annotated_frame = None
            _latest_debug_frame = None

        with _detection_lock:
            _latest_faces = []
            _latest_confirmed_plates = []

        if not _has_cv2:
            _camera_error = "OpenCV (cv2) is not installed."
            _running = False
            return get_status()

        # 3. Open capture source
        is_webcam = source_type == "webcam" or (source == 0 or str(source) == "0")

        if is_webcam:
            _source_type = "webcam"
            _loop_enabled = False
            _source_path = 0
            _source_name = source_name or "Laptop Webcam 0"

            try:
                _cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                if not _cap.isOpened():
                    _cap = cv2.VideoCapture(0)

                if not _cap.isOpened():
                    _camera_error = "Could not open laptop webcam (index 0). Check camera privacy permissions."
                    _cap = None
                    _running = False
                    return get_status()

                _cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                _cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                _cap.set(cv2.CAP_PROP_FPS, 30)
                _video_fps = 30.0
                _frame_width = 640
                _frame_height = 480

                # Flush initialization frames
                for _ in range(3):
                    _cap.read()

            except Exception as e:
                _camera_error = f"Webcam initialization error: {e}"
                _cap = None
                _running = False
                return get_status()
        else:
            _source_type = "uploaded_video" if source_type == "uploaded_video" else "demo_video"
            _loop_enabled = bool(loop)

            target_identifier = source_id or source
            resolved_path, resolved_name = video_manager.resolve_video_path(
                _source_type, target_identifier
            )

            if not resolved_path or not os.path.exists(resolved_path):
                _camera_error = f"Video file not found: {target_identifier}"
                _cap = None
                _running = False
                return get_status()

            _source_path = resolved_path
            _source_name = source_name or resolved_name

            try:
                _cap = cv2.VideoCapture(resolved_path)
                if not _cap.isOpened():
                    _camera_error = f"OpenCV could not open video: {os.path.basename(resolved_path)}"
                    _cap = None
                    _running = False
                    return get_status()

                fps_val = _cap.get(cv2.CAP_PROP_FPS)
                _video_fps = float(fps_val) if (fps_val and 5.0 <= fps_val <= 120.0) else 25.0
                total_f = _cap.get(cv2.CAP_PROP_FRAME_COUNT)
                _total_frames = int(total_f) if (total_f and total_f > 0) else 0

                vw = int(_cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
                vh = int(_cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
                _frame_width = vw if vw > 0 else 640
                _frame_height = vh if vh > 0 else 480

            except Exception as e:
                _camera_error = f"Error opening video: {e}"
                _cap = None
                _running = False
                return get_status()

        # 4. Start frame chain for this session
        session_str = f"session-{current_session}"
        ledger.start_frame_chain(session_str)

        # 5. Launch exactly one capture thread
        _running = True
        _analysis_thread = threading.Thread(
            target=_capture_loop,
            args=(current_session,),
            name=f"CaptureSession-{current_session}",
            daemon=True,
        )
        _analysis_thread.start()
        logger.info(
            f"Started session {current_session} for '{_source_name}' "
            f"({_frame_width}x{_frame_height} @ {_video_fps:.1f} FPS)"
        )
        return get_status()


def stop() -> dict:
    """Stops the active capture session atomically."""
    global _cap, _running, _latest_faces, _latest_confirmed_plates
    global _latest_raw_frame, _latest_annotated_frame, _latest_debug_frame
    global _stop_event, _analysis_thread, _stream_session_id, _frame_session_id
    global _frames_published, _last_valid_frame_at

    with _lifecycle_lock:
        _stop_event.set()
        _running = False

        if _analysis_thread is not None and _analysis_thread.is_alive():
            if _analysis_thread != threading.current_thread():
                _analysis_thread.join(timeout=2.0)
            _analysis_thread = None

        if _cap is not None:
            try:
                _cap.release()
            except Exception:
                pass
            _cap = None

        ledger.stop_frame_chain()
        _frames_published = 0
        _last_valid_frame_at = 0.0

        with _detection_lock:
            _latest_faces = []
            _latest_confirmed_plates = []

        with _frame_lock:
            _latest_raw_frame = None
            _latest_annotated_frame = None
            _latest_debug_frame = None
            _frame_session_id = 0

        logger.info("Stopped active capture stream.")
        return get_status()


def raw_mjpeg_generator(session_id: Optional[int] = None):
    """Streams unannotated JPEG frames from the active session only."""
    while True:
        if session_id is not None and session_id != _stream_session_id:
            break

        frame_bytes = None
        current_sess = _stream_session_id
        with _frame_lock:
            if _frame_session_id == current_sess and _latest_raw_frame is not None:
                frame_bytes = _latest_raw_frame

        if frame_bytes is None or len(frame_bytes) < 4000:
            if _camera_error:
                frame_bytes = _draw_status_card("SOURCE ERROR", _camera_error, (239, 75, 95))
            elif _source_finished:
                frame_bytes = _draw_status_card("PLAYBACK COMPLETED", f"Source: {_source_name}", (22, 185, 201))
            elif not _running:
                frame_bytes = _draw_status_card("SENSOR STANDBY", "Select video source or start webcam", (22, 185, 201))
            else:
                frame_bytes = _draw_status_card("CONNECTING...", f"Connecting to {_source_name}...", (255, 159, 67))

        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
        time.sleep(0.03)


def ai_mjpeg_generator(session_id: Optional[int] = None):
    """Streams annotated JPEG frames from the active session only."""
    while True:
        if session_id is not None and session_id != _stream_session_id:
            break

        frame_bytes = None
        current_sess = _stream_session_id
        with _frame_lock:
            if _frame_session_id == current_sess and _latest_annotated_frame is not None:
                frame_bytes = _latest_annotated_frame

        if frame_bytes is None or len(frame_bytes) < 4000:
            if _camera_error:
                frame_bytes = _draw_status_card("SOURCE ERROR", _camera_error, (239, 75, 95))
            elif _source_finished:
                frame_bytes = _draw_status_card("PLAYBACK COMPLETED", f"Source: {_source_name}", (22, 185, 201))
            elif not _running:
                frame_bytes = _draw_status_card("SENSOR STANDBY", "Select video source or start webcam", (22, 185, 201))
            else:
                frame_bytes = _draw_status_card("CONNECTING...", f"Connecting to {_source_name}...", (255, 159, 67))

        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
        time.sleep(0.03)


def get_debug_face_frame() -> bytes:
    with _frame_lock:
        if _latest_debug_frame is not None:
            return _latest_debug_frame
    return _draw_status_card("DIAGNOSTIC FEED", "Start a source to generate diagnostic frames")


def get_detections_payload() -> dict:
    """Returns JSON detection payload. Only confirmed plates in normal UI."""
    with _detection_lock:
        faces_list = list(_latest_faces)
        confirmed_list = list(_latest_confirmed_plates)

    f_status = face_engine.get_face_engine_status() or {}

    return {
        "faces": faces_list,
        "plates": confirmed_list,
        "counts": {
            "faces": len(faces_list),
            "plates": len(confirmed_list),
        },
        "debug": {
            "face_detector_loaded": bool(f_status.get("yunet_loaded", False)),
            "face_detector_name": "YuNet Face Detector (2023mar)",
            "displayed_fps": round(_displayed_fps, 1),
            "inference_fps": round(_inference_fps, 1),
        },
    }


# --- Main capture and analysis loop ---

def _capture_loop(session_id: int):
    global _latest_raw_frame, _latest_annotated_frame, _latest_debug_frame
    global _latest_faces, _latest_confirmed_plates
    global _frame_width, _frame_height, _camera_error, _last_frame_error, _current_frame_number
    global _source_finished, _running, _cap, _stream_session_id, _frame_session_id
    global _displayed_fps, _inference_fps, _frames_published, _last_valid_frame_at

    frame_interval = 1.0 / max(10.0, min(_video_fps, 60.0))
    frame_counter = 0

    cached_faces_payload = []
    cached_confirmed_plates = []

    raw_candidates = []
    accepted_faces = []
    rejected_candidates = []
    detector_name = "yunet"

    fps_t0 = time.time()
    disp_count = 0
    infer_count = 0

    while not _stop_event.is_set():
        if session_id != _stream_session_id:
            break

        loop_start = time.time()
        try:
            if _cap is None or not _has_cv2 or not _cap.isOpened():
                _stop_event.wait(0.05)
                continue

            ret, frame = _cap.read()

            if not ret or frame is None:
                if _source_type != "webcam":
                    if _loop_enabled:
                        _cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = _cap.read()
                        if not ret or frame is None:
                            if session_id == _stream_session_id:
                                _source_finished = True
                                _running = False
                            break
                    else:
                        if session_id == _stream_session_id:
                            _source_finished = True
                            _running = False
                        break
                else:
                    _last_frame_error = "Webcam read returned empty frame"
                    _stop_event.wait(0.05)
                    continue

            frame_counter += 1
            disp_count += 1

            if _source_type != "webcam":
                try:
                    _current_frame_number = int(_cap.get(cv2.CAP_PROP_POS_FRAMES))
                except Exception:
                    _current_frame_number = frame_counter
            else:
                _current_frame_number = frame_counter

            h, w = frame.shape[:2]
            _frame_width = w
            _frame_height = h

            # --- Downscaled copies ---
            # Inference copy: max width 960
            infer_scale = 960.0 / w if w > 960 else 1.0
            if infer_scale < 1.0:
                infer_w = 960
                infer_h = int(h * infer_scale)
                infer_frame = cv2.resize(frame, (infer_w, infer_h))
            else:
                infer_frame = frame

            # Display copy: max width 1280
            disp_scale = 1280.0 / w if w > 1280 else 1.0
            if disp_scale < 1.0:
                disp_w = 1280
                disp_h = int(h * disp_scale)
                disp_frame = cv2.resize(frame, (disp_w, disp_h))
            else:
                disp_frame = frame

            # --- Per-frame tamper-evidence hash ---
            _, raw_jpg_for_hash = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            raw_hash_bytes = raw_jpg_for_hash.tobytes()
            ledger.enqueue_frame_hash(
                raw_hash_bytes,
                frame_counter,
                _source_name,
            )

            # --- Interleaved AI inference ---
            run_face_ai = (frame_counter % 3 == 0) or (frame_counter <= 2)
            run_plate_ai = (
                (frame_counter % 3 == 0) or (frame_counter <= 2)
            ) and anpr_engine.is_anpr_enabled()

            if run_face_ai:
                infer_count += 1
                accepted_faces, raw_candidates, rejected_candidates, detector_name = (
                    face_engine.detect_faces_debug(infer_frame)
                )
                watchlist = fcr_watchlist.get_watchlist()

                new_faces_payload = []
                for idx, f in enumerate(accepted_faces):
                    bx1, by1, bx2, by2 = f["bbox"]
                    orig_bbox = [
                        max(0, int(bx1 / infer_scale)),
                        max(0, int(by1 / infer_scale)),
                        min(w, int(bx2 / infer_scale)),
                        min(h, int(by2 / infer_scale)),
                    ]
                    conf = f["confidence"]
                    emb = f["embedding"]
                    face_id = f"face-{idx + 1}"

                    match_target, score, is_match = face_engine.compare_embedding(
                        emb, watchlist, threshold=0.55
                    )

                    if is_match and match_target:
                        identity_name = match_target["name"]
                        face_obj = {
                            "id": face_id,
                            "bbox": orig_bbox,
                            "confidence": conf,
                            "identity": identity_name,
                            "possible_match": True,
                            "match_score": score,
                        }
                        _handle_match_alert(identity_name, score, face_id, raw_hash_bytes)
                    else:
                        face_obj = {
                            "id": face_id,
                            "bbox": orig_bbox,
                            "confidence": conf,
                            "identity": "Unknown",
                            "possible_match": False,
                            "match_score": None,
                        }
                    new_faces_payload.append(face_obj)

                cached_faces_payload = new_faces_payload

            if run_plate_ai:
                anpr_result = anpr_engine.process_anpr_frame(
                    infer_frame=infer_frame,
                    source_name=_source_name,
                    orig_w=w,
                    orig_h=h,
                    frame_counter=frame_counter,
                )

                scaled_confirmed = []
                for p in anpr_result.get("confirmed_plates", []):
                    px1, py1, px2, py2 = p["bbox"]
                    scaled_confirmed.append({
                        "id": p.get("id"),
                        "bbox": [
                            max(0, int(px1 / infer_scale)),
                            max(0, int(py1 / infer_scale)),
                            min(w, int(px2 / infer_scale)),
                            min(h, int(py2 / infer_scale)),
                        ],
                        "confidence": p["confidence"],
                        "ocr_confidence": p.get("ocr_confidence"),
                        "plate_text": p.get("plate_text"),
                        "status": "confirmed",
                    })

                    # Record evidence for confirmed plate
                    ledger.record_evidence_event(
                        event_type="confirmed_plate",
                        source_name=_source_name,
                        evidence_jpeg_bytes=raw_hash_bytes,
                        metadata={
                            "plate_text": p.get("plate_text"),
                            "confidence": p["confidence"],
                        },
                    )

                cached_confirmed_plates = scaled_confirmed

            if run_face_ai or run_plate_ai:
                with _detection_lock:
                    if session_id == _stream_session_id:
                        _latest_faces = cached_faces_payload
                        _latest_confirmed_plates = cached_confirmed_plates

            # --- Encode display frames ---
            _, r_jpg = cv2.imencode(".jpg", disp_frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            raw_bytes = r_jpg.tobytes()

            annotated_frame = disp_frame.copy()
            _draw_surveillance_overlay(
                annotated_frame, cached_faces_payload, cached_confirmed_plates,
                _source_name, disp_scale,
            )
            _, a_jpg = cv2.imencode(".jpg", annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            annotated_bytes = a_jpg.tobytes()

            if run_face_ai or run_plate_ai:
                debug_frame = disp_frame.copy()
                _draw_debug_overlay(
                    debug_frame, raw_candidates, accepted_faces, rejected_candidates,
                    detector_name, disp_scale,
                )
                _, d_jpg = cv2.imencode(".jpg", debug_frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                debug_bytes = d_jpg.tobytes()
            else:
                debug_bytes = None

            # Publish frames for this session only
            if session_id == _stream_session_id and len(annotated_bytes) >= 4000:
                with _frame_lock:
                    _latest_raw_frame = raw_bytes
                    _latest_annotated_frame = annotated_bytes
                    if debug_bytes is not None:
                        _latest_debug_frame = debug_bytes
                    _frame_session_id = session_id
                    _frames_published += 1
                    _last_valid_frame_at = time.time()
                    _last_frame_error = None

            # FPS telemetry
            now = time.time()
            if now - fps_t0 >= 1.0:
                _displayed_fps = disp_count / (now - fps_t0)
                _inference_fps = infer_count / (now - fps_t0)
                disp_count = 0
                infer_count = 0
                fps_t0 = now
                anpr_engine.update_fps_metric(_displayed_fps)

        except Exception as e:
            logger.warning(f"Frame processing error: {e}")
            _last_frame_error = str(e)

        elapsed = time.time() - loop_start
        sleep_dur = max(0.001, frame_interval - elapsed)
        time.sleep(sleep_dur)

    # Session ended - stop chain writer only if this is still the active session
    if session_id == _stream_session_id:
        ledger.stop_frame_chain()


def _draw_surveillance_overlay(frame, faces, confirmed_plates, source_title, disp_scale):
    """Draws HUD: face boxes and confirmed plate boxes only."""
    if not _has_cv2:
        return

    h, w = frame.shape[:2]

    # Top status bar
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 32), (10, 18, 28), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    label = f"[LIVE] {source_title.upper()}"
    if len(label) > 35:
        label = label[:32] + "..."

    cv2.putText(frame, label, (12, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0, 255, 120), 1, cv2.LINE_AA)

    match_count = sum(1 for f in faces if f.get("possible_match"))
    cv2.putText(frame, f"FACES: {len(faces)}", (w - 240, 21),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 220, 255), 1, cv2.LINE_AA)
    cv2.putText(frame, f"PLATES: {len(confirmed_plates)}", (w - 150, 21),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 0), 1, cv2.LINE_AA)

    if match_count > 0:
        cv2.putText(frame, f"MATCHES: {match_count}", (w - 70, 21),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 30, 255), 1, cv2.LINE_AA)

    # Face bounding boxes
    for f in faces:
        ox1, oy1, ox2, oy2 = f["bbox"]
        x1 = max(0, min(w - 1, int(ox1 * disp_scale)))
        y1 = max(0, min(h - 1, int(oy1 * disp_scale)))
        x2 = max(x1 + 1, min(w, int(ox2 * disp_scale)))
        y2 = max(y1 + 1, min(h, int(oy2 * disp_scale)))

        is_match = f.get("possible_match", False)
        identity = f.get("identity", "Unknown")
        conf = f.get("confidence", 0.9)

        if is_match:
            color = (0, 30, 255)
            lbl = f"MATCH: {identity.upper()}"
        else:
            color = (0, 230, 100)
            lbl = f"FACE [{int(conf * 100)}%]"

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        bw = max(80, len(lbl) * 7 + 8)
        cv2.rectangle(frame, (x1, max(0, y1 - 18)), (x1 + bw, y1), color, -1)
        cv2.putText(frame, lbl, (x1 + 4, max(13, y1 - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255) if is_match else (0, 0, 0), 1, cv2.LINE_AA)

    # Confirmed plate boxes (GREEN only)
    for p in confirmed_plates:
        ox1, oy1, ox2, oy2 = p["bbox"]
        px1 = max(0, min(w - 1, int(ox1 * disp_scale)))
        py1 = max(0, min(h - 1, int(oy1 * disp_scale)))
        px2 = max(px1 + 1, min(w, int(ox2 * disp_scale)))
        py2 = max(py1 + 1, min(h, int(oy2 * disp_scale)))
        p_text = p.get("plate_text", "")
        ocr_conf = p.get("ocr_confidence")
        if p_text and ocr_conf is not None:
            p_label = f"PLATE: {p_text} [{int(ocr_conf * 100)}%]"
        elif p_text:
            p_label = f"PLATE: {p_text}"
        else:
            p_label = "Plate detected; text unreadable"

        cv2.rectangle(frame, (px1, py1), (px2, py2), (0, 255, 0), 3)
        bw = max(100, len(p_label) * 7 + 10)
        cv2.rectangle(frame, (px1, max(0, py1 - 18)), (px1 + bw, py1), (0, 255, 0), -1)
        cv2.putText(frame, p_label, (px1 + 4, max(13, py1 - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1, cv2.LINE_AA)


def _draw_debug_overlay(frame, raw_candidates, accepted_faces, rejected_candidates, detector_name, disp_scale):
    """Diagnostic overlay showing all raw and accepted detections."""
    if not _has_cv2:
        return
    h, w = frame.shape[:2]

    cv2.rectangle(frame, (0, 0), (w, 36), (15, 20, 30), -1)
    txt = f"DIAGNOSTIC: {detector_name.upper()} | RAW: {len(raw_candidates)} | ACCEPTED: {len(accepted_faces)}"
    cv2.putText(frame, txt, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 220, 255), 1, cv2.LINE_AA)

    for c in raw_candidates:
        x1, y1, x2, y2, score, dname = c
        dx1, dy1 = int(x1 * disp_scale), int(y1 * disp_scale)
        dx2, dy2 = int(x2 * disp_scale), int(y2 * disp_scale)
        cv2.rectangle(frame, (dx1, dy1), (dx2, dy2), (0, 255, 255), 1)

    for acc in accepted_faces:
        x1, y1, x2, y2 = acc["bbox"]
        conf = acc["confidence"]
        dx1, dy1 = int(x1 * disp_scale), int(y1 * disp_scale)
        dx2, dy2 = int(x2 * disp_scale), int(y2 * disp_scale)
        cv2.rectangle(frame, (dx1, dy1), (dx2, dy2), (0, 255, 0), 2)
        cv2.putText(frame, f"ACCEPTED ({conf * 100:.0f}%)", (dx1, max(12, dy1 - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1, cv2.LINE_AA)


def _handle_match_alert(name, score, face_id, evidence_bytes=None):
    """Rate-limited alert for real watchlist matches."""
    global _last_alert_time
    now_t = time.time()
    last_t = _last_alert_time.get(name, 0.0)

    if now_t - last_t > 5.0:
        _last_alert_time[name] = now_t
        alert_id = f"alert-{uuid.uuid4().hex[:6]}"
        now_iso = datetime.utcnow().isoformat() + "Z"

        alert_obj = {
            "id": alert_id,
            "time": now_iso,
            "type": "FCR Possible Match",
            "level": "High",
            "message": f"Possible watchlist match: {name} (Similarity: {score})",
            "evidence_saved": True,
        }
        alert_store.add_alert(alert_obj)

        meta = {"target": name, "similarity": score, "face_id": face_id}
        ledger.record_evidence_event(
            event_type="fcr_match",
            source_name=_source_name,
            evidence_jpeg_bytes=evidence_bytes,
            metadata=meta,
        )
        fcr_watchlist.log_match({"time": now_iso, "name": name, "score": score, "face_id": face_id})


def _draw_status_card(title, message, color=(22, 185, 201)):
    if _has_cv2:
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[:] = (10, 16, 24)
        cv2.rectangle(img, (20, 20), (620, 460), (22, 35, 50), 1)
        cv2.putText(img, "IBVAP FCR SURVEILLANCE", (40, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 130, 160), 1)
        cv2.putText(img, title, (40, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color[::-1], 2)
        cv2.putText(img, message, (40, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 200, 220), 1)
        cv2.putText(img, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), (40, 430),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, (70, 95, 120), 1)
        _, jpeg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return jpeg.tobytes()
    return (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
        b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
        b"\x1f\x1e\x1d\x1a\x1c\x1c $.\' \",#\x1c\x1c(7),01444"
        b"\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01"
        b"\x11\x00\xff\xda\x00\x08\x01\x01\x00\x00?\x00T\xdb\x9e\xa3"
        b"\x13\xa0\x00\x1c\xff\xd9"
    )

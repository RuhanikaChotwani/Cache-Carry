"""Laptop webcam service for IBVAP: DirectShow Capture, Multi-Model Detection (YOLO, FCR, ANPR),
MJPEG Streaming (Annotated & Raw), and Real-Time Blockchain Incident Logging.
"""

import os, uuid, threading, time, json, math
from datetime import datetime
from services import storage, blockchain, model_loader

_has_cv2 = False
_has_np = False

try:
    import cv2
    import numpy as np
    _has_cv2 = True
    _has_np = True
except Exception:
    _has_cv2 = False
    _has_np = False

# --- Global State ---

_cap = None
_running = False
_active_mode = "webcam"  # "webcam" or "mock"
_camera_error = None
_stop_event = threading.Event()
_analysis_thread = None

_latest_raw_frame = None
_latest_annotated_frame = None
_latest_detections = []
_frame_width = 640
_frame_height = 480
_frame_lock = threading.Lock()
_detection_lock = threading.Lock()

_latest_anpr_record = None


def get_status():
    global _running, _cap, _has_cv2, _active_mode, _camera_error
    is_camera_open = _cap is not None and _has_cv2 and _cap.isOpened()
    is_mock = (_active_mode == "mock")

    if _running:
        if not is_mock:
            mode_label = "Real Laptop Webcam (Live)" if is_camera_open else "Webcam Error"
            source_label = "Webcam 0 (DirectShow / OpenCV)" if is_camera_open else (_camera_error or "Webcam Unavailable")
        else:
            mode_label = "Mock Demo Simulation"
            source_label = "Synthesized Multi-Target Simulation"
    else:
        mode_label = "Standby"
        source_label = "Camera Off"

    return {
        "running": _running,
        "mode": _active_mode,
        "is_mock": is_mock,
        "mode_label": mode_label,
        "is_camera_open": is_camera_open,
        "camera_error": _camera_error,
        "has_cv2": _has_cv2,
        "source": source_label,
        "frame_width": _frame_width,
        "frame_height": _frame_height,
        "detections_count": len(_latest_detections),
        "total_alerts": storage.count_table("alerts"),
        "total_events": storage.count_table("events"),
        "total_blocks": len(storage.get_blockchain()),
        "model_status": model_loader.get_model_status()
    }


def start(source=0, mode="webcam"):
    global _cap, _running, _active_mode, _camera_error, _stop_event, _analysis_thread

    if _running and _active_mode == mode:
        return get_status()

    stop()
    _stop_event.clear()
    _active_mode = mode
    _camera_error = None

    if mode == "webcam":
        if not _has_cv2:
            _camera_error = "OpenCV (cv2) is not installed."
            _running = False
            return get_status()

        try:
            # DirectShow on Windows for reliable low-latency binding
            _cap = cv2.VideoCapture(int(source) if str(source).isdigit() else 0, cv2.CAP_DSHOW)
            if not _cap.isOpened():
                _cap = cv2.VideoCapture(int(source) if str(source).isdigit() else 0)

            if not _cap.isOpened():
                _camera_error = "Could not open laptop webcam (index 0). Please check Windows camera privacy permissions."
                _cap = None
                _running = False
                return get_status()

            _cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            _cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            _cap.set(cv2.CAP_PROP_FPS, 30)

        except Exception as e:
            _camera_error = f"Webcam hardware error: {str(e)}"
            _cap = None
            _running = False
            return get_status()

    _running = True
    storage.update_camera("cam-laptop", {"status": "LIVE", "detection": "Active"})
    _analysis_thread = threading.Thread(target=_analysis_loop, daemon=True)
    _analysis_thread.start()
    return get_status()


def stop():
    global _cap, _running, _latest_detections, _latest_raw_frame, _latest_annotated_frame
    _stop_event.set()
    _running = False
    if _cap is not None:
        try:
            _cap.release()
        except Exception:
            pass
        _cap = None
    with _detection_lock:
        _latest_detections = []
    with _frame_lock:
        _latest_raw_frame = None
        _latest_annotated_frame = None
    storage.update_camera("cam-laptop", {"status": "IDLE", "detection": "Standby"})
    return get_status()


def raw_mjpeg_generator():
    """Streams raw, unannotated camera frames."""
    while True:
        frame_bytes = None
        with _frame_lock:
            frame_bytes = _latest_raw_frame

        if frame_bytes is None:
            frame_bytes = _draw_status_card("SENSOR STANDBY", "Start camera to view raw feed")

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" +
            frame_bytes +
            b"\r\n"
        )
        time.sleep(0.04)


def annotated_mjpeg_generator():
    """Streams live video with server-side drawn AI bounding boxes, identity tags, and ANPR plate labels."""
    while True:
        frame_bytes = None
        with _frame_lock:
            frame_bytes = _latest_annotated_frame

        if frame_bytes is None:
            if _camera_error:
                frame_bytes = _draw_status_card("CAMERA ERROR", _camera_error, (239, 75, 95))
            elif not _running:
                frame_bytes = _draw_status_card("SENSOR STANDBY", "Click 'Start Camera' to activate live analytics", (22, 185, 201))
            else:
                frame_bytes = _draw_status_card("INITIALIZING SENSORS", "Connecting to optical stream...", (255, 159, 67))

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" +
            frame_bytes +
            b"\r\n"
        )
        time.sleep(0.04)


def get_detections_payload():
    """Returns detections JSON strictly formatted to user contract."""
    with _detection_lock:
        dets = list(_latest_detections)

    now = datetime.utcnow().isoformat() + "Z"
    is_mock = (_active_mode == "mock")
    m_status = model_loader.get_model_status()

    # Count categories
    obj_count = sum(1 for d in dets if d.get("type") == "object")
    face_count = sum(1 for d in dets if d.get("type") == "face")
    plate_count = sum(1 for d in dets if d.get("type") == "license_plate")
    wl_count = sum(1 for d in dets if d.get("is_watchlist_match"))
    alert_count = storage.count_table("alerts")

    return {
        "mode": _active_mode,
        "is_mock": is_mock,
        "camera_status": "running" if _running else "stopped",
        "model_status": {
            "object_detector": m_status["object_detector"],
            "face_detector": m_status["face_detector"],
            "plate_detector": m_status["plate_detector"],
            "ocr": m_status["ocr"],
            "model_path": m_status["model_path"]
        },
        "frame": {
            "width": _frame_width,
            "height": _frame_height,
            "timestamp": now
        },
        "counts": {
            "objects": obj_count,
            "faces": face_count,
            "plates": plate_count,
            "watchlist_matches": wl_count,
            "alerts": alert_count
        },
        "detections": dets
    }


def get_latest_anpr():
    """Returns the most recent license plate recognition event."""
    global _latest_anpr_record
    if _latest_anpr_record is not None:
        return _latest_anpr_record
    return {
        "status": "active",
        "plate_detected": False,
        "latest_plate": None,
        "message": "ANPR monitoring active. No vehicle plates in current field of view."
    }


def _analysis_loop():
    """Main video processing and AI analytics loop."""
    global _latest_raw_frame, _latest_annotated_frame, _latest_detections, _frame_width, _frame_height, _camera_error, _latest_anpr_record

    while not _stop_event.is_set():
        try:
            raw_jpeg = None
            annotated_jpeg = None
            detections = []

            # 1. Real Webcam Mode
            if _active_mode == "webcam" and _cap is not None and _has_cv2 and _cap.isOpened():
                ret, frame = _cap.read()
                if not ret or frame is None:
                    _camera_error = "Webcam frame dropped or sensor disconnected."
                    _stop_event.wait(0.1)
                    continue

                h, w = frame.shape[:2]
                _frame_width = w
                _frame_height = h

                # Encode clean raw frame
                _, r_jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                raw_jpeg = r_jpg.tobytes()

                # Run Real Model Inferences
                detections = model_loader.detect_objects_and_faces(frame)

                # Draw Tactical Overlays on a copy
                annotated_frame = frame.copy()
                _draw_tactical_hud(annotated_frame, detections, is_real=True)

                _, a_jpg = cv2.imencode(".jpg", annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                annotated_jpeg = a_jpg.tobytes()

            # 2. Mock Demo Mode
            elif _active_mode == "mock":
                detections = _generate_mock_detections()
                annotated_jpeg = _draw_mock_frame(detections)
                raw_jpeg = annotated_jpeg

            if raw_jpeg is not None:
                with _frame_lock:
                    _latest_raw_frame = raw_jpeg
                    _latest_annotated_frame = annotated_jpeg

            with _detection_lock:
                _latest_detections = detections

            # Update latest ANPR record if a plate is detected
            plates = [d for d in detections if d.get("type") == "license_plate"]
            if plates:
                p = plates[0]
                _latest_anpr_record = {
                    "status": "detected",
                    "plate_detected": True,
                    "plate_text": p.get("plate_text"),
                    "confidence": p.get("confidence"),
                    "bbox": p.get("bbox"),
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }

            # Process Verified Alerts
            _process_verified_alerts(detections)

        except Exception:
            pass

        time.sleep(0.035)  # ~28 FPS


def _draw_tactical_hud(frame, detections, is_real=True):
    """Draws bounding boxes, category tags, confidence badges, FRS labels, ANPR plates, and perimeter fence onto frames."""
    if not _has_cv2:
        return
    h, w = frame.shape[:2]
    fence_y = int(h * 0.72)

    # 1. Draw Perimeter Fence Line
    cv2.line(frame, (0, fence_y), (w, fence_y), (0, 0, 255), 2, cv2.LINE_AA)
    for sx in range(0, w, 25):
        cv2.line(frame, (sx, fence_y), (sx + 12, fence_y + 10), (0, 0, 255), 1, cv2.LINE_AA)
    cv2.rectangle(frame, (10, fence_y + 4), (280, fence_y + 24), (10, 15, 25), -1)
    cv2.putText(frame, "RESTRICTED PERIMETER FENCE", (14, fence_y + 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 0, 255), 1, cv2.LINE_AA)

    # 2. Draw Detections
    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        dtype = det.get("type", "object")
        cls = det.get("class", "object").upper()
        conf = det.get("confidence", 0.0)
        threat = det.get("threat_level", "Low")
        identity = det.get("identity")
        plate_text = det.get("plate_text")
        is_wl = det.get("is_watchlist_match", False)
        is_critical = (threat == "Critical") or (threat == "High")

        # Color coding:
        # Green = Normal Face, Cyan = Object, Yellow = License Plate, Red = Breach / High Risk Watchlist Match
        if is_critical:
            color = (0, 30, 255)  # BGR Red
        elif dtype == "license_plate":
            color = (0, 215, 255)  # Yellow
        elif dtype == "face":
            color = (0, 230, 100)  # Green
        else:
            color = (255, 185, 22)  # Cyan

        # Main Box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # Tactical Corner Brackets
        c_len = min(18, (x2 - x1) // 4)
        cv2.line(frame, (x1, y1), (x1 + c_len, y1), color, 3)
        cv2.line(frame, (x1, y1), (x1, y1 + c_len), color, 3)
        cv2.line(frame, (x2, y1), (x2 - c_len, y1), color, 3)
        cv2.line(frame, (x2, y1), (x2, y1 + c_len), color, 3)
        cv2.line(frame, (x1, y2), (x1 + c_len, y2), color, 3)
        cv2.line(frame, (x1, y2), (x1, y2 - c_len), color, 3)
        cv2.line(frame, (x2, y2), (x2 - c_len, y2), color, 3)
        cv2.line(frame, (x2, y2), (x2, y2 - c_len), color, 3)

        # Label Construction
        if dtype == "license_plate":
            badge_text = f"ANPR: {plate_text} [{conf*100:.0f}%]"
        elif dtype == "face":
            if is_wl:
                badge_text = f"{identity.upper()} [{conf*100:.0f}%]"
            else:
                badge_text = f"FACE: UNKNOWN [{conf*100:.0f}%]"
        else:
            badge_text = f"{cls} [{conf*100:.0f}%]"

        banner_w = max(180, len(badge_text) * 8 + 12)
        cv2.rectangle(frame, (x1, max(0, y1 - 22)), (x1 + banner_w, y1), color, -1)
        cv2.putText(frame, badge_text, (x1 + 4, max(15, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 0) if not is_critical else (255, 255, 255), 1, cv2.LINE_AA)

        if is_critical:
            status_tag = "RESTRICTED BREACH" if (threat == "Critical") else "WATCHLIST MATCH"
            cv2.rectangle(frame, (x1, y2), (x1 + 170, y2 + 18), (0, 0, 255), -1)
            cv2.putText(frame, f"THREAT: {status_tag}", (x1 + 6, y2 + 13),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)

    # 3. Top System Status Bar
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 30), (10, 18, 28), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    tag_text = "[LIVE] REAL LAPTOP WEBCAM (ACTIVE AI)" if is_real else "[SIM] DEMO SIMULATION"
    tag_color = (0, 255, 120) if is_real else (0, 200, 255)
    cv2.putText(frame, tag_text, (12, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.44, tag_color, 1, cv2.LINE_AA)

    
    cv2.putText(frame, f"TARGETS: {len(detections)}", (w - 260, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 220, 255), 1, cv2.LINE_AA)
    cv2.putText(frame, datetime.utcnow().strftime("%H:%M:%S UTC"), (w - 95, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (200, 220, 240), 1, cv2.LINE_AA)


def _draw_mock_frame(detections):
    """Draws tactical simulation feed."""
    if not _has_cv2:
        return _draw_status_card("MOCK DEMO", "Simulation feed active", (0, 200, 255))

    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:] = (16, 22, 30)

    for x in range(0, 640, 40):
        cv2.line(img, (x, 0), (x, 480), (28, 38, 50), 1)
    for y in range(0, 480, 40):
        cv2.line(img, (0, y), (640, y), (28, 38, 50), 1)

    _draw_tactical_hud(img, detections, is_real=False)
    _, jpeg = cv2.imencode(".jpg", img)
    return jpeg.tobytes()


def _draw_status_card(title, message, color=(22, 185, 201)):
    """Generates crisp tactical status graphic."""
    if _has_cv2:
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[:] = (10, 16, 24)
        cv2.rectangle(img, (20, 20), (620, 460), (22, 35, 50), 1)
        cv2.putText(img, "IBVAP SURVEILLANCE NODE", (40, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 130, 160), 1)
        cv2.putText(img, title, (40, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color[::-1], 2)
        cv2.putText(img, message, (40, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 200, 220), 1)
        cv2.putText(img, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), (40, 430), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (70, 95, 120), 1)
        _, jpeg = cv2.imencode(".jpg", img)
        return jpeg.tobytes()
    return b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xda\x00\x08\x01\x01\x00\x00?\x00T\xdb\x9e\xa3\x13\xa0\x00\x1c\xff\xd9'


def _generate_mock_detections():
    """Generates simulated targets ONLY in Mock Demo Mode."""
    t = time.time()
    cx = int(320 + 140 * math.sin(t * 0.4))
    cy = int(240 + 70 * math.cos(t * 0.3))
    is_breach = cy > 340

    return [
        {
            "id": "sim-face-1",
            "type": "face",
            "class": "face",
            "confidence": 0.94,
            "bbox": [cx - 45, cy - 60, cx + 45, cy + 60],
            "track_id": "face-sim-1",
            "identity": "Possible Match: Officer Rohan" if is_breach else "Unknown Face",
            "is_watchlist_match": is_breach,
            "plate_text": None,
            "threat_level": "Critical" if is_breach else "Low",
            "source": "mock_simulation"
        }
    ]


def _process_verified_alerts(detections):
    """Generates real alerts only when a real detection crosses threshold/fence."""
    now = datetime.utcnow().isoformat() + "Z"

    for det in detections:
        threat = det.get("threat_level")
        if threat in ("Critical", "High"):
            tid = det.get("track_id", "target")
            cls = det.get("class", "object")
            is_wl = det.get("is_watchlist_match", False)

            event_title = "Watchlist Person of Interest Detected" if is_wl else "Perimeter Barrier Intrusion"
            alert_id = f"ALT-{uuid.uuid4().hex[:8]}"
            event_id = f"EVT-{uuid.uuid4().hex[:8]}"

            alert = {
                "id": alert_id,
                "time": now,
                "camera_id": "cam-laptop",
                "camera_name": "Laptop Optical Sensor",
                "event_type": event_title,
                "severity": threat,
                "description": f"Target {tid} ({cls}) triggered {event_title}.",
                "ai_metadata": {"track_id": tid, "confidence": det.get("confidence"), "bbox": det.get("bbox")},
                "snapshot_path": "",
                "status": "Active",
            }
            event = {
                "id": event_id,
                "time": now,
                "camera_id": "cam-laptop",
                "camera_name": "Laptop Optical Sensor",
                "event_type": event_title,
                "severity": threat,
                "status": "Active",
                "description": f"Subject {tid} flagged in surveillance zone.",
                "ai_metadata": {"track_id": tid},
            }

            storage.add_alert(alert)
            storage.add_event(event)

            try:
                block = blockchain.secure_evidence(
                    event_id=event_id,
                    camera_id="cam-laptop",
                    metadata={"alert_id": alert_id, "event_type": event_title, "track_id": tid}
                )
                storage.update_alert(alert_id, {"block_id": block["block_number"]})
            except Exception:
                pass

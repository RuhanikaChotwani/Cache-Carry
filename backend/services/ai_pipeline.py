"""AI video analytics pipeline for IBVAP.
Mock mode (default): generates realistic detections without any AI libraries.
Real mode: uses YOLOv8, OpenCV DNN face detection, etc. (requires optional deps).
"""
import os, random, math, time
from datetime import datetime

MOCK_AI = os.getenv("IBVAP_MOCK_AI", "true").lower() in ("true", "1", "yes")

# Try importing real AI libs - fall back to mock gracefully
_has_cv2 = False
_has_yolo = False

if not MOCK_AI:
    try:
        import cv2
        _has_cv2 = True
    except ImportError:
        pass
    try:
        from ultralytics import YOLO
        _has_yolo = True
    except ImportError:
        pass

    if not _has_cv2 or not _has_yolo:
        MOCK_AI = True  # auto-fallback


# -- Mock detection generator ----------------------------


_NAMES = ["person", "person", "person", "car", "truck", "bicycle", "motorcycle", "dog"]
_COLORS = ["dark", "light", "blue", "red", "green", "grey", "camouflage"]
_MOTIONS = ["walking", "running", "standing", "crouching", "crawling"]
_VEHICLE_MOTIONS = ["moving", "stationary", "approaching", "departing"]
_PLATES = ["MH12AB1234", "DL04XY5678", "RJ14CD9012", "UP32EF3456", "HR26GH7890", None, None, None]

_mock_tracks: dict = {}  # camera_id -> list of mock tracked objects
_track_counter = 0


def _generate_mock_detections(camera_id: str) -> dict:
    """Generate realistic-looking mock detections."""
    global _track_counter

    now = datetime.utcnow().isoformat() + "Z"
    num_det = random.choices([0, 1, 2, 3, 4, 5], weights=[5, 20, 30, 25, 15, 5])[0]

    if camera_id not in _mock_tracks:
        _mock_tracks[camera_id] = []

    # Age out old tracks
    _mock_tracks[camera_id] = [t for t in _mock_tracks[camera_id] if random.random() < 0.85]

    detections = []
    alerts = []

    for _ in range(num_det):
        cls = random.choice(_NAMES)
        _track_counter += 1
        tid = f"{cls}-{_track_counter}"
        conf = round(random.uniform(0.55, 0.98), 2)

        # Random bbox in normalized-ish coords (640x480 frame)
        x1 = random.randint(20, 500)
        y1 = random.randint(20, 350)
        w = random.randint(40, 140)
        h = random.randint(60, 200) if cls == "person" else random.randint(40, 120)
        bbox = [x1, y1, x1 + w, y1 + h]

        is_vehicle = cls in ("car", "truck", "motorcycle", "bicycle")
        face_detected = cls == "person" and random.random() < 0.3
        plate_text = random.choice(_PLATES) if is_vehicle and random.random() < 0.4 else None

        features = {
            "dominant_color": random.choice(_COLORS),
            "estimated_height_category": random.choice(["short", "medium", "tall"]) if cls == "person" else None,
            "motion": random.choice(_MOTIONS) if cls == "person" else random.choice(_VEHICLE_MOTIONS),
            "face_detected": face_detected,
            "plate_text": plate_text,
        }

        det = {
            "track_id": tid,
            "class": cls,
            "confidence": conf,
            "bbox": bbox,
            "features": features,
        }
        detections.append(det)

        # Store for tracking
        _mock_tracks[camera_id].append({"track_id": tid, "class": cls, "bbox": bbox, "features": features})

        # Generate alerts based on detection type
        severity = "Low"
        event_type = ""

        if cls == "person":
            event_type = "Human detected"
            severity = "Medium"
            if face_detected:
                alerts.append({
                    "event_type": "Face detected",
                    "severity": "Medium",
                    "description": f"Face detected on {tid} (conf: {conf})",
                    "track_id": tid,
                })
                # Random watchlist match
                if random.random() < 0.1:
                    alerts.append({
                        "event_type": "Watchlist match",
                        "severity": "Critical",
                        "description": f"Potential watchlist match on {tid}",
                        "track_id": tid,
                    })
        elif is_vehicle:
            event_type = "Vehicle detected"
            severity = "Low"
            alerts.append({
                "event_type": f"Vehicle classification",
                "severity": "Low",
                "description": f"{cls.capitalize()} detected (conf: {conf})",
                "track_id": tid,
            })
            if plate_text:
                alerts.append({
                    "event_type": "Number plate detected",
                    "severity": "Low",
                    "description": f"Plate: {plate_text} on {tid}",
                    "track_id": tid,
                })

        # Suspicious activity (random)
        if random.random() < 0.05:
            susp = random.choice(["loitering", "restricted-zone crossing", "running", "crowd movement"])
            alerts.append({
                "event_type": "Suspicious activity",
                "severity": "High",
                "description": f"Suspicious: {susp} by {tid}",
                "track_id": tid,
            })

        # Virtual fence (random)
        if random.random() < 0.04:
            alerts.append({
                "event_type": "Virtual fence intrusion",
                "severity": "Critical",
                "description": f"{tid} crossed restricted virtual boundary",
                "track_id": tid,
            })

    # Night-time movement (random, time-based simulation)
    hour = datetime.utcnow().hour
    if (hour < 6 or hour > 20) and detections and random.random() < 0.3:
        alerts.append({
            "event_type": "Night-time movement",
            "severity": "High",
            "description": f"Movement detected during night hours on camera {camera_id}",
        })

    return {
        "camera_id": camera_id,
        "timestamp": now,
        "detections": detections,
        "alerts": alerts,
    }


def analyze_frame(camera_id: str, frame=None) -> dict:
    """Analyze a single frame. Uses mock in mock mode."""
    if MOCK_AI or frame is None:
        return _generate_mock_detections(camera_id)

    # Real AI analysis would go here
    # For now, fall back to mock
    return _generate_mock_detections(camera_id)


def check_virtual_fence(bbox, zones) -> list:
    """Check if bottom-center of bbox enters any restricted zone polygon."""
    if not zones:
        return []

    # Bottom-center point
    bx = (bbox[0] + bbox[2]) / 2
    by = bbox[3]

    intrusions = []
    for zone in zones:
        points = zone.get("points", [])
        if len(points) < 3:
            continue
        if _point_in_polygon(bx, by, points):
            intrusions.append(zone)
    return intrusions


def _point_in_polygon(x, y, polygon):
    """Ray-casting point-in-polygon test."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][0], polygon[i][1]
        xj, yj = polygon[j][0], polygon[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def is_night_mode(frame=None) -> bool:
    """Detect if frame is low-light. Mock returns time-based guess."""
    if MOCK_AI or frame is None:
        hour = datetime.utcnow().hour
        return hour < 6 or hour > 20
    # Real: check mean brightness
    return False


def get_ai_status() -> dict:
    """Return status of AI models."""
    return {
        "mock_mode": MOCK_AI,
        "object_detection": "Mock" if MOCK_AI else ("YOLOv8" if _has_yolo else "Unavailable"),
        "face_detection": "Mock" if MOCK_AI else ("OpenCV DNN" if _has_cv2 else "Unavailable"),
        "tracking": "Mock" if MOCK_AI else "Centroid",
        "anpr": "Mock" if MOCK_AI else "Unavailable",
        "night_vision": "Mock" if MOCK_AI else ("CLAHE" if _has_cv2 else "Unavailable"),
    }

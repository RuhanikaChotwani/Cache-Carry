"""3D scene reconstruction service for IBVAP.
Builds a scene-graph JSON consumable by Three.js on the frontend.
Mock mode: generates moving objects with trails.
Real mode: projects detections via homography to ground-plane coords.
"""
import os, random, math, time
from datetime import datetime
from services import storage

MOCK_AI = os.getenv("IBVAP_MOCK_AI", "true").lower() in ("true", "1", "yes")

# Persistent scene state
_scene_objects: dict = {}  # track_id -> object state
_scene_trails: dict = {}   # track_id -> trail points
_last_update = None


def update_scene_from_detections(camera_id: str, detections: list, camera_data: dict = None):
    """Update scene state from a frame's detections."""
    global _last_update
    _last_update = datetime.utcnow().isoformat() + "Z"

    cal = storage.get_calibration(camera_id) or _default_calibration(camera_id)

    for det in detections:
        tid = det.get("track_id", "")
        bbox = det.get("bbox", [0, 0, 100, 100])
        cls = det.get("class", "person")

        # Project bbox bottom-center to 3D ground plane
        pos = _project_to_3d(bbox, cal)

        height = 1.7 if cls == "person" else 1.5
        if cls in ("car", "truck"):
            height = 1.5 if cls == "car" else 2.5

        _scene_objects[tid] = {
            "track_id": tid,
            "class": cls,
            "position": pos,
            "height": height,
            "confidence": det.get("confidence", 0.9),
            "features": det.get("features", {}),
            "threat_level": _assess_threat(det),
            "camera_id": camera_id,
            "updated_at": _last_update,
        }

        # Update trail
        if tid not in _scene_trails:
            _scene_trails[tid] = []
        _scene_trails[tid].append(pos)
        if len(_scene_trails[tid]) > 20:
            _scene_trails[tid] = _scene_trails[tid][-20:]


def _default_calibration(camera_id: str) -> dict:
    """Default camera calibration for demo."""
    cameras = storage.get_cameras()
    idx = 0
    for i, c in enumerate(cameras):
        if c["id"] == camera_id:
            idx = i
            break

    # Place cameras around scene perimeter
    angle = (idx * 90) % 360
    rad = math.radians(angle)
    x = 60 + 50 * math.cos(rad)
    z = 40 + 30 * math.sin(rad)

    return {
        "camera_position": [x, 8, z],
        "camera_rotation": [0, angle + 180, 0],
        "fov": 70,
    }


def _project_to_3d(bbox, cal):
    """Simple perspective projection to ground plane.
    In real mode this would use homography matrix.
    For demo, maps bbox position to scene coordinates."""
    bx = (bbox[0] + bbox[2]) / 2  # center x
    by = bbox[3]  # bottom y

    # Normalize to 0-1 range assuming 640x480 frame
    nx = bx / 640.0
    ny = by / 480.0

    cam_pos = cal.get("camera_position", [60, 8, 40])
    fov = cal.get("fov", 70)

    # Map to ground plane coordinates around camera position
    scene_x = cam_pos[0] + (nx - 0.5) * fov * 0.5
    scene_z = cam_pos[2] + ny * 30  # depth mapping
    scene_y = 0  # ground level

    return [round(scene_x, 1), scene_y, round(scene_z, 1)]


def _assess_threat(det) -> str:
    features = det.get("features", {})
    if features.get("motion") in ("running", "crawling"):
        return "High"
    if features.get("face_detected") and features.get("motion") == "crouching":
        return "Critical"
    if det.get("class") in ("car", "truck"):
        return "Medium"
    return "Low"


def get_scene_graph() -> dict:
    """Build the full scene graph JSON."""
    cameras = storage.get_cameras()
    zones = storage.get_zones()

    scene_cameras = []
    for cam in cameras:
        cal = storage.get_calibration(cam["id"]) or _default_calibration(cam["id"])
        scene_cameras.append({
            "id": cam["id"],
            "name": cam["name"],
            "position": cal.get("camera_position", [0, 8, 0]),
            "rotation": cal.get("camera_rotation", [0, 0, 0]),
            "fov": cal.get("fov", 70),
            "status": cam["status"],
        })

    scene_zones = []
    for z in zones:
        # Convert 2D zone points to 3D (y=0 ground plane)
        pts3d = [[p[0], 0, p[1]] if len(p) == 2 else p for p in z.get("points", [])]
        scene_zones.append({
            "id": z["id"],
            "name": z["name"],
            "points": pts3d,
            "severity": z["severity"],
        })

    # Add default zone if none exist
    if not scene_zones:
        scene_zones.append({
            "id": "zone-default",
            "name": "Restricted Border Fence",
            "points": [[20, 0, 10], [100, 0, 10], [100, 0, 20], [20, 0, 20]],
            "severity": "Critical",
        })

    # Clean old objects (>30s since update)
    now = datetime.utcnow()
    stale = []
    for tid, obj in _scene_objects.items():
        try:
            upd = datetime.fromisoformat(obj["updated_at"].rstrip("Z"))
            if (now - upd).total_seconds() > 30:
                stale.append(tid)
        except Exception:
            pass
    for tid in stale:
        del _scene_objects[tid]
        _scene_trails.pop(tid, None)

    objects = []
    for tid, obj in _scene_objects.items():
        o = dict(obj)
        o["trail"] = _scene_trails.get(tid, [])
        objects.append(o)

    return {
        "updated_at": _last_update or datetime.utcnow().isoformat() + "Z",
        "scene": {
            "units": "meters",
            "bounds": {"width": 120, "depth": 80},
            "cameras": scene_cameras,
            "zones": scene_zones,
            "objects": objects,
        }
    }


def generate_mock_scene() -> dict:
    """Generate a self-contained mock scene with animated objects."""
    cameras = storage.get_cameras()
    if not cameras:
        # Use default cameras
        cameras = [
            {"id": "cam-1", "name": "North Gate", "status": "LIVE"},
            {"id": "cam-2", "name": "East Border", "status": "LIVE"},
            {"id": "cam-3", "name": "West Tower", "status": "LIVE"},
            {"id": "cam-4", "name": "South Perimeter", "status": "LIVE"},
        ]

    t = time.time()

    scene_cams = []
    cam_positions = [
        [10, 8, 10], [110, 8, 10], [110, 8, 70], [10, 8, 70]
    ]
    cam_rotations = [
        [0, 135, 0], [0, 225, 0], [0, 315, 0], [0, 45, 0]
    ]
    for i, cam in enumerate(cameras[:4]):
        scene_cams.append({
            "id": cam["id"],
            "name": cam["name"],
            "position": cam_positions[i % 4],
            "rotation": cam_rotations[i % 4],
            "fov": 70,
            "status": cam.get("status", "LIVE"),
        })

    # Animated mock objects
    objects = []
    for i in range(random.randint(3, 8)):
        speed = random.uniform(0.3, 1.5)
        phase = random.uniform(0, 2 * math.pi)
        cx = 60 + 40 * math.sin(t * speed * 0.1 + phase)
        cz = 40 + 25 * math.cos(t * speed * 0.1 + phase + i)

        cls = random.choice(["person", "person", "person", "car", "truck"])
        is_vehicle = cls in ("car", "truck")

        trail = []
        for step in range(5):
            st = t - step * 2
            tx = 60 + 40 * math.sin(st * speed * 0.1 + phase)
            tz = 40 + 25 * math.cos(st * speed * 0.1 + phase + i)
            trail.insert(0, [round(tx, 1), 0, round(tz, 1)])

        threat = random.choice(["Low", "Low", "Medium", "High"])
        if 20 < cx < 100 and 10 < cz < 20:
            threat = "Critical"

        objects.append({
            "track_id": f"{cls}-{i + 1}",
            "class": cls,
            "position": [round(cx, 1), 0, round(cz, 1)],
            "height": 1.7 if cls == "person" else (1.5 if cls == "car" else 2.5),
            "confidence": round(random.uniform(0.7, 0.98), 2),
            "features": {
                "dominant_color": random.choice(["dark", "light", "blue", "red"]),
                "motion": random.choice(["walking", "running", "standing"]) if cls == "person" else "moving",
                "face_detected": random.random() < 0.3 if cls == "person" else False,
                "plate_text": random.choice(["MH12AB1234", "DL04XY5678", None]) if is_vehicle else None,
            },
            "trail": trail,
            "threat_level": threat,
        })

    return {
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "scene": {
            "units": "meters",
            "bounds": {"width": 120, "depth": 80},
            "cameras": scene_cams,
            "zones": [{
                "id": "zone-1",
                "name": "Restricted Border Fence",
                "points": [[20, 0, 10], [100, 0, 10], [100, 0, 20], [20, 0, 20]],
                "severity": "Critical",
            }],
            "objects": objects,
        }
    }

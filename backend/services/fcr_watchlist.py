"""FCR Watchlist Service for IBVAP:
Handles image upload, face validation, embedding extraction, and persistent watchlist storage.
"""

import os, json, uuid, base64
from pathlib import Path
from datetime import datetime
from services import face_engine

try:
    import cv2
    import numpy as np
    _has_cv2 = True
except Exception:
    _has_cv2 = False

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
WATCHLIST_FILE = DATA_DIR / "fcr_watchlist.json"
MATCHES_FILE = DATA_DIR / "fcr_matches.json"

_recent_matches = []


def _ensure_storage():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not WATCHLIST_FILE.exists():
        with open(WATCHLIST_FILE, "w") as f:
            json.dump([], f)
    if not MATCHES_FILE.exists():
        with open(MATCHES_FILE, "w") as f:
            json.dump([], f)


_ensure_storage()


def get_watchlist():
    _ensure_storage()
    try:
        with open(WATCHLIST_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def enroll_target_image(name: str, image_bytes: bytes):
    """Enrolls a target person from an uploaded image file.
    Rules:
    1. Must contain exactly 1 clear face.
    2. Rejects if 0 faces or >1 faces found.
    3. Extracts embedding and saves to watchlist.
    """
    _ensure_storage()

    if not _has_cv2:
        raise ValueError("OpenCV is not available to decode the image.")

    # Decode image from bytes
    nparr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Could not decode image file. Please upload a valid JPG/PNG image.")

    # Detect faces
    faces = face_engine.detect_faces(frame)

    if len(faces) == 0:
        raise ValueError("No face found in uploaded image. Please ensure good lighting and front-facing angle.")
    if len(faces) > 1:
        raise ValueError(f"Upload one clear face only. Found {len(faces)} faces in the image.")

    target_face = faces[0]
    bbox = target_face["bbox"]
    embedding = target_face["embedding"]

    # Generate small thumbnail
    x1, y1, x2, y2 = bbox
    crop = frame[max(0, y1):min(frame.shape[0], y2), max(0, x1):min(frame.shape[1], x2)]
    thumb_b64 = ""
    if crop.size > 0:
        _, thumb_jpg = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 80])
        thumb_b64 = base64.b64encode(thumb_jpg).decode("utf-8")

    face_id = f"fcr-{uuid.uuid4().hex[:8]}"
    now = datetime.utcnow().isoformat() + "Z"

    entry = {
        "id": face_id,
        "name": name.strip(),
        "embedding": embedding,
        "confidence": target_face["confidence"],
        "bbox": bbox,
        "thumbnail": thumb_b64,
        "created_at": now
    }

    watchlist = get_watchlist()
    watchlist.append(entry)

    with open(WATCHLIST_FILE, "w") as f:
        json.dump(watchlist, f, indent=2)

    return {
        "id": face_id,
        "name": name.strip(),
        "confidence": target_face["confidence"],
        "created_at": now,
        "status": "Enrolled successfully"
    }


def delete_from_watchlist(face_id: str):
    _ensure_storage()
    watchlist = get_watchlist()
    updated = [item for item in watchlist if item["id"] != face_id]
    with open(WATCHLIST_FILE, "w") as f:
        json.dump(updated, f, indent=2)
    return len(updated) < len(watchlist)


def log_match(match_record: dict):
    global _recent_matches
    _recent_matches.insert(0, match_record)
    if len(_recent_matches) > 50:
        _recent_matches = _recent_matches[:50]


def get_recent_matches():
    return list(_recent_matches)

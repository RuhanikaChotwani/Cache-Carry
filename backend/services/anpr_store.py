"""Persistent storage service for Confirmed ANPR Plate Records in IBVAP.
Saves only verified plates with confirmed OCR registration numbers.
"""

import os
import json
import uuid
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RECORDS_FILE = DATA_DIR / "anpr_records.json"

_last_saved_time: Dict[str, float] = {}


def _to_float(val, default: float = 0.0) -> float:
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, (list, tuple)):
        if len(val) == 0:
            return default
        return _to_float(val[0], default)
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _ensure_file():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not RECORDS_FILE.exists():
        with open(RECORDS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)


def get_records(limit: int = 100) -> List[dict]:
    """Returns confirmed ANPR records, newest first."""
    _ensure_file()
    try:
        with open(RECORDS_FILE, "r", encoding="utf-8") as f:
            records = json.load(f)
            if not isinstance(records, list):
                records = []
            return sorted(records, key=lambda r: r.get("timestamp", ""), reverse=True)[:limit]
    except Exception:
        return []


def add_record(
    plate_text: str,
    detector_confidence: float,
    ocr_confidence: float,
    source_name: str,
    bbox: list,
    frame_sequence: Optional[int] = None,
) -> Optional[dict]:
    """Saves a confirmed plate record with rate-limiting (max 1 record per 30s for the same plate)."""
    global _last_saved_time

    clean_text = "".join(c for c in str(plate_text).upper() if c.isalnum())
    if not clean_text or len(clean_text) < 4 or clean_text == "UNREADABLE":
        return None

    now_t = time.time()
    last_t = _last_saved_time.get(clean_text, 0.0)

    # Rate limiting: max 1 record per 30 seconds per unique registration number
    if now_t - last_t < 30.0:
        return None

    _last_saved_time[clean_text] = now_t
    _ensure_file()

    rec_id = f"anpr-{uuid.uuid4().hex[:6]}"
    now_iso = datetime.utcnow().isoformat() + "Z"

    # Safely unpack and format coordinates and confidence values
    det_c = round(_to_float(detector_confidence, 0.0), 2)
    ocr_c = round(_to_float(ocr_confidence, 0.0), 2)

    safe_bbox = []
    if isinstance(bbox, (list, tuple)):
        for coord in bbox:
            if isinstance(coord, (list, tuple)):
                safe_bbox.append(int(_to_float(coord[0], 0)))
            else:
                safe_bbox.append(int(_to_float(coord, 0)))

    record = {
        "id": rec_id,
        "timestamp": now_iso,
        "plate_text": clean_text,
        "detector_confidence": det_c,
        "ocr_confidence": ocr_c,
        "source_name": str(source_name),
        "bbox": safe_bbox,
        "frame_sequence": frame_sequence,
        "status": "confirmed",
    }

    try:
        with open(RECORDS_FILE, "r", encoding="utf-8") as f:
            records = json.load(f)
            if not isinstance(records, list):
                records = []
        records.append(record)
        with open(RECORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
        return record
    except Exception:
        return None


def clear_records() -> dict:
    """Clears all stored ANPR records."""
    global _last_saved_time
    _ensure_file()
    _last_saved_time.clear()
    with open(RECORDS_FILE, "w", encoding="utf-8") as f:
        json.dump([], f, indent=2)
    return {"status": "cleared", "records_count": 0}

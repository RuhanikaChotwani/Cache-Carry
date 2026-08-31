"""
Surveillance Event Emission & Snapshot Archival Module.
Emits structured JSON events and stores timestamped evidence snapshots
for integration with security dashboards and alert dispatchers.
"""

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
import cv2
import numpy as np


class SurveillanceEventEmitter:
    """
    Manages detection events, snapshot saving, and JSONL log persistence.
    """

    def __init__(
        self,
        camera_id: str = "CAM-BORDER-01",
        events_log_path: str | Path = "data/events.jsonl",
        snapshot_dir: str | Path = "data/snapshots",
        save_snapshots: bool = True,
        snapshot_interval_frames: int = 30,
        save_unknown_alerts: bool = True,
        save_known_alerts: bool = True,
    ):
        self.camera_id = camera_id
        self.events_log_path = Path(events_log_path)
        self.snapshot_dir = Path(snapshot_dir)
        self.save_snapshots = save_snapshots
        self.snapshot_interval_frames = snapshot_interval_frames
        self.save_unknown_alerts = save_unknown_alerts
        self.save_known_alerts = save_known_alerts

        # Track ID to last snapshot frame index
        self._last_snapshot_frame: Dict[int, int] = {}

        # Ensure parent directories exist
        self.events_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def should_save_snapshot(
        self, track_id: int, identity: str, current_frame_idx: int
    ) -> bool:
        """Determines whether a snapshot should be saved to prevent disk flooding."""
        if not self.save_snapshots:
            return False

        if identity == "Unknown" and not self.save_unknown_alerts:
            return False
        if identity != "Unknown" and not self.save_known_alerts:
            return False

        last_frame = self._last_snapshot_frame.get(track_id, -self.snapshot_interval_frames)
        if (current_frame_idx - last_frame) >= self.snapshot_interval_frames:
            self._last_snapshot_frame[track_id] = current_frame_idx
            return True
        return False

    def emit_event(
        self,
        track_id: int,
        identity: str,
        confidence: float,
        bbox: np.ndarray | list,
        full_frame: np.ndarray,
        current_frame_idx: int,
        quality_metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Emits a structured JSON event and saves an evidence snapshot if needed.
        """
        now = datetime.now()
        iso_time = now.isoformat()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S_%f")[:19]
        event_id = f"EVT_{self.camera_id}_{timestamp_str}_{uuid.uuid4().hex[:6]}"

        zone = (quality_metrics or {}).get("operational_zone", "RECOGNITION")
        distance_m = (quality_metrics or {}).get("distance_m", 0.0)

        is_unknown = (identity == "Unknown")
        if zone == "DETECTION_ONLY" and not is_unknown and "Distant" in identity:
            status = "DISTANT_MONITORING"
        elif is_unknown:
            status = "ALERT_UNKNOWN"
        else:
            status = "AUTHORIZED"

        bbox_coords = [int(v) for v in bbox[:4]]
        snapshot_rel_path: Optional[str] = None

        # Check if snapshot is warranted (avoid flooding snapshots for distant unconfirmed targets)
        is_distant_target = (zone == "DETECTION_ONLY" and "Distant" in identity)
        if self.should_save_snapshot(track_id, identity, current_frame_idx) and not is_distant_target:
            sanitized_name = identity.replace(" ", "_").replace("/", "_")
            snap_filename = f"{self.camera_id}_Trk{track_id}_{sanitized_name}_{timestamp_str}.jpg"
            snap_full_path = self.snapshot_dir / snap_filename

            # Create annotated keyframe crop
            annotated_frame = full_frame.copy()
            x1, y1, x2, y2 = bbox_coords
            color = (0, 0, 240) if is_unknown else (0, 220, 0)
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
            label = f"{identity} [{confidence:.2f}] [~{distance_m:.0f}m]"
            cv2.putText(
                annotated_frame,
                label,
                (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
            )

            cv2.imwrite(str(snap_full_path), annotated_frame)
            snapshot_rel_path = str(snap_full_path)

        event_record = {
            "event_id": event_id,
            "timestamp": iso_time,
            "camera_id": self.camera_id,
            "track_id": int(track_id),
            "identity": identity,
            "status": status,
            "operational_zone": zone,
            "distance_meters": distance_m,
            "confidence": round(float(confidence), 3),
            "bbox": bbox_coords,
            "quality": quality_metrics or {},
            "snapshot_path": snapshot_rel_path,
        }

        # Append to JSON Lines file
        with open(self.events_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event_record) + "\n")

        return event_record

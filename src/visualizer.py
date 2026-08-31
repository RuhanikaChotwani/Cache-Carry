"""
Surveillance HUD Overlay & Visualizer Module.
Renders high-contrast bounding boxes, track identifiers, facial landmarks,
telemetry stats (FPS, active track count, hardware status), and alert banners.
"""

from typing import List, Optional
import cv2
import numpy as np
from src.tracker import FaceTrack


class SurveillanceVisualizer:
    """
    Renders professional military/border surveillance overlays on video streams.
    """

    def __init__(
        self,
        box_thickness: int = 2,
        font_scale: float = 0.55,
        color_known: tuple = (0, 220, 0),      # BGR Green
        color_unknown: tuple = (0, 0, 230),    # BGR Red
        color_distant: tuple = (0, 215, 255),  # BGR Amber/Gold
        color_person: tuple = (210, 210, 210), # BGR Light Silver for person body
        color_helmet: tuple = (0, 165, 255),   # BGR Orange for helmeted person / partial face
        show_fps: bool = True,
        show_landmarks: bool = True,
        show_distance: bool = True,
    ):
        self.box_thickness = box_thickness
        self.font_scale = font_scale
        self.color_known = color_known
        self.color_unknown = color_unknown
        self.color_distant = color_distant
        self.color_person = color_person
        self.color_helmet = color_helmet
        self.show_fps = show_fps
        self.show_landmarks = show_landmarks
        self.show_distance = show_distance

    def draw_corner_brackets(
        self,
        img: np.ndarray,
        pt1: tuple,
        pt2: tuple,
        color: tuple,
        thickness: int = 2,
        length: int = 15,
    ) -> None:
        """Draws surveillance corner brackets around a bounding box."""
        x1, y1 = pt1
        x2, y2 = pt2

        # Top-left
        cv2.line(img, (x1, y1), (x1 + length, y1), color, thickness)
        cv2.line(img, (x1, y1), (x1, y1 + length), color, thickness)
        # Top-right
        cv2.line(img, (x2, y1), (x2 - length, y1), color, thickness)
        cv2.line(img, (x2, y1), (x2, y1 + length), color, thickness)
        # Bottom-left
        cv2.line(img, (x1, y2), (x1 + length, y2), color, thickness)
        cv2.line(img, (x1, y2), (x1, y2 - length), color, thickness)
        # Bottom-right
        cv2.line(img, (x2, y2), (x2 - length, y2), color, thickness)
        cv2.line(img, (x2, y2), (x2, y2 - length), color, thickness)

    def render(
        self,
        frame: np.ndarray,
        tracks: List[FaceTrack],
        fps: float = 0.0,
        camera_id: str = "CAM-01",
        hardware_info: str = "RTX 4050 | CUDA",
    ) -> np.ndarray:
        """
        Renders complete surveillance HUD overlay on the frame.
        """
        output = frame.copy()
        h, w = output.shape[:2]

        # Count tracks by zone
        in_range_count = sum(1 for t in tracks if t.operational_zone == "RECOGNITION" or t.history_identities)
        distant_count = len(tracks) - in_range_count

        # 1. Draw telemetry header banner (dark semi-transparent bar)
        overlay = output.copy()
        cv2.rectangle(overlay, (0, 0), (w, 36), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.75, output, 0.25, 0, output)

        header_text = f"SIH26187 BORDER SURVEILLANCE | CAM: {camera_id} | {hardware_info}"
        if self.show_fps:
            header_text += f" | FPS: {fps:.1f}"
        header_text += f" | IN RANGE (8-25m): {in_range_count} | DISTANT (25-50m): {distant_count}"

        cv2.putText(
            output,
            header_text,
            (14, 23),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (230, 230, 230),
            1,
            cv2.LINE_AA,
        )

        # 2. Draw tracks
        for track in tracks:
            x1, y1, x2, y2 = [int(v) for v in track.bbox[:4]]
            
            # Determine color and badge based on identity and occlusion
            if track.identity in ("Helmeted Person", "Partial Face") or track.occlusion_type in ("HELMETED", "PARTIAL_FACE"):
                color = self.color_helmet
            elif "Person" in track.identity and not track.history_identities:
                color = self.color_person
            elif track.identity == "Unknown":
                color = self.color_unknown
            else:
                color = self.color_known

            # Main bounding box (Person body)
            cv2.rectangle(output, (x1, y1), (x2, y2), color, self.box_thickness)
            self.draw_corner_brackets(output, (x1, y1), (x2, y2), color, thickness=self.box_thickness + 1)

            # Draw inner face box if face was associated with body
            if track.face_bbox is not None:
                fx1, fy1, fx2, fy2 = [int(v) for v in track.face_bbox[:4]]
                cv2.rectangle(output, (fx1, fy1), (fx2, fy2), color, 1)

            # Draw 5-point landmarks if available
            if self.show_landmarks and track.landmarks is not None:
                for pt in track.landmarks:
                    px, py = int(pt[0]), int(pt[1])
                    cv2.circle(output, (px, py), 2, (0, 255, 255), -1, cv2.LINE_AA)

            # Build label:
            # - Far away: "ID:1 | Person [~38m]"
            # - Helmeted: "ID:1 | Helmeted Person"
            # - Partial: "ID:1 | Partial Face"
            # - Unknown: "ID:1 | Unknown"
            # - Recognized: "ID:1 | Officer_Rohan (92%)"
            dist_tag = f" [~{track.distance_m:.0f}m]" if (self.show_distance and track.distance_m > 0) else ""
            if track.identity in ("Helmeted Person", "Partial Face"):
                label = f"ID:{track.track_id} | {track.identity}{dist_tag}"
            elif "Person" in track.identity and not track.history_identities:
                label = f"ID:{track.track_id} | Person{dist_tag}"
            elif track.identity == "Unknown":
                label = f"ID:{track.track_id} | Unknown{dist_tag}"
            else:
                label = f"ID:{track.track_id} | {track.identity}{dist_tag}"
                if track.confidence > 0.0:
                    label += f" ({track.confidence * 100:.0f}%)"

            (text_w, text_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, self.font_scale, 1
            )
            label_y = max(y1 - 6, text_h + 8)

            # Dark tag background
            cv2.rectangle(
                output,
                (x1, label_y - text_h - 4),
                (x1 + text_w + 8, label_y + baseline),
                (20, 20, 20),
                -1,
            )
            # Colored left indicator bar
            cv2.rectangle(
                output,
                (x1, label_y - text_h - 4),
                (x1 + 3, label_y + baseline),
                color,
                -1,
            )

            # Text label
            cv2.putText(
                output,
                label,
                (x1 + 6, label_y - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                self.font_scale,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        return output

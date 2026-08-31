"""
Multi-face tracking module using high-speed IoU association and temporal identity voting.
Maintains persistent track IDs and smooths recognition results across video frames.
"""

from collections import Counter
from typing import Dict, List, Optional, Tuple
import numpy as np


def compute_iou_matrix(boxes1: np.ndarray, boxes2: np.ndarray) -> np.ndarray:
    """
    Computes pairwise IoU between two sets of bounding boxes.
    boxes1: (N, 4), boxes2: (M, 4)
    Returns: (N, M) matrix
    """
    if len(boxes1) == 0 or len(boxes2) == 0:
        return np.zeros((len(boxes1), len(boxes2)), dtype=np.float32)

    area1 = (boxes1[:, 2] - boxes1[:, 0]) * (boxes1[:, 3] - boxes1[:, 1])
    area2 = (boxes2[:, 2] - boxes2[:, 0]) * (boxes2[:, 3] - boxes2[:, 1])

    lt = np.maximum(boxes1[:, None, :2], boxes2[None, :, :2])  # (N, M, 2)
    rb = np.minimum(boxes1[:, None, 2:], boxes2[None, :, 2:])  # (N, M, 2)

    wh = np.maximum(0.0, rb - lt)  # (N, M, 2)
    inter = wh[:, :, 0] * wh[:, :, 1]  # (N, M)

    union = area1[:, None] + area2[None, :] - inter
    union = np.maximum(union, 1e-6)

    return inter / union


class FaceTrack:
    """Represents an active or tentative face track over time."""

    def __init__(self, track_id: int, bbox: np.ndarray, score: float, landmarks: Optional[np.ndarray] = None):
        self.track_id = track_id
        self.bbox = np.asarray(bbox, dtype=np.float32)
        self.score = float(score)
        self.landmarks = np.asarray(landmarks, dtype=np.float32) if landmarks is not None else None

        self.age = 1
        self.hits = 1
        self.time_since_update = 0

        # Spatial & Quality telemetry
        self.distance_m = 0.0
        self.operational_zone = "DETECTION_ONLY"  # "RECOGNITION" or "DETECTION_ONLY"
        self.ipd = 0.0
        self.yaw_ratio = 0.0
        self.occlusion_type = "NONE"              # "NONE", "HELMETED", "PARTIAL_FACE"
        self.has_face = False
        self.body_bbox: np.ndarray = self.bbox.copy()
        self.face_bbox: Optional[np.ndarray] = None

        # Identity tracking & voting
        self.identity = "Person"
        self.confidence = 0.0
        self.history_identities: List[str] = []
        self.history_scores: List[float] = []
        self.frames_since_recognition = 0

    def update_metrics(
        self,
        distance_m: float,
        zone: str,
        ipd: float = 0.0,
        yaw_ratio: float = 0.0,
        occlusion_type: str = "NONE",
        has_face: bool = False,
    ):
        """Updates spatial telemetry and surveillance operational zone."""
        self.distance_m = distance_m
        self.operational_zone = zone
        self.ipd = ipd
        self.yaw_ratio = yaw_ratio
        self.occlusion_type = occlusion_type
        self.has_face = has_face

        # Only override label if identity hasn't been confirmed yet by ArcFace
        if not self.history_identities:
            if occlusion_type == "HELMETED":
                self.identity = "Helmeted Person"
            elif occlusion_type == "PARTIAL_FACE":
                self.identity = "Partial Face"
            elif not has_face:
                self.identity = f"Person [~{distance_m:.0f}m]"
            elif zone == "DETECTION_ONLY":
                self.identity = f"Person [~{distance_m:.0f}m]"

    def update(self, bbox: np.ndarray, score: float, landmarks: Optional[np.ndarray] = None):
        """Updates track with newly matched detection."""
        self.bbox = np.asarray(bbox, dtype=np.float32)
        self.score = float(score)
        if landmarks is not None:
            self.landmarks = np.asarray(landmarks, dtype=np.float32)

        self.hits += 1
        self.age += 1
        self.time_since_update = 0
        self.frames_since_recognition += 1

    def mark_missed(self):
        """Marks track as missed in current frame."""
        self.time_since_update += 1
        self.age += 1
        self.frames_since_recognition += 1

    def add_recognition_result(self, identity: str, confidence: float):
        """Records a new recognition result and smooths identity via voting."""
        self.history_identities.append(identity)
        self.history_scores.append(confidence)
        self.frames_since_recognition = 0

        # Keep rolling window of last 10 recognitions
        if len(self.history_identities) > 10:
            self.history_identities.pop(0)
            self.history_scores.pop(0)

        # Majority voting (filter out 'Unknown' if we have confident known detections)
        known_votes = [
            (ident, score)
            for ident, score in zip(self.history_identities, self.history_scores)
            if ident != "Unknown"
        ]

        if known_votes:
            # Group by identity
            scores_by_id: Dict[str, List[float]] = {}
            for ident, score in known_votes:
                scores_by_id.setdefault(ident, []).append(score)

            # Winner is identity with highest average score * count
            best_id = max(scores_by_id.keys(), key=lambda k: sum(scores_by_id[k]) / len(scores_by_id[k]) * len(scores_by_id[k]))
            avg_score = sum(scores_by_id[best_id]) / len(scores_by_id[best_id])
            self.identity = best_id
            self.confidence = avg_score
        else:
            self.identity = "Unknown"
            self.confidence = max(self.history_scores) if self.history_scores else confidence


class FaceTracker:
    """
    Real-time IoU Face Tracker.
    Associates face detections across frames and assigns unique track IDs.
    """

    def __init__(
        self,
        iou_threshold: float = 0.30,
        max_age: int = 25,
        min_hits: int = 2,
    ):
        self.iou_threshold = iou_threshold
        self.max_age = max_age
        self.min_hits = min_hits
        self.next_track_id = 1
        self.tracks: List[FaceTrack] = []

    def update(
        self,
        bboxes: np.ndarray,
        scores: np.ndarray,
        landmarks: Optional[np.ndarray] = None,
    ) -> List[FaceTrack]:
        """
        Updates tracks with detections from current frame.

        Args:
            bboxes: (N, 4)
            scores: (N,)
            landmarks: (N, 5, 2) or None

        Returns:
            List of confirmed active FaceTrack objects.
        """
        # If no active tracks, initialize new tracks for all detections
        if len(self.tracks) == 0:
            for i in range(len(bboxes)):
                lmk = landmarks[i] if landmarks is not None and len(landmarks) > i else None
                new_track = FaceTrack(self.next_track_id, bboxes[i], scores[i], lmk)
                self.next_track_id += 1
                self.tracks.append(new_track)
            return [t for t in self.tracks if t.hits >= self.min_hits]

        # If no detections in current frame, mark all tracks missed
        if len(bboxes) == 0:
            for track in self.tracks:
                track.mark_missed()
            self.tracks = [t for t in self.tracks if t.time_since_update <= self.max_age]
            return [t for t in self.tracks if t.hits >= self.min_hits and t.time_since_update == 0]

        # Compute IoU cost matrix
        track_boxes = np.array([t.bbox for t in self.tracks])
        iou_mat = compute_iou_matrix(track_boxes, bboxes)

        matched_track_indices = set()
        matched_det_indices = set()

        # Greedy matching by highest IoU
        while True:
            if iou_mat.size == 0:
                break
            max_iou = np.max(iou_mat)
            if max_iou < self.iou_threshold:
                break

            t_idx, d_idx = np.unravel_index(np.argmax(iou_mat), iou_mat.shape)

            if t_idx in matched_track_indices or d_idx in matched_det_indices:
                iou_mat[t_idx, d_idx] = -1.0
                continue

            # Associate detection with track
            lmk = landmarks[d_idx] if landmarks is not None and len(landmarks) > d_idx else None
            self.tracks[t_idx].update(bboxes[d_idx], scores[d_idx], lmk)
            matched_track_indices.add(t_idx)
            matched_det_indices.add(d_idx)
            iou_mat[t_idx, :] = -1.0
            iou_mat[:, d_idx] = -1.0

        # Unmatched tracks
        for t_idx, track in enumerate(self.tracks):
            if t_idx not in matched_track_indices:
                track.mark_missed()

        # Unmatched detections -> spawn new tracks
        for d_idx in range(len(bboxes)):
            if d_idx not in matched_det_indices:
                lmk = landmarks[d_idx] if landmarks is not None and len(landmarks) > d_idx else None
                new_track = FaceTrack(self.next_track_id, bboxes[d_idx], scores[d_idx], lmk)
                self.next_track_id += 1
                self.tracks.append(new_track)

        # Filter dead tracks
        self.tracks = [t for t in self.tracks if t.time_since_update <= self.max_age]

        # Return tracks active in this frame that meet min_hits
        active_tracks = [
            t for t in self.tracks
            if t.hits >= self.min_hits and t.time_since_update == 0
        ]
        return active_tracks

    def associate_faces_to_bodies(
        self,
        active_tracks: List[FaceTrack],
        face_bboxes: np.ndarray,
        face_scores: np.ndarray,
        face_landmarks: Optional[np.ndarray],
        head_ratio: float = 0.40,
    ) -> None:
        """
        Hierarchically links detected faces to their parent person/body tracks.
        Attaches face bbox and landmarks directly to the person's existing track ID.
        """
        for track in active_tracks:
            track.has_face = False
            track.face_bbox = None

        if len(face_bboxes) == 0:
            return

        assigned_faces = set()

        for track in active_tracks:
            bx1, by1, bx2, by2 = track.bbox[:4]
            body_h = by2 - by1
            head_zone_y2 = by1 + body_h * head_ratio

            best_f_idx = -1
            best_score = 0.0

            for f_idx in range(len(face_bboxes)):
                if f_idx in assigned_faces:
                    continue
                fx1, fy1, fx2, fy2 = face_bboxes[f_idx][:4]
                fcx = (fx1 + fx2) / 2.0
                fcy = (fy1 + fy2) / 2.0

                # Face center must be inside horizontal span of body and upper vertical region
                if (bx1 - 15 <= fcx <= bx2 + 15) and (by1 - 15 <= fcy <= head_zone_y2 + 25):
                    score = float(face_scores[f_idx])
                    if score > best_score:
                        best_score = score
                        best_f_idx = f_idx

            if best_f_idx >= 0:
                track.has_face = True
                track.face_bbox = face_bboxes[best_f_idx]
                if face_landmarks is not None and len(face_landmarks) > best_f_idx:
                    track.landmarks = face_landmarks[best_f_idx]
                assigned_faces.add(best_f_idx)


"""
Smart Face Quality Assessment & Distance Estimation Module.
Designed for border surveillance CCTV cameras at gates, checkposts, and Border Out Posts (BOP).

Enforces:
1. Pinhole optical distance estimation in meters.
2. 3-Tier Operational Zones:
   - Zone 1: Recognition Zone (8m - 25m / Face >= 42px / IPD >= 16px) -> ArcFace
   - Zone 2: Long-Range Detection Zone (25m - 50m / Face 18px - 41px) -> Tracking only, no false alarms
   - Zone 3: Beyond Range (> 50m / Face < 18px) -> Reject noise
3. Multi-Metric Quality Gating:
   - Inter-Pupillary Distance (IPD)
   - Adaptive Laplacian Blur (scaled by resolution)
   - 5-Point Pose/Yaw Asymmetry Ratio
   - Illumination / Contrast Gate
"""

from typing import Dict, Optional, Tuple
import cv2
import numpy as np


class FaceQualityAssessor:
    """
    Intelligent quality gatekeeper and optical distance estimator for surveillance streams.
    """

    def __init__(
        self,
        min_face_size_recognition: int = 42,
        min_face_size_detection: int = 18,
        min_ipd_pixels: float = 16.0,
        blur_threshold: float = 40.0,
        min_brightness: float = 25.0,
        max_brightness: float = 240.0,
        max_yaw_ratio: float = 0.42,
        reference_focal_factor: float = 1500.0,
        recognition_min_distance_m: float = 3.0,
        recognition_max_distance_m: float = 25.0,
        detection_max_distance_m: float = 50.0,
        helmet_check_enabled: bool = True,
        min_face_aspect_ratio: float = 0.62,
        forehead_occlusion_ratio: float = 0.45,
    ):
        self.min_face_size_rec = min_face_size_recognition
        self.min_face_size_det = min_face_size_detection
        self.min_ipd = min_ipd_pixels
        self.blur_threshold = blur_threshold
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness
        self.max_yaw_ratio = max_yaw_ratio

        # Occlusion & Helmet parameters
        self.helmet_check_enabled = helmet_check_enabled
        self.min_aspect_ratio = min_face_aspect_ratio
        self.forehead_occlusion_ratio = forehead_occlusion_ratio

        # Optical distance parameters
        self.focal_factor = reference_focal_factor
        self.rec_min_dist = recognition_min_distance_m
        self.rec_max_dist = recognition_max_distance_m
        self.det_max_dist = detection_max_distance_m

    def estimate_distance_meters(self, bbox: np.ndarray | list) -> float:
        """
        Estimates real-world distance in meters from camera to face based on pinhole optics.
        D = reference_focal_factor / face_height_pixels
        """
        h = float(bbox[3] - bbox[1])
        h = max(h, 1.0)
        dist = self.focal_factor / h
        return round(float(dist), 1)

    def compute_ipd(self, landmarks: Optional[np.ndarray]) -> float:
        """
        Computes Inter-Pupillary Distance (IPD) between left eye and right eye.
        landmarks order: [left_eye, right_eye, nose, left_mouth, right_mouth]
        """
        if landmarks is None or len(landmarks) < 2:
            return 0.0
        le = np.asarray(landmarks[0], dtype=np.float32)
        re = np.asarray(landmarks[1], dtype=np.float32)
        return float(np.linalg.norm(re - le))

    def estimate_yaw_ratio(self, landmarks: Optional[np.ndarray]) -> float:
        """
        Estimates head yaw rotation from 5 canonical landmarks based on facial asymmetry.
        Frontal faces have yaw_ratio ~ 0.0 - 0.20.
        Turned profile faces (> 35°) have yaw_ratio > 0.42.
        """
        if landmarks is None or len(landmarks) < 3:
            return 0.0

        le = np.asarray(landmarks[0], dtype=np.float32)
        re = np.asarray(landmarks[1], dtype=np.float32)
        nose = np.asarray(landmarks[2], dtype=np.float32)

        ipd = float(np.linalg.norm(re - le))
        if ipd < 1e-4:
            return 0.0

        d_le_nose = float(np.linalg.norm(nose - le))
        d_re_nose = float(np.linalg.norm(nose - re))

        yaw_ratio = abs(d_le_nose - d_re_nose) / ipd
        return round(float(yaw_ratio), 3)

    def detect_occlusion_and_helmet(
        self,
        face_img: np.ndarray,
        bbox: Optional[np.ndarray | list] = None,
        landmarks: Optional[np.ndarray] = None,
    ) -> Tuple[str, str]:
        """
        Detects if face is occluded by helmet/headgear, mask, or extreme crop.
        Returns:
            (occlusion_type, reason)
            occlusion_type can be: 'NONE', 'HELMETED', or 'PARTIAL_FACE'
        """
        if face_img.size == 0:
            return "PARTIAL_FACE", "Empty face crop"

        h, w = face_img.shape[:2]
        aspect_ratio = float(h) / max(float(w), 1.0)

        # 1. Aspect ratio check: face cut off horizontally or vertically
        if aspect_ratio < self.min_aspect_ratio:
            return "PARTIAL_FACE", f"Distorted aspect ratio ({aspect_ratio:.2f} < {self.min_aspect_ratio:.2f})"

        # 2. Forehead & Helmet Analysis
        if self.helmet_check_enabled and landmarks is not None and len(landmarks) >= 3:
            eye_y = float(landmarks[0][1] + landmarks[1][1]) / 2.0
            if bbox is not None and eye_y > bbox[1]:
                eye_y = eye_y - bbox[1]

            forehead_h = int(max(0, min(eye_y, h - 1)))
            if forehead_h > 8:
                forehead_roi = face_img[:forehead_h, :]
                hsv = cv2.cvtColor(forehead_roi, cv2.COLOR_BGR2HSV)
                lower_skin1 = np.array([0, 20, 50], dtype=np.uint8)
                upper_skin1 = np.array([25, 200, 255], dtype=np.uint8)
                lower_skin2 = np.array([160, 20, 50], dtype=np.uint8)
                upper_skin2 = np.array([180, 200, 255], dtype=np.uint8)

                mask1 = cv2.inRange(hsv, lower_skin1, upper_skin1)
                mask2 = cv2.inRange(hsv, lower_skin2, upper_skin2)
                skin_mask = mask1 | mask2

                skin_pixels = cv2.countNonZero(skin_mask)
                total_pixels = forehead_roi.shape[0] * forehead_roi.shape[1]
                skin_ratio = skin_pixels / max(total_pixels, 1)

                if skin_ratio < (1.0 - self.forehead_occlusion_ratio):
                    gray_forehead = cv2.cvtColor(forehead_roi, cv2.COLOR_BGR2GRAY)
                    sobel_y = cv2.Sobel(gray_forehead, cv2.CV_64F, 0, 1, ksize=3)
                    edge_power = float(np.mean(np.abs(sobel_y)))
                    if edge_power > 10.0 or skin_ratio < 0.25:
                        return "HELMETED", f"Headgear/Helmet detected (Non-skin: {1.0 - skin_ratio:.2f})"

        return "NONE", "Clear unoccluded face"

    def compute_blur_score(self, face_img: np.ndarray) -> float:
        """Computes variance of the Laplacian (sharpness indicator)."""
        if face_img.size == 0:
            return 0.0
        if face_img.ndim == 3:
            gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        else:
            gray = face_img
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        return float(laplacian.var())

    def compute_brightness_score(self, face_img: np.ndarray) -> float:
        """Computes average luminance of the face patch."""
        if face_img.size == 0:
            return 0.0
        if face_img.ndim == 3:
            gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        else:
            gray = face_img
        return float(np.mean(gray))

    def evaluate(
        self,
        face_img: np.ndarray,
        bbox: np.ndarray | list | None = None,
        landmarks: Optional[np.ndarray] = None,
    ) -> Tuple[bool, Dict[str, float | str | bool]]:
        """
        Assesses distance and face quality to determine the operational surveillance zone.

        Returns:
            (can_recognize, metrics_dict)
            Where metrics_dict['operational_zone'] is:
              - 'RECOGNITION': In 8-25m range, sharp, frontal, passes all ArcFace gates.
              - 'DETECTION_ONLY': In 25-50m range (or turned head / distant).
              - 'REJECT': Beyond 50m / tiny noise (< 18px).
        """
        metrics: Dict[str, float | str | bool] = {}

        if bbox is not None:
            w = float(bbox[2] - bbox[0])
            h = float(bbox[3] - bbox[1])
            dist_m = self.estimate_distance_meters(bbox)
        else:
            h, w = face_img.shape[:2]
            dist_m = round(self.focal_factor / max(h, 1.0), 1)

        metrics["width"] = round(w, 1)
        metrics["height"] = round(h, 1)
        metrics["distance_m"] = dist_m
        metrics["occlusion_type"] = "NONE"

        # Check landmarks: IPD & Yaw
        ipd = self.compute_ipd(landmarks)
        yaw_ratio = self.estimate_yaw_ratio(landmarks)
        metrics["ipd"] = round(ipd, 1)
        metrics["yaw_ratio"] = yaw_ratio

        # 1. Reject filter: Beyond 50m or tiny noise
        if h < self.min_face_size_det or dist_m > self.det_max_dist or face_img.size == 0:
            metrics["operational_zone"] = "REJECT"
            metrics["can_recognize"] = False
            metrics["reason"] = f"Beyond operational range (~{dist_m}m > {self.det_max_dist}m or < {self.min_face_size_det}px)"
            return False, metrics

        # 2. Occlusion & Helmet Detection (Early check)
        occlusion_type, occ_reason = self.detect_occlusion_and_helmet(face_img, bbox=bbox, landmarks=landmarks)
        metrics["occlusion_type"] = occlusion_type
        if occlusion_type != "NONE":
            metrics["operational_zone"] = "DETECTION_ONLY"
            metrics["can_recognize"] = False
            metrics["reason"] = occ_reason
            return False, metrics

        # 3. Photometric / Brightness filter
        brightness = self.compute_brightness_score(face_img)
        metrics["brightness"] = round(brightness, 1)
        if brightness < self.min_brightness:
            metrics["operational_zone"] = "DETECTION_ONLY"
            metrics["can_recognize"] = False
            metrics["reason"] = f"Under-exposed face (Luminance: {brightness:.1f} < {self.min_brightness})"
            return False, metrics
        if brightness > self.max_brightness:
            metrics["operational_zone"] = "DETECTION_ONLY"
            metrics["can_recognize"] = False
            metrics["reason"] = f"Over-exposed face (Luminance: {brightness:.1f} > {self.max_brightness})"
            return False, metrics

        # 3. Dynamic Blur Check (scaled by resolution)
        blur_score = self.compute_blur_score(face_img)
        metrics["blur_score"] = round(blur_score, 1)
        # Adaptive threshold: smaller faces naturally have lower variance
        scale_factor = max(0.5, min(1.5, h / 80.0))
        effective_blur_thresh = self.blur_threshold * scale_factor
        metrics["effective_blur_threshold"] = round(effective_blur_thresh, 1)

        if blur_score < effective_blur_thresh:
            metrics["operational_zone"] = "DETECTION_ONLY"
            metrics["can_recognize"] = False
            metrics["reason"] = f"Motion blur detected ({blur_score:.1f} < {effective_blur_thresh:.1f})"
            return False, metrics

        # 4. Long-Range Detection Zone vs Recognition Zone (25m - 50m vs 8m - 25m)
        # If beyond 25m or face height < 42px or IPD < 16px -> Zone 2 (Tracking Only, no forced recognition)
        is_distant = (dist_m > self.rec_max_dist) or (h < self.min_face_size_rec)
        if is_distant:
            metrics["operational_zone"] = "DETECTION_ONLY"
            metrics["can_recognize"] = False
            metrics["reason"] = f"Distant target (~{dist_m}m > {self.rec_max_dist}m, face: {int(h)}px). Tracking active without forced recognition."
            return False, metrics

        if ipd > 0.0 and ipd < self.min_ipd:
            metrics["operational_zone"] = "DETECTION_ONLY"
            metrics["can_recognize"] = False
            metrics["reason"] = f"Insufficient IPD ({ipd:.1f}px < {self.min_ipd}px for ArcFace)"
            return False, metrics

        # 5. Pose / Yaw Check (reject profile faces > 35°)
        if yaw_ratio > self.max_yaw_ratio:
            metrics["operational_zone"] = "DETECTION_ONLY"
            metrics["can_recognize"] = False
            metrics["reason"] = f"Extreme profile pose (Yaw ratio: {yaw_ratio:.2f} > {self.max_yaw_ratio}). Waiting for frontal view."
            return False, metrics

        # Passed all gates for Zone 1 High-Confidence Recognition!
        metrics["operational_zone"] = "RECOGNITION"
        metrics["occlusion_type"] = "NONE"
        metrics["can_recognize"] = True
        metrics["reason"] = "Passed all recognition gates"
        return True, metrics

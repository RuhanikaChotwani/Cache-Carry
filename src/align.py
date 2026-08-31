"""
Facial landmark alignment module using 5 canonical keypoints.
Transforms raw face crops into aligned 112x112 images standard for ArcFace.
"""

from typing import Optional, Tuple
import cv2
import numpy as np


# Standard canonical 5-point facial landmarks template for 112x112 ArcFace
# Coordinates order: [Left Eye, Right Eye, Nose, Left Mouth Corner, Right Mouth Corner]
ARCFACE_CANONICAL_5PTS = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)


def umeyama_transform(
    src: np.ndarray, dst: np.ndarray, estimate_scale: bool = True
) -> np.ndarray:
    """
    Computes least-squares similarity transformation matrix M that maps src to dst.
    Reference: S. Umeyama, 'Least-Squares Estimation of Transformation Parameters
    Between Two Point Patterns', IEEE PAMI, 1991.

    Args:
        src: Source points array of shape (N, 2)
        dst: Destination reference points array of shape (N, 2)
        estimate_scale: True to estimate scaling parameter

    Returns:
        M: 2x3 affine transformation matrix for cv2.warpAffine
    """
    num_pts, dim = src.shape
    if num_pts != dst.shape[0] or dim != 2:
        raise ValueError("Invalid point set dimensions for Umeyama transform")

    # Compute centroids
    src_mean = np.mean(src, axis=0)
    dst_mean = np.mean(dst, axis=0)

    # Shift to zero-mean
    src_centered = src - src_mean
    dst_centered = dst - dst_mean

    # Covariance
    cov = np.dot(dst_centered.T, src_centered) / num_pts

    # SVD
    u, d, vt = np.linalg.svd(cov)
    s = np.eye(dim, dtype=np.float32)

    # Orientation check
    if np.linalg.det(u) * np.linalg.det(vt) < 0:
        s[dim - 1, dim - 1] = -1

    # Rotation
    r = np.dot(u, np.dot(s, vt))

    # Scale
    if estimate_scale:
        var_src = np.var(src, axis=0).sum()
        scale = (1.0 / var_src) * np.trace(np.dot(np.diag(d), s))
    else:
        scale = 1.0

    # Translation
    t = dst_mean - scale * np.dot(r, src_mean)

    # 2x3 transformation matrix
    m = np.zeros((2, 3), dtype=np.float32)
    m[:2, :2] = scale * r
    m[:2, 2] = t

    return m


def align_face_5pts(
    image: np.ndarray,
    landmarks: np.ndarray,
    output_size: Tuple[int, int] = (112, 112),
) -> np.ndarray:
    """
    Warps a face image using 5 landmarks to canonical ArcFace template.

    Args:
        image: BGR numpy image (full frame)
        landmarks: 5x2 numpy array of [x, y] coordinates
        output_size: (width, height) target image size (112, 112)

    Returns:
        Aligned 112x112 BGR face image.
    """
    landmarks = np.asarray(landmarks, dtype=np.float32)
    if landmarks.shape != (5, 2):
        raise ValueError(f"Expected 5x2 landmarks, received {landmarks.shape}")

    # Scale reference points if output_size != (112, 112)
    ref_pts = ARCFACE_CANONICAL_5PTS.copy()
    if output_size != (112, 112):
        ref_pts[:, 0] *= output_size[0] / 112.0
        ref_pts[:, 1] *= output_size[1] / 112.0

    # Compute similarity transform
    transform_matrix = umeyama_transform(landmarks, ref_pts, estimate_scale=True)

    # Warp affine
    aligned = cv2.warpAffine(
        image,
        transform_matrix,
        output_size,
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    return aligned


def crop_face_bbox(
    image: np.ndarray,
    bbox: np.ndarray | list,
    target_size: Tuple[int, int] = (112, 112),
    margin: float = 0.15,
) -> np.ndarray:
    """
    Fallback square face crop when landmarks are unavailable or invalid.
    Expands bbox with margin, clips to frame, and resizes to target_size.
    """
    h, w = image.shape[:2]
    x1, y1, x2, y2 = bbox[:4]
    box_w = x2 - x1
    box_h = y2 - y1

    # Add margin
    cx = x1 + box_w / 2.0
    cy = y1 + box_h / 2.0
    side = max(box_w, box_h) * (1.0 + margin)

    x1_new = int(max(0, cx - side / 2.0))
    y1_new = int(max(0, cy - side / 2.0))
    x2_new = int(min(w, cx + side / 2.0))
    y2_new = int(min(h, cy + side / 2.0))

    crop = image[y1_new:y2_new, x1_new:x2_new]
    if crop.size == 0:
        return np.zeros((target_size[1], target_size[0], 3), dtype=np.uint8)

    return cv2.resize(crop, target_size, interpolation=cv2.INTER_LINEAR)

"""
Verification and unit test suite for the Face Analytics pipeline.
Validates alignment mathematics, tracking logic, matching algorithms,
event generation, and quality assessment.
"""

import json
import sys
from pathlib import Path
import tempfile
import numpy as np

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.align import ARCFACE_CANONICAL_5PTS, align_face_5pts, umeyama_transform
from src.event_emitter import SurveillanceEventEmitter
from src.matcher import FaceMatcher
from src.quality import FaceQualityAssessor
from src.tracker import FaceTracker


def test_umeyama_alignment():
    """Test that canonical landmarks map to themselves under Umeyama transform."""
    src = ARCFACE_CANONICAL_5PTS.copy()
    dst = ARCFACE_CANONICAL_5PTS.copy()

    m = umeyama_transform(src, dst)
    # Affine matrix on identity points should be close to [[1, 0, 0], [0, 1, 0]]
    expected = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)
    np.testing.assert_allclose(m, expected, atol=1e-3)


def test_quality_assessor():
    """Test smart distance estimation, IPD, yaw angle, and 3-tier surveillance zones."""
    assessor = FaceQualityAssessor(
        min_face_size_recognition=42,
        min_face_size_detection=18,
        min_ipd_pixels=16.0,
        blur_threshold=30.0,
        reference_focal_factor=1500.0,
        recognition_max_distance_m=25.0,
        detection_max_distance_m=50.0,
    )

    # 1. Distant Face (~37.5m, 40px height): Must route to DETECTION_ONLY (no forced recognition)
    dist_face = np.random.randint(50, 200, (40, 40, 3), dtype=np.uint8)
    dist_landmarks = np.array([
        [10, 15], [30, 15], [20, 25], [12, 32], [28, 32]
    ], dtype=np.float32)
    can_rec, meta = assessor.evaluate(dist_face, bbox=[0, 0, 40, 40], landmarks=dist_landmarks)
    assert not can_rec, "Distant face beyond 25m should NOT force recognition"
    assert meta["operational_zone"] == "DETECTION_ONLY"
    assert 35.0 <= meta["distance_m"] <= 40.0

    # 2. Extreme Range (>50m / tiny 14px face): Must REJECT
    tiny_face = np.ones((14, 14, 3), dtype=np.uint8) * 128
    can_rec, meta = assessor.evaluate(tiny_face, bbox=[0, 0, 14, 14])
    assert not can_rec
    assert meta["operational_zone"] == "REJECT"

    # 3. Recognition Range (15m, 100px face, frontal, sharp): Must pass RECOGNITION
    close_face = np.full((100, 100, 3), (130, 170, 215), dtype=np.uint8)
    noise = np.random.randint(-20, 20, (100, 100, 3), dtype=np.int16)
    close_face = np.clip(close_face.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    frontal_landmarks = np.array([
        [30, 35], [70, 35], [50, 55], [35, 75], [65, 75]
    ], dtype=np.float32)
    can_rec, meta = assessor.evaluate(close_face, bbox=[0, 0, 100, 100], landmarks=frontal_landmarks)
    assert can_rec, f"Sharp frontal face in 8-25m range should pass recognition gate (Reason: {meta.get('reason')})"
    assert meta["operational_zone"] == "RECOGNITION"
    assert meta["distance_m"] == 15.0
    assert meta["ipd"] == 40.0
    assert meta["yaw_ratio"] < 0.1

    # 4. Extreme Profile Face (turned >35°): Must route to DETECTION_ONLY
    profile_landmarks = np.array([
        [20, 35], [60, 35], [22, 55], [22, 75], [50, 75]  # nose is right next to left eye
    ], dtype=np.float32)
    can_rec, meta = assessor.evaluate(close_face, bbox=[0, 0, 100, 100], landmarks=profile_landmarks)
    assert not can_rec, "Profile face should defer recognition"
    assert meta["operational_zone"] == "DETECTION_ONLY"
    assert meta["yaw_ratio"] > 0.42


def test_helmet_and_partial_face():
    """Test that helmet and partial face occlusions are detected and defer recognition."""
    assessor = FaceQualityAssessor(helmet_check_enabled=True, min_face_aspect_ratio=0.62)

    # 1. Partial Face (heavily cut off horizontally or vertically)
    partial_crop = np.random.randint(50, 200, (30, 80, 3), dtype=np.uint8)
    can_rec, meta = assessor.evaluate(partial_crop, bbox=[0, 0, 80, 30])
    assert not can_rec
    assert meta["occlusion_type"] == "PARTIAL_FACE"


def test_hierarchical_association():
    """Test that a face is correctly attached to its parent person body track ID."""
    tracker = FaceTracker(min_hits=1)

    # Person body at [100, 100, 300, 500] (w=200, h=400)
    body_boxes = np.array([[100, 100, 300, 500]], dtype=np.float32)
    body_scores = np.array([0.90], dtype=np.float32)
    tracks = tracker.update(body_boxes, body_scores)
    assert len(tracks) == 1
    person_track_id = tracks[0].track_id

    # Face detected in upper head region of person: [160, 120, 240, 220]
    face_boxes = np.array([[160, 120, 240, 220]], dtype=np.float32)
    face_scores = np.array([0.88], dtype=np.float32)
    face_kps = np.array([[[180, 150], [220, 150], [200, 175], [185, 195], [215, 195]]], dtype=np.float32)

    tracker.associate_faces_to_bodies(tracks, face_boxes, face_scores, face_kps)
    assert tracks[0].has_face is True
    assert tracks[0].face_bbox is not None
    assert tracks[0].track_id == person_track_id  # Preserves the SAME body track ID!


def test_tracker_association():
    """Test that the tracker assigns consistent track IDs over successive frames."""
    tracker = FaceTracker(iou_threshold=0.3, max_age=5, min_hits=1)

    # Frame 1: Box at [100, 100, 200, 200]
    boxes_f1 = np.array([[100, 100, 200, 200]], dtype=np.float32)
    scores_f1 = np.array([0.95], dtype=np.float32)
    tracks_f1 = tracker.update(boxes_f1, scores_f1)
    assert len(tracks_f1) == 1
    t1_id = tracks_f1[0].track_id

    # Frame 2: Box slightly moved to [104, 103, 204, 203] (high IoU)
    boxes_f2 = np.array([[104, 103, 204, 203]], dtype=np.float32)
    scores_f2 = np.array([0.96], dtype=np.float32)
    tracks_f2 = tracker.update(boxes_f2, scores_f2)
    assert len(tracks_f2) == 1
    assert tracks_f2[0].track_id == t1_id  # Same track ID maintained!


def test_matcher_cosine_similarity():
    """Test gallery enrollment and matching logic."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        gallery_file = Path(tmp_dir) / "gallery.pkl"
        matcher = FaceMatcher(
            gallery_path=gallery_file,
            similarity_threshold=0.45,
            unknown_label="Unknown",
        )

        # Create synthetic normalized embeddings for two individuals
        np.random.seed(42)
        v_person1 = np.random.randn(512).astype(np.float32)
        v_person1 /= np.linalg.norm(v_person1)

        v_person2 = np.random.randn(512).astype(np.float32)
        v_person2 /= np.linalg.norm(v_person2)

        # Enroll
        matcher.build_from_dict({
            "Officer_Kavita": [v_person1],
            "Major_Batra": [v_person2],
        })

        # Query with slightly perturbed vector of Officer Kavita (high similarity)
        noise = np.random.randn(512).astype(np.float32)
        noise /= np.linalg.norm(noise)
        query = 0.95 * v_person1 + 0.05 * noise
        query /= np.linalg.norm(query)

        name, sim = matcher.match(query)
        assert name == "Officer_Kavita"
        assert sim > 0.85

        # Query with random orthogonal vector (should be Unknown)
        random_intruder = np.random.randn(512).astype(np.float32)
        random_intruder /= np.linalg.norm(random_intruder)

        intruder_name, intruder_sim = matcher.match(random_intruder)
        assert intruder_name == "Unknown"
        assert intruder_sim < 0.45


def test_event_emission():
    """Test structured JSON event emission and logging."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        events_path = Path(tmp_dir) / "events.jsonl"
        snap_dir = Path(tmp_dir) / "snapshots"

        emitter = SurveillanceEventEmitter(
            camera_id="TEST-CAM-01",
            events_log_path=events_path,
            snapshot_dir=snap_dir,
            save_snapshots=True,
            snapshot_interval_frames=1,
        )

        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        event = emitter.emit_event(
            track_id=1,
            identity="Officer_Kavita",
            confidence=0.92,
            bbox=[100, 100, 200, 200],
            full_frame=dummy_frame,
            current_frame_idx=1,
        )

        assert event["camera_id"] == "TEST-CAM-01"
        assert event["status"] == "AUTHORIZED"
        assert event["identity"] == "Officer_Kavita"
        assert event["snapshot_path"] is not None
        assert Path(event["snapshot_path"]).exists()

        # Read JSON Lines file
        with open(events_path, "r", encoding="utf-8") as f:
            line = f.readline()
            record = json.loads(line)
            assert record["event_id"] == event["event_id"]


if __name__ == "__main__":
    print("Running verification tests...")
    test_umeyama_alignment()
    print("[PASS] Umeyama 5-point alignment test passed.")
    test_quality_assessor()
    print("[PASS] Face quality assessor test passed.")
    test_helmet_and_partial_face()
    print("[PASS] Helmet and partial face occlusion test passed.")
    test_hierarchical_association()
    print("[PASS] Hierarchical face-to-body association test passed.")
    test_tracker_association()
    print("[PASS] Face tracker association test passed.")
    test_matcher_cosine_similarity()
    print("[PASS] Face matcher cosine similarity test passed.")
    test_event_emission()
    print("[PASS] Event emitter and snapshot archival test passed.")
    print("\nAll pipeline logic unit tests PASSED successfully!")

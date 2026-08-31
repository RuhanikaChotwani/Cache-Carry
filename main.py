"""
SIH26187: Hierarchical Offline Person & Face Analytics Pipeline.
Edge Video Analytics for Border Surveillance CCTV Infrastructure.

Hierarchical Pipeline Workflow:
1. Long-Range Person Tracking:
   - Tracks full human body across frames with persistent Track ID.
   - Far away (small body): Labeled as "Person" + Track ID + Distance.
2. Gated Head/Face Detection:
   - When person is in candidate range (>= 85px body height):
     Associates face detection (SCRFD) directly to the parent body Track ID.
3. Multi-Metric Quality & Helmet/Occlusion Gate:
   - Checks face size, blur, IPD, and headgear/helmet occlusion.
   - If helmet or mask detected: Labeled as "Helmeted Person" or "Partial Face".
     Bypasses ArcFace to prevent false alarms.
4. Tiered Recognition:
   - When quality passes and face is frontal: ArcFace runs and attaches Name
     directly to the SAME persistent body Track ID!
"""

import argparse
from pathlib import Path
import sys
import time
import cv2
import numpy as np

from src.align import align_face_5pts, crop_face_bbox
from src.config import load_config
from src.detector import PersonDetector, SCRFDDetector
from src.event_emitter import SurveillanceEventEmitter
from src.matcher import FaceMatcher
from src.quality import FaceQualityAssessor
from src.recognizer import ArcFaceRecognizer
from src.tracker import FaceTrack, FaceTracker
from src.visualizer import SurveillanceVisualizer

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def run_image_pipeline(
    image_path: str | Path,
    config_path: str = "configs/config.yaml",
    headless: bool = False,
    output_path: str | None = None,
) -> None:
    """Processes a static image with hierarchical body detection and gated face recognition."""
    cfg = load_config(config_path)
    img_path = Path(image_path)
    if not img_path.exists():
        print(f"[ERROR] Input image not found: {img_path}")
        sys.exit(1)

    frame = cv2.imread(str(img_path))
    if frame is None:
        print(f"[ERROR] Could not decode image: {img_path}")
        sys.exit(1)

    device = cfg["system"]["device"].lower()
    use_cuda = (device == "cuda")
    cuda_id = cfg["system"].get("cuda_device_id", 0)

    # Models
    det_path = Path(cfg["models"]["detector_path"])
    rec_path = Path(cfg["models"]["recognizer_path"])
    hier_cfg = cfg.get("hierarchical", {})

    person_detector = PersonDetector(
        model_path=hier_cfg.get("person_model_path", "models/yolov8n.onnx"),
        conf_threshold=hier_cfg.get("person_conf_threshold", 0.40),
        use_cuda=use_cuda,
        cuda_device_id=cuda_id,
    )

    face_detector = SCRFDDetector(
        model_path=det_path,
        conf_threshold=cfg["detection"]["conf_threshold"],
        nms_threshold=cfg["detection"]["nms_threshold"],
        input_size=tuple(cfg["models"]["det_input_size"]),
        use_cuda=use_cuda,
        cuda_device_id=cuda_id,
    )

    recognizer = ArcFaceRecognizer(
        model_path=rec_path,
        use_cuda=use_cuda,
        cuda_device_id=cuda_id,
    )

    matcher = FaceMatcher(
        gallery_path=cfg["recognition"]["gallery_path"],
        similarity_threshold=cfg["recognition"]["similarity_threshold"],
        unknown_label=cfg["recognition"]["unknown_label"],
    )

    dist_cfg = cfg.get("distance_estimation", {})
    qf_cfg = cfg.get("quality_filter", {})
    quality_filter = FaceQualityAssessor(
        min_face_size_recognition=qf_cfg.get("min_face_size_recognition", 40),
        min_face_size_detection=qf_cfg.get("min_face_size_detection", 18),
        min_ipd_pixels=qf_cfg.get("min_ipd_pixels", 16.0),
        blur_threshold=qf_cfg.get("blur_threshold", 40.0),
        min_brightness=qf_cfg.get("min_brightness", 25.0),
        max_brightness=qf_cfg.get("max_brightness", 240.0),
        max_yaw_ratio=qf_cfg.get("max_yaw_ratio", 0.42),
        reference_focal_factor=dist_cfg.get("reference_focal_factor", 1500.0),
        recognition_min_distance_m=dist_cfg.get("recognition_min_distance_m", 3.0),
        recognition_max_distance_m=dist_cfg.get("recognition_max_distance_m", 25.0),
        detection_max_distance_m=dist_cfg.get("detection_max_distance_m", 50.0),
        helmet_check_enabled=qf_cfg.get("helmet_check_enabled", True),
        min_face_aspect_ratio=qf_cfg.get("min_face_aspect_ratio", 0.62),
        forehead_occlusion_ratio=qf_cfg.get("forehead_occlusion_ratio", 0.45),
    )

    event_emitter = SurveillanceEventEmitter(
        camera_id=cfg["events"]["camera_id"],
        events_log_path=cfg["events"]["events_log_path"],
        snapshot_dir=cfg["events"]["snapshot_dir"],
        save_snapshots=cfg["events"]["save_snapshots"],
        snapshot_interval_frames=1,
    )

    visualizer = SurveillanceVisualizer(
        box_thickness=cfg["visualization"]["box_thickness"],
        font_scale=cfg["visualization"]["font_scale"],
        color_known=tuple(cfg["visualization"]["color_known"]),
        color_unknown=tuple(cfg["visualization"]["color_unknown"]),
        color_distant=tuple(cfg["visualization"].get("color_distant", [0, 215, 255])),
        color_person=tuple(cfg["visualization"].get("color_person", [210, 210, 210])),
        color_helmet=tuple(cfg["visualization"].get("color_helmet", [0, 165, 255])),
        show_fps=False,
        show_landmarks=cfg["visualization"]["show_landmarks"],
        show_distance=cfg["visualization"].get("show_distance", True),
    )

    print(f"\n[Pipeline] Processing static image: {img_path} ({frame.shape[1]}x{frame.shape[0]})")

    # Step 1: Detect Person Bodies
    person_bboxes, person_scores = person_detector.detect(frame)
    print(f"[Pipeline] Detected {len(person_bboxes)} person body(s).")

    # Step 2: Detect Faces
    face_bboxes, face_scores, face_landmarks = face_detector.detect(frame)
    print(f"[Pipeline] Detected {len(face_bboxes)} face(s).")

    active_tracks = []
    tracker = FaceTracker(min_hits=1)

    if len(person_bboxes) > 0:
        active_tracks = tracker.update(person_bboxes, person_scores)
        tracker.associate_faces_to_bodies(
            active_tracks,
            face_bboxes,
            face_scores,
            face_landmarks,
            head_ratio=hier_cfg.get("head_region_ratio", 0.38),
        )
    else:
        # Fallback to direct face tracks if person body not detected
        active_tracks = tracker.update(face_bboxes, face_scores, face_landmarks)
        for t in active_tracks:
            t.has_face = True
            t.face_bbox = t.bbox

    for track in active_tracks:
        if track.has_face and track.face_bbox is not None:
            if track.landmarks is not None:
                aligned_face = align_face_5pts(frame, track.landmarks)
            else:
                aligned_face = crop_face_bbox(frame, track.face_bbox)

            can_rec, q_meta = quality_filter.evaluate(
                aligned_face, bbox=track.face_bbox, landmarks=track.landmarks
            )
            zone = q_meta.get("operational_zone", "DETECTION_ONLY")
            dist_m = q_meta.get("distance_m", 0.0)
            occ_type = q_meta.get("occlusion_type", "NONE")

            track.update_metrics(
                distance_m=dist_m,
                zone=zone,
                ipd=q_meta.get("ipd", 0.0),
                yaw_ratio=q_meta.get("yaw_ratio", 0.0),
                occlusion_type=occ_type,
                has_face=True,
            )

            if zone == "RECOGNITION" and can_rec and occ_type == "NONE":
                embedding = recognizer.extract_embedding(aligned_face)
                identity, sim = matcher.match(embedding)
                track.add_recognition_result(identity, sim)
                print(f"  Track #{track.track_id} [Zone: {zone}, Dist: ~{dist_m:.0f}m]: {identity} (Sim: {sim:.3f})")
            else:
                print(f"  Track #{track.track_id} [{track.identity}, Dist: ~{dist_m:.0f}m]: {q_meta.get('reason')}")
        else:
            # Person far away without clear face
            body_h = track.bbox[3] - track.bbox[1]
            dist_m = round(float(1500.0 * 1.7 / max(body_h, 1.0)), 1)
            track.update_metrics(distance_m=dist_m, zone="DETECTION_ONLY", has_face=False)
            q_meta = {"operational_zone": "DETECTION_ONLY", "distance_m": dist_m, "reason": "Person at range; face not resolved"}
            print(f"  Track #{track.track_id} [Person, Dist: ~{dist_m:.0f}m]: Body tracking active")

        event_emitter.emit_event(
            track_id=track.track_id,
            identity=track.identity,
            confidence=track.confidence,
            bbox=track.bbox,
            full_frame=frame,
            current_frame_idx=1,
            quality_metrics=q_meta,
        )

    rendered_frame = visualizer.render(
        frame=frame,
        tracks=active_tracks,
        fps=0.0,
        camera_id=cfg["events"]["camera_id"],
        hardware_info="Hierarchical Image Analytics",
    )

    if output_path:
        out_file = Path(output_path)
    else:
        out_file = Path("data/snapshots") / f"detected_{img_path.stem}.jpg"

    out_file.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_file), rendered_frame)
    print(f"[Pipeline] Saved annotated output image to: {out_file}")

    if not headless and cfg["visualization"]["show_window"]:
        print("\nDisplaying image. Press any key in the window to close...")
        cv2.imshow(cfg["visualization"]["window_title"], rendered_frame)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


def run_pipeline(
    source: str | int,
    config_path: str = "configs/config.yaml",
    headless: bool = False,
    output_video_path: str | None = None,
) -> None:
    if isinstance(source, str) and Path(source).suffix.lower() in IMAGE_EXTENSIONS:
        run_image_pipeline(
            image_path=source,
            config_path=config_path,
            headless=headless,
            output_path=output_video_path,
        )
        return

    cfg = load_config(config_path)

    print("\n" + "=" * 70)
    print("  SIH26187: HIERARCHICAL PERSON & FACE SURVEILLANCE PIPELINE (OFFLINE)  ")
    print("=" * 70)

    device = cfg["system"]["device"].lower()
    use_cuda = (device == "cuda")
    cuda_id = cfg["system"].get("cuda_device_id", 0)

    det_path = Path(cfg["models"]["detector_path"])
    rec_path = Path(cfg["models"]["recognizer_path"])
    hier_cfg = cfg.get("hierarchical", {})
    hierarchical_enabled = hier_cfg.get("enabled", True)
    head_ratio = hier_cfg.get("head_region_ratio", 0.38)
    min_person_height = hier_cfg.get("min_person_height_for_face", 85)

    if not det_path.exists() or not rec_path.exists():
        print("[ERROR] Required model files missing. Run 'python download_models.py'.")
        sys.exit(1)

    print(f"[Pipeline] Initializing Person Detector ({hier_cfg.get('person_model_path')})...")
    person_detector = PersonDetector(
        model_path=hier_cfg.get("person_model_path", "models/yolov8n.onnx"),
        conf_threshold=hier_cfg.get("person_conf_threshold", 0.40),
        use_cuda=use_cuda,
        cuda_device_id=cuda_id,
    )

    print(f"[Pipeline] Initializing Face Detector from {det_path}...")
    face_detector = SCRFDDetector(
        model_path=det_path,
        conf_threshold=cfg["detection"]["conf_threshold"],
        nms_threshold=cfg["detection"]["nms_threshold"],
        input_size=tuple(cfg["models"]["det_input_size"]),
        use_cuda=use_cuda,
        cuda_device_id=cuda_id,
    )

    print(f"[Pipeline] Initializing ArcFace Recognizer from {rec_path}...")
    recognizer = ArcFaceRecognizer(
        model_path=rec_path,
        use_cuda=use_cuda,
        cuda_device_id=cuda_id,
    )

    matcher = FaceMatcher(
        gallery_path=cfg["recognition"]["gallery_path"],
        similarity_threshold=cfg["recognition"]["similarity_threshold"],
        unknown_label=cfg["recognition"]["unknown_label"],
    )

    tracker = FaceTracker(
        iou_threshold=cfg["tracking"]["iou_threshold"],
        max_age=cfg["tracking"]["max_age"],
        min_hits=cfg["tracking"]["min_hits"],
    )

    dist_cfg = cfg.get("distance_estimation", {})
    qf_cfg = cfg.get("quality_filter", {})
    quality_filter = FaceQualityAssessor(
        min_face_size_recognition=qf_cfg.get("min_face_size_recognition", 40),
        min_face_size_detection=qf_cfg.get("min_face_size_detection", 18),
        min_ipd_pixels=qf_cfg.get("min_ipd_pixels", 16.0),
        blur_threshold=qf_cfg.get("blur_threshold", 40.0),
        min_brightness=qf_cfg.get("min_brightness", 25.0),
        max_brightness=qf_cfg.get("max_brightness", 240.0),
        max_yaw_ratio=qf_cfg.get("max_yaw_ratio", 0.42),
        reference_focal_factor=dist_cfg.get("reference_focal_factor", 1500.0),
        recognition_min_distance_m=dist_cfg.get("recognition_min_distance_m", 3.0),
        recognition_max_distance_m=dist_cfg.get("recognition_max_distance_m", 25.0),
        detection_max_distance_m=dist_cfg.get("detection_max_distance_m", 50.0),
        helmet_check_enabled=qf_cfg.get("helmet_check_enabled", True),
        min_face_aspect_ratio=qf_cfg.get("min_face_aspect_ratio", 0.62),
        forehead_occlusion_ratio=qf_cfg.get("forehead_occlusion_ratio", 0.45),
    )

    event_emitter = SurveillanceEventEmitter(
        camera_id=cfg["events"]["camera_id"],
        events_log_path=cfg["events"]["events_log_path"],
        snapshot_dir=cfg["events"]["snapshot_dir"],
        save_snapshots=cfg["events"]["save_snapshots"],
        snapshot_interval_frames=cfg["events"]["snapshot_interval_frames"],
        save_unknown_alerts=cfg["events"]["save_unknown_alerts"],
        save_known_alerts=cfg["events"]["save_known_alerts"],
    )

    visualizer = SurveillanceVisualizer(
        box_thickness=cfg["visualization"]["box_thickness"],
        font_scale=cfg["visualization"]["font_scale"],
        color_known=tuple(cfg["visualization"]["color_known"]),
        color_unknown=tuple(cfg["visualization"]["color_unknown"]),
        color_distant=tuple(cfg["visualization"].get("color_distant", [0, 215, 255])),
        color_person=tuple(cfg["visualization"].get("color_person", [210, 210, 210])),
        color_helmet=tuple(cfg["visualization"].get("color_helmet", [0, 165, 255])),
        show_fps=cfg["visualization"]["show_fps"],
        show_landmarks=cfg["visualization"]["show_landmarks"],
        show_distance=cfg["visualization"].get("show_distance", True),
    )

    # Video Capture
    stream_source: str | int = source
    if isinstance(source, str) and source.isdigit():
        stream_source = int(source)

    print(f"[Pipeline] Opening video input source: {stream_source}")
    cap = cv2.VideoCapture(stream_source)
    if isinstance(stream_source, int) and sys.platform.startswith("win"):
        cap.release()
        cap = cv2.VideoCapture(stream_source, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print(f"[ERROR] Could not open video source: {stream_source}")
        sys.exit(1)

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    input_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    print(f"[Pipeline] Stream connected: {frame_width}x{frame_height} @ {input_fps:.1f} FPS")

    video_writer = None
    if output_video_path:
        out_p = Path(output_video_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        video_writer = cv2.VideoWriter(str(out_p), fourcc, input_fps, (frame_width, frame_height))
        print(f"[Pipeline] Recording output stream to: {out_p}")

    recognize_interval = cfg["tracking"].get("recognize_every_n_frames", 5)
    frame_idx = 0
    fps = 0.0
    fps_smoothing = 0.9
    paused = False

    print("\nSurveillance Stream Active. Press 'q' or ESC in window to exit, 's' to snapshot, 'p' to pause.\n")

    try:
        while True:
            if not paused:
                ret, frame = cap.read()
                if not ret:
                    print("[Pipeline] End of video stream or connection lost.")
                    break

                frame_idx += 1
                loop_start = time.time()

                # Step 1: Long-Range Person Body Detection First
                body_bboxes, body_scores = np.zeros((0, 4), dtype=np.float32), np.zeros((0,), dtype=np.float32)
                if hierarchical_enabled:
                    body_bboxes, body_scores = person_detector.detect(frame)

                # Step 2: Face Detection & 5 Landmarks
                face_bboxes, face_scores, face_landmarks = face_detector.detect(frame)

                # Step 3: Hierarchical Tracking
                if len(body_bboxes) > 0:
                    active_tracks = tracker.update(body_bboxes, body_scores)
                    tracker.associate_faces_to_bodies(
                        active_tracks, face_bboxes, face_scores, face_landmarks, head_ratio=head_ratio
                    )
                else:
                    # Fallback to direct face tracking when person detector finds no bodies
                    active_tracks = tracker.update(face_bboxes, face_scores, face_landmarks)
                    for t in active_tracks:
                        t.has_face = True
                        t.face_bbox = t.bbox

                # Step 4: Gated Quality, Occlusion & Recognition
                for track in active_tracks:
                    if track.has_face and track.face_bbox is not None:
                        if track.landmarks is not None:
                            aligned_face = align_face_5pts(frame, track.landmarks)
                        else:
                            aligned_face = crop_face_bbox(frame, track.face_bbox)

                        can_rec, quality_meta = quality_filter.evaluate(
                            aligned_face, bbox=track.face_bbox, landmarks=track.landmarks
                        )
                        zone = quality_meta.get("operational_zone", "DETECTION_ONLY")
                        dist_m = quality_meta.get("distance_m", 0.0)
                        occ_type = quality_meta.get("occlusion_type", "NONE")

                        track.update_metrics(
                            distance_m=dist_m,
                            zone=zone,
                            ipd=quality_meta.get("ipd", 0.0),
                            yaw_ratio=quality_meta.get("yaw_ratio", 0.0),
                            occlusion_type=occ_type,
                            has_face=True,
                        )

                        # Recognition gate: In range + clear + not occluded
                        if zone == "RECOGNITION" and can_rec and occ_type == "NONE":
                            needs_rec = (
                                track.identity in ("Unknown", "Person")
                                or "Person" in track.identity
                                or track.frames_since_recognition >= recognize_interval
                            )
                            if needs_rec:
                                embedding = recognizer.extract_embedding(aligned_face)
                                identity, sim = matcher.match(embedding)
                                track.add_recognition_result(identity, sim)
                        else:
                            track.frames_since_recognition += 1
                    else:
                        # Person body tracked, but face not yet resolved
                        body_h = track.bbox[3] - track.bbox[1]
                        dist_m = round(float(1500.0 * 1.7 / max(body_h, 1.0)), 1)
                        track.update_metrics(distance_m=dist_m, zone="DETECTION_ONLY", has_face=False)
                        quality_meta = {
                            "operational_zone": "DETECTION_ONLY",
                            "distance_m": dist_m,
                            "occlusion_type": "NONE",
                            "reason": "Person at long range; face not yet resolved",
                        }

                    # Step 5: Emit Event & Snapshot
                    event_emitter.emit_event(
                        track_id=track.track_id,
                        identity=track.identity,
                        confidence=track.confidence,
                        bbox=track.bbox,
                        full_frame=frame,
                        current_frame_idx=frame_idx,
                        quality_metrics=quality_meta,
                    )

                # FPS calculation
                loop_time = time.time() - loop_start
                instant_fps = 1.0 / max(loop_time, 1e-5)
                fps = (fps * fps_smoothing) + (instant_fps * (1.0 - fps_smoothing))

                # Step 6: Visualizer Overlay with Hierarchical Labels
                rendered_frame = visualizer.render(
                    frame=frame,
                    tracks=active_tracks,
                    fps=fps,
                    camera_id=cfg["events"]["camera_id"],
                    hardware_info=f"RTX 4050 ({'CUDA' if use_cuda else 'CPU'})",
                )

                if video_writer:
                    video_writer.write(rendered_frame)

            if not headless and cfg["visualization"]["show_window"]:
                cv2.imshow(cfg["visualization"]["window_title"], rendered_frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q"), ord("Q")):
                    print("[Pipeline] Exit signal received.")
                    break
                elif key in (ord("p"), ord("P")):
                    paused = not paused
                    print(f"[Pipeline] Stream {'PAUSED' if paused else 'RESUMED'}")
                elif key in (ord("s"), ord("S")):
                    manual_snap = f"data/snapshots/manual_snap_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
                    cv2.imwrite(manual_snap, rendered_frame)
                    print(f"[Pipeline] Manual snapshot saved to: {manual_snap}")

    except KeyboardInterrupt:
        print("\n[Pipeline] Interrupted by user.")
    finally:
        cap.release()
        if video_writer:
            video_writer.release()
        if not headless:
            cv2.destroyAllWindows()
        print("[Pipeline] Video capture and display terminated safely.")


def main():
    parser = argparse.ArgumentParser(
        description="SIH26187 Hierarchical Offline Surveillance Pipeline"
    )
    parser.add_argument(
        "--source",
        type=str,
        default="0",
        help="Input source: webcam index (0), image file, video file, or RTSP URL",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/config.yaml",
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without displaying GUI window",
    )
    parser.add_argument(
        "--record",
        type=str,
        default=None,
        help="Path to output file to record annotated surveillance stream or save image",
    )
    args = parser.parse_args()

    run_pipeline(
        source=args.source,
        config_path=args.config,
        headless=args.headless,
        output_video_path=args.record,
    )


if __name__ == "__main__":
    main()

"""
Offline Face Enrollment CLI Script.

Scans the local gallery directory structure:
  data/gallery/
    Person_Name_1/
      photo1.jpg
      photo2.png
    Person_Name_2/
      photo1.jpg

Detects faces, extracts 5-point landmarks, aligns to canonical 112x112,
computes 512-d ArcFace embeddings, and creates the offline gallery index.
"""

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Dict, List
import cv2
import numpy as np
from tqdm import tqdm

from src.align import align_face_5pts, crop_face_bbox
from src.config import load_config
from src.detector import SCRFDDetector
from src.matcher import FaceMatcher
from src.quality import FaceQualityAssessor
from src.recognizer import ArcFaceRecognizer


VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def enroll_gallery(
    gallery_dir: Path,
    config_path: Path | str = "configs/config.yaml",
) -> None:
    cfg = load_config(config_path)

    # Initialize components
    print("\n" + "=" * 65)
    print("      SIH26187 OFFLINE FACE ENROLLMENT PIPELINE      ")
    print("=" * 65)

    det_path = Path(cfg["models"]["detector_path"])
    rec_path = Path(cfg["models"]["recognizer_path"])

    if not det_path.exists():
        print(f"\n[ERROR] Detector model not found at: {det_path}")
        print("Please run python download_models.py or place det_10g.onnx in models/")
        sys.exit(1)

    if not rec_path.exists():
        print(f"\n[ERROR] Recognizer model not found at: {rec_path}")
        print("Please run python download_models.py or place w600k_r50.onnx in models/")
        sys.exit(1)

    use_cuda = (cfg["system"]["device"].lower() == "cuda")
    cuda_id = cfg["system"].get("cuda_device_id", 0)

    detector = SCRFDDetector(
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

    quality_filter = FaceQualityAssessor(
        min_face_size=cfg["quality_filter"]["min_face_size"],
        blur_threshold=cfg["quality_filter"]["blur_threshold"],
        min_brightness=cfg["quality_filter"]["min_brightness"],
        max_brightness=cfg["quality_filter"]["max_brightness"],
    )

    matcher = FaceMatcher(
        gallery_path=cfg["recognition"]["gallery_path"],
        similarity_threshold=cfg["recognition"]["similarity_threshold"],
        unknown_label=cfg["recognition"]["unknown_label"],
    )

    if not gallery_dir.exists():
        gallery_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n[Info] Created empty gallery folder at: {gallery_dir}")
        print("Drop person subfolders (e.g. data/gallery/Amit_Sharma/*.jpg) and re-run.")
        sys.exit(0)

    person_dirs = [d for d in gallery_dir.iterdir() if d.is_dir()]
    if not person_dirs:
        print(f"\n[Warning] No person directories found in: {gallery_dir}")
        print("Expected structure:")
        print("  data/gallery/<Person_Name>/img1.jpg")
        sys.exit(0)

    print(f"\nFound {len(person_dirs)} person folders in {gallery_dir}:")
    for d in person_dirs:
        print(f"  - {d.name}")

    enrollment_data: Dict[str, List[np.ndarray]] = {}
    manifest_records: Dict[str, Dict] = {}
    total_images_processed = 0
    total_faces_enrolled = 0

    start_time = time.time()

    for p_dir in person_dirs:
        person_name = p_dir.name
        image_files = [
            f for f in p_dir.iterdir() if f.suffix.lower() in VALID_EXTENSIONS
        ]

        if not image_files:
            print(f"  [Skip] No valid images found in {p_dir.name}")
            continue

        person_embeddings: List[np.ndarray] = []
        accepted_files: List[str] = []

        print(f"\nProcessing '{person_name}' ({len(image_files)} images)...")

        for img_file in tqdm(image_files, desc=f"  {person_name}", leave=False):
            total_images_processed += 1
            img = cv2.imread(str(img_file))
            if img is None:
                print(f"    [Warning] Could not read image: {img_file.name}")
                continue

            # Detect faces (prefer largest face in enrollment image)
            bboxes, scores, landmarks = detector.detect(img, max_num=1, metric="max")

            if len(bboxes) == 0:
                print(f"    [Notice] No face detected in: {img_file.name}")
                continue

            bbox = bboxes[0]
            score = scores[0]
            kps = landmarks[0] if landmarks is not None else None

            # Align face
            if kps is not None:
                aligned_face = align_face_5pts(img, kps, output_size=(112, 112))
            else:
                aligned_face = crop_face_bbox(img, bbox, target_size=(112, 112))

            # Quality assessment
            if cfg["quality_filter"]["enabled"]:
                passed, metrics = quality_filter.evaluate(aligned_face, bbox=bbox)
                if not passed:
                    print(f"    [Filtered] {img_file.name} skipped: {metrics.get('reason')}")
                    continue

            # Extract 512-d normalized embedding
            emb = recognizer.extract_embedding(aligned_face)
            person_embeddings.append(emb)
            accepted_files.append(img_file.name)
            total_faces_enrolled += 1

        if person_embeddings:
            enrollment_data[person_name] = person_embeddings
            manifest_records[person_name] = {
                "enrolled_images_count": len(person_embeddings),
                "image_files": accepted_files,
            }

    # Build and serialize local gallery
    matcher.build_from_dict(enrollment_data)
    matcher.save_gallery()

    # Save human-readable manifest
    manifest_path = Path(cfg["recognition"]["gallery_manifest_path"])
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_content = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "identities_count": len(enrollment_data),
        "total_embeddings": total_faces_enrolled,
        "identities": manifest_records,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_content, f, indent=2)

    elapsed = time.time() - start_time
    print("\n" + "=" * 65)
    print("               ENROLLMENT COMPLETE SUMMARY               ")
    print("=" * 65)
    print(f"Total images scanned   : {total_images_processed}")
    print(f"Valid faces enrolled   : {total_faces_enrolled}")
    print(f"Total unique identities: {len(enrollment_data)}")
    print(f"Elapsed time           : {elapsed:.2f} seconds")
    print(f"Gallery binary index   : {cfg['recognition']['gallery_path']}")
    print(f"Manifest JSON          : {manifest_path}")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(
        description="SIH26187 Offline Face Enrollment CLI"
    )
    parser.add_argument(
        "--gallery-dir",
        type=str,
        default="data/gallery",
        help="Path to folder containing person subdirectories",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/config.yaml",
        help="Path to YAML configuration file",
    )
    args = parser.parse_args()

    enroll_gallery(
        gallery_dir=Path(args.gallery_dir),
        config_path=args.config,
    )


if __name__ == "__main__":
    main()

# IBVAP Sample Videos Directory

This directory contains optional bundled sample video files used for offline surveillance demonstration and testing.

## Recommended Video Specifications

1. **Duration**: 15 to 45 seconds per clip.
2. **Resolution**: 480p (640x480) or 720p (1280x720) recommended.
3. **Format / Codec**: MP4 container with H.264 video codec.
4. **Ethics and Consent**: Videos containing human faces must be recorded by the team with explicit consent or sourced from appropriately licensed datasets.

## Recommended Demonstration Setup

- **`team_face_reference.jpg`**: A clear, front-facing photo of a consenting teammate enrolled in the FCR Watchlist (via UI or `/api/fcr/enroll`).
- **`demo_match.mp4`**: A video where that enrolled teammate enters the frame. The system will detect the face via YuNet, extract the SFace embedding, match against the enrolled vector (cosine similarity >= 0.55), and raise a rate-limited high-threat alert + SHA-256 evidence certificate.
- **`demo_unknown.mp4`**: A video where an unenrolled subject appears. The face is detected and marked as `Unknown` without triggering any alert or ledger entry.
- **`demo_plate.mp4`**: A vehicle approaching with a visible license plate for the optional ANPR engine.

## Git Tracking Notice

Large video binary files (*.mp4, *.avi, *.mov, *.mkv) are excluded from git repository commits via `.gitignore`.

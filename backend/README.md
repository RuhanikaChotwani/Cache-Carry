# IBVAP Backend

FastAPI backend service for the Intelligent Border Video Analytics Platform (FCR Surveillance Prototype).

---

## 1. Quick Start

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start backend service
uvicorn main:app --host 127.0.0.1 --port 8000
```

Interactive API documentation will be available at: `http://127.0.0.1:8000/docs`

---

## 2. Models Setup

Place the following OpenCV Zoo model files in `backend/models/`:
- `face_detection_yunet_2023mar.onnx` (YuNet Face Detector)
- `face_recognition_sface_2021dec.onnx` (SFace Face Recognizer)
- `license_plate_detection_lpd_yunet_2023mar.onnx` (LPD YuNet Plate Detector, optional)

---

## 3. Endpoints Overview

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Model and service health status |
| `/api/webcam/start` | POST | Start live webcam acquisition |
| `/api/webcam/stop` | POST | Stop webcam capture loop |
| `/api/webcam/status` | GET | Camera and model status |
| `/api/webcam/raw.mjpg` | GET | Raw camera MJPEG stream |
| `/api/webcam/ai.mjpg` | GET | AI annotated MJPEG stream |
| `/api/webcam/detections` | GET | Current frame detections JSON |
| `/api/webcam/debug-face-frame.jpg` | GET | Visual diagnostic snapshot frame |
| `/api/fcr/enroll` | POST | Target image upload and SFace vector extraction |
| `/api/fcr/watchlist` | GET | Enrolled targets watchlist |
| `/api/fcr/watchlist/{face_id}` | DELETE | Remove enrolled target |
| `/api/fcr/matches` | GET | Match event history |
| `/api/anpr/latest` | GET | ANPR detector status and results |
| `/api/alerts` | GET | Verified threat alerts log |
| `/api/alerts` | DELETE | Clear alert records |
| `/api/ledger` | GET | Local SHA-256 evidence hash chain |
| `/api/ledger/validate` | GET | Cryptographic ledger validation |

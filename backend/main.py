"""IBVAP Backend - Main FastAPI Application Entry Point.
Intelligent Border Video Analytics Platform (FCR Surveillance Prototype).
"""

import os
from typing import Optional, Union
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services import webcam, fcr_watchlist, anpr_engine, anpr_store, alert_store, ledger, face_engine, video_manager

app = FastAPI(
    title="IBVAP - Intelligent Border Video Analytics Platform",
    version="2.0.0",
    description="Face-first surveillance prototype with live FCR watchlist matching and SHA-256 evidence integrity.",
)

# CORS - allow frontend dev server and public domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_private_network_header(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response



class StartStreamRequest(BaseModel):
    source_type: str = "webcam"
    source_id: Optional[str] = None
    source: Optional[Union[int, str]] = None
    source_name: Optional[str] = None
    loop: bool = True


# System Health
@app.get("/api/health")
def health():
    f_status = face_engine.get_face_engine_status() or {}
    a_status = anpr_engine.get_status() or {}
    w_status = webcam.get_status() or {}

    return {
        "status": "operational",
        "service": "IBVAP Face-First Surveillance Prototype",
        "version": "2.0.0",
        "models": {
            "yunet": {
                "name": "YuNet Face Detector (2023mar)",
                "path": f_status.get("yunet_path"),
                "file_exists": f_status.get("yunet_file_exists", False),
                "loaded": f_status.get("yunet_loaded", False),
                "error": f_status.get("yunet_error"),
            },
            "sface": {
                "name": "SFace Face Recognizer (2021dec)",
                "path": f_status.get("sface_path"),
                "file_exists": f_status.get("sface_file_exists", False),
                "loaded": f_status.get("sface_loaded", False),
                "error": f_status.get("sface_error"),
            },
            "lpd_yunet": {
                "name": "LPD YuNet License Plate Detector (2023mar)",
                "path": a_status.get("lpd_path"),
                "file_exists": a_status.get("lpd_file_exists", False),
                "loaded": a_status.get("lpd_loaded", False),
                "error": a_status.get("lpd_error"),
            },
        },
        "camera": w_status,
    }


# Live Video and Streams
@app.post("/api/webcam/start")
def start_webcam(
    body: Optional[StartStreamRequest] = Body(None),
    source: Optional[Union[int, str]] = None,
):
    if body is not None:
        return webcam.start(
            source=body.source if body.source is not None else (body.source_id or 0),
            source_type=body.source_type,
            source_id=body.source_id,
            source_name=body.source_name,
            loop=body.loop,
        )
    src_val = source if source is not None else 0
    return webcam.start(source=src_val, source_type="webcam")


@app.post("/api/webcam/stop")
def stop_webcam():
    return webcam.stop()


@app.get("/api/webcam/status")
def webcam_status():
    return webcam.get_status()


@app.get("/api/webcam/raw.mjpg")
def webcam_raw_stream(session: Optional[int] = None):
    return StreamingResponse(
        webcam.raw_mjpeg_generator(session_id=session),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/api/webcam/ai.mjpg")
def webcam_ai_stream(session: Optional[int] = None):
    return StreamingResponse(
        webcam.ai_mjpeg_generator(session_id=session),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/api/webcam/detections")
def webcam_detections():
    return webcam.get_detections_payload()


@app.get("/api/webcam/debug-face-frame.jpg")
def webcam_debug_face_frame():
    from fastapi.responses import Response
    return Response(
        content=webcam.get_debug_face_frame(),
        media_type="image/jpeg",
    )


# Video Source Management and Upload
@app.get("/api/video-sources")
def get_video_sources():
    return video_manager.list_demo_videos()


@app.post("/api/video/upload")
async def upload_video(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        res = video_manager.save_uploaded_video(file.filename or "uploaded_video.mp4", file_bytes)
        return res
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


# FCR Watchlist and Enrollment
@app.post("/api/fcr/enroll")
async def enroll_face(name: str = Form(...), image: UploadFile = File(...)):
    try:
        image_bytes = await image.read()
        res = fcr_watchlist.enroll_target_image(name=name, image_bytes=image_bytes)
        return res
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enrollment failed: {e}")


@app.get("/api/fcr/watchlist")
def get_watchlist():
    return fcr_watchlist.get_watchlist()


@app.delete("/api/fcr/watchlist/{face_id}")
def delete_watchlist_face(face_id: str):
    success = fcr_watchlist.delete_from_watchlist(face_id)
    if not success:
        raise HTTPException(status_code=404, detail="Face record not found")
    return {"status": "deleted", "id": face_id}


@app.get("/api/fcr/matches")
def get_recent_matches():
    return fcr_watchlist.get_recent_matches()


# ANPR / License Plate Recognition
@app.get("/api/anpr/latest")
def get_latest_anpr():
    return anpr_engine.get_latest_anpr()


@app.get("/api/anpr/diagnostics")
def get_anpr_diagnostics():
    return anpr_engine.get_diagnostics()


@app.post("/api/anpr/toggle")
def toggle_anpr(body: dict = Body(...)):
    enabled = body.get("enabled", True)
    anpr_engine.set_anpr_enabled(enabled)
    return {"status": "updated", "anpr_enabled": anpr_engine.is_anpr_enabled()}


@app.get("/api/anpr/records")
def get_anpr_records(limit: int = 100):
    return anpr_store.get_records(limit=limit)


@app.delete("/api/anpr/records")
def clear_anpr_records():
    return anpr_store.clear_records()


# Verified Alerts
@app.get("/api/alerts")
def get_alerts(limit: int = 100):
    return alert_store.get_alerts(limit=limit)


@app.delete("/api/alerts")
def clear_alerts():
    return alert_store.clear_alerts()


# Cryptographic Evidence Ledger - Event Evidence Blocks
@app.get("/api/ledger")
def get_ledger_entries():
    return ledger.get_ledger()


@app.get("/api/ledger/validate")
def validate_ledger_entries():
    return ledger.validate_ledger()


# Frame Hash Chain and Evidence Integrity
@app.get("/api/ledger/status")
def ledger_status():
    return ledger.get_ledger_status()


@app.get("/api/ledger/recent")
def ledger_recent(limit: int = 50):
    return ledger.get_recent_chain(limit=limit)


@app.get("/api/ledger/verify")
def ledger_verify(session_id: Optional[str] = None):
    return ledger.verify_frame_chain(session_id=session_id)

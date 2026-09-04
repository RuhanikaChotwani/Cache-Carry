"""Camera management service + API router for IBVAP."""
import os, uuid, threading, time
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from schemas.api import CameraCreate, CameraUpdate, CameraOut, ZoneCreate, CalibrationData
from services import storage, ai_pipeline, scene3d, blockchain, laptop_camera

router = APIRouter(prefix="/api", tags=["cameras"])


# --- Laptop Webcam Specific Endpoints ---
@router.post("/cameras/laptop/start")
def start_laptop_camera(source: int = 0, mode: str = "webcam"):
    return laptop_camera.start(source=source, mode=mode)


@router.post("/cameras/laptop/stop")
def stop_laptop_camera():
    return laptop_camera.stop()


@router.get("/cameras/laptop/status")
def laptop_camera_status():
    return laptop_camera.get_status()


@router.get("/cameras/laptop/stream.mjpg")
def laptop_camera_raw_stream():
    """Raw MJPEG video stream."""
    return StreamingResponse(
        laptop_camera.raw_mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/cameras/laptop/annotated-stream.mjpg")
def laptop_camera_annotated_stream():
    """Annotated MJPEG video stream with bounding boxes & tactical HUD."""
    return StreamingResponse(
        laptop_camera.annotated_mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/cameras/laptop/detections")
def laptop_camera_detections():
    """Structured detections JSON with bounding boxes, threat level, and frame dimensions."""
    return laptop_camera.get_detections_payload()


# --- General Camera Management ---

@router.get("/cameras")
def list_cameras():
    cams = storage.get_cameras()
    has_laptop = any(c["id"] == "cam-laptop" for c in cams)
    if not has_laptop:
        laptop_info = {
            "id": "cam-laptop",
            "name": "Laptop Optical Sensor (Webcam 0)",
            "location": "Local Command Node",
            "source": "webcam:0",
            "type": "webcam",
            "status": "LIVE" if laptop_camera.get_status()["running"] else "IDLE",
            "detection": "Intelligent Perimeter Analytics",
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        storage.add_camera(laptop_info)
        cams = storage.get_cameras()
    return cams


@router.post("/cameras")
def create_camera(cam: CameraCreate):
    camera_id = f"cam-{uuid.uuid4().hex[:6]}"
    data = {
        "id": camera_id,
        "name": cam.name,
        "location": cam.location,
        "source": cam.source,
        "type": cam.type,
        "status": "IDLE",
        "detection": "",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    storage.add_camera(data)
    return data


@router.patch("/cameras/{camera_id}")
def update_camera(camera_id: str, updates: CameraUpdate):
    cam = storage.get_camera(camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    upd = {k: v for k, v in updates.model_dump().items() if v is not None}
    if upd:
        storage.update_camera(camera_id, upd)
    return storage.get_camera(camera_id)


@router.delete("/cameras/{camera_id}")
def delete_camera(camera_id: str):
    cam = storage.get_camera(camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    if camera_id == "cam-laptop":
        laptop_camera.stop()
    storage.delete_camera(camera_id)
    return {"status": "deleted", "id": camera_id}


@router.post("/cameras/{camera_id}/start")
def start_analysis(camera_id: str):
    if camera_id in ("cam-laptop", "laptop"):
        return laptop_camera.start()
    storage.update_camera(camera_id, {"status": "LIVE", "detection": "Analyzing"})
    return {"status": "started", "camera_id": camera_id}


@router.post("/cameras/{camera_id}/stop")
def stop_analysis(camera_id: str):
    if camera_id in ("cam-laptop", "laptop"):
        return laptop_camera.stop()
    storage.update_camera(camera_id, {"status": "IDLE", "detection": "Standby"})
    return {"status": "stopped", "camera_id": camera_id}


@router.get("/cameras/{camera_id}/status")
def camera_status(camera_id: str):
    if camera_id in ("cam-laptop", "laptop"):
        return laptop_camera.get_status()
    cam = storage.get_camera(camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    return {
        "camera_id": camera_id,
        "status": cam["status"],
        "analyzing": cam["status"] == "LIVE",
        "ai_status": ai_pipeline.get_ai_status(),
    }


@router.get("/cameras/{camera_id}/snapshot")
def get_snapshot(camera_id: str):
    snap_dir = os.path.join(os.path.dirname(__file__), "..", "data", "snapshots")
    snap_path = os.path.join(snap_dir, f"{camera_id}_latest.jpg")
    if os.path.exists(snap_path):
        return FileResponse(snap_path)
    return {"snapshot": None, "message": "Snapshot buffer active"}


@router.get("/cameras/{camera_id}/zones")
def get_zones(camera_id: str):
    return storage.get_zones(camera_id)


@router.post("/cameras/{camera_id}/zones")
def create_zone(camera_id: str, zone: ZoneCreate):
    zone_id = f"zone-{uuid.uuid4().hex[:6]}"
    data = {
        "id": zone_id,
        "camera_id": camera_id,
        "name": zone.name,
        "points": zone.points,
        "severity": zone.severity,
    }
    storage.add_zone(data)
    return data


@router.get("/cameras/{camera_id}/calibration")
def get_calibration(camera_id: str):
    cal = storage.get_calibration(camera_id)
    if not cal:
        return {"camera_id": camera_id, "calibration": None}
    return {"camera_id": camera_id, "calibration": cal}


@router.post("/cameras/{camera_id}/calibration")
def set_calibration(camera_id: str, cal: CalibrationData):
    storage.set_calibration(camera_id, cal.model_dump())
    return {"status": "saved", "camera_id": camera_id}

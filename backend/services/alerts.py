"""Alerts, events, analytics, FCR face watchlist, ANPR, and evidence router for IBVAP."""
import uuid, json, asyncio
from datetime import datetime, timedelta
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Body, HTTPException
from services import storage, blockchain, laptop_camera, model_loader

router = APIRouter(prefix="/api", tags=["alerts"])

_ws_clients: list[WebSocket] = []


# Events
@router.get("/events")
def list_events(limit: int = 100):
    return storage.get_events(limit)


@router.get("/events/{event_id}")
def get_event(event_id: str):
    events = storage.get_events(1000)
    for e in events:
        if e["id"] == event_id:
            return e
    return {"error": "not found"}


# Alerts
@router.get("/alerts")
def list_alerts(limit: int = 100):
    return storage.get_alerts(limit)


@router.post("/alerts/clear")
def clear_all_alerts():
    storage.clear_alerts()
    return {"status": "cleared", "message": "All alert records cleared from current session"}


@router.patch("/alerts/{alert_id}")
def update_alert(alert_id: str, body: dict):
    allowed = {"status", "severity", "description"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if updates:
        storage.update_alert(alert_id, updates)
    return {"status": "updated"}


# FCR Face Recognition Watchlist
@router.get("/faces/watchlist")
def get_face_watchlist():
    return model_loader.get_watchlist()


@router.post("/faces/enroll")
def enroll_face_record(body: dict = Body(...)):
    name = body.get("name", "Enrolled Subject")
    role = body.get("role", "Authorized Personnel")
    risk_level = body.get("risk_level", "Medium")
    new_entry = model_loader.enroll_face(name=name, role=role, risk_level=risk_level)
    return {"status": "enrolled", "subject": new_entry}


@router.delete("/faces/watchlist/{face_id}")
def delete_face_record(face_id: str):
    success = model_loader.delete_from_watchlist(face_id)
    if not success:
        raise HTTPException(404, "Face record not found")
    return {"status": "deleted", "id": face_id}


# ANPR / License Plate Recognition
@router.get("/anpr/latest")
def get_latest_anpr_record():
    return laptop_camera.get_latest_anpr()


# Evidence Ledger
@router.get("/blockchain")
def get_blockchain():
    return storage.get_blockchain()


@router.get("/blockchain/validate")
def validate_chain():
    return blockchain.validate_chain()


@router.get("/blockchain/events/{event_id}/certificate")
def get_certificate(event_id: str):
    cert = blockchain.get_evidence_certificate(event_id)
    if not cert:
        return {"error": "No evidence block found for this event ID"}
    return cert


@router.get("/reports/audit")
def audit_report():
    return blockchain.get_audit_report()


# WebSocket
async def websocket_handler(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _ws_clients.remove(websocket)
    except Exception:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)

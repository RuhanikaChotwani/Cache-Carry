"""Pydantic schemas for IBVAP API."""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


# Camera Schemas
class CameraCreate(BaseModel):
    name: str
    location: str = ""
    source: str = "webcam:0"
    type: str = "webcam"


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    source: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None


class CameraOut(BaseModel):
    id: str
    name: str
    location: str
    source: str
    type: str
    status: str
    detection: str
    created_at: str


# Zone Schemas
class ZoneCreate(BaseModel):
    name: str
    points: List[List[float]]
    severity: str = "Critical"


class ZoneOut(BaseModel):
    id: str
    camera_id: str
    name: str
    points: List[List[float]]
    severity: str


# Alert and Event Schemas
class AlertOut(BaseModel):
    id: str
    time: str
    camera_id: str
    camera_name: str
    event_type: str
    severity: str
    description: str
    ai_metadata: Optional[dict] = None
    snapshot_path: Optional[str] = None
    block_id: Optional[int] = None
    status: str = "Active"


class EventOut(BaseModel):
    id: str
    time: str
    camera_id: str
    camera_name: str
    event_type: str
    severity: str
    status: str
    description: str


# Evidence Ledger Schemas
class BlockOut(BaseModel):
    block_number: int
    event_id: str
    camera_id: str
    evidence_hash: str
    metadata_hash: str
    timestamp: str
    previous_hash: str
    block_hash: str
    status: str = "Secured"


class EvidenceSecureRequest(BaseModel):
    event_id: str
    camera_id: str = ""
    metadata: dict = {}


class EvidenceVerifyRequest(BaseModel):
    evidence_hash: str


# Analytics Schemas
class AnalyticsSummary(BaseModel):
    total_cameras: int = 0
    active_cameras: int = 0
    total_events: int = 0
    total_alerts: int = 0
    critical_alerts: int = 0
    suspicious_events: int = 0
    faces_detected: int = 0
    vehicles_detected: int = 0
    plates_detected: int = 0
    uptime: str = "99.7%"
    chart_data: List[dict] = []
    alert_distribution: List[dict] = []


# 3D Scene Schemas
class SceneCamera(BaseModel):
    id: str
    name: str
    position: List[float]
    rotation: List[float]
    fov: float = 70
    status: str = "LIVE"


class SceneZone(BaseModel):
    id: str
    name: str
    points: List[List[float]]
    severity: str = "Critical"


class SceneObject(BaseModel):
    track_id: str
    object_class: str = Field(alias="class", default="person")
    position: List[float]
    height: float = 1.7
    confidence: float = 0.9
    features: dict = {}
    trail: List[List[float]] = []
    threat_level: str = "Low"

    class Config:
        populate_by_name = True


class SceneGraph(BaseModel):
    units: str = "meters"
    bounds: dict = {"width": 120, "depth": 80}
    cameras: List[SceneCamera] = []
    zones: List[SceneZone] = []
    objects: List[dict] = []


class SceneResponse(BaseModel):
    updated_at: str
    scene: SceneGraph


# Calibration Schemas
class CalibrationData(BaseModel):
    camera_position: List[float] = [0, 8, 0]
    camera_rotation: List[float] = [0, 0, 0]
    fov: float = 70
    image_points: List[List[float]] = []
    world_points: List[List[float]] = []


# Detection Schemas
class Detection(BaseModel):
    track_id: str
    object_class: str = "person"
    confidence: float = 0.9
    bbox: List[float] = [0, 0, 0, 0]
    features: dict = {}


class FrameAnalysis(BaseModel):
    camera_id: str
    timestamp: str
    detections: List[Detection] = []
    alerts: List[dict] = []

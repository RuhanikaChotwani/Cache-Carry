import React, { useRef, useEffect, useState } from "react";
import * as api from "../api";
import { Box, Camera, RefreshCw } from "lucide-react";

/**
 * 2.5D Scene Projection using HTML5 Canvas.
 * Renders a ground grid, camera origin, and markers from real confirmed detections only.
 * No fake people, vehicles, trails, or intrusion zones.
 */
export default function SceneTab() {
  const canvasRef = useRef(null);
  const [detections, setDetections] = useState(null);
  const [camStatus, setCamStatus] = useState(null);

  useEffect(() => {
    const poll = () => {
      api.getDetections().then((d) => d && setDetections(d));
      api.getWebcamStatus().then((s) => s && setCamStatus(s));
    };
    poll();
    const interval = setInterval(poll, 1500);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;
    const CX = W / 2;
    const CY = H * 0.85;

    // Clear
    ctx.fillStyle = "#020e1a";
    ctx.fillRect(0, 0, W, H);

    // Draw ground grid (2.5D perspective)
    ctx.strokeStyle = "rgba(22, 60, 96, 0.35)";
    ctx.lineWidth = 1;

    const gridRows = 12;
    const gridCols = 16;
    const horizonY = H * 0.18;

    for (let r = 0; r <= gridRows; r++) {
      const t = r / gridRows;
      const y = horizonY + (CY - horizonY) * t;
      const spread = 0.3 + 0.7 * t;
      const x1 = CX - (W / 2) * spread;
      const x2 = CX + (W / 2) * spread;
      ctx.beginPath();
      ctx.moveTo(x1, y);
      ctx.lineTo(x2, y);
      ctx.stroke();
    }

    for (let c = 0; c <= gridCols; c++) {
      const frac = (c / gridCols - 0.5) * 2;
      const topX = CX + frac * (W * 0.15);
      const botX = CX + frac * (W * 0.5);
      ctx.beginPath();
      ctx.moveTo(topX, horizonY);
      ctx.lineTo(botX, CY);
      ctx.stroke();
    }

    // Horizon line
    ctx.strokeStyle = "rgba(22, 185, 201, 0.25)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, horizonY);
    ctx.lineTo(W, horizonY);
    ctx.stroke();

    // Camera origin marker
    ctx.fillStyle = "rgba(22, 185, 201, 0.8)";
    ctx.beginPath();
    ctx.arc(CX, CY, 8, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "rgba(22, 185, 201, 0.5)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(CX, CY, 14, 0, Math.PI * 2);
    ctx.stroke();

    ctx.fillStyle = "#b5cde4";
    ctx.font = "11px Inter, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("CAMERA ORIGIN", CX, CY + 28);

    // Title
    ctx.fillStyle = "rgba(22, 185, 201, 0.9)";
    ctx.font = "bold 13px Inter, sans-serif";
    ctx.textAlign = "left";
    ctx.fillText("2.5D SCENE PROJECTION", 16, 24);

    ctx.fillStyle = "#8aa2bc";
    ctx.font = "11px Inter, sans-serif";
    ctx.fillText("Markers from confirmed detections only", 16, 40);

    // Get frame dimensions
    const frameW = camStatus?.current_frame_width || 640;
    const frameH = camStatus?.current_frame_height || 480;

    const faces = detections?.faces || [];
    const plates = detections?.plates || [];

    // Project 2D frame coordinate to 2.5D scene position
    function projectToScene(bboxCenterX, bboxBottomY) {
      const normX = bboxCenterX / frameW;
      const normY = bboxBottomY / frameH;
      const depth = Math.max(0.05, Math.min(1.0, normY));
      const sceneY = horizonY + (CY - horizonY) * depth;
      const spread = 0.3 + 0.7 * depth;
      const sceneX = CX + (normX - 0.5) * W * spread;
      return { x: sceneX, y: sceneY, depth: depth };
    }

    // Draw confirmed face markers
    const drawnLabels = [];

    for (const face of faces) {
      const [x1, y1, x2, y2] = face.bbox;
      const cx = (x1 + x2) / 2;
      const by = y2;
      const { x, y, depth } = projectToScene(cx, by);

      const isMatch = face.possible_match;
      const markerSize = 4 + depth * 6;
      const color = isMatch ? "rgba(239, 75, 95, 0.9)" : "rgba(25, 211, 155, 0.9)";

      // Marker
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(x, y, markerSize, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = color;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(x, y, markerSize + 4, 0, Math.PI * 2);
      ctx.stroke();

      // Label with collision avoidance
      const label = isMatch ? `MATCH: ${face.identity}` : "Face";
      let labelY = y - markerSize - 8;
      for (const prev of drawnLabels) {
        if (Math.abs(prev.x - x) < 60 && Math.abs(prev.y - labelY) < 14) {
          labelY -= 16;
        }
      }

      ctx.fillStyle = color;
      ctx.font = `${isMatch ? "bold " : ""}10px Inter, sans-serif`;
      ctx.textAlign = "center";
      ctx.fillText(label, x, labelY);
      drawnLabels.push({ x, y: labelY });
    }

    // Draw confirmed plate markers
    for (const plate of plates) {
      const [x1, y1, x2, y2] = plate.bbox;
      const cx = (x1 + x2) / 2;
      const by = y2;
      const { x, y, depth } = projectToScene(cx, by);

      const markerSize = 5 + depth * 5;

      // Diamond marker for vehicles
      ctx.fillStyle = "rgba(0, 220, 255, 0.85)";
      ctx.beginPath();
      ctx.moveTo(x, y - markerSize);
      ctx.lineTo(x + markerSize, y);
      ctx.lineTo(x, y + markerSize);
      ctx.lineTo(x - markerSize, y);
      ctx.closePath();
      ctx.fill();

      const label = plate.plate_text ? `PLATE: ${plate.plate_text}` : "Vehicle";
      let labelY = y - markerSize - 8;
      for (const prev of drawnLabels) {
        if (Math.abs(prev.x - x) < 80 && Math.abs(prev.y - labelY) < 14) {
          labelY -= 16;
        }
      }

      ctx.fillStyle = "rgba(0, 220, 255, 0.9)";
      ctx.font = "bold 10px Inter, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(label, x, labelY);
      drawnLabels.push({ x, y: labelY });
    }

    // Status text
    const isLive = camStatus?.running || false;
    ctx.fillStyle = isLive ? "rgba(25, 211, 155, 0.7)" : "rgba(120, 160, 190, 0.5)";
    ctx.font = "10px Inter, sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(
      isLive
        ? `LIVE | Faces: ${faces.length} | Plates: ${plates.length}`
        : "STANDBY - Start a video source to populate scene",
      W - 16,
      H - 12,
    );

  }, [detections, camStatus]);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
        <div>
          <h2 style={{ margin: "0 0 4px 0", fontSize: "1.3rem" }}>2.5D Scene Projection</h2>
          <p style={{ margin: 0, fontSize: "12px", color: "var(--muted)" }}>
            Perspective scene view derived from confirmed detection coordinates. Not photogrammetry or true 3D reconstruction.
          </p>
        </div>
        <button onClick={() => {
          api.getDetections().then((d) => d && setDetections(d));
          api.getWebcamStatus().then((s) => s && setCamStatus(s));
        }} style={{
          background: "transparent", border: "none", color: "var(--cyan)", cursor: "pointer",
          display: "flex", alignItems: "center", gap: "6px", fontSize: "12px",
        }}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <section style={{
        background: "#04192c", border: "1px solid var(--border)", borderRadius: "8px",
        overflow: "hidden", display: "flex", justifyContent: "center",
      }}>
        <canvas ref={canvasRef} width={960} height={540} style={{ display: "block", width: "100%", maxHeight: "540px" }} />
      </section>
    </div>
  );
}

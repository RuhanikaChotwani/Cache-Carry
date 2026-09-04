import React from "react";

export default function SettingsTab({ healthData }) {
  return (
    <div>
      <div style={{ marginBottom: "20px" }}>
        <h2 style={{ margin: "0 0 4px 0", fontSize: "1.3rem" }}>Sensor and Model Diagnostics</h2>
        <p style={{ margin: 0, fontSize: "12px", color: "var(--muted)" }}>
          Hardware device state, active inference engines, and model configurations.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
        <section style={{ background: "#04192c", border: "1px solid var(--border)", borderRadius: "8px", padding: "20px" }}>
          <h3 style={{ margin: "0 0 16px 0", fontSize: "14px" }}>HARDWARE AND SENSOR</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "12px", fontSize: "13px" }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--muted)" }}>Active Stream Source:</span>
              <strong>{healthData?.camera?.source_name || "Laptop Webcam 0"}</strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--muted)" }}>Source Type:</span>
              <strong style={{ color: "var(--cyan)" }}>
                {(healthData?.camera?.source_type || "webcam").toUpperCase()}
              </strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--muted)" }}>DirectShow / OpenCV State:</span>
              <strong style={{ color: healthData?.camera?.is_camera_open ? "var(--green)" : "var(--muted)" }}>
                {healthData?.camera?.is_camera_open ? "Connected and Streaming" : "Standby"}
              </strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--muted)" }}>Resolution:</span>
              <strong className="mono">
                {healthData?.camera?.current_frame_width || 640} x {healthData?.camera?.current_frame_height || 480}
              </strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--muted)" }}>Display / Inference FPS:</span>
              <strong className="mono">
                {healthData?.camera?.displayed_fps || 0} / {healthData?.camera?.inference_fps || 0} FPS
              </strong>
            </div>
          </div>
        </section>

        <section style={{ background: "#04192c", border: "1px solid var(--border)", borderRadius: "8px", padding: "20px" }}>
          <h3 style={{ margin: "0 0 16px 0", fontSize: "14px" }}>AI INFERENCE ENGINES</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "12px", fontSize: "13px" }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--muted)" }}>YuNet Face Detector:</span>
              <strong style={{ color: healthData?.models?.yunet?.loaded ? "var(--green)" : "var(--red)" }}>
                {healthData?.models?.yunet?.loaded ? "Loaded (2023mar.onnx)" : "Unavailable"}
              </strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--muted)" }}>SFace Face Recognizer:</span>
              <strong style={{ color: healthData?.models?.sface?.loaded ? "var(--green)" : "var(--red)" }}>
                {healthData?.models?.sface?.loaded ? "Loaded (2021dec.onnx)" : "Unavailable"}
              </strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--muted)" }}>FastALPR Plate Engine:</span>
              <strong style={{ color: healthData?.models?.fast_alpr?.loaded ? "var(--green)" : "var(--orange)" }}>
                {healthData?.models?.fast_alpr?.loaded ? "Loaded (YOLOv9 + Global ONNX)" : "Not installed / Loading"}
              </strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--muted)" }}>Evidence Ledger:</span>
              <strong style={{ color: "var(--green)" }}>SHA-256 Cryptographic Chain Active</strong>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

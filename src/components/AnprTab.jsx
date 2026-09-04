import React, { useState, useEffect } from "react";
import * as api from "../api";
import { Car, RefreshCw, Trash2, ToggleLeft, ToggleRight } from "lucide-react";

export default function AnprTab({ isRunning }) {
  const [diag, setDiag] = useState(null);
  const [records, setRecords] = useState([]);
  const [anprEnabled, setAnprEnabled] = useState(true);

  const loadData = () => {
    api.getAnprDiagnostics().then((res) => {
      if (res) {
        setDiag(res);
        if (res.anpr_enabled !== undefined) {
          setAnprEnabled(res.anpr_enabled);
        }
      }
    });
    api.getAnprRecords(100).then((recs) => setRecords(recs || []));
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleToggle = async () => {
    const newState = !anprEnabled;
    setAnprEnabled(newState);
    await api.toggleAnpr(newState);
    loadData();
  };

  const handleClearRecords = async () => {
    await api.clearAnprRecords();
    loadData();
  };

  const modelLoaded = diag?.model_loaded || false;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px", flexWrap: "wrap", gap: "12px" }}>
        <div>
          <h2 style={{ margin: "0 0 4px 0", fontSize: "1.3rem" }}>Automatic Number Plate Recognition</h2>
          <p style={{ margin: 0, fontSize: "12px", color: "var(--muted)" }}>
            FastALPR ONNX detector with strict 3-tier validation. Only confirmed plates with consensus OCR text are saved.
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <button type="button" onClick={handleToggle} style={{
            padding: "6px 14px", fontSize: "12px", fontWeight: "600", borderRadius: "6px",
            border: `1px solid ${anprEnabled ? "var(--cyan)" : "var(--border)"}`,
            background: anprEnabled ? "rgba(22,185,201,0.15)" : "#020e1a",
            color: anprEnabled ? "var(--cyan)" : "var(--muted)", cursor: "pointer",
            display: "flex", alignItems: "center", gap: "6px",
          }}>
            {anprEnabled ? <ToggleRight size={16} color="var(--cyan)" /> : <ToggleLeft size={16} />}
            ANPR: {anprEnabled ? "ON" : "OFF"}
          </button>
          <button onClick={loadData} style={{ background: "transparent", border: "none", color: "var(--cyan)", cursor: "pointer", fontSize: "12px", display: "flex", alignItems: "center", gap: "4px" }}>
            <RefreshCw size={13} /> Refresh
          </button>
        </div>
      </div>

      {/* Diagnostics */}
      <section style={{ background: "#04192c", border: "1px solid var(--border)", borderRadius: "8px", padding: "20px", marginBottom: "20px" }}>
        <h3 style={{ margin: "0 0 14px 0", fontSize: "14px" }}>DIAGNOSTICS</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "14px", fontSize: "12px" }}>
          <DiagCard label="Engine" value={diag?.engine || diag?.primary_detector || "FastALPR (ONNX CPU)"} color={modelLoaded ? "var(--green)" : "var(--red)"} />
          {diag?.exact_error && <DiagCard label="Model Error" value={diag.exact_error} color="var(--red)" />}
          <DiagCard label="OCR Engine" value={diag?.ocr_engine || "Global Plates ONNX"} color={diag?.ocr_available ? "var(--green)" : "var(--orange)"} />
          {diag?.ocr_error && <DiagCard label="OCR Error" value={diag.ocr_error} color="var(--orange)" />}
          <DiagCard label="Display FPS" value={`${diag?.display_fps || 0} FPS`} color="var(--cyan)" />
          <DiagCard label="Processing Time" value={`${diag?.detection_ms || 0} ms`} color="#fff" />
          <DiagCard label="Frame Res" value={`Native: ${diag?.input_dimensions || "?"} | Inference: ${diag?.inference_dimensions || "?"}`} color="#fff" />
          <DiagCard label="Pipeline Counts" value={`Raw: ${diag?.raw_candidates_count || 0} | Validated: ${diag?.validated_candidates_count || 0} | Confirmed: ${diag?.confirmed_plates_count || 0}`} color="#fff" />
        </div>
      </section>

      {/* Confirmed Plate Records */}
      <section style={{ background: "#04192c", border: "1px solid var(--border)", borderRadius: "8px", padding: "20px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <div>
            <h3 style={{ margin: "0 0 2px 0", fontSize: "14px" }}>Confirmed Plate Log ({records.length})</h3>
            <span style={{ fontSize: "11px", color: "var(--muted)" }}>
              Only plates with 3 or more consistent OCR readings are saved here.
            </span>
          </div>
          {records.length > 0 && (
            <button onClick={handleClearRecords} style={{
              padding: "4px 10px", fontSize: "11px", background: "rgba(239,75,95,0.15)",
              border: "1px solid var(--red)", color: "var(--red)", borderRadius: "4px",
              cursor: "pointer", display: "flex", alignItems: "center", gap: "4px",
            }}>
              <Trash2 size={12} /> Clear
            </button>
          )}
        </div>

        {records.length === 0 ? (
          <div style={{ textAlign: "center", padding: "50px 20px", color: "var(--muted)" }}>
            <Car size={36} style={{ opacity: 0.3, marginBottom: "8px" }} />
            <p style={{ margin: 0, fontSize: "13px" }}>No confirmed plates recorded.</p>
            <span style={{ fontSize: "11px" }}>Plates with valid OCR will appear here automatically.</span>
          </div>
        ) : (
          <div style={{ maxHeight: "400px", overflowY: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)", textAlign: "left", color: "var(--muted)" }}>
                  <th style={{ padding: "8px" }}>TIME</th>
                  <th style={{ padding: "8px" }}>PLATE</th>
                  <th style={{ padding: "8px" }}>DET CONF</th>
                  <th style={{ padding: "8px" }}>OCR CONF</th>
                  <th style={{ padding: "8px" }}>SOURCE</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r) => (
                  <tr key={r.id} style={{ borderBottom: "1px solid rgba(18,60,96,0.5)" }}>
                    <td style={{ padding: "8px", fontFamily: "monospace", color: "var(--muted)" }}>{(r.timestamp || "").slice(11, 19)}</td>
                    <td style={{ padding: "8px" }}>
                      <strong style={{ fontFamily: "monospace", fontSize: "13px", color: "var(--green)" }}>{r.plate_text}</strong>
                    </td>
                    <td style={{ padding: "8px" }}>{Math.round((r.detector_confidence || 0) * 100)}%</td>
                    <td style={{ padding: "8px" }}>{Math.round((r.ocr_confidence || 0) * 100)}%</td>
                    <td style={{ padding: "8px", color: "#b5cde4" }}>{r.source_name}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function DiagCard({ label, value, color }) {
  return (
    <div style={{ background: "#020e1a", padding: "12px", borderRadius: "6px", border: "1px solid var(--border)" }}>
      <span style={{ color: "var(--muted)", display: "block", marginBottom: "4px", fontSize: "11px" }}>{label}</span>
      <strong style={{ color, fontSize: "12px", wordBreak: "break-all" }}>{value}</strong>
    </div>
  );
}

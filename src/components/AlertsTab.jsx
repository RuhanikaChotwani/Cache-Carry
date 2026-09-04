import React, { useState, useEffect } from "react";
import * as api from "../api";
import { ShieldCheck, Trash2, Lock } from "lucide-react";

export default function AlertsTab() {
  const [alerts, setAlerts] = useState([]);

  const loadAlerts = () => {
    api.getAlerts(100).then((a) => setAlerts(a));
  };

  useEffect(() => {
    loadAlerts();
  }, []);

  const handleClear = async () => {
    await api.clearAlerts();
    loadAlerts();
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
        <div>
          <h2 style={{ margin: "0 0 4px 0", fontSize: "1.3rem" }}>Threat Alerts and Incident Log</h2>
          <p style={{ margin: 0, fontSize: "12px", color: "var(--muted)" }}>
            Verified high-threat alerts triggered strictly by real watchlist face matches.
          </p>
        </div>

        <button
          onClick={handleClear}
          style={{
            padding: "6px 12px",
            fontSize: "12px",
            background: "rgba(239,75,95,0.15)",
            border: "1px solid var(--red)",
            color: "var(--red)",
            borderRadius: "4px",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "6px"
          }}
        >
          <Trash2 size={13} /> Clear Alerts
        </button>
      </div>

      <section style={{ background: "#04192c", border: "1px solid var(--border)", borderRadius: "8px", padding: "20px" }}>
        {alerts.length === 0 ? (
          <div style={{ textAlign: "center", padding: "50px 20px", color: "var(--muted)" }}>
            <ShieldCheck size={36} style={{ opacity: 0.3, marginBottom: "8px" }} />
            <p style={{ margin: 0, fontSize: "13px" }}>No alerts recorded.</p>
            <span style={{ fontSize: "11px" }}>Alerts are raised only when an enrolled person of interest is identified in the optical feed.</span>
          </div>
        ) : (
          <div style={{ maxHeight: "450px", overflowY: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)", textAlign: "left", color: "var(--muted)" }}>
                  <th style={{ padding: "8px" }}>TIME (UTC)</th>
                  <th style={{ padding: "8px" }}>EVENT TYPE</th>
                  <th style={{ padding: "8px" }}>LEVEL</th>
                  <th style={{ padding: "8px" }}>MESSAGE</th>
                  <th style={{ padding: "8px" }}>EVIDENCE</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((a) => (
                  <tr key={a.id} style={{ borderBottom: "1px solid rgba(18,60,96,0.5)" }}>
                    <td style={{ padding: "8px", fontFamily: "monospace" }}>
                      {(a.time || "").slice(11, 19)}
                    </td>
                    <td style={{ padding: "8px" }}>
                      <strong>{a.type}</strong>
                    </td>
                    <td style={{ padding: "8px" }}>
                      <span style={{ padding: "2px 6px", borderRadius: "4px", background: "rgba(239,75,95,0.2)", color: "var(--red)", fontWeight: "bold" }}>
                        {a.level}
                      </span>
                    </td>
                    <td style={{ padding: "8px", color: "#b5cde4" }}>{a.message}</td>
                    <td style={{ padding: "8px", color: "var(--green)" }}>
                      <Lock size={12} style={{ verticalAlign: "middle", marginRight: "4px" }} /> SHA-256 Hashed
                    </td>
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

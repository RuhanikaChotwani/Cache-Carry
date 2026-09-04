import React, { useState, useEffect } from "react";
import * as api from "../api";
import { Lock, CheckCircle, AlertTriangle, Shield, Activity } from "lucide-react";

export default function LedgerTab() {
  const [eventLedger, setEventLedger] = useState([]);
  const [eventValidation, setEventValidation] = useState(null);
  const [chainStatus, setChainStatus] = useState(null);
  const [chainVerify, setChainVerify] = useState(null);
  const [recentData, setRecentData] = useState(null);
  const [validating, setValidating] = useState(false);
  const [verifying, setVerifying] = useState(false);

  const loadData = () => {
    api.getLedger().then((l) => setEventLedger(l));
    api.getLedgerStatus().then((s) => setChainStatus(s));
    api.getLedgerRecent(20).then((r) => setRecentData(r));
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleValidateEvents = async () => {
    setValidating(true);
    const res = await api.validateLedger();
    setEventValidation(res);
    setValidating(false);
  };

  const handleVerifyChain = async () => {
    setVerifying(true);
    const res = await api.verifyFrameChain();
    setChainVerify(res);
    setVerifying(false);
  };

  const framesHashed = chainStatus?.frames_hashed || 0;
  const writerActive = chainStatus?.writer_active || false;
  const currentHash = chainStatus?.current_chain_hash || ("0".repeat(64));
  const shortHash = currentHash.slice(0, 16) + "..." + currentHash.slice(-8);

  const frameRecords = recentData?.frame_chain_records || [];
  const eventRecords = recentData?.event_evidence_records || [];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
        <div>
          <h2 style={{ margin: "0 0 4px 0", fontSize: "1.3rem" }}>Evidence Integrity Ledger</h2>
          <p style={{ margin: 0, fontSize: "12px", color: "var(--muted)" }}>
            Local append-only SHA-256 hash chain providing tamper-evident audit for captured frames and verified events.
          </p>
        </div>
        <div style={{ display: "flex", gap: "8px" }}>
          <button onClick={handleVerifyChain} disabled={verifying} style={{
            padding: "8px 14px", fontSize: "12px", background: "var(--cyan)", color: "#020e1a", border: "none",
            borderRadius: "6px", fontWeight: "600", cursor: "pointer", display: "flex", alignItems: "center", gap: "6px",
          }}>
            <Shield size={14} /> {verifying ? "Verifying..." : "Verify Frame Chain"}
          </button>
          <button onClick={handleValidateEvents} disabled={validating} style={{
            padding: "8px 14px", fontSize: "12px", background: "#04192c", color: "var(--cyan)",
            border: "1px solid var(--cyan)", borderRadius: "6px", fontWeight: "600", cursor: "pointer",
            display: "flex", alignItems: "center", gap: "6px",
          }}>
            <CheckCircle size={14} /> {validating ? "Checking..." : "Validate Events"}
          </button>
        </div>
      </div>

      {/* Frame Chain Status */}
      <section style={{ background: "#04192c", border: "1px solid var(--border)", borderRadius: "8px", padding: "20px", marginBottom: "20px" }}>
        <h3 style={{ margin: "0 0 14px 0", fontSize: "14px" }}>FRAME HASH CHAIN STATUS</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "14px", fontSize: "12px" }}>
          <div style={{ background: "#020e1a", padding: "12px", borderRadius: "6px", border: "1px solid var(--border)" }}>
            <span style={{ color: "var(--muted)", display: "block", marginBottom: "4px" }}>Frames Secured</span>
            <strong style={{ color: "var(--cyan)", fontSize: "18px" }}>{framesHashed}</strong>
          </div>
          <div style={{ background: "#020e1a", padding: "12px", borderRadius: "6px", border: "1px solid var(--border)" }}>
            <span style={{ color: "var(--muted)", display: "block", marginBottom: "4px" }}>Writer Status</span>
            <strong style={{ color: writerActive ? "var(--green)" : "var(--muted)" }}>
              {writerActive ? "Active" : "Idle"}
            </strong>
          </div>
          <div style={{ background: "#020e1a", padding: "12px", borderRadius: "6px", border: "1px solid var(--border)" }}>
            <span style={{ color: "var(--muted)", display: "block", marginBottom: "4px" }}>Queue</span>
            <strong className="mono">{chainStatus?.queue_pending || 0} / {chainStatus?.queue_capacity || 512}</strong>
            {(chainStatus?.queue_drops || 0) > 0 && (
              <span style={{ color: "var(--orange)", fontSize: "10px", marginLeft: "6px" }}>
                ({chainStatus.queue_drops} drops)
              </span>
            )}
          </div>
          <div style={{ background: "#020e1a", padding: "12px", borderRadius: "6px", border: "1px solid var(--border)" }}>
            <span style={{ color: "var(--muted)", display: "block", marginBottom: "4px" }}>Latest Chain Hash</span>
            <strong className="mono" style={{ fontSize: "11px", color: "var(--cyan)", wordBreak: "break-all" }}>{shortHash}</strong>
          </div>
        </div>
      </section>

      {/* Verification Results */}
      {chainVerify && (
        <div style={{
          padding: "12px 16px", borderRadius: "8px", marginBottom: "16px",
          background: chainVerify.valid ? "rgba(25,211,155,0.15)" : "rgba(239,75,95,0.15)",
          border: `1px solid ${chainVerify.valid ? "var(--green)" : "var(--red)"}`,
          display: "flex", alignItems: "center", gap: "10px",
        }}>
          {chainVerify.valid ? <CheckCircle size={18} color="var(--green)" /> : <AlertTriangle size={18} color="var(--red)" />}
          <div>
            <strong style={{ color: chainVerify.valid ? "var(--green)" : "var(--red)" }}>
              {chainVerify.valid ? "Frame Chain Integrity Verified" : "Frame Chain Integrity Broken"}
            </strong>
            <div style={{ fontSize: "12px", color: "#b5cde4" }}>{chainVerify.message}</div>
            {chainVerify.checked_frames !== undefined && (
              <div style={{ fontSize: "11px", color: "var(--muted)" }}>Checked: {chainVerify.checked_frames} frames</div>
            )}
          </div>
        </div>
      )}
      {eventValidation && (
        <div style={{
          padding: "12px 16px", borderRadius: "8px", marginBottom: "16px",
          background: eventValidation.valid ? "rgba(25,211,155,0.15)" : "rgba(239,75,95,0.15)",
          border: `1px solid ${eventValidation.valid ? "var(--green)" : "var(--red)"}`,
          display: "flex", alignItems: "center", gap: "10px",
        }}>
          <Lock size={18} color={eventValidation.valid ? "var(--green)" : "var(--red)"} />
          <div>
            <strong style={{ color: eventValidation.valid ? "var(--green)" : "var(--red)" }}>
              {eventValidation.valid ? "Event Evidence Chain Verified" : "Event Chain Broken"}
            </strong>
            <div style={{ fontSize: "12px", color: "#b5cde4" }}>{eventValidation.message}</div>
          </div>
        </div>
      )}

      {/* Event Evidence Records */}
      <section style={{ background: "#04192c", border: "1px solid var(--border)", borderRadius: "8px", padding: "20px", marginBottom: "20px" }}>
        <h3 style={{ margin: "0 0 14px 0", fontSize: "14px" }}>EVENT EVIDENCE RECORDS ({eventLedger.length})</h3>
        {eventLedger.length === 0 ? (
          <div style={{ textAlign: "center", padding: "40px 20px", color: "var(--muted)" }}>
            <Lock size={36} style={{ opacity: 0.3, marginBottom: "8px" }} />
            <p style={{ margin: 0, fontSize: "13px" }}>No event evidence blocks recorded.</p>
            <span style={{ fontSize: "11px" }}>Blocks are created for confirmed FCR matches and confirmed plate detections.</span>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "10px", maxHeight: "350px", overflowY: "auto" }}>
            {eventLedger.map((block) => (
              <div key={block.block_number} style={{
                background: "#020e1a", border: "1px solid var(--border)", borderLeft: "4px solid var(--cyan)",
                borderRadius: "6px", padding: "12px 16px",
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                  <strong>BLOCK #{block.block_number} - {block.event_id}</strong>
                  <span style={{ fontSize: "11px", color: "var(--muted)" }}>{block.timestamp}</span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", fontSize: "11px", fontFamily: "monospace" }}>
                  <div>
                    <span style={{ color: "var(--muted)" }}>BLOCK HASH:</span>
                    <div style={{ color: "var(--cyan)", wordBreak: "break-all" }}>{block.current_hash}</div>
                  </div>
                  <div>
                    <span style={{ color: "var(--muted)" }}>PREVIOUS:</span>
                    <div style={{ color: "#8aa2bc", wordBreak: "break-all" }}>{block.previous_hash}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Recent Frame Chain Records */}
      <section style={{ background: "#04192c", border: "1px solid var(--border)", borderRadius: "8px", padding: "20px" }}>
        <h3 style={{ margin: "0 0 14px 0", fontSize: "14px" }}>RECENT FRAME CHAIN RECORDS ({frameRecords.length})</h3>
        {frameRecords.length === 0 ? (
          <div style={{ textAlign: "center", padding: "30px 20px", color: "var(--muted)" }}>
            <Activity size={28} style={{ opacity: 0.3, marginBottom: "6px" }} />
            <p style={{ margin: 0, fontSize: "13px" }}>No frame chain records yet. Start a stream to begin hashing frames.</p>
          </div>
        ) : (
          <div style={{ maxHeight: "250px", overflowY: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "11px", fontFamily: "monospace" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)", textAlign: "left", color: "var(--muted)" }}>
                  <th style={{ padding: "6px" }}>SEQ</th>
                  <th style={{ padding: "6px" }}>TIME</th>
                  <th style={{ padding: "6px" }}>FRAME HASH (first 16)</th>
                  <th style={{ padding: "6px" }}>CHAIN HASH (first 16)</th>
                </tr>
              </thead>
              <tbody>
                {frameRecords.slice(-20).reverse().map((rec, idx) => (
                  <tr key={idx} style={{ borderBottom: "1px solid rgba(18,60,96,0.3)" }}>
                    <td style={{ padding: "6px", color: "var(--cyan)" }}>{rec.sequence}</td>
                    <td style={{ padding: "6px", color: "var(--muted)" }}>{(rec.timestamp || "").slice(11, 23)}</td>
                    <td style={{ padding: "6px" }}>{(rec.frame_hash || "").slice(0, 16)}</td>
                    <td style={{ padding: "6px", color: "var(--cyan)" }}>{(rec.chain_hash || "").slice(0, 16)}</td>
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

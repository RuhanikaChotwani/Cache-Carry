import React, { useState, useEffect } from "react";
import * as api from "./api";
import {
  ShieldCheck, Camera, UserRound, Car, Bell, Lock,
  Settings as SettingsIcon, Box
} from "lucide-react";

import LiveFeedTab from "./components/LiveFeedTab";
import WatchlistTab from "./components/WatchlistTab";
import AnprTab from "./components/AnprTab";
import AlertsTab from "./components/AlertsTab";
import LedgerTab from "./components/LedgerTab";
import SettingsTab from "./components/SettingsTab";
import SceneTab from "./components/SceneTab";

export default function App() {
  const [activeTab, setActiveTab] = useState("live");
  const [healthData, setHealthData] = useState(null);

  useEffect(() => {
    const checkHealth = () => {
      api.health().then((h) => setHealthData(h)).catch(() => setHealthData(null));
    };
    checkHealth();
    const interval = setInterval(checkHealth, 3000);
    return () => clearInterval(interval);
  }, []);

  const isBackendOnline = healthData !== null && healthData.status === "operational";
  const isCameraRunning = Boolean(healthData?.camera?.feed_active || healthData?.camera?.running);
  const activeSourceType = healthData?.camera?.source_type || "webcam";
  const displayedFps = isCameraRunning ? (healthData?.camera?.displayed_fps || 0) : 0;
  const sourceLabel =
    activeSourceType === "demo_video"
      ? "DEMO VIDEO"
      : activeSourceType === "uploaded_video"
      ? "UPLOADED VIDEO"
      : "WEBCAM";

  return (
    <div style={{ minHeight: "100vh", background: "#020e1a", color: "#e4f1ff", fontFamily: "Inter, sans-serif" }}>
      <header style={{
        background: "#04192c", borderBottom: "1px solid #0c304d", padding: "12px 24px",
        display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "16px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{
            width: "36px", height: "36px", borderRadius: "8px", background: "rgba(22,185,201,0.15)",
            border: "1px solid var(--cyan)", display: "grid", placeItems: "center", color: "var(--cyan)",
          }}>
            <ShieldCheck size={22} />
          </div>
          <div>
            <div style={{ fontSize: "15px", fontWeight: "700", letterSpacing: "1px" }}>
              IBVAP <span style={{ color: "var(--cyan)" }}>FCR SURVEILLANCE</span>
            </div>
            <div style={{ fontSize: "11px", color: "var(--muted)" }}>
              Intelligent Border Video Analytics Platform (Prototype)
            </div>
          </div>
        </div>

        <nav style={{ display: "flex", gap: "4px", background: "#020e1a", padding: "4px", borderRadius: "8px", border: "1px solid var(--border)", flexWrap: "wrap" }}>
          <TabBtn id="live" label="Live Feed" icon={<Camera size={14} />} active={activeTab} onClick={setActiveTab} />
          <TabBtn id="watchlist" label="Watchlist" icon={<UserRound size={14} />} active={activeTab} onClick={setActiveTab} />
          <TabBtn id="anpr" label="ANPR" icon={<Car size={14} />} active={activeTab} onClick={setActiveTab} />
          <TabBtn id="alerts" label="Alerts" icon={<Bell size={14} />} active={activeTab} onClick={setActiveTab} />
          <TabBtn id="ledger" label="Ledger" icon={<Lock size={14} />} active={activeTab} onClick={setActiveTab} />
          <TabBtn id="scene" label="2.5D Scene" icon={<Box size={14} />} active={activeTab} onClick={setActiveTab} />
          <TabBtn id="settings" label="Settings" icon={<SettingsIcon size={14} />} active={activeTab} onClick={setActiveTab} />
        </nav>

        <div style={{ display: "flex", gap: "8px", alignItems: "center", fontSize: "11px" }}>
          <Pill label="Backend" value={isBackendOnline ? "ONLINE" : "CONNECTING..."} color={isBackendOnline ? "var(--green)" : "var(--orange)"} />
          <Pill label="Feed" value={isCameraRunning ? `ACTIVE (${displayedFps} FPS)` : "STANDBY"} color={isCameraRunning ? "var(--green)" : "var(--orange)"} />
          <Pill label="Source" value={sourceLabel} color="var(--cyan)" />
        </div>
      </header>

      <main style={{ maxWidth: "1400px", margin: "0 auto", padding: "24px 20px" }}>
        {activeTab === "live" && <LiveFeedTab onNavigateToWatchlist={() => setActiveTab("watchlist")} />}
        {activeTab === "watchlist" && <WatchlistTab />}
        {activeTab === "anpr" && <AnprTab isRunning={isCameraRunning} />}
        {activeTab === "alerts" && <AlertsTab />}
        {activeTab === "ledger" && <LedgerTab />}
        {activeTab === "scene" && <SceneTab />}
        {activeTab === "settings" && <SettingsTab healthData={healthData} />}
      </main>
    </div>
  );
}

function TabBtn({ id, label, icon, active, onClick }) {
  const isActive = active === id;
  return (
    <button type="button" onClick={() => onClick(id)} style={{
      display: "flex", alignItems: "center", gap: "5px", padding: "7px 12px",
      fontSize: "11px", fontWeight: "600", borderRadius: "6px", border: "none",
      background: isActive ? "var(--cyan)" : "transparent",
      color: isActive ? "#020e1a" : "var(--muted)", cursor: "pointer",
    }}>
      {icon} <span>{label}</span>
    </button>
  );
}

function Pill({ label, value, color }) {
  return (
    <div style={{
      background: "#03172a", border: "1px solid var(--border)", borderRadius: "6px",
      padding: "4px 8px", display: "flex", gap: "6px", alignItems: "center",
    }}>
      <span style={{ color: "var(--muted)" }}>{label}:</span>
      <strong style={{ color }}>{value}</strong>
    </div>
  );
}
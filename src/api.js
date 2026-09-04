/**
 * IBVAP Frontend API Helper
 * Base URL configurable via VITE_API_BASE, defaults to http://127.0.0.1:8000
 */

export const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

async function apiFetch(path, options = {}) {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: options.body instanceof FormData ? {} : { "Content-Type": "application/json", ...options.headers },
      ...options,
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `API error: ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    console.warn(`API call failed: ${path}`, err.message);
    throw err;
  }
}

// Health
export function health() {
  return apiFetch("/api/health").catch(() => null);
}

// Video Sources and Upload
export function getVideoSources() {
  return apiFetch("/api/video-sources").catch(() => ({ videos: [], message: "Could not fetch demo videos" }));
}

export function uploadVideo(file) {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch("/api/video/upload", {
    method: "POST",
    body: formData,
  });
}

// Stream Control
export function startStream(params = {}) {
  return apiFetch("/api/webcam/start", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export function startWebcam(source = 0) {
  return startStream({
    source_type: "webcam",
    source: source,
    source_name: `Laptop Webcam ${source}`,
    loop: false,
  });
}

export function stopWebcam() {
  return apiFetch("/api/webcam/stop", { method: "POST" });
}

export function getWebcamStatus() {
  return apiFetch("/api/webcam/status").catch(() => null);
}

export function getDetections() {
  return apiFetch("/api/webcam/detections").catch(() => null);
}

export function getRawStreamUrl() {
  return `${API_BASE}/api/webcam/raw.mjpg`;
}

export function getAiStreamUrl() {
  return `${API_BASE}/api/webcam/ai.mjpg`;
}

// FCR Watchlist
export function enrollFace(name, imageFile) {
  const formData = new FormData();
  formData.append("name", name);
  formData.append("image", imageFile);

  return apiFetch("/api/fcr/enroll", {
    method: "POST",
    body: formData,
  });
}

export function getWatchlist() {
  return apiFetch("/api/fcr/watchlist").catch(() => []);
}

export function deleteWatchlistFace(faceId) {
  return apiFetch(`/api/fcr/watchlist/${faceId}`, {
    method: "DELETE",
  });
}

export function getMatches() {
  return apiFetch("/api/fcr/matches").catch(() => []);
}

// ANPR
export function getLatestAnpr() {
  return apiFetch("/api/anpr/latest").catch(() => null);
}

export function getAnprDiagnostics() {
  return apiFetch("/api/anpr/diagnostics").catch(() => null);
}

export function toggleAnpr(enabled) {
  return apiFetch("/api/anpr/toggle", {
    method: "POST",
    body: JSON.stringify({ enabled }),
  });
}

export function getAnprRecords(limit = 100) {
  return apiFetch(`/api/anpr/records?limit=${limit}`).catch(() => []);
}

export function clearAnprRecords() {
  return apiFetch("/api/anpr/records", { method: "DELETE" });
}

// Alerts
export function getAlerts(limit = 100) {
  return apiFetch(`/api/alerts?limit=${limit}`).catch(() => []);
}

export function clearAlerts() {
  return apiFetch("/api/alerts", { method: "DELETE" });
}

// Event Evidence Ledger
export function getLedger() {
  return apiFetch("/api/ledger").catch(() => []);
}

export function validateLedger() {
  return apiFetch("/api/ledger/validate").catch(() => null);
}

// Frame Hash Chain
export function getLedgerStatus() {
  return apiFetch("/api/ledger/status").catch(() => null);
}

export function getLedgerRecent(limit = 50) {
  return apiFetch(`/api/ledger/recent?limit=${limit}`).catch(() => ({ frame_chain_records: [], event_evidence_records: [] }));
}

export function verifyFrameChain(sessionId) {
  const query = sessionId ? `?session_id=${sessionId}` : "";
  return apiFetch(`/api/ledger/verify${query}`).catch(() => null);
}

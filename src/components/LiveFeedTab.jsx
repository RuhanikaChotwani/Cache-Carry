import React, { useState, useEffect, useRef } from "react";
import * as api from "../api";
import {
  Camera, Film, Upload, Play, Square, RefreshCw, Eye, Layers, Activity,
  AlertTriangle, CheckCircle, FileVideo, X, Car, AlertCircle, Loader2, Video
} from "lucide-react";

export default function LiveFeedTab({ onNavigateToWatchlist }) {
  const [streamType, setStreamType] = useState("ai");
  const [camStatus, setCamStatus] = useState(null);
  const [detections, setDetections] = useState(null);
  const [loading, setLoading] = useState(false);
  const [feedReady, setFeedReady] = useState(false);
  const [feedError, setFeedError] = useState(null);
  const [streamSessionId, setStreamSessionId] = useState(Date.now());
  const [streamKey, setStreamKey] = useState(Date.now());

  const [selectedSourceType, setSelectedSourceType] = useState("webcam");
  const [demoVideos, setDemoVideos] = useState([]);
  const [selectedDemoId, setSelectedDemoId] = useState("");
  const [demoMessage, setDemoMessage] = useState("");
  const [loopEnabled, setLoopEnabled] = useState(true);

  const [uploadedVideo, setUploadedVideo] = useState(null);
  const [localVideoUrl, setLocalVideoUrl] = useState(null);
  const [localWebcamActive, setLocalWebcamActive] = useState(false);
  const [localWebcamStream, setLocalWebcamStream] = useState(null);
  const [backendAvailable, setBackendAvailable] = useState(false);

  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const fileInputRef = useRef(null);
  const videoRef = useRef(null);

  const refreshState = async () => {
    try {
      const s = await api.getWebcamStatus();
      if (s) setCamStatus(s);
      const d = await api.getDetections();
      if (d) setDetections(d);
    } catch {
      // Ignore poll errors
    }
  };

  // Check if Python backend is reachable
  const checkBackend = async () => {
    try {
      const h = await api.health();
      setBackendAvailable(h !== null);
    } catch {
      setBackendAvailable(false);
    }
  };

  const loadDemoVideos = async () => {
    try {
      const res = await api.getVideoSources();
      const vids = res?.videos || [];
      setDemoVideos(vids);
      setDemoMessage(res?.message || "");
      if (vids.length > 0 && !selectedDemoId) {
        setSelectedDemoId(vids[0].id);
      }
    } catch {
      setDemoMessage("Could not fetch demo videos.");
    }
  };

  useEffect(() => {
    refreshState();
    loadDemoVideos();
    checkBackend();
    const interval = setInterval(refreshState, 1000);
    const backendInterval = setInterval(checkBackend, 5000);
    return () => { clearInterval(interval); clearInterval(backendInterval); };
  }, []);

  useEffect(() => {
    if (localWebcamActive && localWebcamStream && videoRef.current) {
      videoRef.current.srcObject = localWebcamStream;
      videoRef.current.play().catch(() => {});
    }
  }, [localWebcamActive, localWebcamStream]);

  const stopLocalWebcam = () => {
    if (localWebcamStream) {
      localWebcamStream.getTracks().forEach((t) => t.stop());
      setLocalWebcamStream(null);
    }
    setLocalWebcamActive(false);
  };

  const handleStartStream = async () => {
    setLoading(true);
    setUploadError(null);
    setFeedReady(false);
    setFeedError(null);
    stopLocalWebcam();

    const newSession = Date.now();
    setStreamSessionId(newSession);
    setStreamKey(newSession);

    try {
      if (selectedSourceType === "webcam") {
        // Check if backend is remote (e.g. Render cloud server has no local hardware webcam)
        const isRemoteBackend = !api.API_BASE.includes("localhost") && !api.API_BASE.includes("127.0.0.1");
        let backendOk = false;

        if (!isRemoteBackend) {
          try {
            const res = await api.startWebcam(0);
            if (res && res.running && !res.camera_error && !res.detail) {
              backendOk = true;
            }
          } catch {
            backendOk = false;
          }
        }

        // For remote cloud server (Render) or when local camera fails, use browser webcam directly
        if (!backendOk) {
          try {
            const stream = await navigator.mediaDevices.getUserMedia({
              video: { width: { ideal: 1280 }, height: { ideal: 720 } },
              audio: false,
            });
            setLocalWebcamStream(stream);
            setLocalWebcamActive(true);
            setFeedReady(true);
            setUploadError(null);
            setFeedError(null);
          } catch (camErr) {
            throw new Error(`Webcam permission denied or camera unavailable: ${camErr.message}`);
          }
        }
      } else if (selectedSourceType === "demo_video") {
        if (!selectedDemoId) {
          setUploadError("Please select a demo video from the dropdown.");
          setLoading(false);
          return;
        }
        await api.startStream({
          source_type: "demo_video",
          source_id: selectedDemoId,
          loop: loopEnabled,
        });
      } else if (selectedSourceType === "uploaded_video") {
        if (!uploadedVideo) {
          setUploadError("No uploaded video selected. Choose an MP4/AVI/MOV file first.");
          setLoading(false);
          return;
        }

        // If backend uploaded successfully, start AI stream through backend
        if (uploadedVideo.id && !uploadedVideo.local) {
          await api.startStream({
            source_type: "uploaded_video",
            source_id: uploadedVideo.id,
            source_name: uploadedVideo.name,
            loop: loopEnabled,
          });
        } else if (localVideoUrl) {
          // Fallback: play locally without AI (no fake boxes)
          setFeedReady(true);
        }
      }
      await refreshState();
    } catch (e) {
      if (selectedSourceType !== "uploaded_video" || !localVideoUrl) {
        setUploadError(`Could not start stream: ${e.message}`);
        setFeedError(e.message);
      }
    }
    setLoading(false);
  };

  const handleStopStream = async () => {
    setLoading(true);
    setFeedReady(false);
    setFeedError(null);
    stopLocalWebcam();
    try {
      await api.stopWebcam();
      await refreshState();
    } catch {
      // Ignore stop errors
    }
    setLoading(false);
  };

  const handleSourceTabChange = (type) => {
    setSelectedSourceType(type);
    setUploadError(null);
    if (type === "demo_video" && demoVideos.length === 0) {
      loadDemoVideos();
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 200 * 1024 * 1024) {
      setUploadError("File exceeds the maximum 200 MB limit.");
      return;
    }
    setUploading(true);
    setUploadError(null);

    // Create local browser URL for fallback playback
    const blobUrl = URL.createObjectURL(file);
    setLocalVideoUrl(blobUrl);

    // Try uploading to Python backend for real AI processing
    try {
      const res = await api.uploadVideo(file);
      setUploadedVideo(res); // res.id exists = backend has the file
    } catch {
      // Backend unreachable - store local-only reference
      setUploadedVideo({
        name: file.name,
        size_mb: (file.size / (1024 * 1024)).toFixed(1),
        local: true,
      });
    }

    setSelectedSourceType("uploaded_video");
    setUploading(false);
  };

  const handleClearUpload = () => {
    if (localVideoUrl) URL.revokeObjectURL(localVideoUrl);
    setLocalVideoUrl(null);
    setUploadedVideo(null);
    setUploadError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    if (selectedSourceType === "uploaded_video") setSelectedSourceType("webcam");
  };

  const isBackendActive = camStatus?.feed_active || camStatus?.running || false;
  const isFeedActive = isBackendActive || localWebcamActive || Boolean(localVideoUrl && selectedSourceType === "uploaded_video" && feedReady);
  const isFinished = camStatus?.source_finished || false;
  const cameraError = feedError || uploadError;
  const displayedFps = isBackendActive ? (camStatus?.displayed_fps || 0) : 0;

  const faces = detections?.faces || [];
  const confirmedPlates = detections?.plates || [];
  const matches = faces.filter((f) => f.possible_match);

  const activeSession = camStatus?.session_id || streamSessionId;
  const currentStreamUrl =
    streamType === "ai"
      ? `${api.getAiStreamUrl()}?session=${activeSession}&t=${streamKey}`
      : streamType === "raw"
      ? `${api.getRawStreamUrl()}?session=${activeSession}&t=${streamKey}`
      : `${api.API_BASE}/api/webcam/debug-face-frame.jpg?session=${activeSession}&t=${Date.now()}`;

  const currentSourceName =
    selectedSourceType === "demo_video"
      ? (demoVideos.find((v) => v.id === selectedDemoId)?.name || "Demo Video")
      : selectedSourceType === "uploaded_video"
      ? (uploadedVideo?.name || "Uploaded Video")
      : "Laptop Webcam 0";

  // Show warning when using local-only playback (no AI)
  const isLocalOnlyPlayback = isFeedActive && !isBackendActive && !localWebcamActive && selectedSourceType === "uploaded_video";

  return (
    <div>
      {/* SOURCE SELECTION */}
      <section style={{
        background: "#04192c",
        border: "1px solid var(--border)",
        borderRadius: "8px",
        padding: "16px 20px",
        marginBottom: "20px",
      }}>
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "14px",
        }}>
          <div>
            <div style={{ fontSize: "11px", color: "var(--muted)", marginBottom: "6px", fontWeight: "600" }}>
              VIDEO SOURCE:
            </div>
            <div style={{
              display: "flex",
              background: "#020e1a",
              padding: "3px",
              borderRadius: "6px",
              border: "1px solid var(--border)",
            }}>
              {[
                { id: "webcam", label: "Laptop Webcam", icon: <Camera size={14} /> },
                { id: "demo_video", label: "Demo Video", icon: <Film size={14} /> },
                { id: "uploaded_video", label: "Upload Video", icon: <Upload size={14} /> },
              ].map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => handleSourceTabChange(s.id)}
                  style={{
                    padding: "6px 14px",
                    fontSize: "12px",
                    fontWeight: "600",
                    borderRadius: "4px",
                    border: "none",
                    background: selectedSourceType === s.id ? "var(--cyan)" : "transparent",
                    color: selectedSourceType === s.id ? "#020e1a" : "var(--muted)",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  {s.icon} {s.label}
                </button>
              ))}
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "14px", flexWrap: "wrap" }}>
            {selectedSourceType === "demo_video" && (
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                {demoVideos.length === 0 ? (
                  <span style={{ fontSize: "12px", color: "var(--orange)" }}>
                    {demoMessage || "No demo videos found."}
                  </span>
                ) : (
                  <select
                    value={selectedDemoId}
                    onChange={(e) => setSelectedDemoId(e.target.value)}
                    style={{
                      padding: "6px 10px",
                      background: "#020e1a",
                      border: "1px solid var(--border)",
                      borderRadius: "6px",
                      color: "#fff",
                      fontSize: "12px",
                    }}
                  >
                    {demoVideos.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.name} ({v.size_mb} MB)
                      </option>
                    ))}
                  </select>
                )}
              </div>
            )}

            {selectedSourceType === "uploaded_video" && (
              <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                <input
                  type="file"
                  accept=".mp4,.avi,.mov,.mkv,.webm"
                  ref={fileInputRef}
                  onChange={handleFileUpload}
                  style={{ display: "none" }}
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  style={{
                    padding: "6px 12px",
                    background: "#020e1a",
                    border: "1px solid var(--border)",
                    borderRadius: "6px",
                    color: "var(--cyan)",
                    fontSize: "12px",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  <FileVideo size={14} /> {uploading ? "Uploading..." : uploadedVideo ? "Choose Another" : "Select Video"}
                </button>
                {uploadedVideo && (
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    fontSize: "12px",
                    background: "#020e1a",
                    padding: "4px 8px",
                    borderRadius: "4px",
                    border: "1px solid var(--border)",
                  }}>
                    <span style={{ color: "var(--green)" }}>
                      Selected: <strong>{uploadedVideo.name}</strong>
                    </span>
                    <button
                      type="button"
                      onClick={handleClearUpload}
                      style={{
                        background: "transparent",
                        border: "none",
                        color: "var(--red)",
                        cursor: "pointer",
                        padding: "0 2px",
                      }}
                      title="Clear uploaded video"
                    >
                      <X size={14} />
                    </button>
                  </div>
                )}
              </div>
            )}

            {selectedSourceType !== "webcam" && (
              <label style={{ display: "flex", alignItems: "center", gap: "5px", fontSize: "11px", color: "#b5cde4", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={loopEnabled}
                  onChange={(e) => setLoopEnabled(e.target.checked)}
                /> Loop
              </label>
            )}

            {isFeedActive ? (
              <button
                type="button"
                onClick={handleStopStream}
                disabled={loading}
                style={{
                  padding: "8px 16px",
                  fontSize: "12px",
                  fontWeight: "600",
                  borderRadius: "6px",
                  border: "1px solid var(--red)",
                  background: "rgba(239,75,95,0.15)",
                  color: "var(--red)",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <Square size={13} /> Stop
              </button>
            ) : (
              <button
                type="button"
                onClick={handleStartStream}
                disabled={loading || uploading}
                style={{
                  padding: "8px 18px",
                  fontSize: "12px",
                  fontWeight: "600",
                  borderRadius: "6px",
                  border: "none",
                  background: "var(--cyan)",
                  color: "#020e1a",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                {loading ? <Loader2 size={13} className="spin" /> : <Play size={13} />} Start
              </button>
            )}
          </div>
        </div>
        {uploadError && (
          <div style={{ marginTop: "10px", fontSize: "12px", color: "var(--red)", display: "flex", alignItems: "center", gap: "6px" }}>
            <AlertCircle size={14} /> Error: {uploadError}
          </div>
        )}
      </section>

      {/* LOCAL-ONLY PLAYBACK WARNING */}
      {isLocalOnlyPlayback && (
        <div style={{
          background: "rgba(255,170,50,0.12)",
          border: "1px solid var(--orange)",
          borderRadius: "8px",
          padding: "12px 16px",
          marginBottom: "16px",
          fontSize: "12px",
          color: "#ffcca0",
          display: "flex",
          alignItems: "center",
          gap: "10px",
        }}>
          <AlertTriangle size={18} color="var(--orange)" />
          <div>
            <strong>Playing video locally (no AI detection).</strong> To enable real-time AI bounding boxes for face &amp; plate detection,
            run the Python backend locally: <code style={{ background: "#020e1a", padding: "2px 6px", borderRadius: "3px" }}>python -m uvicorn main:app --port 8000</code> in the <code style={{ background: "#020e1a", padding: "2px 6px", borderRadius: "3px" }}>backend/</code> folder, then open <code style={{ background: "#020e1a", padding: "2px 6px", borderRadius: "3px" }}>http://localhost:5173</code>.
          </div>
        </div>
      )}

      {/* STREAM VIEW TOGGLES */}
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        marginBottom: "16px",
        flexWrap: "wrap",
        gap: "12px",
      }}>
        <div>
          <h2 style={{ margin: "0 0 4px 0", fontSize: "1.2rem" }}>Live Surveillance Display</h2>
          <p style={{ margin: 0, fontSize: "12px", color: "var(--muted)" }}>
            Real-time YuNet face detection, SFace watchlist matching, and FastALPR plate recognition.
          </p>
        </div>
        <div style={{ display: "flex", background: "#04192c", padding: "3px", borderRadius: "6px", border: "1px solid var(--border)" }}>
          {[
            { id: "ai", label: "AI Overlay", icon: <Layers size={13} /> },
            { id: "raw", label: "Raw Feed", icon: <Eye size={13} /> },
            { id: "debug", label: "Diagnostic", icon: <Activity size={13} /> },
          ].map((v) => (
            <button
              key={v.id}
              type="button"
              onClick={() => setStreamType(v.id)}
              style={{
                padding: "6px 12px",
                fontSize: "11px",
                fontWeight: "600",
                borderRadius: "4px",
                border: "none",
                background: streamType === v.id ? (v.id === "debug" ? "var(--orange)" : "var(--cyan)") : "transparent",
                color: streamType === v.id ? "#020e1a" : "var(--muted)",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "4px",
              }}
            >
              {v.icon} {v.label}
            </button>
          ))}
        </div>
      </div>

      {/* MATCH ALERT */}
      {matches.length > 0 && (
        <div style={{
          background: "rgba(239,75,95,0.18)",
          border: "1px solid var(--red)",
          borderRadius: "8px",
          padding: "14px 18px",
          marginBottom: "20px",
          display: "flex",
          alignItems: "center",
          gap: "14px",
        }}>
          <AlertTriangle size={26} color="var(--red)" />
          <div>
            <strong style={{ color: "var(--red)", fontSize: "14px" }}>POSSIBLE WATCHLIST MATCH DETECTED</strong>
            <div style={{ fontSize: "12px", color: "#ffcdd2", marginTop: "2px" }}>
              Target: <strong>{matches.map((m) => m.identity).join(", ")}</strong>
            </div>
          </div>
        </div>
      )}

      {/* DUAL GRID */}
      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: "20px" }}>
        {/* Video Screen */}
        <section style={{
          background: "#04192c",
          border: "1px solid var(--border)",
          borderRadius: "8px",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}>
          <div style={{
            padding: "12px 16px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}>
            <span style={{ fontSize: "12px", fontWeight: "700" }}>
              SOURCE: {camStatus?.source_name || currentSourceName}
            </span>
            <span style={{
              fontSize: "11px",
              color: isFeedActive ? "var(--green)" : cameraError ? "var(--red)" : "var(--muted)",
            }}>
              {isBackendActive
                ? `AI ACTIVE (${displayedFps} FPS)`
                : localWebcamActive
                ? "BROWSER WEBCAM ACTIVE"
                : isFeedActive
                ? "VIDEO PLAYING (No AI)"
                : cameraError
                ? "SOURCE ERROR"
                : isFinished
                ? "PLAYBACK FINISHED"
                : "STANDBY"}
            </span>
          </div>

          <div style={{
            position: "relative",
            background: "#020e1a",
            width: "100%",
            height: "480px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            overflow: "hidden",
          }}>
            {/* 1. Python Backend AI Stream (real bounding boxes) */}
            {isBackendActive && (
              <img
                key={`feed-${streamSessionId}-${streamType}`}
                src={currentStreamUrl}
                alt="AI Surveillance Feed"
                onLoad={() => {
                  setFeedReady(true);
                  setFeedError(null);
                }}
                onError={() => {
                  setFeedError("AI stream disconnected.");
                }}
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "contain",
                }}
              />
            )}

            {/* 2. Local Video Player (no AI overlay - just raw playback) */}
            {!isBackendActive && selectedSourceType === "uploaded_video" && localVideoUrl && feedReady && (
              <video
                ref={videoRef}
                src={localVideoUrl}
                controls
                autoPlay
                loop={loopEnabled}
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "contain",
                }}
              />
            )}

            {/* 3. Browser Webcam (no AI overlay - just raw feed) */}
            {!isBackendActive && localWebcamActive && (
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "contain",
                }}
              />
            )}

            {/* Standby State */}
            {!isFeedActive && !loading && !cameraError && (
              <div style={{ textAlign: "center", padding: "60px 20px", color: "var(--muted)" }}>
                <Video size={48} style={{ marginBottom: "12px", opacity: 0.4 }} />
                <h4 style={{ margin: "0 0 6px 0", color: "#e4f1ff" }}>Surveillance Stream Standby</h4>
                <p style={{ margin: 0, fontSize: "13px" }}>
                  Select a video source or upload an MP4 video, then click <strong>Start</strong>.
                </p>
              </div>
            )}

            {/* Connecting State */}
            {loading && !cameraError && (
              <div style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                background: "#020e1a",
                color: "#b5cde4",
              }}>
                <Loader2 size={36} className="spin" style={{ color: "var(--cyan)", marginBottom: "12px" }} />
                <strong style={{ fontSize: "14px" }}>Connecting to {currentSourceName}...</strong>
                <span style={{ fontSize: "12px", color: "var(--muted)", marginTop: "4px" }}>
                  Initializing optical sensor and surveillance feed
                </span>
              </div>
            )}

            {/* Error State */}
            {cameraError && !isFeedActive && !loading && (
              <div style={{ textAlign: "center", padding: "60px 20px", color: "var(--red)" }}>
                <AlertCircle size={48} style={{ marginBottom: "12px" }} />
                <h4 style={{ margin: "0 0 8px 0" }}>Source Error</h4>
                <p style={{ margin: "0 0 16px 0", fontSize: "13px", color: "#ffcdd2" }}>{cameraError}</p>
                <button
                  type="button"
                  onClick={handleStartStream}
                  style={{
                    padding: "8px 16px",
                    background: "var(--cyan)",
                    color: "#020e1a",
                    border: "none",
                    borderRadius: "6px",
                    fontWeight: "600",
                    fontSize: "12px",
                    cursor: "pointer",
                  }}
                >
                  Retry Connection
                </button>
              </div>
            )}
          </div>
        </section>

        {/* DETECTIONS SIDE PANEL */}
        <section style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div style={{
            background: "#04192c",
            border: "1px solid var(--border)",
            borderRadius: "8px",
            padding: "16px",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <h3 style={{ margin: 0, fontSize: "13px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                DETECTIONS (Faces: {faces.length} | Plates: {confirmedPlates.length})
              </h3>
              <button
                type="button"
                onClick={refreshState}
                style={{ background: "transparent", border: "none", color: "var(--cyan)", cursor: "pointer" }}
                title="Refresh detections"
              >
                <RefreshCw size={13} /> Refresh
              </button>
            </div>

            {faces.length === 0 && confirmedPlates.length === 0 ? (
              <div style={{ textAlign: "center", padding: "30px 10px", color: "var(--muted)", fontSize: "12px" }}>
                {isBackendActive
                  ? "Scanning frame for faces & license plates..."
                  : isLocalOnlyPlayback
                  ? "AI detection requires the Python backend. Video is playing without AI analysis."
                  : "Stream is stopped."}
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "10px", maxHeight: "380px", overflowY: "auto" }}>
                {faces.map((f, i) => (
                  <div
                    key={`face-${i}`}
                    style={{
                      background: f.possible_match ? "rgba(239,75,95,0.12)" : "#020e1a",
                      border: `1px solid ${f.possible_match ? "var(--red)" : "var(--border)"}`,
                      borderRadius: "6px",
                      padding: "10px",
                      display: "flex",
                      gap: "10px",
                      alignItems: "center",
                    }}
                  >
                    <div style={{
                      width: "42px", height: "42px", borderRadius: "4px", background: "#0a2744",
                      display: "grid", placeItems: "center", fontSize: "10px", fontWeight: "700", color: "var(--cyan)"
                    }}>
                      FACE
                    </div>
                    <div style={{ flex: 1, fontSize: "12px" }}>
                      <div style={{ fontWeight: "700", color: f.possible_match ? "var(--red)" : "#fff" }}>
                        {f.identity || "Unknown Person"}
                      </div>
                      <div style={{ fontSize: "11px", color: "var(--muted)" }}>
                        Confidence: {(f.confidence * 100).toFixed(1)}% | Quality: {f.quality_score || "Good"}
                      </div>
                    </div>
                  </div>
                ))}

                {confirmedPlates.map((p, i) => (
                  <div
                    key={`plate-${i}`}
                    style={{
                      background: "#020e1a",
                      border: "1px solid var(--border)",
                      borderRadius: "6px",
                      padding: "10px",
                      display: "flex",
                      gap: "10px",
                      alignItems: "center",
                    }}
                  >
                    <Car size={20} style={{ color: "var(--cyan)" }} />
                    <div style={{ flex: 1, fontSize: "12px" }}>
                      <div style={{ fontWeight: "700", letterSpacing: "1px", color: "var(--cyan)" }}>
                        {p.text}
                      </div>
                      <div style={{ fontSize: "11px", color: "var(--muted)" }}>
                        Plate Confidence: {(p.confidence * 100).toFixed(1)}%
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* FCR WATCHLIST Quick Link */}
          <div style={{
            background: "#04192c",
            border: "1px solid var(--border)",
            borderRadius: "8px",
            padding: "14px 16px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}>
            <span style={{ fontSize: "13px", fontWeight: "700" }}>FCR WATCHLIST</span>
            {onNavigateToWatchlist && (
              <button
                type="button"
                onClick={onNavigateToWatchlist}
                style={{
                  padding: "5px 10px",
                  fontSize: "11px",
                  background: "transparent",
                  border: "1px solid var(--cyan)",
                  borderRadius: "4px",
                  color: "var(--cyan)",
                  cursor: "pointer",
                }}
              >
                + Manage
              </button>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

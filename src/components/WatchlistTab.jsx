import React, { useState, useEffect, useRef } from "react";
import * as api from "../api";
import { UserRound, Upload, Check, X, RefreshCw, Trash2 } from "lucide-react";

export default function WatchlistTab() {
  const [watchlist, setWatchlist] = useState([]);
  const [name, setName] = useState("");
  const [imageFile, setImageFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState(null);
  const fileInputRef = useRef(null);

  const loadWatchlist = () => {
    api.getWatchlist().then((w) => setWatchlist(w));
  };

  useEffect(() => {
    loadWatchlist();
  }, []);

  const handleEnrollSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim() || !imageFile) {
      setMessage({ type: "error", text: "Please enter a target name and select a photo." });
      return;
    }

    setUploading(true);
    setMessage(null);

    try {
      const res = await api.enrollFace(name.trim(), imageFile);
      setMessage({ type: "success", text: `Target "${res.name}" enrolled successfully. Confidence: ${Math.round(res.confidence * 100)}%` });
      setName("");
      setImageFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      loadWatchlist();
    } catch (err) {
      setMessage({ type: "error", text: err.message || "Failed to enroll face." });
    }
    setUploading(false);
  };

  const handleDelete = async (id) => {
    if (confirm("Remove this person from the watchlist?")) {
      await api.deleteWatchlistFace(id);
      loadWatchlist();
    }
  };

  return (
    <div>
      <div style={{ marginBottom: "20px" }}>
        <h2 style={{ margin: "0 0 4px 0", fontSize: "1.3rem" }}>FCR Target Watchlist</h2>
        <p style={{ margin: 0, fontSize: "12px", color: "var(--muted)" }}>
          Upload clear front-facing photos of persons of interest to trigger real-time alerts when seen by the optical feed.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.5fr", gap: "20px" }}>
        {/* ENROLL TARGET FORM */}
        <section style={{ background: "#04192c", border: "1px solid var(--border)", borderRadius: "8px", padding: "20px" }}>
          <h3 style={{ margin: "0 0 14px 0", fontSize: "14px" }}>Enroll New Target Person</h3>

          {message && (
            <div
              style={{
                padding: "10px 14px",
                borderRadius: "6px",
                marginBottom: "16px",
                fontSize: "12px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
                background: message.type === "success" ? "rgba(25,211,155,0.15)" : "rgba(239,75,95,0.15)",
                border: `1px solid ${message.type === "success" ? "var(--green)" : "var(--red)"}`,
                color: message.type === "success" ? "var(--green)" : "var(--red)"
              }}
            >
              {message.type === "success" ? <Check size={16} /> : <X size={16} />}
              <span>{message.text}</span>
            </div>
          )}

          <form onSubmit={handleEnrollSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div>
              <label style={{ fontSize: "12px", color: "#b5cde4", display: "block", marginBottom: "6px" }}>
                Target Person Name:
              </label>
              <input
                type="text"
                placeholder="e.g. Officer Rohan, Subject #401"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  background: "#020e1a",
                  border: "1px solid var(--border)",
                  borderRadius: "6px",
                  color: "#fff",
                  fontSize: "13px"
                }}
              />
            </div>

            <div>
              <label style={{ fontSize: "12px", color: "#b5cde4", display: "block", marginBottom: "6px" }}>
                Upload Clear Face Photo (JPG/PNG):
              </label>
              <input
                type="file"
                accept="image/*"
                ref={fileInputRef}
                onChange={(e) => setImageFile(e.target.files[0])}
                required
                style={{
                  width: "100%",
                  padding: "8px",
                  background: "#020e1a",
                  border: "1px solid var(--border)",
                  borderRadius: "6px",
                  color: "#b5cde4",
                  fontSize: "12px"
                }}
              />
              <span style={{ fontSize: "11px", color: "var(--muted)", marginTop: "4px", display: "block" }}>
                Requirement: Exactly one front-facing face in the photo.
              </span>
            </div>

            <button
              type="submit"
              disabled={uploading}
              style={{
                padding: "10px 16px",
                background: "var(--cyan)",
                color: "#020e1a",
                border: "none",
                borderRadius: "6px",
                fontWeight: "600",
                fontSize: "13px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px"
              }}
            >
              <Upload size={16} />
              {uploading ? "Extracting Face and Enrolling..." : "Enroll Target to Watchlist"}
            </button>
          </form>
        </section>

        {/* ENROLLED WATCHLIST TABLE */}
        <section style={{ background: "#04192c", border: "1px solid var(--border)", borderRadius: "8px", padding: "20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <h3 style={{ margin: 0, fontSize: "14px" }}>Enrolled Watchlist ({watchlist.length})</h3>
            <button
              onClick={loadWatchlist}
              style={{ background: "transparent", border: "none", color: "var(--cyan)", cursor: "pointer", fontSize: "11px" }}
            >
              <RefreshCw size={11} /> Refresh
            </button>
          </div>

          {watchlist.length === 0 ? (
            <div style={{ textAlign: "center", padding: "50px 20px", color: "var(--muted)" }}>
              <UserRound size={36} style={{ opacity: 0.3, marginBottom: "10px" }} />
              <p style={{ margin: 0, fontSize: "13px" }}>No target persons enrolled yet.</p>
              <span style={{ fontSize: "11px" }}>Upload an image on the left to begin active FCR matching.</span>
            </div>
          ) : (
            <div style={{ maxHeight: "400px", overflowY: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)", textAlign: "left", color: "var(--muted)" }}>
                    <th style={{ padding: "8px" }}>THUMBNAIL</th>
                    <th style={{ padding: "8px" }}>TARGET NAME</th>
                    <th style={{ padding: "8px" }}>FACE ID</th>
                    <th style={{ padding: "8px" }}>ENROLLED AT</th>
                    <th style={{ padding: "8px" }}>ACTION</th>
                  </tr>
                </thead>
                <tbody>
                  {watchlist.map((person) => (
                    <tr key={person.id} style={{ borderBottom: "1px solid rgba(18,60,96,0.5)" }}>
                      <td style={{ padding: "8px" }}>
                        {person.thumbnail ? (
                          <img
                            src={`data:image/jpeg;base64,${person.thumbnail}`}
                            alt={person.name}
                            style={{ width: "36px", height: "36px", borderRadius: "4px", objectFit: "cover" }}
                          />
                        ) : (
                          <div style={{ width: "36px", height: "36px", borderRadius: "4px", background: "#020e1a", display: "grid", placeItems: "center" }}>
                            <UserRound size={16} />
                          </div>
                        )}
                      </td>
                      <td style={{ padding: "8px" }}>
                        <strong style={{ color: "#fff" }}>{person.name}</strong>
                      </td>
                      <td style={{ padding: "8px", fontFamily: "monospace", color: "var(--cyan)" }}>
                        {person.id}
                      </td>
                      <td style={{ padding: "8px", color: "var(--muted)" }}>
                        {(person.created_at || "").slice(0, 10)}
                      </td>
                      <td style={{ padding: "8px" }}>
                        <button
                          onClick={() => handleDelete(person.id)}
                          style={{ background: "transparent", border: "none", color: "var(--red)", cursor: "pointer" }}
                          title="Remove from Watchlist"
                        >
                          <Trash2 size={15} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

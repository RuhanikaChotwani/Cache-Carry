"""SQLite storage layer for IBVAP."""
import sqlite3, os, json
from datetime import datetime

DB_PATH = os.getenv("IBVAP_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "ibvap.db"))


def _db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = _db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS cameras (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        location TEXT DEFAULT '',
        source TEXT DEFAULT 'mock',
        type TEXT DEFAULT 'mock',
        status TEXT DEFAULT 'IDLE',
        detection TEXT DEFAULT '',
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        time TEXT,
        camera_id TEXT,
        camera_name TEXT DEFAULT '',
        event_type TEXT,
        severity TEXT DEFAULT 'Low',
        status TEXT DEFAULT 'Active',
        description TEXT DEFAULT '',
        ai_metadata TEXT DEFAULT '{}'
    );
    CREATE TABLE IF NOT EXISTS alerts (
        id TEXT PRIMARY KEY,
        time TEXT,
        camera_id TEXT,
        camera_name TEXT DEFAULT '',
        event_type TEXT,
        severity TEXT DEFAULT 'Medium',
        description TEXT DEFAULT '',
        ai_metadata TEXT DEFAULT '{}',
        snapshot_path TEXT DEFAULT '',
        block_id INTEGER DEFAULT NULL,
        status TEXT DEFAULT 'Active'
    );
    CREATE TABLE IF NOT EXISTS blockchain (
        block_number INTEGER PRIMARY KEY,
        event_id TEXT,
        camera_id TEXT DEFAULT '',
        evidence_hash TEXT,
        metadata_hash TEXT,
        timestamp TEXT,
        previous_hash TEXT,
        block_hash TEXT,
        status TEXT DEFAULT 'Secured'
    );
    CREATE TABLE IF NOT EXISTS zones (
        id TEXT PRIMARY KEY,
        camera_id TEXT,
        name TEXT,
        points TEXT DEFAULT '[]',
        severity TEXT DEFAULT 'Critical'
    );
    CREATE TABLE IF NOT EXISTS calibrations (
        camera_id TEXT PRIMARY KEY,
        data TEXT DEFAULT '{}'
    );
    """)
    conn.commit()
    conn.close()


# --- Camera CRUD ---
def get_cameras():
    conn = _db()
    rows = conn.execute("SELECT * FROM cameras ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_camera(camera_id):
    conn = _db()
    row = conn.execute("SELECT * FROM cameras WHERE id=?", (camera_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_camera(cam: dict):
    conn = _db()
    conn.execute(
        "INSERT INTO cameras (id,name,location,source,type,status,detection,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (cam["id"], cam["name"], cam["location"], cam["source"], cam["type"],
         cam.get("status", "IDLE"), cam.get("detection", ""), cam.get("created_at", datetime.utcnow().isoformat()))
    )
    conn.commit()
    conn.close()


def update_camera(camera_id, updates: dict):
    conn = _db()
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [camera_id]
    conn.execute(f"UPDATE cameras SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()


def delete_camera(camera_id):
    conn = _db()
    conn.execute("DELETE FROM cameras WHERE id=?", (camera_id,))
    conn.commit()
    conn.close()


# --- Events ---
def get_events(limit=100):
    conn = _db()
    rows = conn.execute("SELECT * FROM events ORDER BY time DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_event(evt: dict):
    conn = _db()
    conn.execute(
        "INSERT OR REPLACE INTO events (id,time,camera_id,camera_name,event_type,severity,status,description,ai_metadata) VALUES (?,?,?,?,?,?,?,?,?)",
        (evt["id"], evt["time"], evt["camera_id"], evt.get("camera_name", ""),
         evt["event_type"], evt.get("severity", "Low"), evt.get("status", "Active"),
         evt.get("description", ""), json.dumps(evt.get("ai_metadata", {})))
    )
    conn.commit()
    conn.close()


# --- Alerts ---
def get_alerts(limit=100):
    conn = _db()
    rows = conn.execute("SELECT * FROM alerts ORDER BY time DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["ai_metadata"] = json.loads(d.get("ai_metadata", "{}"))
        except Exception:
            d["ai_metadata"] = {}
        result.append(d)
    return result


def add_alert(alert: dict):
    conn = _db()
    conn.execute(
        "INSERT OR REPLACE INTO alerts (id,time,camera_id,camera_name,event_type,severity,description,ai_metadata,snapshot_path,block_id,status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (alert["id"], alert["time"], alert["camera_id"], alert.get("camera_name", ""),
         alert["event_type"], alert.get("severity", "Medium"), alert.get("description", ""),
         json.dumps(alert.get("ai_metadata", {})), alert.get("snapshot_path", ""),
         alert.get("block_id"), alert.get("status", "Active"))
    )
    conn.commit()
    conn.close()


def update_alert(alert_id, updates: dict):
    conn = _db()
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [alert_id]
    conn.execute(f"UPDATE alerts SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()


def clear_alerts():
    conn = _db()
    conn.execute("DELETE FROM alerts")
    conn.commit()
    conn.close()



# --- Blockchain ---
def get_blockchain():
    conn = _db()
    rows = conn.execute("SELECT * FROM blockchain ORDER BY block_number ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_block(block: dict):
    conn = _db()
    conn.execute(
        "INSERT INTO blockchain (block_number,event_id,camera_id,evidence_hash,metadata_hash,timestamp,previous_hash,block_hash,status) VALUES (?,?,?,?,?,?,?,?,?)",
        (block["block_number"], block["event_id"], block.get("camera_id", ""),
         block["evidence_hash"], block["metadata_hash"], block["timestamp"],
         block["previous_hash"], block["block_hash"], block.get("status", "Secured"))
    )
    conn.commit()
    conn.close()


def get_last_block():
    conn = _db()
    row = conn.execute("SELECT * FROM blockchain ORDER BY block_number DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


# --- Zones ---
def get_zones(camera_id=None):
    conn = _db()
    if camera_id:
        rows = conn.execute("SELECT * FROM zones WHERE camera_id=?", (camera_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM zones").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["points"] = json.loads(d["points"])
        except Exception:
            d["points"] = []
        result.append(d)
    return result


def add_zone(zone: dict):
    conn = _db()
    conn.execute(
        "INSERT INTO zones (id,camera_id,name,points,severity) VALUES (?,?,?,?,?)",
        (zone["id"], zone["camera_id"], zone["name"],
         json.dumps(zone["points"]), zone.get("severity", "Critical"))
    )
    conn.commit()
    conn.close()


# --- Calibrations ---
def get_calibration(camera_id):
    conn = _db()
    row = conn.execute("SELECT * FROM calibrations WHERE camera_id=?", (camera_id,)).fetchone()
    conn.close()
    if row:
        d = dict(row)
        try:
            d["data"] = json.loads(d["data"])
        except Exception:
            d["data"] = {}
        return d["data"]
    return None


def set_calibration(camera_id, data: dict):
    conn = _db()
    conn.execute(
        "INSERT OR REPLACE INTO calibrations (camera_id, data) VALUES (?,?)",
        (camera_id, json.dumps(data))
    )
    conn.commit()
    conn.close()


# --- Counts for analytics ---

def count_table(table, where=None):
    conn = _db()
    q = f"SELECT COUNT(*) FROM {table}"
    params = ()
    if where:
        q += f" WHERE {where[0]}"
        params = where[1] if len(where) > 1 else ()
    row = conn.execute(q, params).fetchone()
    conn.close()
    return row[0] if row else 0

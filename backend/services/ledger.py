"""Frame-by-frame tamper-evidence hash chain for IBVAP.
Local append-only SHA-256 chain providing tamper-evident audit trails.
Supports per-frame hashing in a bounded FIFO queue with a background writer,
and event-evidence blocks for confirmed FCR matches and confirmed ANPR plates.
"""

import hashlib
import json
import threading
import time
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional, List

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LEDGER_FILE = DATA_DIR / "ledger.json"
FRAME_CHAIN_FILE = DATA_DIR / "frame_chain.json"
EVIDENCE_DIR = DATA_DIR / "evidence"

_ledger_lock = threading.Lock()
_ledger = []  # event-evidence blocks only

_chain_lock = threading.Lock()
_frame_chain = []  # frame hash chain records
_current_chain_hash = "0" * 64
_frame_queue = deque(maxlen=512)  # bounded FIFO queue
_frames_hashed = 0
_queue_drops = 0

_writer_thread: Optional[threading.Thread] = None
_writer_stop = threading.Event()
_writer_error: Optional[str] = None
_active_session_id: Optional[str] = None

MAX_CHAIN_RECORDS_IN_MEMORY = 2000


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_str(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- Event-Evidence Ledger (existing functionality) ---

def _load_ledger():
    global _ledger
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if LEDGER_FILE.exists():
        try:
            with open(LEDGER_FILE, "r") as f:
                _ledger = json.load(f)
        except Exception:
            _ledger = []
    else:
        _ledger = []
        _save_ledger()


def _save_ledger():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_FILE, "w") as f:
        json.dump(_ledger, f, indent=2)


_load_ledger()


def get_ledger():
    with _ledger_lock:
        return list(_ledger)


def add_entry(event_id: str, metadata: dict):
    """Adds an event-evidence block to the event ledger."""
    with _ledger_lock:
        prev_hash = _ledger[-1]["current_hash"] if _ledger else "0" * 64
        block_num = len(_ledger) + 1
        timestamp = datetime.utcnow().isoformat() + "Z"

        payload_str = f"{block_num}:{event_id}:{timestamp}:{json.dumps(metadata, sort_keys=True)}:{prev_hash}"
        current_hash = _sha256_str(payload_str)

        block = {
            "block_number": block_num,
            "event_id": event_id,
            "timestamp": timestamp,
            "metadata": metadata,
            "previous_hash": prev_hash,
            "current_hash": current_hash,
        }
        _ledger.append(block)
        _save_ledger()
        return block


def validate_ledger():
    """Validates the event-evidence ledger chain."""
    with _ledger_lock:
        if not _ledger:
            return {
                "valid": True,
                "total_blocks": 0,
                "message": "Event evidence ledger is empty. Chain is intact.",
            }

        for i, block in enumerate(_ledger):
            expected_prev = "0" * 64 if i == 0 else _ledger[i - 1]["current_hash"]
            if block["previous_hash"] != expected_prev:
                return {
                    "valid": False,
                    "broken_at_block": block["block_number"],
                    "expected_hash": expected_prev,
                    "actual_hash": block["previous_hash"],
                    "message": f"Hash chain broken at block #{block['block_number']}. Previous hash mismatch.",
                }

            payload_str = (
                f"{block['block_number']}:{block['event_id']}:{block['timestamp']}:"
                f"{json.dumps(block['metadata'], sort_keys=True)}:{block['previous_hash']}"
            )
            recalculated = _sha256_str(payload_str)
            if recalculated != block["current_hash"]:
                return {
                    "valid": False,
                    "broken_at_block": block["block_number"],
                    "expected_hash": recalculated,
                    "actual_hash": block["current_hash"],
                    "message": f"Block #{block['block_number']} content hash mismatch (tampered).",
                }

        return {
            "valid": True,
            "total_blocks": len(_ledger),
            "latest_hash": _ledger[-1]["current_hash"],
            "message": f"Integrity verified across all {len(_ledger)} event-evidence blocks.",
        }


# --- Frame-by-Frame Hash Chain ---

def start_frame_chain(session_id: str):
    """Starts a new frame hash chain session and background writer."""
    global _frame_chain, _current_chain_hash, _frames_hashed, _queue_drops
    global _writer_thread, _writer_stop, _writer_error, _active_session_id

    stop_frame_chain()

    with _chain_lock:
        _frame_chain = []
        _current_chain_hash = "0" * 64
        _frames_hashed = 0
        _queue_drops = 0
        _frame_queue.clear()
        _active_session_id = session_id
        _writer_error = None

    _writer_stop.clear()
    _writer_thread = threading.Thread(
        target=_frame_chain_writer,
        name=f"FrameChainWriter-{session_id}",
        daemon=True,
    )
    _writer_thread.start()


def stop_frame_chain():
    """Stops the background writer and persists the frame chain."""
    global _writer_thread, _active_session_id
    _writer_stop.set()
    if _writer_thread is not None and _writer_thread.is_alive():
        _writer_thread.join(timeout=2.0)
    _writer_thread = None

    _persist_frame_chain()


def enqueue_frame_hash(frame_jpeg_bytes: bytes, frame_sequence: int, source_id: str):
    """Enqueues a frame hash record. Non-blocking; drops oldest if queue is full."""
    global _queue_drops
    if not _active_session_id or _writer_stop.is_set():
        return

    frame_hash = _sha256(frame_jpeg_bytes)
    timestamp = datetime.utcnow().isoformat() + "Z"

    record = {
        "session_id": _active_session_id,
        "sequence": frame_sequence,
        "timestamp": timestamp,
        "source": source_id,
        "frame_hash": frame_hash,
    }

    try:
        _frame_queue.append(record)
    except Exception:
        _queue_drops += 1


def record_evidence_event(
    event_type: str,
    source_name: str,
    evidence_jpeg_bytes: Optional[bytes] = None,
    metadata: Optional[dict] = None,
):
    """Creates an event-evidence block referencing the current frame chain state.
    Saves evidence snapshot if provided.
    """
    global _frames_hashed

    evidence_hash = None
    evidence_path = None

    if evidence_jpeg_bytes:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        evidence_hash = _sha256(evidence_jpeg_bytes)
        fname = f"evidence_{uuid.uuid4().hex[:8]}.jpg"
        evidence_path = str(EVIDENCE_DIR / fname)
        try:
            with open(evidence_path, "wb") as f:
                f.write(evidence_jpeg_bytes)
        except Exception:
            evidence_path = None

    event_id = f"evt-{uuid.uuid4().hex[:6]}"
    meta = metadata or {}
    meta["event_type"] = event_type
    meta["source"] = source_name
    if evidence_hash:
        meta["evidence_hash"] = evidence_hash
    if evidence_path:
        meta["evidence_path"] = evidence_path

    with _chain_lock:
        meta["frame_chain_sequence"] = _frames_hashed
        meta["frame_chain_hash"] = _current_chain_hash

    return add_entry(event_id=event_id, metadata=meta)


def get_ledger_status() -> dict:
    """Returns frame chain status for the API."""
    with _chain_lock:
        chain_len = len(_frame_chain)
        current_hash = _current_chain_hash
        frames = _frames_hashed
        drops = _queue_drops
        session = _active_session_id
        queue_size = len(_frame_queue)

    return {
        "active_session": session,
        "frames_hashed": frames,
        "current_chain_hash": current_hash,
        "chain_records_in_memory": chain_len,
        "queue_pending": queue_size,
        "queue_capacity": 512,
        "queue_drops": drops,
        "writer_active": _writer_thread is not None and _writer_thread.is_alive(),
        "writer_error": _writer_error,
    }


def get_recent_chain(limit: int = 50) -> dict:
    """Returns recent frame hash chain records and event evidence records."""
    with _chain_lock:
        recent_frames = list(_frame_chain[-limit:])
    with _ledger_lock:
        recent_events = list(_ledger[-limit:])

    return {
        "frame_chain_records": recent_frames,
        "event_evidence_records": recent_events,
    }


def verify_frame_chain(session_id: Optional[str] = None) -> dict:
    """Recomputes and validates the frame hash chain."""
    with _chain_lock:
        chain = list(_frame_chain)

    if not chain:
        return {
            "valid": True,
            "checked_frames": 0,
            "message": "Frame chain is empty. No frames to verify.",
        }

    if session_id and chain[0].get("session_id") != session_id:
        return {
            "valid": False,
            "checked_frames": 0,
            "message": f"No chain found for session {session_id}.",
        }

    prev_hash = "0" * 64
    for i, rec in enumerate(chain):
        expected_chain = _sha256_str(
            prev_hash
            + rec["frame_hash"]
            + rec["session_id"]
            + str(rec["sequence"])
            + rec["timestamp"]
            + rec["source"]
        )
        if rec["chain_hash"] != expected_chain:
            return {
                "valid": False,
                "checked_frames": i,
                "first_broken_sequence": rec["sequence"],
                "expected_hash": expected_chain,
                "actual_hash": rec["chain_hash"],
                "message": f"Frame chain broken at sequence {rec['sequence']}. Hash mismatch detected.",
            }
        prev_hash = rec["chain_hash"]

    return {
        "valid": True,
        "checked_frames": len(chain),
        "latest_chain_hash": chain[-1]["chain_hash"],
        "message": f"Frame chain integrity verified across {len(chain)} frames.",
    }


def _frame_chain_writer():
    """Background writer that processes the frame hash queue."""
    global _current_chain_hash, _frames_hashed, _writer_error

    while not _writer_stop.is_set():
        try:
            while _frame_queue:
                record = _frame_queue.popleft()

                with _chain_lock:
                    chain_hash = _sha256_str(
                        _current_chain_hash
                        + record["frame_hash"]
                        + record["session_id"]
                        + str(record["sequence"])
                        + record["timestamp"]
                        + record["source"]
                    )
                    record["previous_chain_hash"] = _current_chain_hash
                    record["chain_hash"] = chain_hash
                    _current_chain_hash = chain_hash
                    _frames_hashed += 1

                    _frame_chain.append(record)

                    # Trim old records from memory
                    if len(_frame_chain) > MAX_CHAIN_RECORDS_IN_MEMORY:
                        _frame_chain[:] = _frame_chain[-MAX_CHAIN_RECORDS_IN_MEMORY:]

        except Exception as e:
            _writer_error = str(e)

        _writer_stop.wait(timeout=0.05)

    # Drain remaining items on stop
    try:
        while _frame_queue:
            record = _frame_queue.popleft()
            with _chain_lock:
                chain_hash = _sha256_str(
                    _current_chain_hash
                    + record["frame_hash"]
                    + record["session_id"]
                    + str(record["sequence"])
                    + record["timestamp"]
                    + record["source"]
                )
                record["previous_chain_hash"] = _current_chain_hash
                record["chain_hash"] = chain_hash
                _current_chain_hash = chain_hash
                _frames_hashed += 1
                _frame_chain.append(record)
    except Exception:
        pass


def _persist_frame_chain():
    """Saves the current frame chain to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _chain_lock:
        chain_copy = list(_frame_chain)
    try:
        with open(FRAME_CHAIN_FILE, "w") as f:
            json.dump(chain_copy, f, indent=2)
    except Exception:
        pass

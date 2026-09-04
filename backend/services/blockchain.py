"""Blockchain evidence integrity service for IBVAP.
Reuses hash/chain logic from existing app.py Streamlit code.
"""
import hashlib, json, os
from datetime import datetime
from services import storage


def calculate_hash(data_bytes: bytes) -> str:
    """SHA-256 fingerprint of evidence bytes."""
    return hashlib.sha256(data_bytes).hexdigest()


def calculate_metadata_hash(metadata: dict) -> str:
    """SHA-256 of JSON-serialized metadata."""
    encoded = json.dumps(metadata, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def calculate_block_hash(block_number, event_id, evidence_hash, timestamp, previous_hash, metadata_hash="") -> str:
    """Cryptographic hash for a blockchain block."""
    block_data = {
        "block_number": block_number,
        "event_id": event_id,
        "evidence_hash": evidence_hash,
        "metadata_hash": metadata_hash,
        "timestamp": timestamp,
        "previous_hash": previous_hash,
    }
    encoded = json.dumps(block_data, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


GENESIS_PREV = "0" * 64


def secure_evidence(event_id: str, evidence_bytes: bytes = None, camera_id: str = "", metadata: dict = None) -> dict:
    """Create a new block securing evidence into the chain."""
    if metadata is None:
        metadata = {}

    evidence_hash = calculate_hash(evidence_bytes) if evidence_bytes else calculate_hash(event_id.encode())
    metadata_hash = calculate_metadata_hash(metadata)

    last = storage.get_last_block()
    block_number = (last["block_number"] + 1) if last else 1
    previous_hash = last["block_hash"] if last else GENESIS_PREV
    timestamp = datetime.utcnow().isoformat() + "Z"

    block_hash = calculate_block_hash(block_number, event_id, evidence_hash, timestamp, previous_hash, metadata_hash)

    block = {
        "block_number": block_number,
        "event_id": event_id,
        "camera_id": camera_id,
        "evidence_hash": evidence_hash,
        "metadata_hash": metadata_hash,
        "timestamp": timestamp,
        "previous_hash": previous_hash,
        "block_hash": block_hash,
        "status": "Secured",
    }
    storage.add_block(block)
    return block


def validate_chain() -> tuple[bool, str]:
    """Validate entire blockchain integrity."""
    chain = storage.get_blockchain()
    if not chain:
        return False, "No evidence blocks to validate yet."

    for i, block in enumerate(chain):
        recalc = calculate_block_hash(
            block["block_number"], block["event_id"],
            block["evidence_hash"], block["timestamp"],
            block["previous_hash"], block.get("metadata_hash", "")
        )
        if recalc != block["block_hash"]:
            return False, f"Block #{block['block_number']} has been modified."

        if i == 0:
            if block["previous_hash"] != GENESIS_PREV:
                return False, "Genesis block has invalid previous hash."
        else:
            if block["previous_hash"] != chain[i - 1]["block_hash"]:
                return False, f"Block #{block['block_number']} is not correctly linked."

    return True, f"All {len(chain)} blocks are cryptographically intact."


def verify_evidence(evidence_hash: str) -> dict:
    """Check if a given evidence hash exists in the chain."""
    chain = storage.get_blockchain()
    for block in chain:
        if block["evidence_hash"] == evidence_hash:
            return {"found": True, "block": block}
    return {"found": False, "block": None}


def get_certificate(event_id: str) -> dict | None:
    """Generate a verification certificate for an event."""
    chain = storage.get_blockchain()
    for block in chain:
        if block["event_id"] == event_id:
            valid, msg = validate_chain()
            return {
                "certificate_id": f"CERT-{block['block_number']:04d}",
                "event_id": event_id,
                "block_number": block["block_number"],
                "evidence_hash": block["evidence_hash"],
                "block_hash": block["block_hash"],
                "timestamp": block["timestamp"],
                "chain_valid": valid,
                "chain_message": msg,
                "issued_at": datetime.utcnow().isoformat() + "Z",
                "issuer": "IBVAP Evidence Integrity System",
            }
    return None


def get_audit_report() -> dict:
    """Full audit report of the evidence chain."""
    chain = storage.get_blockchain()
    valid, msg = validate_chain()
    return {
        "total_blocks": len(chain),
        "chain_valid": valid,
        "validation_message": msg,
        "blocks": chain,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }

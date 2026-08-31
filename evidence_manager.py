
import os
import json
import hashlib
from datetime import datetime

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATA_FILE = os.path.join(
    BASE_DIR,
    "blockchain_data.json"
)

SECURED_DIR = os.path.join(
    BASE_DIR,
    "evidence_storage",
    "secured"
)


# =========================================================
# HASH FUNCTIONS
# =========================================================

def calculate_hash(file_bytes):
    """
    Return the SHA-256 fingerprint of evidence bytes.
    """
    return hashlib.sha256(
        file_bytes
    ).hexdigest()


def calculate_block_hash(
    block_number,
    event_id,
    evidence_hash,
    timestamp,
    previous_hash,
):
    """
    Return the SHA-256 hash of a blockchain block.
    """

    block_data = {
        "block_number": block_number,
        "event_id": event_id,
        "evidence_hash": evidence_hash,
        "timestamp": timestamp,
        "previous_hash": previous_hash,
    }

    encoded_data = json.dumps(
        block_data,
        sort_keys=True,
    ).encode("utf-8")

    return hashlib.sha256(
        encoded_data
    ).hexdigest()


# =========================================================
# BLOCKCHAIN FILE FUNCTIONS
# =========================================================

def load_blockchain():
    """
    Load the existing blockchain_data.json.

    This function does NOT delete or recreate
    the existing blockchain.
    """

    if not os.path.exists(
        DATA_FILE
    ):
        return []

    try:

        with open(
            DATA_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

        if isinstance(
            data,
            list,
        ):

            return data

        return []

    except (
        json.JSONDecodeError,
        OSError,
    ):

        return []


def save_blockchain(
    blockchain
):
    """
    Save the blockchain to blockchain_data.json.
    """

    with open(
        DATA_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            blockchain,
            file,
            indent=4,
            ensure_ascii=False,
        )


# =========================================================
# AUTOMATIC EVIDENCE SECURITY
# =========================================================

def automatically_secure_evidence(
    file_bytes,
    filename,
    event_type="Intrusion Detected",
    location="Border Zone A",
    source_filename=None,
):
    """
    Secure new evidence by:

    1. Calculating SHA-256.
    2. Storing the evidence image.
    3. Creating a blockchain block.
    4. Linking it to the previous block.
    """

    os.makedirs(
        SECURED_DIR,
        exist_ok=True,
    )

    blockchain = load_blockchain()

    block_number = (
        len(blockchain) + 1
    )

    event_id = (
        f"EVT{block_number:03d}"
    )

    # -----------------------------------------------------
    # EVIDENCE HASH
    # -----------------------------------------------------

    evidence_hash = calculate_hash(
        file_bytes
    )

    # -----------------------------------------------------
    # SECURED FILE
    # -----------------------------------------------------

    safe_filename = os.path.basename(
        filename
    )

    stored_filename = (
        f"{event_id}_{safe_filename}"
    )

    evidence_path = os.path.join(
        SECURED_DIR,
        stored_filename,
    )

    with open(
        evidence_path,
        "wb",
    ) as file:

        file.write(
            file_bytes
        )

    # -----------------------------------------------------
    # TIMESTAMP
    # -----------------------------------------------------

    timestamp = datetime.now().strftime(
        "%d %B %Y, %I:%M %p"
    )

    # -----------------------------------------------------
    # PREVIOUS BLOCK HASH
    # -----------------------------------------------------

    if not blockchain:

        previous_hash = "0" * 64

    else:

        previous_hash = blockchain[-1].get(
            "block_hash",
            "0" * 64,
        )

    # -----------------------------------------------------
    # CURRENT BLOCK HASH
    # -----------------------------------------------------

    block_hash = calculate_block_hash(
        block_number,
        event_id,
        evidence_hash,
        timestamp,
        previous_hash,
    )

    # -----------------------------------------------------
    # BLOCK
    # -----------------------------------------------------

    new_block = {
        "block_number": block_number,

        "event_id": event_id,

        "event_type": event_type,

        "location": location,

        "filename": stored_filename,

        "source_filename": (
            os.path.basename(
                source_filename
            )
            if source_filename
            else safe_filename
        ),

        "file_size": len(
            file_bytes
        ),

        "evidence_hash": evidence_hash,

        "timestamp": timestamp,

        "previous_hash": previous_hash,

        "block_hash": block_hash,

        "status": "Secured",
    }

    # -----------------------------------------------------
    # SAVE BLOCK
    # -----------------------------------------------------

    blockchain.append(
        new_block
    )

    save_blockchain(
        blockchain
    )

    return new_block
def secure_intrusion_alert(
    image_bytes,
    filename,
    location="Unknown"
):
    """
    Called by the backend whenever an intrusion alert is detected.

    This function:
    1. Stores the evidence image.
    2. Calculates SHA-256 hash.
    3. Creates a new blockchain block.
    4. Links it with the previous block.
    5. Saves the updated blockchain.
    """

    return automatically_secure_evidence(
        file_bytes=image_bytes,
        filename=filename,
        event_type="Intrusion Detected",
        location=location,
        source_filename=filename,
    )

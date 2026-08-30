import os
import streamlit as st
import hashlib
import json
from datetime import datetime


# =========================================================
# PAGE SETTINGS
# =========================================================
st.set_page_config(
    page_title="BorderGuard",
    page_icon="B",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# =========================================================
# CUSTOM DESIGN
# =========================================================
st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=Manrope:wght@400;500;600;700&display=swap');


/* =========================================================
   GLOBAL
========================================================= */

.stApp {
    background: #F6F0EA;
    color: #332724 !important;
    font-family: 'Manrope', sans-serif;
}

.block-container {
    max-width: 1250px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

#MainMenu {
    visibility: hidden;
}

footer {
    visibility: hidden;
}

header {
    background: transparent !important;
}


/* =========================================================
   HERO SECTION
========================================================= */

.hero {
    background: linear-gradient(120deg, #542535, #7A3A4A);
    border-radius: 24px;
    padding: 2.8rem 3.2rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 14px 35px rgba(84, 37, 53, 0.16);
    position: relative;
    overflow: hidden;
}

.hero:after {
    content: "";
    position: absolute;
    width: 260px;
    height: 260px;
    right: -70px;
    top: -100px;
    border-radius: 50%;
    border: 1px solid rgba(255, 255, 255, 0.12);
}

.hero:before {
    content: "";
    position: absolute;
    width: 180px;
    height: 180px;
    right: 90px;
    bottom: -120px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.04);
}

.hero-title {
    font-family: 'Cormorant Garamond', serif !important;
    color: #FFF9F4 !important;
    font-size: 3.8rem;
    font-weight: 700;
    line-height: 1;
    position: relative;
    z-index: 2;
}

.hero-subtitle {
    font-family: 'Manrope', sans-serif !important;
    color: #F1DCD5 !important;
    font-size: 1rem;
    margin-top: 0.8rem;
    position: relative;
    z-index: 2;
}


/* =========================================================
   OVERVIEW CARDS
========================================================= */

.overview-card {
    background: #FFFDF9;
    border: 1px solid #E2D5CD;
    border-radius: 16px;
    padding: 1.2rem 1.4rem;
    min-height: 125px;
    box-shadow: 0 5px 18px rgba(60, 35, 30, 0.04);
}

.overview-number {
    font-family: 'Cormorant Garamond', serif !important;
    font-size: 2.2rem;
    font-weight: 700;
    color: #6B2E40 !important;
    line-height: 1;
}

.overview-title {
    color: #4D3934 !important;
    font-weight: 700;
    font-size: 0.9rem;
    margin-top: 0.6rem;
}

.overview-text {
    color: #786963 !important;
    font-size: 0.78rem;
    margin-top: 0.25rem;
    line-height: 1.5;
}


/* =========================================================
   HEADINGS
========================================================= */

h1, h2, h3 {
    font-family: 'Cormorant Garamond', serif !important;
    color: #4A2630 !important;
}

h2 {
    font-size: 2.25rem !important;
    font-weight: 700 !important;
    margin-bottom: 0.25rem !important;
}

h3 {
    font-size: 1.45rem !important;
}


/* =========================================================
   TABS
========================================================= */

.stTabs {
    margin-top: 1.5rem;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 2.2rem;
    border-bottom: 1px solid #DCCFC7;
}

.stTabs [data-baseweb="tab"] {
    color: #776762 !important;
    font-family: 'Manrope', sans-serif !important;
    font-size: 0.9rem;
    font-weight: 600;
    padding: 0.9rem 0.2rem;
}

.stTabs [aria-selected="true"] {
    color: #6B2E40 !important;
    border-bottom: 3px solid #6B2E40 !important;
}


/* =========================================================
   TEXT & CAPTIONS
========================================================= */

.stApp [data-testid="stMarkdownContainer"] p {
    color: #5D4C47 !important;
    font-family: 'Manrope', sans-serif !important;
    line-height: 1.65;
}

.stCaption,
[data-testid="stCaptionContainer"] {
    color: #786963 !important;
}


/* =========================================================
   FORM INPUTS
========================================================= */

.stTextInput label,
.stFileUploader label {
    color: #4A3934 !important;
    font-weight: 700 !important;
}

.stTextInput input {
    background: #FFFDF9 !important;
    color: #332724 !important;
    border: 1px solid #D8C8C0 !important;
    border-radius: 10px !important;
    min-height: 45px;
}

.stTextInput input:focus {
    border-color: #6B2E40 !important;
    box-shadow: 0 0 0 1px #6B2E40 !important;
}


/* =========================================================
   FILE UPLOADER
========================================================= */

[data-testid="stFileUploader"] {
    background: #FFFDF9;
    border: 1px dashed #BFA59C;
    border-radius: 14px;
    padding: 0.9rem;
}


/* =========================================================
   BUTTONS
========================================================= */

.stButton > button {
    background: #6B2E40 !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 9px !important;
    padding: 0.65rem 1.5rem !important;
    font-family: 'Manrope', sans-serif !important;
    font-weight: 700 !important;
}

.stButton > button * {
    color: #FFFFFF !important;
}

.stButton > button:hover,
.stButton > button:hover * {
    background: #4F2030 !important;
    color: #FFFFFF !important;
}


/* =========================================================
   STREAMLIT INFORMATION CONTAINERS
========================================================= */

[data-testid="stVerticalBlockBorderWrapper"] {
    background: #FFFDF9 !important;
    border: 1px solid #E1D5CD !important;
    border-radius: 16px !important;
    padding: 0.7rem 1rem !important;
    box-shadow: 0 8px 20px rgba(70, 35, 40, 0.05);
}

[data-testid="stVerticalBlockBorderWrapper"] h3 {
    color: #5A2634 !important;
}


/* =========================================================
   WORKFLOW CARD
========================================================= */

.workflow {
    background: #EFE2DA;
    border-radius: 18px;
    padding: 1.4rem 1.6rem;
    margin-top: 2rem;
    border: 1px solid #E0CEC4;
}

.workflow-title {
    font-family: 'Cormorant Garamond', serif !important;
    color: #5A2634 !important;
    font-size: 1.5rem;
    font-weight: 700;
    margin-bottom: 0.4rem;
}

.workflow-text {
    color: #5D4C47 !important;
    font-size: 0.9rem;
}


/* =========================================================
   BLOCKCHAIN AUDIT CARDS
========================================================= */

.block-card {
    background: #FFFDF9;
    border: 1px solid #E1D6CF;
    border-radius: 16px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 0.5rem;
    border-left: 5px solid #7A3447;
    box-shadow: 0 5px 18px rgba(60, 35, 30, 0.04);
}

.block-number {
    font-size: 0.78rem;
    font-weight: 700;
    color: #8A7770 !important;
    text-transform: uppercase;
    letter-spacing: 0.7px;
}

.block-event {
    color: #4D202D !important;
    font-size: 1.2rem;
    font-weight: 700;
    margin-top: 0.3rem;
}

.block-details {
    color: #756660 !important;
    margin-top: 0.5rem;
    line-height: 1.7;
}

.chain-link {
    text-align: center;
    color: #7A3447 !important;
    font-size: 1.6rem;
    margin: 0.15rem 0 0.35rem 0;
}


/* =========================================================
   ALERTS
========================================================= */

[data-testid="stAlert"] {
    border-radius: 12px !important;
}

[data-testid="stAlert"] * {
    color: #382A27 !important;
    font-family: 'Manrope', sans-serif !important;
    font-weight: 600;
}


/* =========================================================
   CODE BLOCKS & DIVIDERS
========================================================= */

[data-testid="stCodeBlock"] {
    border-radius: 10px;
}

hr {
    border-color: #DED1CA !important;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# HASH FUNCTIONS
# =========================================================
def calculate_hash(file_bytes):
    """Creates a SHA-256 fingerprint of the evidence file."""
    return hashlib.sha256(file_bytes).hexdigest()


def calculate_block_hash(
    block_number,
    event_id,
    evidence_hash,
    timestamp,
    previous_hash
):
    """Creates the cryptographic hash for a blockchain block."""

    block_data = {
        "block_number": block_number,
        "event_id": event_id,
        "evidence_hash": evidence_hash,
        "timestamp": timestamp,
        "previous_hash": previous_hash
    }

    encoded_data = json.dumps(
        block_data,
        sort_keys=True
    ).encode()

    return hashlib.sha256(encoded_data).hexdigest()


def validate_blockchain():
    """
    Checks whether every block is intact and correctly linked
    to the previous block.
    """

    blockchain = st.session_state.blockchain

    if len(blockchain) == 0:
        return False, "There are no evidence blocks to validate yet."

    for index, block in enumerate(blockchain):

        # Recalculate this block's hash using its original data
        recalculated_hash = calculate_block_hash(
            block["block_number"],
            block["event_id"],
            block["evidence_hash"],
            block["timestamp"],
            block["previous_hash"]
        )

        # Check whether the block's data has been modified
        if recalculated_hash != block["block_hash"]:
            return False, (
                f"Block #{block['block_number']} has been modified."
            )

        # Check whether the block is correctly connected
        # to the previous block
        if index == 0:
            if block["previous_hash"] != "0" * 64:
                return False, "The Genesis Block has an invalid previous hash."
        else:
            previous_block = blockchain[index - 1]

            if block["previous_hash"] != previous_block["block_hash"]:
                return False, (
                    f"Block #{block['block_number']} is not correctly "
                    "linked to the previous block."
                )

    return True, "All blocks are cryptographically intact."

# =========================================================
# PERSISTENT BLOCKCHAIN STORAGE
# =========================================================

DATA_FILE = "blockchain_data.json"


def load_blockchain():
    """Loads previously secured blockchain records from storage."""

    if not os.path.exists(DATA_FILE):
        return []

    try:
        with open(DATA_FILE, "r") as file:
            return json.load(file)

    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_blockchain():
    """Saves the current blockchain permanently to storage."""

    with open(DATA_FILE, "w") as file:
        json.dump(
            st.session_state.blockchain,
            file,
            indent=4
        )
# =========================================================
# EVIDENCE SECURITY CERTIFICATE
# =========================================================

def generate_certificate(block):
    """Creates a downloadable evidence security certificate."""

    certificate = f"""
============================================================
                    BORDERGUARD
             EVIDENCE SECURITY CERTIFICATE
============================================================

CERTIFICATE STATUS: SECURED

Event ID: {block['event_id']}
Block Number: #{block['block_number']}
Evidence File: {block['filename']}
File Size: {block['file_size'] / 1024:.1f} KB
Secured On: {block['timestamp']}

------------------------------------------------------------
CRYPTOGRAPHIC EVIDENCE FINGERPRINT (SHA-256)
------------------------------------------------------------

{block['evidence_hash']}

------------------------------------------------------------
BLOCKCHAIN RECORD
------------------------------------------------------------

Previous Block Hash:
{block['previous_hash']}

Current Block Hash:
{block['block_hash']}

------------------------------------------------------------

This certificate confirms that the evidence file listed above was
registered with BorderGuard and assigned a cryptographic SHA-256
fingerprint. Any modification to the original file will produce a
different fingerprint during integrity verification.

============================================================
                BORDERGUARD SECURITY PLATFORM
============================================================
"""

    return certificate
# =========================================================
# SESSION STORAGE — BLOCKCHAIN
# =========================================================
if "blockchain" not in st.session_state:
    st.session_state.blockchain = load_blockchain()

if "evidence_records" not in st.session_state:
    st.session_state.evidence_records = {}
    for block in st.session_state.blockchain:
        st.session_state.evidence_records[
            block["event_id"]
        ] = block


# =========================================================
# HEADER
# =========================================================
st.markdown("""
<div class="hero">
    <div class="hero-title">BorderGuard</div>
    <div class="hero-subtitle">
        Blockchain-Based Evidence Security & Integrity Platform
    </div>
</div>
""", unsafe_allow_html=True)


# =========================================================
# PLATFORM OVERVIEW
# =========================================================
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div class="overview-card">
        <div class="overview-number">01</div>
        <div class="overview-title">Secure</div>
        <div class="overview-text">
            Create a unique digital fingerprint for CCTV evidence.
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="overview-card">
        <div class="overview-number">02</div>
        <div class="overview-title">Verify</div>
        <div class="overview-text">
            Detect modifications by comparing evidence fingerprints.
        </div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="overview-card">
        <div class="overview-number">03</div>
        <div class="overview-title">Record</div>
        <div class="overview-text">
            Link each evidence record to create a traceable audit chain.
        </div>
    </div>
    """, unsafe_allow_html=True)


# =========================================================
# LIVE SECURITY DASHBOARD
# =========================================================
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("## Security Overview")

total_blocks = len(st.session_state.blockchain)
total_evidence = len(st.session_state.evidence_records)

if total_blocks == 0:
    chain_status = "Waiting for Records"
    chain_symbol = "—"
else:
    is_valid, _ = validate_blockchain()
    chain_status = "Chain Intact" if is_valid else "Integrity Failed"
    chain_symbol = "✓" if is_valid else "!"


dash1, dash2, dash3, dash4 = st.columns(4)

with dash1:
    st.markdown(f"""
    <div class="overview-card">
        <div class="overview-number">{total_blocks}</div>
        <div class="overview-title">Evidence Blocks</div>
        <div class="overview-text">
            Blockchain records secured in this session.
        </div>
    </div>
    """, unsafe_allow_html=True)

with dash2:
    st.markdown(f"""
    <div class="overview-card">
        <div class="overview-number">{total_evidence}</div>
        <div class="overview-title">Evidence Records</div>
        <div class="overview-text">
            Unique evidence items registered securely.
        </div>
    </div>
    """, unsafe_allow_html=True)

with dash3:
    st.markdown(f"""
    <div class="overview-card">
        <div class="overview-number">{chain_symbol}</div>
        <div class="overview-title">{chain_status}</div>
        <div class="overview-text">
            Cryptographic blockchain integrity status.
        </div>
    </div>
    """, unsafe_allow_html=True)

with dash4:
    st.markdown("""
    <div class="overview-card">
        <div class="overview-number">SHA</div>
        <div class="overview-title">SHA-256 Security</div>
        <div class="overview-text">
            Cryptographic fingerprints protect every record.
        </div>
    </div>
    """, unsafe_allow_html=True)


# =========================================================
# TABS
# =========================================================
register_tab, verify_tab, audit_tab = st.tabs([
    "Secure Evidence",
    "Verify Evidence",
    "Security Audit Trail"
])


# =========================================================
# TAB 1 — SECURE EVIDENCE
# =========================================================
with register_tab:

    st.header("Secure New Evidence")
    st.write(
        "Create a unique SHA-256 fingerprint for your evidence and "
        "secure it inside a blockchain-linked integrity record."
    )

    event_id = st.text_input(
        "Event ID",
        placeholder="Example: EVT001"
    )

    uploaded_file = st.file_uploader(
        "Upload Evidence",
        type=["jpg", "jpeg", "png"],
        key="register"
    )

    if uploaded_file is not None:

        left_col, right_col = st.columns([1.1, 1])

        with left_col:
            st.image(
                uploaded_file,
                caption="Evidence Preview",
                width=500
            )

        with right_col:
            with st.container(border=True):
                st.markdown("### Evidence Details")
                st.write(f"**File name:** {uploaded_file.name}")
                st.write(
                    f"**File size:** {uploaded_file.size / 1024:.1f} KB"
                )
                st.caption(
                    "The exact contents of this file will be converted into "
                    "a unique SHA-256 fingerprint for integrity verification."
                )

        st.markdown("""
        <div class="workflow">
            <div class="workflow-title">How blockchain protection works</div>
            <div class="workflow-text">
                Your evidence receives a unique SHA-256 fingerprint and is
                stored inside a new block. Each block is cryptographically
                linked to the previous block, creating a traceable chain of
                evidence records.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.write("")

        if st.button("Secure Evidence Record"):

            if event_id.strip() == "":
                st.error("Please enter an Event ID before continuing.")

            elif event_id in st.session_state.evidence_records:
                st.error(
                    "This Event ID already exists. Please use a unique Event ID."
                )

            else:
                file_bytes = uploaded_file.getvalue()
                evidence_hash = calculate_hash(file_bytes)

                block_number = len(st.session_state.blockchain) + 1

                timestamp = datetime.now().strftime(
                    "%d %B %Y, %I:%M %p"
                )

                if len(st.session_state.blockchain) == 0:
                    previous_hash = "0" * 64
                else:
                    previous_hash = (
                        st.session_state.blockchain[-1]["block_hash"]
                    )

                block_hash = calculate_block_hash(
                    block_number,
                    event_id,
                    evidence_hash,
                    timestamp,
                    previous_hash
                )

                new_block = {
                    "block_number": block_number,
                    "event_id": event_id,
                    "filename": uploaded_file.name,
                    "file_size": uploaded_file.size,
                    "evidence_hash": evidence_hash,
                    "timestamp": timestamp,
                    "previous_hash": previous_hash,
                    "block_hash": block_hash,
                    "status": "Secured"
                }

                st.session_state.blockchain.append(new_block)
                st.session_state.evidence_records[event_id] = new_block
                # Permanently save the updated blockchain.
                save_blockchain()
                st.success(
                    f"Evidence secured successfully in Block #{block_number}."
                )

                st.markdown("### Evidence Fingerprint")
                st.code(evidence_hash)

                st.info(
                    "Any change made to this file will generate a different "
                    "fingerprint during verification."
                )
                # Generate and offer the Evidence Security Certificate.
                certificate = generate_certificate(new_block)

                st.download_button(
                    label="Download Evidence Security Certificate",
                    data=certificate,
                    file_name=f"BorderGuard_Certificate_{event_id}.txt",
                    mime="text/plain"
                )


# =========================================================
# TAB 2 — VERIFY EVIDENCE
# =========================================================
with verify_tab:

    st.header("Verify Evidence Integrity")
    st.write(
        "Upload an evidence file and compare its fingerprint with "
        "the original secured record."
    )

    verify_event_id = st.text_input(
        "Event ID",
        placeholder="Example: EVT001",
        key="verify_event"
    )

    verify_file = st.file_uploader(
        "Upload Evidence for Verification",
        type=["jpg", "jpeg", "png"],
        key="verify"
    )

    if verify_file is not None:

        left_col, right_col = st.columns([1.1, 1])

        with left_col:
            st.image(
                verify_file,
                caption="Evidence Submitted for Verification",
                width=500
            )

        with right_col:
            with st.container(border=True):
                st.markdown("### Verification Process")
                st.write(
                    "A new fingerprint will be generated from the uploaded "
                    "file and compared with the original secured record."
                )
                st.caption(
                    "If both fingerprints match, the evidence is authentic. "
                    "Any difference indicates that the file has been modified."
                )

        st.write("")

        if st.button("Verify Evidence Integrity"):

            if verify_event_id not in st.session_state.evidence_records:

                st.error(
                    "No secured evidence record was found for this Event ID."
                )

            else:
                current_hash = calculate_hash(
                    verify_file.getvalue()
                )

                original_hash = (
                    st.session_state.evidence_records[
                        verify_event_id
                    ]["evidence_hash"]
                )

                if current_hash == original_hash:
                    st.success(
                        "AUTHENTIC EVIDENCE — The file matches the original "
                        "secured record."
                    )
                else:
                    st.error(
                        "TAMPERING DETECTED — The submitted file does not "
                        "match the original evidence record."
                    )

                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("### Submitted File Hash")
                    st.code(current_hash)

                with col2:
                    st.markdown("### Original Record Hash")
                    st.code(original_hash)


# =========================================================
# TAB 3 — SECURITY AUDIT TRAIL
# =========================================================
with audit_tab:

    st.header("Blockchain Security Audit Trail")
    st.write(
        "Each evidence record is stored as a block and linked "
        "cryptographically to the block before it."
    )
        # =========================================================
    # SECURITY DEMO — TAMPERING SIMULATION
    # =========================================================
    if len(st.session_state.blockchain) > 0:

        st.markdown("### Security Demonstration")
        st.caption(
            "Demonstrate how BorderGuard detects unauthorized modifications "
            "to a blockchain record."
        )

        demo_col1, demo_col2 = st.columns(2)

        with demo_col1:
            if st.button(
                "⚠️ Simulate Tampering (Demo)",
                key="simulate_tampering"
            ):
                # Modify only the in-memory blockchain.
                # The saved JSON file remains unchanged.
                st.session_state.blockchain[0]["event_id"] = (
                    "TAMPERED_RECORD"
                )

                # Keep evidence_records consistent with the modified
                # in-memory block for the demonstration.
                st.session_state.evidence_records = {
                    block["event_id"]: block
                    for block in st.session_state.blockchain
                }

                st.warning(
                    "DEMO ATTACK SIMULATED — A blockchain record has been "
                    "modified. Run blockchain validation to detect it."
                )

        with demo_col2:
            if st.button(
                "Restore Secure Blockchain",
                key="restore_blockchain"
            ):
                # Reload the original data from permanent storage.
                st.session_state.blockchain = load_blockchain()

                st.session_state.evidence_records = {
                    block["event_id"]: block
                    for block in st.session_state.blockchain
                }

                st.success(
                    "Original blockchain restored successfully."
                )
                st.rerun()

        st.divider()
    # =========================================================
    # DOWNLOAD BLOCKCHAIN AUDIT REPORT
    # =========================================================

    if len(st.session_state.blockchain) == 0:

        st.info("No evidence records have been secured yet.")

    else:

        # Create the audit report
        is_valid, _ = validate_blockchain()

        audit_report = {
            "platform": "BorderGuard",
            "report_type": "Blockchain Security Audit Report",
            "generated_on": datetime.now().strftime(
                "%d %B %Y, %I:%M %p"
            ),
            "total_evidence_blocks": len(
                st.session_state.blockchain
            ),
            "blockchain_integrity": (
                "Valid" if is_valid else "Integrity Failed"
            ),
            "blocks": st.session_state.blockchain
        }

        audit_report_json = json.dumps(
            audit_report,
            indent=4
        )

        # Download button
        st.download_button(
            label="Download Blockchain Audit Report",
            data=audit_report_json,
            file_name="BorderGuard_Blockchain_Audit_Report.json",
            mime="application/json"
        )

        st.caption(
            "Download a complete cryptographic record of all evidence "
            "blocks secured in BorderGuard."
        )

        st.divider()

        # Blockchain status
        st.success(
            f"Blockchain active — {len(st.session_state.blockchain)} "
            f"evidence block(s) secured successfully."
        )

        # Validate blockchain
        if st.button(
            "Validate Blockchain Integrity",
            key="validate_blockchain_button"
        ):

            is_valid, message = validate_blockchain()

            if is_valid:
                st.success(
                    "BLOCKCHAIN VERIFIED — " + message
                )
            else:
                st.error(
                    "BLOCKCHAIN INTEGRITY FAILED — " + message
                )

        # =====================================================
        # DISPLAY BLOCKCHAIN RECORDS
        # =====================================================

        for index, block in enumerate(st.session_state.blockchain):

            st.markdown(
                f"""
                <div class="block-card">
                    <div class="block-number">
                        BLOCK #{block['block_number']}
                    </div>
                    <div class="block-event">
                        Event ID: {block['event_id']}
                    </div>
                    <div class="block-details">
                        Status: {block['status']}<br>
                        Evidence: {block['filename']}<br>
                        Secured: {block['timestamp']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            with st.expander(
                f"View cryptographic details for "
                f"Block #{block['block_number']}"
            ):
                st.write("**Evidence SHA-256 Hash**")
                st.code(block["evidence_hash"])

                st.write("**Previous Block Hash**")
                st.code(block["previous_hash"])

                st.write("**Current Block Hash**")
                st.code(block["block_hash"])

            # Visual connection between consecutive blocks
            if index < len(st.session_state.blockchain) - 1:
                st.markdown(
                    '<div class="chain-link">↓ ⛓ ↓</div>',
                    unsafe_allow_html=True
                )
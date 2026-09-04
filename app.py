import os
import json
import html
from datetime import datetime
import streamlit as st
print("RUNNING APP FROM:", os.path.abspath(__file__))
from evidence_manager import (
    load_blockchain,
    calculate_hash,
    calculate_block_hash,
)


# =========================================================
# PAGE SETTINGS
# =========================================================

st.set_page_config(
    page_title="BorderGuard",
    page_icon="B",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =========================================================
# PATHS
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EVIDENCE_DIR = os.path.join(BASE_DIR, "evidence_storage")

DATA_FILE = os.path.join(BASE_DIR, "blockchain_data.json")

# =========================================================
# DESIGN
# =========================================================

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');

    /* =========================
       MAIN PAGE
       ========================= */

    .stApp {
        background: #F4F8FC;
        color: #172B4D !important;
        font-family: 'Manrope', sans-serif;
    }

    .block-container {
        max-width: 1250px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    #MainMenu,
    footer {
        visibility: hidden;
    }

    header {
        background: transparent !important;
    }


    /* =========================
       HEADINGS
       ========================= */

    h1, h2, h3 {
        font-family: 'Manrope', sans-serif !important;
        color: #123B66 !important;
        font-weight: 800 !important;
    }

    h1 {
        font-size: 3rem !important;
    }

    h2 {
        font-size: 2.25rem !important;
    }

    h3 {
        font-size: 1.45rem !important;
    }

    .stApp [data-testid="stMarkdownContainer"] p {
        color: #52677F !important;
        font-family: 'Manrope', sans-serif !important;
        line-height: 1.65;
    }


    /* =========================
       BORDERGUARD HEADER
       ========================= */

    .borderguard-header {
        background: linear-gradient(
            135deg,
            #092B4C,
            #124D7A,
            #176B9E
        );

        border-radius: 24px;
        padding: 2.8rem 3.2rem;
        margin-bottom: 1.5rem;

        box-shadow:
            0 14px 35px rgba(9, 43, 76, 0.20);
    }

    .borderguard-title {
        font-family: 'Manrope', sans-serif;
        color: #FFFFFF;
        font-size: 3.6rem;
        font-weight: 800;
        line-height: 1;
        letter-spacing: -1px;
    }

    .borderguard-subtitle {
        font-family: 'Manrope', sans-serif;
        color: #D8ECFA;
        font-size: 1rem;
        margin-top: 0.8rem;
    }


    /* =========================
       METRIC CARDS
       ========================= */

    [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #D7E5F0;
        border-radius: 16px;
        padding: 1rem;

        box-shadow:
            0 5px 18px rgba(20, 65, 100, 0.07);
    }

    [data-testid="stMetricValue"] {
        color: #12679B !important;
        font-family: 'Manrope', sans-serif !important;
        font-weight: 800 !important;
    }

    [data-testid="stMetricLabel"] {
        color: #244A6A !important;
        font-family: 'Manrope', sans-serif !important;
        font-weight: 700;
    }


    /* =========================
       BUTTONS
       ========================= */

    .stButton > button {
        background: #125B8A !important;
        color: #FFFFFF !important;

        border: none !important;
        border-radius: 9px !important;

        padding: 0.65rem 1.5rem !important;

        font-family: 'Manrope', sans-serif !important;
        font-weight: 700 !important;

        box-shadow:
            0 4px 10px rgba(18, 91, 138, 0.15);
    }

    .stButton > button:hover {
        background: #0A4168 !important;
        color: #FFFFFF !important;
    }


    /* =========================
       FILE UPLOADER
       ========================= */

    [data-testid="stFileUploader"] {
        background: #FFFFFF;
        border: 1px dashed #7EAAC7;
        border-radius: 14px;
        padding: 0.9rem;
    }


    /* =========================
       BLOCK CARDS
       ========================= */

    [data-testid="stVerticalBlockBorderWrapper"] {
        background: #FFFFFF !important;

        border: 1px solid #D5E3EE !important;
        border-left: 5px solid #176B9E !important;

        border-radius: 16px !important;

        box-shadow:
            0 5px 18px rgba(20, 65, 100, 0.06);
    }


    /* =========================
       EVENT ID BADGE
       ========================= */

    .event-id-box {
        display: inline-block;

        background: #E8F4FC;

        border: 2px solid #2379AA;

        border-radius: 8px;

        padding: 0.35rem 0.8rem;

        margin: 0.35rem 0 0.8rem 0;

        color: #0B4D78;

        font-family: 'Manrope', sans-serif;

        font-size: 1.05rem;

        font-weight: 800;

        letter-spacing: 0.4px;

        box-shadow:
            0 2px 7px rgba(35, 121, 170, 0.10);
    }


    /* =========================
       SMALL LABEL
       ========================= */

    .small-label {
        color: #6B8196;

        font-size: 0.78rem;

        font-weight: 700;

        text-transform: uppercase;

        letter-spacing: 0.7px;
    }


    /* =========================
       EVENT TITLE
       ========================= */

    .event-title {
        color: #123B66;

        font-size: 1.2rem;

        font-weight: 700;

        margin-top: 0.25rem;
    }


    /* =========================
       SECTION CARD
       ========================= */

    .section-card {
        background: #FFFFFF;

        border: 1px solid #D5E3EE;

        border-left: 5px solid #176B9E;

        border-radius: 16px;

        padding: 1.2rem 1.5rem;

        margin-bottom: 1rem;

        box-shadow:
            0 5px 18px rgba(20, 65, 100, 0.06);
    }


    /* =========================
       CHAIN ARROW
       ========================= */

    .chain-arrow {
        text-align: center;

        color: #176B9E;

        font-size: 1.7rem;

        font-weight: 700;

        margin: 0.3rem 0 0.6rem 0;
    }


    /* =========================
       EXPANDER
       ========================= */

    [data-testid="stExpander"] {
        background: #F8FBFE !important;

        border: 1px solid #D4E3EE !important;

        border-radius: 10px !important;
    }


    /* =========================
       TABS
       ========================= */

    button[data-baseweb="tab"] {
        color: #46647D !important;

        font-family: 'Manrope', sans-serif !important;

        font-weight: 700 !important;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        color: #0E5D8D !important;
    }


    /* =========================
       SUCCESS MESSAGE
       ========================= */

    [data-testid="stAlert"] {
        border-radius: 10px;
    }


    /* =========================
       CODE / HASH BOX
       ========================= */

    [data-testid="stCodeBlock"] {
        border-radius: 10px !important;
    }

    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# LOAD BLOCKCHAIN
# =========================================================

blockchain = load_blockchain()


# =========================================================
# BLOCKCHAIN VALIDATION
# =========================================================

def validate_blockchain(blockchain):
    if not blockchain:
        return False, "There are no evidence blocks."

    for index, block in enumerate(blockchain):
        required = [
            "block_number",
            "event_id",
            "evidence_hash",
            "timestamp",
            "previous_hash",
            "block_hash",
        ]

        missing = [key for key in required if key not in block]

        if missing:
            return (
                False,
                f"Block #{index + 1} is missing: {', '.join(missing)}.",
            )

        try:
            recalculated_hash = calculate_block_hash(
                block["block_number"],
                block["event_id"],
                block["evidence_hash"],
                block["timestamp"],
                block["previous_hash"],
            )
        except Exception as exc:
            return (
                False,
                f"Could not recalculate Block #{block['block_number']}: {exc}",
            )

        if recalculated_hash != block["block_hash"]:
            return (
                False,
                f"Block #{block['block_number']} has been modified.",
            )

        if index == 0:
            if block["previous_hash"] != "0" * 64:
                return (
                    False,
                    "The Genesis Block has an invalid previous hash.",
                )
        else:
            previous_block = blockchain[index - 1]

            if block["previous_hash"] != previous_block.get("block_hash"):
                return (
                    False,
                    f"Block #{block['block_number']} is not correctly linked.",
                )

    return True, "All blocks are cryptographically intact."


# =========================================================
# FIND EVIDENCE IMAGE
# =========================================================

def find_evidence_file(block):
    possible_names = [
        block.get("filename"),
        block.get("source_filename"),
    ]

    for name in possible_names:
        if not name:
            continue

        safe_name = os.path.basename(str(name))

        candidates = [
            os.path.join(EVIDENCE_DIR, safe_name),
            os.path.join(EVIDENCE_DIR, "secured", safe_name),
            os.path.join(EVIDENCE_DIR, "incoming", safe_name),
            os.path.join(BASE_DIR, safe_name),
        ]

        for path in candidates:
            if os.path.isfile(path):
                return path

    return None


# =========================================================
# HEADER
# =========================================================

st.markdown(
    """
    <div style="
        background: linear-gradient(120deg, #0B1F3A, #123E6A);
        border-radius: 24px;
        padding: 2.8rem 3.2rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 14px 35px rgba(11, 31, 58, 0.20);
    ">
        <div style="
            font-family: 'Cormorant Garamond', serif;
            color: #FFFFFF;
            font-size: 3.8rem;
            font-weight: 700;
            line-height: 1;
        ">
            BorderGuard
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
# PLATFORM OVERVIEW
# =========================================================

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Secure", "01", "Evidence protection")

with col2:
    st.metric("Verify", "02", "SHA-256 verification")

with col3:
    st.metric("Record", "03", "Linked audit trail")


# =========================================================
# SECURITY OVERVIEW
# =========================================================

st.markdown("<br>", unsafe_allow_html=True)
st.header("Security Overview")

total_blocks = len(blockchain)
total_evidence = len(blockchain)

if total_blocks == 0:
    chain_valid = False
    chain_status = "Waiting for Records"
else:
    chain_valid, validation_message = validate_blockchain(blockchain)
    chain_status = "Chain Intact" if chain_valid else "Integrity Failed"

overview_col1, overview_col2, overview_col3, overview_col4 = st.columns(4)

with overview_col1:
    st.metric("Evidence Blocks", total_blocks)

with overview_col2:
    st.metric("Evidence Records", total_evidence)

with overview_col3:
    st.metric("Blockchain Status", chain_status)

with overview_col4:
    st.metric("Security", "SHA-256")


# =========================================================
# MAIN TABS
# =========================================================

officer_tab, audit_tab = st.tabs(
    [
        "Officer Panel",
        "Security Audit Trail",
    ]
)


# =========================================================
# OFFICER PANEL
# =========================================================

with officer_tab:

    st.header("Officer Panel")

    st.write(
        "Monitor intrusion alerts, access secured evidence and "
        "verify evidence integrity."
    )

    intrusion_blocks = [
        block
        for block in blockchain
        if block.get("event_type", "Intrusion Detected")
        == "Intrusion Detected"
    ]

    if not intrusion_blocks:

        st.info("No active intrusion alerts.")

    else:

        st.subheader("Intrusion Alerts")

        alert_options = [
            block.get("event_id", "")
            for block in intrusion_blocks
        ]

        selected_event = st.selectbox(
            "Select Alert",
            alert_options,
            index=len(alert_options) - 1,
            key="selected_alert",
        )

        selected_block = next(
            block
            for block in intrusion_blocks
            if block.get("event_id") == selected_event
        )

        st.markdown(
            f"""
            <div class="section-card">
                <div class="small-label">Intrusion Alert</div>
                <div class="event-title">
                    {html.escape(str(selected_event))}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.subheader("Alert Details")

        detail_col1, detail_col2 = st.columns(2)

        with detail_col1:
            st.write(
                f"**Event:** "
                f"{selected_block.get('event_type', 'Intrusion Detected')}"
            )
            st.write(
                f"**Location:** "
                f"{selected_block.get('location', 'Unknown')}"
            )

        with detail_col2:
            st.write(
                f"**Time:** "
                f"{selected_block.get('timestamp', 'Unknown')}"
            )

            display_filename = os.path.basename(
                str(
                    selected_block.get(
                        "source_filename",
                        selected_block.get("filename", "Unknown"),
                    )
                )
            )

            st.write(f"**Evidence:** {display_filename}")

        st.divider()

        st.subheader("Secured Evidence")

        evidence_path = find_evidence_file(selected_block)

        if evidence_path:

            evidence_col1, evidence_col2 = st.columns([1.1, 1])

            with evidence_col1:
                st.image(
                    evidence_path,
                    caption="Automatically Secured Evidence",
                    width=500,
                )

            with evidence_col2:
                st.write("**Evidence automatically stored in BorderGuard.**")
                st.write(f"**File:** {display_filename}")

                file_size = selected_block.get(
                    "file_size",
                    os.path.getsize(evidence_path),
                )

                st.write(f"**Size:** {file_size / 1024:.1f} KB")

                with open(evidence_path, "rb") as file:
                    evidence_bytes = file.read()

                st.download_button(
                    "Download Evidence",
                    data=evidence_bytes,
                    file_name=display_filename,
                    key=f"download_{selected_event}",
                )

        else:
            st.warning(
                "The blockchain record exists, but the corresponding "
                "evidence image could not be found."
            )

        st.divider()

        st.subheader("Evidence Integrity Verification")

        st.write(
            "Upload the evidence received by the officer. "
            "BorderGuard calculates its SHA-256 fingerprint and "
            "compares it with the fingerprint stored in the blockchain."
        )

        officer_file = st.file_uploader(
            "Upload Evidence for Verification",
            type=["jpg", "jpeg", "png"],
            key=f"officer_verify_{selected_event}",
        )

        if officer_file is not None:

            current_hash = calculate_hash(
                officer_file.getvalue()
            )

            original_hash = str(
                selected_block.get("evidence_hash", "")
            )

            st.subheader("Hash Comparison")

            hash_col1, hash_col2 = st.columns(2)

            with hash_col1:
                st.write("**Officer Evidence Hash**")
                st.code(current_hash, language="text")

            with hash_col2:
                st.write("**Blockchain Hash**")
                st.code(original_hash, language="text")

            if current_hash == original_hash:
                st.success(
                    "AUTHENTIC EVIDENCE — Hashes match. "
                    "No modification detected."
                )
            else:
                st.error(
                    "TAMPERING DETECTED — Hashes do not match."
                )


# =========================================================
# SECURITY AUDIT TRAIL
# =========================================================

with audit_tab:

    st.header("Blockchain Security Audit Trail")

    st.write(
        "Each evidence record is stored as a block and linked "
        "cryptographically to the block before it."
    )

    if not blockchain:

        st.info("No evidence records have been secured yet.")

    else:

        is_valid, message = validate_blockchain(blockchain)

        if is_valid:
            st.success(
                "BLOCKCHAIN VERIFIED — " + message
            )
        else:
            st.error(
                "BLOCKCHAIN INTEGRITY FAILED — " + message
            )

        st.divider()

        for index, block in enumerate(blockchain):

            block_number = block.get(
                "block_number",
                index + 1,
            )

            event_id = block.get(
                "event_id",
                f"EVT{block_number:03d}",
            )

            status = block.get(
                "status",
                "Secured",
            )

            filename = os.path.basename(
                str(
                    block.get(
                        "source_filename",
                        block.get("filename", "Unknown"),
                    )
                )
            )

            timestamp = block.get(
                "timestamp",
                "Unknown",
            )

            # =====================================================
            # BLOCK CARD
            # =====================================================

            with st.container(border=True):

                st.caption(f"BLOCK #{block_number}")

                st.markdown(
                    f"""
                    <div class="event-id-box">
                        Event ID: {html.escape(str(event_id))}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.write(
                    f"**Status:** {status}"
                )

                st.write(
                    f"**Evidence:** {filename}"
                )

                st.write(
                    f"**Secured:** {timestamp}"
                )

                # =================================================
                # CRYPTOGRAPHIC DETAILS
                # =================================================

                with st.expander(
                    f"View cryptographic details for Block #{block_number}"
                ):

                    evidence_hash = str(
                        block.get(
                            "evidence_hash",
                            "Not available"
                        )
                    )

                    previous_hash = str(
                        block.get(
                            "previous_hash",
                            "Not available"
                        )
                    )

                    current_block_hash = str(
                        block.get(
                            "block_hash",
                            "Not available"
                        )
                    )

                    st.write("**Evidence SHA-256 Hash**")
                    st.code(
                        evidence_hash,
                        language="text"
                    )

                    st.write("**Previous Block Hash**")
                    st.code(
                        previous_hash,
                        language="text"
                    )

                    st.write("**Current Block Hash**")
                    st.code(
                        current_block_hash,
                        language="text"
                    )

            # =====================================================
            # CHAIN CONNECTION
            # =====================================================

            if index < len(blockchain) - 1:
                st.markdown(
                    "<div style='text-align:center; "
                    "font-size:24px;'>↓</div>",
                    unsafe_allow_html=True,
                )

        st.divider()

        audit_report = {
            "platform": "BorderGuard",
            "report_type": "Blockchain Security Audit Report",
            "generated_on": datetime.now().strftime(
                "%d %B %Y, %I:%M %p"
            ),
            "total_evidence_blocks": len(blockchain),
            "blockchain_integrity": (
                "Valid"
                if is_valid
                else "Integrity Failed"
            ),
            "blocks": blockchain,
        }

        audit_report_json = json.dumps(
            audit_report,
            indent=4,
        )

        st.download_button(
            label="Download Blockchain Audit Report",
            data=audit_report_json,
            file_name="BorderGuard_Blockchain_Audit_Report.json",
            mime="application/json",
            key="download_audit_report",
        )

        st.caption(
            "Download a complete cryptographic record of all evidence blocks "
            "secured in BorderGuard."
        )

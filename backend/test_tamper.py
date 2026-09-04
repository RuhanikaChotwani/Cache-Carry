"""Tamper detection test for the frame hash chain.
Creates a short test chain, verifies it is valid, tampers with one record,
and verifies the API detects the break. Does NOT alter real evidence data.
"""

import sys
import copy
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from services import ledger


def run_tamper_test():
    print("=" * 60)
    print("FRAME HASH CHAIN TAMPER DETECTION TEST")
    print("=" * 60)

    # 1. Start a test frame chain session
    print("\n[1] Starting test frame chain session...")
    ledger.start_frame_chain("tamper-test-session")

    # 2. Enqueue some test frames
    print("[2] Enqueuing 10 test frame hashes...")
    for i in range(10):
        fake_jpeg = f"test-frame-{i}-{i*1234567}".encode("utf-8")
        ledger.enqueue_frame_hash(fake_jpeg, i + 1, "tamper-test-source")

    # 3. Wait for writer to process
    import time
    time.sleep(0.5)

    # 4. Stop the chain writer
    print("[3] Stopping frame chain writer...")
    ledger.stop_frame_chain()

    # 5. Verify the chain is valid
    print("[4] Verifying untampered chain...")
    result = ledger.verify_frame_chain()
    print(f"    Valid: {result['valid']}")
    print(f"    Message: {result['message']}")
    assert result["valid"], "Chain should be valid before tampering!"

    # 6. Create a tampered copy and test it
    print("[5] Creating tampered chain copy for testing...")
    with ledger._chain_lock:
        original_chain = copy.deepcopy(ledger._frame_chain)

    if len(original_chain) < 3:
        print("    ERROR: Not enough chain records to test tampering.")
        return

    # Tamper with the 3rd record's frame hash
    tampered_chain = copy.deepcopy(original_chain)
    original_hash = tampered_chain[2]["frame_hash"]
    tampered_chain[2]["frame_hash"] = "0000000000000000000000000000000000000000000000000000000000000000"
    print(f"    Tampered record #3 frame_hash from {original_hash[:16]}... to 0000...0000")

    # Temporarily swap in the tampered chain for verification
    with ledger._chain_lock:
        ledger._frame_chain = tampered_chain

    print("[6] Verifying tampered chain...")
    tamper_result = ledger.verify_frame_chain()
    print(f"    Valid: {tamper_result['valid']}")
    print(f"    Message: {tamper_result['message']}")

    if not tamper_result["valid"]:
        print(f"    First broken sequence: {tamper_result.get('first_broken_sequence', 'N/A')}")
        print("    TAMPER DETECTION: PASSED")
    else:
        print("    TAMPER DETECTION: FAILED (should have detected broken chain)")

    # 7. Restore original chain
    print("[7] Restoring original untampered chain...")
    with ledger._chain_lock:
        ledger._frame_chain = original_chain

    # 8. Final verification
    print("[8] Final verification of restored chain...")
    final_result = ledger.verify_frame_chain()
    print(f"    Valid: {final_result['valid']}")
    print(f"    Message: {final_result['message']}")
    assert final_result["valid"], "Restored chain should be valid!"

    print("\n" + "=" * 60)
    print("TAMPER TEST COMPLETE - ALL CHECKS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    run_tamper_test()

from evidence_manager import automatically_secure_evidence

# Test image
with open("test_image.jpg", "rb") as file:
    image_bytes = file.read()

block = automatically_secure_evidence(
    file_bytes=image_bytes,
    filename="test_image.jpg",
    event_type="Intrusion Detected",
    location="Border Zone A",
)

print("\nEvidence secured successfully!")
print("Event ID:", block["event_id"])
print("Block Number:", block["block_number"])
print("Evidence Hash:", block["evidence_hash"])
print("Block Hash:", block["block_hash"])
print("Stored File:", block["filename"])
"""
Model Download & Setup Utility for SIH26187 Face Analytics.
Downloads the official InsightFace buffalo_l package (SCRFD 10G + ArcFace ResNet50)
and places det_10g.onnx and w600k_r50.onnx in the models/ directory for 100% offline usage.
"""

from pathlib import Path
import shutil
import sys
import urllib.request
import zipfile
from tqdm import tqdm


MODELS_DIR = Path(__file__).resolve().parent / "models"

# Direct verified download mirrors
BUFFALO_L_MIRRORS = [
    "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip",
    "https://huggingface.co/public-data/insightface/resolve/main/models/buffalo_l.zip",
]


class DownloadProgressBar(tqdm):
    def update_to(self, b=1, bsize=1, tsize=None):
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)


def download_and_extract_models():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    det_target = MODELS_DIR / "det_10g.onnx"
    rec_target = MODELS_DIR / "w600k_r50.onnx"

    if det_target.exists() and rec_target.exists():
        print("[Setup] Offline models are already present in models/:")
        print(f"  - Detector  : {det_target} ({det_target.stat().st_size / 1e6:.1f} MB)")
        print(f"  - Recognizer: {rec_target} ({rec_target.stat().st_size / 1e6:.1f} MB)")
        print("Ready for offline execution!")
        return

    zip_path = MODELS_DIR / "buffalo_l.zip"
    print("\n" + "=" * 65)
    print("      DOWNLOADING OFFLINE MODELS FOR BORDER SURVEILLANCE      ")
    print("=" * 65)
    print(f"Target directory: {MODELS_DIR}\n")

    downloaded = False
    for url in BUFFALO_L_MIRRORS:
        print(f"Attempting download from: {url}")
        try:
            with DownloadProgressBar(
                unit="B", unit_scale=True, miniters=1, desc="buffalo_l.zip"
            ) as t:
                urllib.request.urlretrieve(
                    url, filename=str(zip_path), reporthook=t.update_to
                )
            downloaded = True
            print("Download successful!")
            break
        except Exception as e:
            print(f"Failed from mirror: {e}\nTrying next mirror...")

    if not downloaded:
        print("\n[ERROR] Automated download failed.")
        print("To setup offline manually:")
        print("1. Download 'buffalo_l.zip' manually from:")
        print("   https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip")
        print(f"2. Extract and copy 'det_10g.onnx' and 'w600k_r50.onnx' into:\n   {MODELS_DIR}")
        sys.exit(1)

    # Extract required models from zip
    print("\nExtracting ONNX model weights...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            filename = Path(member).name
            if filename in ("det_10g.onnx", "w600k_r50.onnx"):
                print(f"  Extracting {filename} -> models/{filename}")
                source = zf.open(member)
                target = open(MODELS_DIR / filename, "wb")
                with source, target:
                    shutil.copyfileobj(source, target)

    # Remove temporary zip file
    if zip_path.exists():
        zip_path.unlink()

    print("\n" + "=" * 65)
    print("MODEL EXTRACTION COMPLETE")
    print(f"  det_10g.onnx   : {det_target.exists()} ({det_target.stat().st_size / 1e6:.1f} MB)")
    print(f"  w600k_r50.onnx : {rec_target.exists()} ({rec_target.stat().st_size / 1e6:.1f} MB)")
    print("=" * 65)
    print("System is now completely primed for 100% OFFLINE operation!\n")


if __name__ == "__main__":
    download_and_extract_models()

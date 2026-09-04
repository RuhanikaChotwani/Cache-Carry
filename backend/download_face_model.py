import urllib.request, os

models_dir = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(models_dir, exist_ok=True)
onnx_target = os.path.join(models_dir, "opencv_face_detector.onnx")

urls = [
    "https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20180423_res10_300x300_ssd_iter_140000/opencv_face_detector.onnx",
    "https://huggingface.co/opencv/face_detector/resolve/main/opencv_face_detector.onnx"
]

for url in urls:
    try:
        print(f"Downloading from {url}...")
        urllib.request.urlretrieve(url, onnx_target)
        if os.path.exists(onnx_target) and os.path.getsize(onnx_target) > 100000:
            print(f"Success! Model saved at {onnx_target} ({os.path.getsize(onnx_target)} bytes)")
            break
    except Exception as e:
        print(f"Failed: {e}")

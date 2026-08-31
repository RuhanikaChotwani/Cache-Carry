"""
Offline Face Recognition Module using ArcFace ResNet-50 via ONNX Runtime.

Extracts 512-dimensional L2-normalized feature embeddings from aligned
112x112 facial images.
"""

from pathlib import Path
from typing import List, Union
import cv2
import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    ort = None


class ArcFaceRecognizer:
    """
    Offline ArcFace feature extraction engine.
    """

    def __init__(
        self,
        model_path: str | Path,
        use_cuda: bool = True,
        cuda_device_id: int = 0,
    ):
        if ort is None:
            raise ImportError(
                "onnxruntime is required. Install onnxruntime-gpu or onnxruntime."
            )

        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"ArcFace recognizer model not found at: {self.model_path}\n"
                "Please download w600k_r50.onnx into the models/ folder."
            )

        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )

        # Probe CUDA runtime DLLs to avoid ONNX Runtime error 126 on Windows
        providers = []
        cuda_ready = False
        if use_cuda and "CUDAExecutionProvider" in ort.get_available_providers():
            try:
                import ctypes
                for dll in ("cudart64_12.dll", "cudart64_11.dll"):
                    try:
                        ctypes.CDLL(dll)
                        cuda_ready = True
                        break
                    except OSError:
                        pass
            except Exception:
                cuda_ready = False

            if cuda_ready:
                providers.append(
                    (
                        "CUDAExecutionProvider",
                        {
                            "device_id": cuda_device_id,
                            "arena_extend_strategy": "kNextPowerOfTwo",
                            "gpu_mem_limit": 2 * 1024 * 1024 * 1024,
                        },
                    )
                )
            else:
                print("[Recognizer] CUDA runtime (cudart64_12.dll) not detected in PATH. Defaulting to CPUExecutionProvider.")

        providers.append("CPUExecutionProvider")

        print(f"[Recognizer] Initializing ArcFace session with provider: {providers[0] if isinstance(providers[0], str) else providers[0][0]}")
        self.session = ort.InferenceSession(
            str(self.model_path), sess_options, providers=providers
        )

        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        input_shape = self.session.get_inputs()[0].shape
        self.input_size = (112, 112)

    def preprocess(self, face_imgs: Union[np.ndarray, List[np.ndarray]]) -> np.ndarray:
        """
        Preprocesses aligned 112x112 BGR face image(s) into NCHW RGB normalized tensor.
        Normalized to [-1.0, 1.0]: (x - 127.5) / 127.5
        """
        if isinstance(face_imgs, np.ndarray) and face_imgs.ndim == 3:
            face_imgs = [face_imgs]

        batch_tensors = []
        for img in face_imgs:
            if img.shape[:2] != self.input_size:
                img = cv2.resize(img, self.input_size, interpolation=cv2.INTER_LINEAR)

            # BGR to RGB
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            # Normalize to [-1, 1]
            norm = (rgb.astype(np.float32) - 127.5) / 127.5
            # HWC to CHW
            chw = np.transpose(norm, (2, 0, 1))
            batch_tensors.append(chw)

        blob = np.stack(batch_tensors, axis=0).astype(np.float32)
        return blob

    def extract_embedding(
        self, face_imgs: Union[np.ndarray, List[np.ndarray]]
    ) -> np.ndarray:
        """
        Extracts 512-dimensional L2-normalized feature embeddings.

        Args:
            face_imgs: Single (112, 112, 3) BGR image or list/array of images.

        Returns:
            Embeddings of shape (N, 512), where each row is L2-normalized (||e|| = 1.0).
        """
        is_single = isinstance(face_imgs, np.ndarray) and face_imgs.ndim == 3
        blob = self.preprocess(face_imgs)

        # Run inference
        raw_embeddings = self.session.run([self.output_name], {self.input_name: blob})[0]

        # L2-normalize embeddings: embedding / ||embedding||
        norms = np.linalg.norm(raw_embeddings, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-12)
        normalized_embeddings = raw_embeddings / norms

        if is_single:
            return normalized_embeddings[0]
        return normalized_embeddings

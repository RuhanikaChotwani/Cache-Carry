"""
Offline Face Detection Module using SCRFD (Sample and Computation Redistribution
for Efficient Face Detection) executed via ONNX Runtime.

Predicts face bounding boxes, confidence scores, and 5 canonical facial landmarks
in a single forward pass.
"""

from pathlib import Path
from typing import List, Optional, Tuple
import cv2
import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    ort = None


def distance2bbox(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
    """Decodes distances (l, t, r, b) from anchor center points into [x1, y1, x2, y2]."""
    x1 = points[:, 0] - distance[:, 0]
    y1 = points[:, 1] - distance[:, 1]
    x2 = points[:, 0] + distance[:, 2]
    y2 = points[:, 1] + distance[:, 3]
    return np.stack([x1, y1, x2, y2], axis=-1)


def distance2kps(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
    """Decodes 5-point facial landmarks from anchor center offsets."""
    preds = []
    for i in range(0, distance.shape[1], 2):
        px = points[:, 0] + distance[:, i]
        py = points[:, 1] + distance[:, i + 1]
        preds.append(px)
        preds.append(py)
    return np.stack(preds, axis=-1)


def nms(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float) -> List[int]:
    """Pure numpy Non-Maximum Suppression (NMS)."""
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]

    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]

    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter)

        inds = np.where(ovr <= iou_thresh)[0]
        order = order[inds + 1]

    return keep


def _is_cuda_runtime_available() -> bool:
    """Checks if CUDA runtime DLLs are accessible to avoid Error 126 on Windows."""
    if ort is None or "CUDAExecutionProvider" not in ort.get_available_providers():
        return False
    try:
        import ctypes
        for dll in ("cudart64_12.dll", "cudart64_11.dll"):
            try:
                ctypes.CDLL(dll)
                return True
            except OSError:
                pass
    except Exception:
        pass
    return False


class SCRFDDetector:
    """
    High-performance offline SCRFD face detector.
    Outputs:
        bboxes: array of shape (N, 4) [x1, y1, x2, y2]
        scores: array of shape (N,)
        landmarks: array of shape (N, 5, 2) [5 canonical facial points]
    """

    def __init__(
        self,
        model_path: str | Path,
        conf_threshold: float = 0.5,
        nms_threshold: float = 0.4,
        input_size: Tuple[int, int] = (640, 640),
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
                f"SCRFD detector model not found at: {self.model_path}\n"
                "Please download det_10g.onnx into the models/ folder."
            )

        self.conf_thresh = conf_threshold
        self.nms_thresh = nms_threshold
        self.input_size = input_size
        self.fmc = 3  # Feature map count (3 strides: 8, 16, 32)
        self._feat_stride_fpn = [8, 16, 32]
        self._num_anchors = 2
        self.use_kps = True

        # Configure ONNX Runtime session
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
                            "cudnn_conv_algo_search": "EXHAUSTIVE",
                            "do_copy_in_default_stream": True,
                        },
                    )
                )
            else:
                print("[Detector] CUDA runtime (cudart64_12.dll) not detected in PATH. Defaulting to CPUExecutionProvider.")

        providers.append("CPUExecutionProvider")

        print(f"[Detector] Initializing SCRFD session with provider: {providers[0] if isinstance(providers[0], str) else providers[0][0]}")
        self.session = ort.InferenceSession(
            str(self.model_path), sess_options, providers=providers
        )

        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]

        # Inspect if landmark outputs exist
        if len(self.output_names) == 6:
            self.use_kps = False
        elif len(self.output_names) == 9:
            self.use_kps = True
        elif len(self.output_names) == 10:
            self.use_kps = True
            self._num_anchors = 1
        elif len(self.output_names) == 15:
            self.use_kps = True
            self._num_anchors = 2

    def forward(
        self, img: np.ndarray, thresh: float
    ) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray]]:
        """
        Runs forward pass on preprocessed image tensor.
        """
        scores_list = []
        bboxes_list = []
        kpss_list = []

        input_height, input_width = img.shape[2], img.shape[3]
        net_outs = self.session.run(self.output_names, {self.input_name: img})

        input_shape = (input_height, input_width)

        # Parse outputs
        num_strides = len(self._feat_stride_fpn)
        for idx, stride in enumerate(self._feat_stride_fpn):
            score = net_outs[idx]
            bbox_delta = net_outs[idx + num_strides]
            if self.use_kps:
                kps_delta = net_outs[idx + num_strides * 2]

            height = input_height // stride
            width = input_width // stride
            anchor_centers = np.stack(
                np.mgrid[:height, :width][::-1], axis=-1
            ).astype(np.float32)
            anchor_centers = (anchor_centers * stride).reshape((-1, 2))

            if self._num_anchors > 1:
                anchor_centers = np.stack(
                    [anchor_centers] * self._num_anchors, axis=1
                ).reshape((-1, 2))

            pos_inds = np.where(score >= thresh)[0]
            if len(pos_inds) == 0:
                continue

            bboxes = distance2bbox(anchor_centers, bbox_delta * stride)
            pos_scores = score[pos_inds]
            pos_bboxes = bboxes[pos_inds]

            scores_list.append(pos_scores)
            bboxes_list.append(pos_bboxes)

            if self.use_kps:
                kpss = distance2kps(anchor_centers, kps_delta * stride)
                kpss = kpss.reshape((kpss.shape[0], -1, 2))
                pos_kpss = kpss[pos_inds]
                kpss_list.append(pos_kpss)

        if len(scores_list) == 0:
            return (
                np.zeros((0,), dtype=np.float32),
                np.zeros((0, 4), dtype=np.float32),
                np.zeros((0, 5, 2), dtype=np.float32) if self.use_kps else None,
            )

        scores = np.concatenate(scores_list, axis=0)
        bboxes = np.concatenate(bboxes_list, axis=0)
        kpss = (
            np.concatenate(kpss_list, axis=0)
            if self.use_kps and len(kpss_list) > 0
            else None
        )

        return scores, bboxes, kpss

    def detect(
        self,
        image: np.ndarray,
        max_num: int = 0,
        metric: str = "default",
    ) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray]]:
        """
        Detects faces in BGR image.

        Returns:
            bboxes: (N, 4) [x1, y1, x2, y2]
            scores: (N,)
            landmarks: (N, 5, 2)
        """
        im_ratio = float(image.shape[0]) / image.shape[1]
        model_ratio = float(self.input_size[1]) / self.input_size[0]

        if im_ratio > model_ratio:
            new_height = self.input_size[1]
            new_width = int(new_height / im_ratio)
        else:
            new_width = self.input_size[0]
            new_height = int(new_width * im_ratio)

        det_scale = float(new_height) / image.shape[0]
        resized_img = cv2.resize(image, (new_width, new_height))

        det_img = np.zeros(
            (self.input_size[1], self.input_size[0], 3), dtype=np.uint8
        )
        det_img[:new_height, :new_width, :] = resized_img

        # Preprocessing: convert to float32, normalize, transpose to [1, 3, H, W]
        input_tensor = cv2.dnn.blobFromImage(
            det_img,
            1.0 / 128.0,
            self.input_size,
            (127.5, 127.5, 127.5),
            swapRB=True,
        )

        scores, bboxes, kpss = self.forward(input_tensor, self.conf_thresh)

        if bboxes.shape[0] == 0:
            return (
                np.zeros((0, 4), dtype=np.float32),
                np.zeros((0,), dtype=np.float32),
                np.zeros((0, 5, 2), dtype=np.float32) if self.use_kps else None,
            )

        # Rescale coordinates to original image
        bboxes = bboxes / det_scale
        if kpss is not None:
            kpss = kpss / det_scale

        # Apply Non-Maximum Suppression (NMS)
        scores = scores.flatten()
        keep = nms(bboxes, scores, self.nms_thresh)
        bboxes = bboxes[keep]
        scores = scores[keep]
        if kpss is not None:
            kpss = kpss[keep]

        # Limit to max_num if specified
        if max_num > 0 and bboxes.shape[0] > max_num:
            if metric == "max":
                area = (bboxes[:, 2] - bboxes[:, 0]) * (
                    bboxes[:, 3] - bboxes[:, 1]
                )
                order = np.argsort(area)[::-1][:max_num]
            else:
                order = np.argsort(scores)[::-1][:max_num]
            bboxes = bboxes[order]
            scores = scores[order]
            if kpss is not None:
                kpss = kpss[order]

        return bboxes, scores, kpss


class PersonDetector:
    """
    Offline Person/Body Detector for long-range surveillance tracking.
    Uses YOLOv8 (either via ONNX Runtime or ultralytics YOLO).
    Detects class 0 ('person') bounding boxes.
    """

    def __init__(
        self,
        model_path: str = "models/yolov8n.onnx",
        conf_threshold: float = 0.40,
        nms_threshold: float = 0.45,
        use_cuda: bool = True,
        cuda_device_id: int = 0,
    ):
        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold
        self.model_path = Path(model_path)
        self.use_cuda = use_cuda
        self.cuda_device_id = cuda_device_id
        self.session = None
        self.yolo_model = None

        if self.model_path.exists() and self.model_path.suffix.lower() == ".onnx":
            providers = []
            if use_cuda and _is_cuda_runtime_available():
                providers.append(
                    (
                        "CUDAExecutionProvider",
                        {"device_id": cuda_device_id, "arena_extend_strategy": "kNextPowerOfTwo"},
                    )
                )
            providers.append("CPUExecutionProvider")
            self.session = ort.InferenceSession(str(self.model_path), providers=providers)
            self.input_name = self.session.get_inputs()[0].name
            self.input_shape = self.session.get_inputs()[0].shape
        else:
            try:
                from ultralytics import YOLO
                pt_path = self.model_path.with_suffix(".pt")
                self.yolo_model = YOLO(str(pt_path) if pt_path.exists() else "yolov8n.pt")
            except Exception as e:
                print(f"[PersonDetector] Running in adaptive body mode: {e}")

    def detect(self, image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Detects person bodies in BGR image.
        Returns:
            bboxes: (N, 4) [x1, y1, x2, y2]
            scores: (N,)
        """
        if self.yolo_model is not None:
            try:
                results = self.yolo_model(image, classes=[0], conf=self.conf_threshold, verbose=False)
                if results and len(results) > 0:
                    boxes = results[0].boxes
                    if len(boxes) > 0:
                        xyxy = boxes.xyxy.cpu().numpy()
                        confs = boxes.conf.cpu().numpy()
                        return xyxy.astype(np.float32), confs.astype(np.float32)
                return np.zeros((0, 4), dtype=np.float32), np.zeros((0,), dtype=np.float32)
            except Exception:
                pass

        if self.session is not None:
            h, w = image.shape[:2]
            det_img = cv2.resize(image, (640, 640))
            blob = cv2.dnn.blobFromImage(det_img, 1.0 / 255.0, (640, 640), swapRB=True)
            preds = self.session.run(None, {self.input_name: blob})[0]
            preds = np.transpose(preds[0], (1, 0))  # [8400, 84]
            boxes_raw = preds[:, :4]
            person_scores = preds[:, 4]  # class 0 is person
            mask = person_scores > self.conf_threshold
            boxes_filtered = boxes_raw[mask]
            scores_filtered = person_scores[mask]
            if len(scores_filtered) == 0:
                return np.zeros((0, 4), dtype=np.float32), np.zeros((0,), dtype=np.float32)

            scale_x = w / 640.0
            scale_y = h / 640.0
            x1 = (boxes_filtered[:, 0] - boxes_filtered[:, 2] / 2.0) * scale_x
            y1 = (boxes_filtered[:, 1] - boxes_filtered[:, 3] / 2.0) * scale_y
            x2 = (boxes_filtered[:, 0] + boxes_filtered[:, 2] / 2.0) * scale_x
            y2 = (boxes_filtered[:, 1] + boxes_filtered[:, 3] / 2.0) * scale_y
            boxes_xyxy = np.stack([x1, y1, x2, y2], axis=-1).astype(np.float32)

            keep = nms(boxes_xyxy, scores_filtered, self.nms_threshold)
            return boxes_xyxy[keep], scores_filtered[keep]

        return np.zeros((0, 4), dtype=np.float32), np.zeros((0,), dtype=np.float32)


from __future__ import annotations

import os
from typing import Any, Dict, Optional, Set

import numpy as np

from src.camera_rig import FramePair
from src.perception.hailo_runner import HailoSharedVDevice, HailoSyncInferencer
from src.perception.heads.base import PerceptionHead
from src.perception.types import SegmentationOutput


def _postprocess_seg_logits(tensor: np.ndarray) -> np.ndarray:
    """Convert network output to H×W label indices (NCHW or NHWC logits, or argmax map)."""
    x = np.asarray(tensor)
    if x.ndim == 4:
        x = x[0]
    if x.ndim == 3:
        c_first = x.shape[0]
        c_last = x.shape[-1]
        if c_last > 1 and c_last <= 128 and c_last >= c_first:
            return np.argmax(x, axis=-1).astype(np.uint8)
        if c_first > 1 and c_first <= 128 and c_first < min(x.shape[1], x.shape[2]):
            return np.argmax(x, axis=0).astype(np.uint8)
    if x.ndim == 2:
        return x.astype(np.uint8)
    return np.argmax(x, axis=-1).astype(np.uint8)


class SegmentationStdc1Head(PerceptionHead):
    name = "segmentation"

    def __init__(
        self,
        hef_path: str,
        input_height: int,
        input_width: int,
        stream_interface: str = "integrated",
        device_id_index: int = 0,
        hailo_shared: Optional[HailoSharedVDevice] = None,
    ):
        self.hef_path = hef_path
        self.input_height = input_height
        self.input_width = input_width
        self._stream_interface = stream_interface
        self._device_id_index = device_id_index
        self._hailo_shared = hailo_shared
        self._infer: HailoSyncInferencer | None = None

    def required_inputs(self) -> Set[str]:
        return {"left_bgr"}

    def setup(self) -> None:
        if not self.hef_path or not os.path.isfile(self.hef_path):
            raise FileNotFoundError(f"STDC1 HEF not found: {self.hef_path}")
        vd = self._hailo_shared.ensure_open() if self._hailo_shared else None
        self._infer = HailoSyncInferencer(
            self.hef_path,
            stream_interface=self._stream_interface,
            device_id_index=self._device_id_index,
            vdevice=vd,
        )
        self._infer.open()

    def teardown(self) -> None:
        if self._infer:
            self._infer.close()
            self._infer = None

    def run(self, ctx: Dict[str, Any], frame: FramePair) -> SegmentationOutput:
        del frame
        import cv2

        if self._infer is None:
            raise RuntimeError("SegmentationStdc1Head not setup()")
        img = ctx["left_bgr"]
        h0, w0 = img.shape[:2]
        resized = cv2.resize(img, (self.input_width, self.input_height), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        in_name = self._infer.input_names[0]
        outs = self._infer.infer({in_name: rgb})
        out_name = self._infer.output_names[0]
        raw = outs[out_name]
        labels_small = _postprocess_seg_logits(raw)
        labels = cv2.resize(labels_small, (w0, h0), interpolation=cv2.INTER_NEAREST)
        return SegmentationOutput(
            labels=labels,
            source_size_hw=(h0, w0),
            model_name="stdc1",
            extra={"hef": self.hef_path},
        )

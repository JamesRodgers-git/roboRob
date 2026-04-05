from __future__ import annotations

import os
from typing import Any, Dict, List, Set

import numpy as np

from src.camera_rig import FramePair
from src.perception.hailo_runner import HailoSyncInferencer
from src.perception.heads.base import PerceptionHead
from src.perception.types import DepthOutput


def _postprocess_disparity(tensor: np.ndarray) -> np.ndarray:
    x = np.asarray(tensor, dtype=np.float32)
    if x.ndim == 4:
        x = x[0]
    if x.ndim == 3:
        if x.shape[0] == 1 or x.shape[-1] == 1:
            x = x.squeeze()
        else:
            x = np.mean(x, axis=-1)
    return x.astype(np.float32)


class StereoStereonetHead(PerceptionHead):
    name = "stereo"

    def __init__(self, hef_path: str, input_height: int, input_width: int):
        self.hef_path = hef_path
        self.input_height = input_height
        self.input_width = input_width
        self._infer: HailoSyncInferencer | None = None

    def required_inputs(self) -> Set[str]:
        return {"left_bgr", "right_bgr"}

    def setup(self) -> None:
        if not self.hef_path or not os.path.isfile(self.hef_path):
            raise FileNotFoundError(f"Stereonet HEF not found: {self.hef_path}")
        self._infer = HailoSyncInferencer(self.hef_path, use_pcie=True)
        self._infer.open()

    def teardown(self) -> None:
        if self._infer:
            self._infer.close()
            self._infer = None

    def _build_inputs(self, left: np.ndarray, right: np.ndarray) -> Dict[str, np.ndarray]:
        import cv2

        if self._infer is None:
            raise RuntimeError("StereoStereonetHead not setup()")
        names: List[str] = self._infer.input_names
        l = cv2.resize(left, (self.input_width, self.input_height), interpolation=cv2.INTER_LINEAR)
        r = cv2.resize(right, (self.input_width, self.input_height), interpolation=cv2.INTER_LINEAR)
        l = cv2.cvtColor(l, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        r = cv2.cvtColor(r, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        if len(names) == 1:
            if l.shape == r.shape:
                stacked = np.concatenate([l, r], axis=-1)
                return {names[0]: stacked}
            return {names[0]: l}
        if len(names) >= 2:
            ordered = sorted(names)
            return {ordered[0]: l, ordered[1]: r}
        return {names[0]: l}

    def run(self, ctx: Dict[str, Any], frame: FramePair) -> DepthOutput:
        del frame
        import cv2

        left = ctx["left_bgr"]
        right = ctx["right_bgr"]
        h0, w0 = left.shape[:2]
        feed = self._build_inputs(left, right)
        assert self._infer is not None
        outs = self._infer.infer(feed)
        out_name = self._infer.output_names[0]
        disp_small = _postprocess_disparity(outs[out_name])
        disp = cv2.resize(disp_small, (w0, h0), interpolation=cv2.INTER_LINEAR)
        return DepthOutput(
            data=disp,
            kind="disparity",
            source_size_hw=(h0, w0),
            model_name="stereonet",
            extra={"hef": self.hef_path},
        )

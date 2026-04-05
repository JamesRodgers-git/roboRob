from __future__ import annotations

from typing import Any, Dict, Set

import numpy as np

from src.camera_rig import FramePair
from src.perception.heads.base import PerceptionHead
from src.perception.types import SegmentationOutput


class StubSegmentationHead(PerceptionHead):
    """Synthetic Cityscapes-like labels for testing without Hailo."""

    name = "segmentation"

    def required_inputs(self) -> Set[str]:
        return {"left_bgr"}

    def run(self, ctx: Dict[str, Any], frame: FramePair) -> SegmentationOutput:
        del frame
        img = ctx["left_bgr"]
        h, w = img.shape[:2]
        labels = np.zeros((h, w), dtype=np.uint8)  # road
        labels[: h // 3] = 10  # sky
        labels[h // 3 : 2 * h // 3] = 8  # vegetation band
        return SegmentationOutput(labels=labels, source_size_hw=(h, w), model_name="stub-seg")

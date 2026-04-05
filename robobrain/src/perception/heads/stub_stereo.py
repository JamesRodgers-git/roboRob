from __future__ import annotations

from typing import Any, Dict, Set

import numpy as np

from src.camera_rig import FramePair
from src.perception.heads.base import PerceptionHead
from src.perception.types import DepthOutput


class StubStereoHead(PerceptionHead):
    """Smooth synthetic disparity map for fusion testing."""

    name = "stereo"

    def required_inputs(self) -> Set[str]:
        return {"left_bgr", "right_bgr"}

    def run(self, ctx: Dict[str, Any], frame: FramePair) -> DepthOutput:
        del frame
        left = ctx["left_bgr"]
        h, w = left.shape[:2]
        u = np.linspace(0.0, 1.0, w, dtype=np.float32)
        v = np.linspace(0.0, 1.0, h, dtype=np.float32)
        disp = 32.0 + 8.0 * np.outer(v, np.ones_like(u)) + 2.0 * np.outer(np.ones_like(v), u)
        return DepthOutput(
            data=disp,
            kind="disparity",
            source_size_hw=(h, w),
            model_name="stub-stereo",
        )

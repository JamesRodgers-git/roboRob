"""
Future: object / person detection head.

To add:
  1. Subclass PerceptionHead with a unique `name` (e.g. "detection").
  2. Implement `run()` returning `DetectionOutput` and store via pipeline into `ctx["heads"][name]`.
  3. Register the head in `PerceptionPipeline.from_config` (append to `heads` list after stereo).
  4. Extend `TraversabilityFusion.fuse(..., detections=...)` to lower traversability under boxes
     or mark dynamic obstacles (see `DetectionOutput` in `src/perception/types.py`).
"""

from __future__ import annotations

from typing import Any, Dict, Set

from src.camera_rig import FramePair
from src.perception.heads.base import PerceptionHead


class DetectionPlaceholderHead(PerceptionHead):
    """Not registered by default; copy and implement when adding a Hailo detection HEF."""

    name = "detection"

    def required_inputs(self) -> Set[str]:
        return {"left_bgr"}

    def run(self, ctx: Dict[str, Any], frame: FramePair) -> None:
        raise NotImplementedError("Implement detection inference and return DetectionOutput")

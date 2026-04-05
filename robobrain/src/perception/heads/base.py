from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Set

from src.camera_rig import FramePair


class PerceptionHead(ABC):
    """One model / postprocess unit; registered on PerceptionPipeline."""

    name: str = "head"

    def required_inputs(self) -> Set[str]:
        """Keys this head reads from the working dict (e.g. 'frame_rectified')."""
        return set()

    def setup(self) -> None:
        """Open device resources."""

    def teardown(self) -> None:
        """Release resources."""

    @abstractmethod
    def run(self, ctx: Dict[str, Any], frame: FramePair) -> Any:
        """Read from ctx, write result under ctx['heads'][self.name]."""

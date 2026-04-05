from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class SegmentationOutput:
    """Semantic label map H×W, uint8 or int; values are Cityscapes train IDs unless noted."""
    labels: np.ndarray  # shape (H, W)
    source_size_hw: tuple[int, int]
    model_name: str = "stdc1"
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DepthOutput:
    """Disparity or inverse depth; higher often = closer depending on model postprocess."""
    data: np.ndarray  # shape (H, W) float32
    kind: str = "disparity"  # "disparity" | "depth"
    source_size_hw: tuple[int, int] = (0, 0)
    model_name: str = "stereonet"
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectionOutput:
    """Future: bounding boxes for fusion (person / object)."""
    boxes_xyxy: np.ndarray  # (N, 4)
    class_ids: np.ndarray  # (N,)
    scores: np.ndarray  # (N,)
    class_names: List[str] = field(default_factory=list)
    model_name: str = "detection"
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TraversabilityMap:
    """Fused traversability scores in [0, 1], same spatial size as stored (may be strided)."""
    scores: np.ndarray  # (H, W) float32
    stride: int = 1
    roi_mask: Optional[np.ndarray] = None  # optional (H, W) bool
    used_depth: bool = False
    mean_score_roi: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerceptionBundle:
    """All head outputs + fused map for one timestamp."""
    timestamp: float
    heads: Dict[str, Any]
    traversability: TraversabilityMap

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

import config as robobrain_config
from src.camera_rig import FramePair
from src.perception.calibration import StereoRectifier
from src.perception.fusion.traversability import TraversabilityFusion, load_cityscapes_weights
from src.perception.heads.base import PerceptionHead
from src.perception.heads.segmentation_stdc1 import SegmentationStdc1Head
from src.perception.heads.stereo_stereonet import StereoStereonetHead
from src.perception.heads.stub_segmentation import StubSegmentationHead
from src.perception.heads.stub_stereo import StubStereoHead
from src.perception.types import DepthOutput, PerceptionBundle, SegmentationOutput, TraversabilityMap

LOGGER = logging.getLogger("robobrain.perception")


def steer_from_map(trav: TraversabilityMap, throttle_gain: float = 0.4, turn_gain: float = 1.2) -> Tuple[float, float]:
    """Simple column voting: higher center score -> throttle; left vs right -> turn."""
    s = trav.scores
    if s.size == 0:
        return 0.0, 0.0
    h, w = s.shape
    third = max(1, w // 3)
    c0, c1, c2 = 0, third, 2 * third
    left_m = float(np.mean(s[:, c0:c1]))
    center_m = float(np.mean(s[:, c1:c2]))
    right_m = float(np.mean(s[:, c2:]))
    turn = (right_m - left_m) * turn_gain
    turn = max(-1.0, min(1.0, turn))
    throttle = max(0.0, min(1.0, center_m * throttle_gain))
    return throttle, turn


class PerceptionPipeline:
    """
    Ordered perception heads + traversability fusion.
    Extend by appending heads (e.g. DetectionHead) and teaching fusion to consume ctx['heads'].
    """

    def __init__(
        self,
        heads: List[PerceptionHead],
        fusion: TraversabilityFusion,
        rectifier: Optional[StereoRectifier] = None,
    ):
        self.heads = heads
        self.fusion = fusion
        self.rectifier = rectifier

    @classmethod
    def from_config(cls, cfg: Any = None) -> "PerceptionPipeline":
        cfg = cfg or robobrain_config
        rectifier: Optional[StereoRectifier] = None
        calib_path = getattr(cfg, "STEREO_CALIB_NPZ_PATH", "") or ""
        if calib_path:
            rectifier = StereoRectifier.from_npz(calib_path)
            LOGGER.info("Loaded stereo calibration from %s", calib_path)

        class_weights = load_cityscapes_weights()
        fusion = TraversabilityFusion(
            class_weights=class_weights,
            stride=getattr(cfg, "TRAV_MAP_STRIDE", 4),
            roi_top_y=getattr(cfg, "TRAV_ROI_TOP_Y_FRAC", 0.35),
            roi_bottom_y=getattr(cfg, "TRAV_ROI_BOTTOM_Y_FRAC", 1.0),
            roi_top_half_w=getattr(cfg, "TRAV_ROI_TOP_HALF_WIDTH_FRAC", 0.15),
            roi_bottom_half_w=getattr(cfg, "TRAV_ROI_BOTTOM_HALF_WIDTH_FRAC", 0.45),
            seg_weight=getattr(cfg, "FUSION_SEG_WEIGHT", 0.7),
            geom_weight=getattr(cfg, "FUSION_GEOM_WEIGHT", 0.3),
            disp_grad_high=getattr(cfg, "FUSION_DISP_GRAD_HIGH", 0.85),
        )

        use_hailo = bool(getattr(cfg, "USE_HAILO", False))
        seg_hef = getattr(cfg, "HAILO_STDC1_HEF", "") or ""
        stereo_hef = getattr(cfg, "HAILO_STEREONET_HEF", "") or ""

        heads: List[PerceptionHead] = []
        if use_hailo and seg_hef:
            heads.append(
                SegmentationStdc1Head(
                    seg_hef,
                    getattr(cfg, "STDC1_INPUT_HEIGHT", 1024),
                    getattr(cfg, "STDC1_INPUT_WIDTH", 1920),
                )
            )
        else:
            heads.append(StubSegmentationHead())

        if use_hailo and stereo_hef:
            heads.append(
                StereoStereonetHead(
                    stereo_hef,
                    getattr(cfg, "STEREONET_INPUT_HEIGHT", 368),
                    getattr(cfg, "STEREONET_INPUT_WIDTH", 1232),
                )
            )
        else:
            heads.append(StubStereoHead())

        pipe = cls(heads=heads, fusion=fusion, rectifier=rectifier)
        return pipe

    def setup(self) -> None:
        for h in self.heads:
            h.setup()

    def teardown(self) -> None:
        for h in reversed(self.heads):
            h.teardown()

    def _rectify_pair(self, left, right):
        if self.rectifier and self.rectifier.is_loaded:
            return self.rectifier.apply(left, right)
        return left, right

    def process(self, frame: FramePair) -> PerceptionBundle:
        left_bgr, right_bgr = self._rectify_pair(frame.left, frame.right)
        ctx: Dict[str, Any] = {
            "left_bgr": left_bgr,
            "right_bgr": right_bgr,
            "timestamp": frame.timestamp,
            "heads": {},
        }
        for h in self.heads:
            missing = h.required_inputs() - ctx.keys()
            if missing:
                LOGGER.warning("Head %s missing ctx keys %s", h.name, missing)
                continue
            try:
                out = h.run(ctx, frame)
            except Exception as exc:
                LOGGER.exception("Head %s failed: %s", h.name, exc)
                continue
            ctx["heads"][h.name] = out

        seg: Optional[SegmentationOutput] = ctx["heads"].get("segmentation")
        depth: Optional[DepthOutput] = ctx["heads"].get("stereo")

        if seg is None:
            h, w = left_bgr.shape[:2]
            seg = SegmentationOutput(
                labels=np.zeros((h, w), dtype=np.uint8),
                source_size_hw=(h, w),
                model_name="fallback",
            )

        trav = self.fusion.fuse(seg, depth, detections=None)
        return PerceptionBundle(timestamp=frame.timestamp, heads=dict(ctx["heads"]), traversability=trav)

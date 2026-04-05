from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Tuple

import numpy as np

from src.perception.types import DepthOutput, SegmentationOutput, TraversabilityMap


def load_cityscapes_weights(json_path: Optional[str] = None) -> Dict[int, float]:
    """Load class_id -> traversability weight [0,1]."""
    if json_path is None:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        json_path = os.path.join(base, "semantic", "cityscapes_traversability.json")
    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {int(k): float(v) for k, v in raw.items()}


def _trapezoid_mask(h: int, w: int, top_y: float, bot_y: float, top_hw: float, bot_hw: float) -> np.ndarray:
    """Boolean mask for bottom-centered trapezoid. Fractions 0-1 of image size."""
    y0 = int(top_y * h)
    y1 = int(bot_y * h)
    y0 = max(0, min(h - 1, y0))
    y1 = max(y0 + 1, min(h, y1))
    mask = np.zeros((h, w), dtype=bool)
    cx = w * 0.5
    for y in range(y0, y1):
        t = (y - y0) / max(1, (y1 - y0))
        half_w = top_hw * w * (1 - t) + bot_hw * w * t
        x0 = int(cx - half_w)
        x1 = int(cx + half_w)
        x0 = max(0, x0)
        x1 = min(w, x1)
        mask[y, x0:x1] = True
    return mask


def _resize_mask_to(mask: np.ndarray, th: int, tw: int) -> np.ndarray:
    if mask.shape[0] == th and mask.shape[1] == tw:
        return mask
    import cv2

    return cv2.resize(mask.astype(np.uint8), (tw, th), interpolation=cv2.INTER_NEAREST).astype(bool)


class TraversabilityFusion:
    def __init__(
        self,
        class_weights: Dict[int, float],
        stride: int = 4,
        roi_top_y: float = 0.35,
        roi_bottom_y: float = 1.0,
        roi_top_half_w: float = 0.15,
        roi_bottom_half_w: float = 0.45,
        seg_weight: float = 0.7,
        geom_weight: float = 0.3,
        disp_grad_high: float = 0.85,
    ):
        self.class_weights = class_weights
        self.stride = max(1, stride)
        self.roi_top_y = roi_top_y
        self.roi_bottom_y = roi_bottom_y
        self.roi_top_half_w = roi_top_half_w
        self.roi_bottom_half_w = roi_bottom_half_w
        self.seg_weight = seg_weight
        self.geom_weight = geom_weight
        self.disp_grad_high = disp_grad_high

    def _labels_to_score(self, labels: np.ndarray) -> np.ndarray:
        h, w = labels.shape
        flat = labels.reshape(-1)
        out = np.zeros_like(flat, dtype=np.float32)
        default_w = self.class_weights.get(255, 0.0)
        for i, lid in enumerate(flat):
            out[i] = float(self.class_weights.get(int(lid), default_w))
        return out.reshape(h, w)

    def _geom_score_from_disparity(self, disp: np.ndarray, roi: np.ndarray) -> Tuple[np.ndarray, bool]:
        """Higher geom score = smoother / safer (low gradient). Returns map same shape as disp."""
        gx = np.gradient(disp.astype(np.float32), axis=1)
        gy = np.gradient(disp.astype(np.float32), axis=0)
        grad_mag = np.sqrt(gx * gx + gy * gy)
        if not np.any(roi):
            return np.ones_like(disp, dtype=np.float32), False
        vals = grad_mag[roi]
        thresh = float(np.percentile(vals, self.disp_grad_high * 100))
        # Normalize: below thresh -> high score, above -> low
        normed = np.clip(grad_mag / max(thresh, 1e-6), 0.0, 1.0)
        geom = 1.0 - normed
        return geom.astype(np.float32), True

    def fuse(
        self,
        seg: SegmentationOutput,
        depth: Optional[DepthOutput],
        detections: Optional[Any] = None,
    ) -> TraversabilityMap:
        """
        Build traversability map from segmentation + optional disparity.
        """
        del detections  # reserved for future DetectionOutput fusion
        labels = seg.labels
        h, w = labels.shape
        seg_score = self._labels_to_score(labels)

        if self.stride > 1:
            import cv2

            nh, nw = max(1, h // self.stride), max(1, w // self.stride)
            seg_score = cv2.resize(seg_score, (nw, nh), interpolation=cv2.INTER_AREA)
        else:
            nh, nw = h, w

        roi = _trapezoid_mask(
            nh,
            nw,
            self.roi_top_y,
            self.roi_bottom_y,
            self.roi_top_half_w,
            self.roi_bottom_half_w,
        )

        used_depth = False
        if depth is not None and depth.data.size > 0:
            disp = depth.data.astype(np.float32)
            if disp.shape[0] != nh or disp.shape[1] != nw:
                import cv2

                disp = cv2.resize(disp, (nw, nh), interpolation=cv2.INTER_LINEAR)
            geom, used_depth = self._geom_score_from_disparity(disp, roi)
            fused = self.seg_weight * seg_score + self.geom_weight * geom
            fused = np.clip(fused, 0.0, 1.0)
        else:
            fused = seg_score

        mean_roi = float(np.mean(fused[roi])) if np.any(roi) else float(np.mean(fused))
        return TraversabilityMap(
            scores=fused.astype(np.float32),
            stride=self.stride,
            roi_mask=roi,
            used_depth=used_depth,
            mean_score_roi=mean_roi,
            extra={"label_shape": (h, w), "downsampled_shape": (nh, nw)},
        )

#!/usr/bin/env python3
"""
Capture one stereo frame, run the same perception stack as brain.py, save images.

Usage (from anywhere):
  python3 tools/pipeline_snapshot.py
  python3 tools/pipeline_snapshot.py --out-dir ./my_run

Uses config.py for cameras, Hailo paths, and fusion settings.

Outputs (under --out-dir, default ./pipeline_snapshot_<unix_ts>):
  00_left_raw.png, 00_right_raw.png  — camera frames
  01_left.png, 01_right.png          — after stereo rectify if calib loaded; else same as raw
  10_segmentation_color.png          — colorized label map
  20_disparity.png                   — stereo/disparity heatmap (if head ran)
  30_traversability.png              — fused score map [0,1] as color
  31_traversability_overlay.png     — scores overlaid on left + ROI polygon
  meta.json                          — model names, ROI mean, flags
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
os.chdir(_REPO_ROOT)

import cv2

import config
from src.camera_rig import DualCameraRig
from src.perception.pipeline import PerceptionPipeline
from src.perception.types import DepthOutput, SegmentationOutput, TraversabilityMap

LOGGER = logging.getLogger("robobrain.snapshot")


def _colorize_segmentation(labels: np.ndarray) -> np.ndarray:
    """Stable pseudo-color for arbitrary label ids (BGR)."""
    h = ((labels.astype(np.uint32) * 47 + labels.astype(np.uint32) * 13) % 180).astype(np.uint8)
    s = np.full_like(h, 220, dtype=np.uint8)
    v = np.where(labels > 0, 255, 120).astype(np.uint8)
    hsv = np.stack([h, s, v], axis=-1)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def _colorize_disparity(disp: np.ndarray) -> np.ndarray:
    d = disp.astype(np.float32)
    d = d - np.nanmin(d)
    mx = float(np.nanmax(d)) or 1.0
    u8 = np.clip(d / mx * 255.0, 0, 255).astype(np.uint8)
    return cv2.applyColorMap(u8, cv2.COLORMAP_INFERNO)


def _colorize_scores(scores: np.ndarray) -> np.ndarray:
    u8 = np.clip(scores * 255.0, 0, 255).astype(np.uint8)
    return cv2.applyColorMap(u8, cv2.COLORMAP_VIRIDIS)


def _upsample_mask(mask: np.ndarray, size: Tuple[int, int]) -> np.ndarray:
    w, h = size
    if mask.shape[0] == h and mask.shape[1] == w:
        return mask
    return cv2.resize(mask.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST).astype(bool)


def _roi_polygon_points(roi: np.ndarray) -> Optional[np.ndarray]:
    """Return Nx2 int points for largest contour of ROI mask, or None."""
    m = roi.astype(np.uint8) * 255
    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    best = max(contours, key=cv2.contourArea)
    return best.reshape(-1, 2)


def _build_rig() -> DualCameraRig:
    return DualCameraRig(
        left_index=int(getattr(config, "CAMERA_LEFT_INDEX", 0)),
        right_index=int(getattr(config, "CAMERA_RIGHT_INDEX", 1)),
        width=config.CAMERA_WIDTH,
        height=config.CAMERA_HEIGHT,
        fps=config.CAMERA_FPS,
        left_path=getattr(config, "CAMERA_LEFT_PATH", "") or "",
        right_path=getattr(config, "CAMERA_RIGHT_PATH", "") or "",
        backend=str(getattr(config, "CAMERA_BACKEND", "auto") or "auto"),
        picamera_left=int(getattr(config, "CAMERA_PICAMERA_LEFT", 0)),
        picamera_right=int(getattr(config, "CAMERA_PICAMERA_RIGHT", 1)),
    )


def _grab_frame_pair(rig: DualCameraRig, max_tries: int, warmup: int):
    rig.start()
    try:
        for _ in range(max(0, warmup)):
            rig.read()
        for attempt in range(max_tries):
            fp = rig.read()
            if fp is not None:
                return fp
            LOGGER.warning("Camera read failed (attempt %s/%s)", attempt + 1, max_tries)
            time.sleep(0.05)
        return None
    finally:
        rig.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=str,
        default="",
        help="Output directory (default: ./pipeline_snapshot_<timestamp> under repo)",
    )
    parser.add_argument("--max-tries", type=int, default=60, help="Max camera read attempts")
    parser.add_argument("--warmup", type=int, default=2, help="Frames to discard before capture")
    parser.add_argument(
        "--log-level",
        default=os.environ.get("ROBOBRAIN_LOG_LEVEL", "INFO"),
        help="Logging level (default INFO or ROBOBRAIN_LOG_LEVEL)",
    )
    parser.add_argument(
        "--save-npy",
        action="store_true",
        help="Also save raw npy arrays (segmentation labels, disparity, traversability scores)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    out = Path(args.out_dir) if args.out_dir else _REPO_ROOT / f"pipeline_snapshot_{int(time.time())}"
    out.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Saving to %s", out.resolve())

    rig = _build_rig()
    LOGGER.info("Cameras: %s / %s — %s", rig.left_source, rig.right_source, rig.capture_kind)

    frame_pair = _grab_frame_pair(rig, max_tries=args.max_tries, warmup=args.warmup)
    if frame_pair is None:
        LOGGER.error("No frame pair; check cameras and config.")
        return 1

    cv2.imwrite(str(out / "00_left_raw.png"), frame_pair.left)
    cv2.imwrite(str(out / "00_right_raw.png"), frame_pair.right)
    LOGGER.info("Saved raw left/right")

    pipeline = PerceptionPipeline.from_config(config)
    left_inf, right_inf = frame_pair.left, frame_pair.right
    bundle = None
    try:
        pipeline.setup()
        left_inf, right_inf = pipeline._rectify_pair(frame_pair.left, frame_pair.right)
        cv2.imwrite(str(out / "01_left.png"), left_inf)
        cv2.imwrite(str(out / "01_right.png"), right_inf)
        LOGGER.info(
            "Saved inference pair (rectified=%s)",
            bool(pipeline.rectifier and pipeline.rectifier.is_loaded),
        )
        bundle = pipeline.process(frame_pair)
    finally:
        pipeline.teardown()

    if bundle is None:
        LOGGER.error("Pipeline failed before producing a bundle.")
        return 1

    seg_o: Optional[SegmentationOutput] = bundle.heads.get("segmentation")
    dep_o: Optional[DepthOutput] = bundle.heads.get("stereo")
    trav: TraversabilityMap = bundle.traversability

    if seg_o is not None:
        cv2.imwrite(str(out / "10_segmentation_color.png"), _colorize_segmentation(seg_o.labels))
        if args.save_npy:
            np.save(str(out / "10_segmentation_labels.npy"), seg_o.labels)
        LOGGER.info("Segmentation model=%s", seg_o.model_name)
    else:
        LOGGER.warning("No segmentation output in bundle")

    if dep_o is not None:
        cv2.imwrite(str(out / "20_disparity.png"), _colorize_disparity(dep_o.data))
        if args.save_npy:
            np.save(str(out / "20_disparity.npy"), dep_o.data)
        LOGGER.info("Stereo model=%s kind=%s", dep_o.model_name, dep_o.kind)
    else:
        LOGGER.warning("No stereo output in bundle")

    h0, w0 = left_inf.shape[:2]
    scores = trav.scores
    if scores.shape[0] != h0 or scores.shape[1] != w0:
        scores_vis = cv2.resize(scores, (w0, h0), interpolation=cv2.INTER_LINEAR)
    else:
        scores_vis = scores
    cv2.imwrite(str(out / "30_traversability.png"), _colorize_scores(scores_vis))
    if args.save_npy:
        np.save(str(out / "30_traversability_scores.npy"), trav.scores)
        np.save(str(out / "30_traversability_scores_fullres.npy"), scores_vis.astype(np.float32))

    overlay = left_inf.copy()
    heat = _colorize_scores(scores_vis)
    overlay = cv2.addWeighted(overlay, 0.55, heat, 0.45, 0.0)
    roi_full = None
    if trav.roi_mask is not None:
        roi_full = _upsample_mask(trav.roi_mask, (w0, h0))
        poly = _roi_polygon_points(roi_full)
        if poly is not None:
            cv2.polylines(overlay, [poly], isClosed=True, color=(0, 255, 0), thickness=2)
    cv2.imwrite(str(out / "31_traversability_overlay.png"), overlay)
    LOGGER.info(
        "Traversability mean_roi=%.4f used_depth=%s stride=%s",
        trav.mean_score_roi,
        trav.used_depth,
        trav.stride,
    )

    meta: Dict[str, Any] = {
        "timestamp": bundle.timestamp,
        "frame_size_hw": [int(h0), int(w0)],
        "rectified": bool(pipeline.rectifier and pipeline.rectifier.is_loaded),
        "camera_left_source": str(rig.left_source),
        "camera_right_source": str(rig.right_source),
        "capture_kind": rig.capture_kind,
        "segmentation": None
        if seg_o is None
        else {"model_name": seg_o.model_name, "source_size_hw": list(seg_o.source_size_hw)},
        "stereo": None
        if dep_o is None
        else {
            "model_name": dep_o.model_name,
            "kind": dep_o.kind,
            "source_size_hw": list(dep_o.source_size_hw),
        },
        "traversability": {
            "mean_score_roi": trav.mean_score_roi,
            "used_depth": trav.used_depth,
            "stride": trav.stride,
            "score_map_hw": list(trav.scores.shape),
        },
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    LOGGER.info("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

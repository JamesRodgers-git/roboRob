from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np


@dataclass
class StereoCalibrationData:
    map_x_left: np.ndarray
    map_y_left: np.ndarray
    map_x_right: np.ndarray
    map_y_right: np.ndarray
    image_size: Tuple[int, int]  # (width, height) used when calibrating
    roi_left: Tuple[int, int, int, int]
    roi_right: Tuple[int, int, int, int]
    q: Optional[np.ndarray] = None
    rms_error: float = 0.0
    meta: Optional[dict] = None


class StereoRectifier:
    """
    Loads stereo rectify maps from stereo_calibrate.py output (.npz).
    """

    def __init__(self, calib: Optional[StereoCalibrationData] = None):
        self._calib = calib

    @classmethod
    def from_npz(cls, path: str) -> "StereoRectifier":
        data = np.load(path, allow_pickle=True)
        meta: Optional[Dict[str, Any]] = None
        if "meta_json" in data.files:
            meta = json.loads(str(data["meta_json"]))
        elif "meta" in data.files:
            raw = data["meta"]
            meta = raw.item() if hasattr(raw, "item") else None
        calib = StereoCalibrationData(
            map_x_left=data["map_x_left"],
            map_y_left=data["map_y_left"],
            map_x_right=data["map_x_right"],
            map_y_right=data["map_y_right"],
            image_size=(int(data["image_width"]), int(data["image_height"])),
            roi_left=tuple(int(x) for x in data["roi_left"]),
            roi_right=tuple(int(x) for x in data["roi_right"]),
            q=data["Q"] if "Q" in data.files else None,
            rms_error=float(data["rms_error"]) if "rms_error" in data.files else 0.0,
            meta=meta,
        )
        return cls(calib)

    @property
    def is_loaded(self) -> bool:
        return self._calib is not None

    def calibration_size(self) -> Optional[Tuple[int, int]]:
        if self._calib is None:
            return None
        return self._calib.image_size

    def apply(self, left: np.ndarray, right: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if self._calib is None:
            raise RuntimeError("StereoRectifier: no calibration loaded")
        import cv2

        exp_w, exp_h = self._calib.image_size
        h, w = left.shape[:2]
        if w != exp_w or h != exp_h:
            raise ValueError(
                f"StereoRectifier: image size ({w}x{h}) does not match calibration ({exp_w}x{exp_h}). "
                "Recapture with same resolution or re-run stereo_calibrate."
            )
        l_rect = cv2.remap(
            left,
            self._calib.map_x_left,
            self._calib.map_y_left,
            cv2.INTER_LINEAR,
        )
        r_rect = cv2.remap(
            right,
            self._calib.map_x_right,
            self._calib.map_y_right,
            cv2.INTER_LINEAR,
        )
        return l_rect, r_rect


def save_stereo_npz(
    path: str,
    map_x_left: np.ndarray,
    map_y_left: np.ndarray,
    map_x_right: np.ndarray,
    map_y_right: np.ndarray,
    image_width: int,
    image_height: int,
    roi_left: Tuple[int, int, int, int],
    roi_right: Tuple[int, int, int, int],
    q: np.ndarray,
    rms_error: float,
    meta: dict,
) -> None:
    np.savez(
        path,
        map_x_left=map_x_left,
        map_y_left=map_y_left,
        map_x_right=map_x_right,
        map_y_right=map_y_right,
        image_width=image_width,
        image_height=image_height,
        roi_left=np.array(roi_left, dtype=np.int32),
        roi_right=np.array(roi_right, dtype=np.int32),
        Q=q,
        rms_error=rms_error,
        meta_json=json.dumps(meta),
    )

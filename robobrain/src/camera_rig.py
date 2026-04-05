import time
from dataclasses import dataclass
from typing import Any, Optional, Tuple

try:
    import cv2
except ImportError:
    cv2 = None


@dataclass
class FramePair:
    timestamp: float
    left: Any
    right: Any


class DualCameraRig:
    """
    Basic dual-camera capture wrapper for a Pi 5 inference loop.
    """

    def __init__(
        self,
        left_index: int = 0,
        right_index: int = 1,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
    ):
        self.left_index = left_index
        self.right_index = right_index
        self.width = width
        self.height = height
        self.fps = fps
        self.left_cap = None
        self.right_cap = None

    def start(self) -> None:
        if cv2 is None:
            raise RuntimeError("OpenCV is required for camera capture. Install opencv-python.")
        self.left_cap = cv2.VideoCapture(self.left_index)
        self.right_cap = cv2.VideoCapture(self.right_index)
        for cap in (self.left_cap, self.right_cap):
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_FPS, self.fps)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self.left_cap.isOpened() or not self.right_cap.isOpened():
            self.stop()
            raise RuntimeError(
                f"Could not open dual cameras (left={self.left_index}, right={self.right_index})."
            )

    def read(self) -> Optional[FramePair]:
        if self.left_cap is None or self.right_cap is None:
            return None
        ok_l, frame_l = self.left_cap.read()
        ok_r, frame_r = self.right_cap.read()
        if not ok_l or not ok_r:
            return None
        return FramePair(timestamp=time.time(), left=frame_l, right=frame_r)

    def read_resized(self, size: Tuple[int, int]) -> Optional[FramePair]:
        frame_pair = self.read()
        if frame_pair is None:
            return None
        if cv2 is None:
            return frame_pair
        w, h = size
        return FramePair(
            timestamp=frame_pair.timestamp,
            left=cv2.resize(frame_pair.left, (w, h)),
            right=cv2.resize(frame_pair.right, (w, h)),
        )

    def stop(self) -> None:
        if self.left_cap is not None:
            self.left_cap.release()
        if self.right_cap is not None:
            self.right_cap.release()
        self.left_cap = None
        self.right_cap = None

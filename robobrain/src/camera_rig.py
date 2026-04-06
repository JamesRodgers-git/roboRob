import time
from dataclasses import dataclass
from typing import Any, Optional, Tuple, Union

try:
    import cv2
except ImportError:
    cv2 = None

CaptureSource = Union[int, str]


def _picamera2_available() -> bool:
    try:
        import picamera2  # noqa: F401

        return True
    except ImportError:
        return False


def _resolve_backend(name: str) -> str:
    n = (name or "auto").strip().lower()
    if n == "auto":
        return "picamera2" if _picamera2_available() else "opencv"
    if n in ("opencv", "picamera2"):
        return n
    raise ValueError(f"Unknown CAMERA_BACKEND {name!r}; use auto, opencv, or picamera2")


def _open_video_capture(source: CaptureSource):
    """
    Open a camera or V4L2 device path.

    On Raspberry Pi, OpenCV often defaults to GStreamer for numeric indices, which can fail
    (memory, wrong pipeline). Try ``CAP_V4L2`` first, then the default backend.
    """
    if cv2 is None:
        raise RuntimeError("OpenCV is required for camera capture. Install opencv-python.")
    cap = cv2.VideoCapture(source, cv2.CAP_V4L2)
    if cap.isOpened():
        return cap
    cap.release()
    cap = cv2.VideoCapture(source)
    if cap.isOpened():
        return cap
    cap.release()
    return cv2.VideoCapture(source)


@dataclass
class FramePair:
    timestamp: float
    left: Any
    right: Any


class DualCameraRig:
    """
    Basic dual-camera capture wrapper for a Pi 5 inference loop.

    **Raspberry Pi 5 + libcamera / PISP:** Plain V4L2 (``/dev/video*``) nodes may open in OpenCV
    but **fail to stream** (`read()` always false) until libcamera configures the pipeline.
    Use ``CAMERA_BACKEND = "picamera2"`` or ``"auto"`` (default when ``picamera2`` is installed).

    **USB / laptop:** Set ``CAMERA_BACKEND = "opencv"`` and use indices or device paths.

    Picamera2 uses **libcamera camera indices** (same order as ``rpicam-hello --list-cameras``),
    not ``/dev/videoN`` numbers.
    """

    def __init__(
        self,
        left_index: int = 0,
        right_index: int = 1,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
        left_path: str = "",
        right_path: str = "",
        backend: str = "auto",
        picamera_left: int = 0,
        picamera_right: int = 1,
    ):
        self.left_index = left_index
        self.right_index = right_index
        self.left_path = (left_path or "").strip()
        self.right_path = (right_path or "").strip()
        self.width = width
        self.height = height
        self.fps = fps
        self.backend_requested = backend
        self.picamera_left = int(picamera_left)
        self.picamera_right = int(picamera_right)
        self._backend = _resolve_backend(backend)
        self.left_cap = None
        self.right_cap = None
        self._picam_left = None
        self._picam_right = None

    @property
    def left_source(self) -> CaptureSource:
        """Resolved OpenCV source, or a picamera2 label for logging."""
        if self._backend == "picamera2":
            return f"picamera2:{self.picamera_left}"
        return self.left_path if self.left_path else self.left_index

    @property
    def right_source(self) -> CaptureSource:
        if self._backend == "picamera2":
            return f"picamera2:{self.picamera_right}"
        return self.right_path if self.right_path else self.right_index

    @property
    def capture_kind(self) -> str:
        if self._backend == "picamera2":
            return "picamera2 (libcamera)"
        return "OpenCV V4L2" if (self.left_path and self.right_path) else "OpenCV (path or index)"

    def start(self) -> None:
        if self._backend == "picamera2":
            self._start_picamera2()
            return

        if cv2 is None:
            raise RuntimeError("OpenCV is required for camera capture. Install opencv-python.")
        left_src = self.left_path if self.left_path else self.left_index
        right_src = self.right_path if self.right_path else self.right_index
        self.left_cap = _open_video_capture(left_src)
        self.right_cap = _open_video_capture(right_src)
        for cap in (self.left_cap, self.right_cap):
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_FPS, self.fps)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self.left_cap.isOpened() or not self.right_cap.isOpened():
            self.stop()
            raise RuntimeError(
                f"Could not open dual cameras (left={left_src!r}, right={right_src!r}). "
                "Check cables and permissions (video group). Run `v4l2-ctl --list-devices` and set "
                "`CAMERA_LEFT_PATH` / `CAMERA_RIGHT_PATH` in config.py to real capture nodes "
                "(e.g. /dev/video0 and /dev/video2). If using indices only, try CAMERA_RIGHT_INDEX=2 "
                "when video1 is not a capture device. On Pi 5 CSI cameras, try CAMERA_BACKEND='picamera2'."
            )

    def _start_picamera2(self) -> None:
        from picamera2 import Picamera2

        if cv2 is None:
            raise RuntimeError("OpenCV is required to convert picamera2 frames to BGR for the pipeline.")
        size = (self.width, self.height)
        try:
            self._picam_left = Picamera2(self.picamera_left)
            self._picam_right = Picamera2(self.picamera_right)
            for p in (self._picam_left, self._picam_right):
                p.configure(
                    p.create_preview_configuration(
                        main={"size": size, "format": "RGB888"},
                    )
                )
            self._picam_left.start()
            self._picam_right.start()
        except Exception:
            self.stop()
            raise

    def read(self) -> Optional[FramePair]:
        if self._backend == "picamera2":
            return self._read_picamera2()
        if self.left_cap is None or self.right_cap is None:
            return None
        ok_l, frame_l = self.left_cap.read()
        ok_r, frame_r = self.right_cap.read()
        if not ok_l or not ok_r:
            return None
        return FramePair(timestamp=time.time(), left=frame_l, right=frame_r)

    def _read_picamera2(self) -> Optional[FramePair]:
        if self._picam_left is None or self._picam_right is None:
            return None
        try:
            rgb_l = self._picam_left.capture_array("main")
            rgb_r = self._picam_right.capture_array("main")
        except Exception:
            return None
        frame_l = cv2.cvtColor(rgb_l, cv2.COLOR_RGB2BGR)
        frame_r = cv2.cvtColor(rgb_r, cv2.COLOR_RGB2BGR)
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
        if self._picam_left is not None:
            try:
                self._picam_left.stop()
            except Exception:
                pass
            try:
                self._picam_left.close()
            except Exception:
                pass
            self._picam_left = None
        if self._picam_right is not None:
            try:
                self._picam_right.stop()
            except Exception:
                pass
            try:
                self._picam_right.close()
            except Exception:
                pass
            self._picam_right = None

        if self.left_cap is not None:
            self.left_cap.release()
        if self.right_cap is not None:
            self.right_cap.release()
        self.left_cap = None
        self.right_cap = None

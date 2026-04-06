# --- Cameras (see README "Dual CSI on Pi 5") ---
# Pi 5 + libcamera: OpenCV on /dev/video* often opens but never streams. Use picamera2 (default
# "auto" picks it when installed). Indices below are libcamera order (rpicam-hello --list-cameras).
# For USB webcams on a PC, set CAMERA_BACKEND = "opencv" and use paths or indices.
CAMERA_BACKEND = "auto"  # auto | picamera2 | opencv
CAMERA_PICAMERA_LEFT = 0
CAMERA_PICAMERA_RIGHT = 1

# OpenCV-only: non-empty paths take precedence over indices. Ignored for device selection when
# CAMERA_BACKEND is picamera2 (still used if you switch to opencv).
CAMERA_LEFT_PATH = "/dev/video0"
CAMERA_RIGHT_PATH = "/dev/video8"
CAMERA_LEFT_INDEX = 0
CAMERA_RIGHT_INDEX = 1
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30

# Stereo rectification maps from tools/stereo_calibrate.py (empty = skip rectify / depth-only path degraded)
STEREO_CALIB_NPZ_PATH = ""

# On Pi 5 host side, "auto" scans /dev/ttyACM* and USB serial candidates.
MOVEMENT_SERIAL_PORT = "auto"
MOVEMENT_SERIAL_BAUD_RATE = 115200

CONTROL_LOOP_HZ = 20
DEFAULT_THROTTLE = 0.0
DEFAULT_TURN = 0.0

# brain.py logging: DEBUG for verbose; INFO normal
LOG_LEVEL = "INFO"
# Seconds between periodic status lines (traversability, commands, loop rate).
BRAIN_STATUS_INTERVAL_S = 2.0

# --- Hailo / perception (reference: Hailo-10H, e.g. Raspberry Pi 5 AI Kit / AI HAT+) ---
USE_HAILO = True
# Index into hailo_platform.Device.scan() for this process (0 = first Hailo). Set -1 to pass
# device_ids=None and let VDevice use defaults.
HAILO_DEVICE_ID = 0
# Legacy knob (InferModel API ignores this; kept for future compatibility).
HAILO_STREAM_INTERFACE = "integrated"
HAILO_STDC1_HEF = "~/Downloads/stdc1.hef"
HAILO_STEREONET_HEF = "~/Downloads/stereonet.hef"
# If a configured .hef is missing, clone hailo-ai/hailo_model_zoo, read public-model RST for this
# family, and download the compiled HEF from the linked S3 URL (must match silicon, e.g. HAILO10H).
HAILO_AUTO_FETCH_HEFS = True
HAILO_MODEL_ZOO_GIT_URL = "https://github.com/hailo-ai/hailo_model_zoo.git"
HAILO_MODEL_ZOO_GIT_REF = "master"
HAILO_MODEL_ZOO_DOCS_FAMILY = "HAILO10H"
HAILO_MODEL_ZOO_CLONE_PATH = ""  # default: ~/.cache/robobrain/hailo_model_zoo

# Hailo model zoo nominal input sizes (H, W, channels)
STDC1_INPUT_HEIGHT = 1024
STDC1_INPUT_WIDTH = 1920
STEREONET_INPUT_HEIGHT = 368
STEREONET_INPUT_WIDTH = 1232

# Fusion: downsample factor for traversability map (1 = full resolution after seg head size)
TRAV_MAP_STRIDE = 4
# Bottom-centered trapezoid as fractions of width/height (0-1): top_y, bottom_y, top_half_width, bottom_half_width
TRAV_ROI_TOP_Y_FRAC = 0.35
TRAV_ROI_BOTTOM_Y_FRAC = 1.0
TRAV_ROI_TOP_HALF_WIDTH_FRAC = 0.15
TRAV_ROI_BOTTOM_HALF_WIDTH_FRAC = 0.45
# Weights: final = seg_weight * seg + geom_weight * geom (geom from disparity smoothness)
FUSION_SEG_WEIGHT = 0.7
FUSION_GEOM_WEIGHT = 0.3
# Disparity gradient above this percentile in ROI is treated as hazard (0-1 scale after normalize)
FUSION_DISP_GRAD_HIGH = 0.85

# Safety: if True, never send non-zero AI commands when depth head did not run
REQUIRE_DEPTH_FOR_MOTION = False
# If True, derive throttle/turn from traversability map; else always send DEFAULT_* unless overridden
AI_STEER_ENABLE = False

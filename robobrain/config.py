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

# --- Hailo / perception ---
USE_HAILO = False
HAILO_DEVICE_ID = 0
HAILO_STDC1_HEF = ""
HAILO_STEREONET_HEF = ""

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

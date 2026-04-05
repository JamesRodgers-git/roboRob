# RoboBrain (Pi 5 + AI HAT+)

`robobrain` is the high-level inference process. It captures dual-camera frames,
runs a **perception pipeline** (semantic segmentation + optional stereo depth),
fuses outputs into a **traversability map**, and sends normalized movement
requests (`throttle`, `turn`) to `robowheels` over serial USB.

The movement client auto-detects the Zero 2 W gadget serial device on the Pi 5
(prefers `/dev/ttyACM*`) and auto-reconnects if USB is unplugged/replugged.

## Perception pipeline

- **Segmentation:** `stdc1` (Cityscapes) via Hailo HEF when `USE_HAILO` and
  `HAILO_STDC1_HEF` are set; otherwise a **stub** head produces synthetic labels.
- **Stereo:** `stereonet` via Hailo when `HAILO_STEREONET_HEF` is set; otherwise a
  **stub** disparity map for testing fusion.
- **Rectification:** If `STEREO_CALIB_NPZ_PATH` points to a file from
  `tools/stereo_calibrate.py`, left/right frames are rectified before inference.
- **Fusion:** Class weights are in `semantic/cityscapes_traversability.json`;
  disparity smoothness is combined in `src/perception/fusion/traversability.py`.
- **Motion:** With `AI_STEER_ENABLE = False` (default), commands stay at
  `DEFAULT_THROTTLE` / `DEFAULT_TURN`. Set `AI_STEER_ENABLE = True` to steer from
  the map (`steer_from_map` in `src/perception/pipeline.py`). If
  `REQUIRE_DEPTH_FOR_MOTION = True`, commands are zero unless depth fusion ran.

## Hailo on Raspberry Pi

Install the OS packages (see [Hailo Pi docs](https://community.hailo.ai/)); e.g.
`sudo apt install hailo-all`. The Python module `hailo_platform` is usually
provided with that stack (often under system `dist-packages`). A venv may need
`--system-site-packages` to see it.

Set in `config.py`:

- `USE_HAILO = True`
- `HAILO_STDC1_HEF` / `HAILO_STEREONET_HEF` to your `.hef` paths (from the
  [Hailo Model Zoo](https://github.com/hailo-ai/hailo_model_zoo)).

Input sizes default to model-zoo defaults (`STDC1_*`, `STEREONET_*`).

Postprocess for segmentation/disparity may need tuning to match your exact HEF
outputs (see `segmentation_stdc1.py` / `stereo_stereonet.py`).

## Stereo calibration

Capture 20–40 synchronized pairs of the same chessboard visible in **both**
cameras, at the **same resolution** you use in production.

**Option A — two folders (same filenames / sort order):**

```bash
python3 tools/stereo_calibrate.py --left_dir ./captures/left --right_dir ./captures/right -o ./calibration/stereo_rectify.npz
```

**Option B — paired names in one folder:** `timestamp_L.png` and
`timestamp_R.png`

```bash
python3 tools/stereo_calibrate.py --pairs_dir ./captures/pairs -o ./calibration/stereo_rectify.npz
```

Flags: `--board_width`, `--board_height` (inner corners), `--square_size_m`.

Then set `STEREO_CALIB_NPZ_PATH` in `config.py` to that `.npz`.

## Adding another model (e.g. detection)

1. Add a class in `src/perception/heads/` subclassing `PerceptionHead` with a
   unique `name`.
2. Append it to the `heads` list in `PerceptionPipeline.from_config`.
3. Use `ctx["heads"][your_name]` in `TraversabilityFusion.fuse(...,
   detections=...)` (hook already reserved) or extend `PerceptionBundle`.

See `src/perception/heads/detection_placeholder.py` and `DetectionOutput` in
`src/perception/types.py`.

## Command/Status Protocol

The Pi 5 sends newline-delimited JSON commands:

```json
{"type":"command","throttle":0.25,"turn":-0.1,"source":"robobrain-ai","timestamp":1711843200.0}
```

The Pi Zero 2 W responds with status lines:

```json
{
  "type":"status",
  "source":"radio|serial-ai|radio-idle",
  "requested_throttle":0.25,
  "requested_turn":-0.1,
  "estimated_speed_mph":1.1,
  "estimated_throttle":0.22,
  "actual_turn_power":-0.08,
  "left_speed_mph":1.2,
  "right_speed_mph":1.0,
  "left_brake":100.0,
  "right_brake":100.0,
  "timestamp":1711843200.1
}
```

## Layout

- `brain.py` — main loop: capture → `PerceptionPipeline.process` → movement
- `config.py` — cameras, serial, Hailo paths, fusion ROI, safety flags
- `semantic/cityscapes_traversability.json` — class id → traversability weight
- `src/camera_rig.py` — `DualCameraRig`
- `src/movement_client.py` — serial client
- `src/movement_protocol.py` — JSON dataclasses
- `src/perception/` — calibration, Hailo runner, heads, fusion, pipeline
- `tools/stereo_calibrate.py` — chessboard stereo calibration

## Run

```bash
pip3 install -r requirements.txt
python3 brain.py
```

## Tests

```bash
pip3 install pytest
pytest tests/
```

## USB device detection (Pi 5)

- Default `MOVEMENT_SERIAL_PORT = "auto"` scans for USB CDC ACM/serial gadget ports.
- Pin a port in `config.py` if needed (e.g. `"/dev/ttyACM0"`).

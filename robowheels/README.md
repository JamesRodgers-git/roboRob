# RoboWheels (Pi Zero 2 W Motion Controller)

`robowheels` is the low-level motion and safety controller.

- Manual radio (CRSF) and AI requests are both normalized to `throttle` + `turn`.
- Manual radio input always has override priority when stick deflection is non-trivial.
- AI requests arrive over serial USB (newline-delimited JSON).
- Safety limits (acceleration, turn rate, lateral acceleration) are enforced in one place.
- USB gadget serial endpoint auto-detects and reconnects when cable/power cycles.

## Input Model

- `throttle`: desired forward speed in `[-1.0, 1.0]` (forward-only by default in config).
- `turn`: desired turn power in `[-1.0, 1.0]`.

Both radio and AI paths use this same model.

## Turning Behavior

The default movement curve is tuned for stability:

- Near stationary and turning: sharpest turning mode is used.
- At low speed: turning is moderated for easier control.
- At high speed: turn gain softens further to reduce aggressive roll/jerk.

Tune with:

- `TURN_GAIN_AT_STOP`
- `TURN_GAIN_AT_MAX_SPEED`
- `PIVOT_TURN_SPEED_MPH`
- `MAX_LATERAL_ACCELERATION`
- `MAX_TURN_RATE`
- `BRAKE_APPLY_RATE_PER_S`

## AI Serial Protocol (Pi 5 -> Pi Zero 2 W)

Command line format:

```json
{"type":"command","throttle":0.3,"turn":-0.2,"source":"robobrain-ai","timestamp":1711843200.0}
```

Status response format:

```json
{
  "type":"status",
  "source":"radio|serial-ai|radio-idle",
  "requested_throttle":0.3,
  "requested_turn":-0.2,
  "estimated_speed_mph":1.2,
  "estimated_throttle":0.24,
  "actual_turn_power":-0.16,
  "left_speed_mph":1.3,
  "right_speed_mph":1.1,
  "left_brake":100.0,
  "right_brake":100.0,
  "timestamp":1711843200.1
}
```

## Config

Update in `config.py`:

- radio: `CRSF_THROTTLE_CHANNEL`, `CRSF_TURN_CHANNEL`
- safety: `MAX_SPEED`, `MAX_ACCELERATION`, `MAX_LATERAL_ACCELERATION`, `MAX_TURN_RATE`
- curve: `TURN_GAIN_AT_STOP`, `TURN_GAIN_AT_MAX_SPEED`, `PIVOT_TURN_SPEED_MPH`
- serial USB: `USB_COMMAND_PORT`, `USB_COMMAND_BAUD_RATE`, `USB_COMMAND_TIMEOUT_S`
  - set `USB_COMMAND_PORT='auto'` (default) to wait for `/dev/ttyGS*`
- safety timeout: `AI_FAILSAFE_TIMEOUT_S` (hard stop if AI control signal is lost)
- logging: `DRIVE_LOG_LEVEL`

## USB Gadget Mode (Pi Zero 2 W)

`robowheels` now expects the Zero 2 W to expose a USB CDC ACM gadget serial device.
When gadget mode is active, this process listens on `/dev/ttyGS*` automatically.

Typical Pi OS setup (OS-level, one-time):

1. In `/boot/firmware/config.txt`, ensure:
   - `dtoverlay=dwc2`
2. In `/boot/firmware/cmdline.txt`, add `modules-load=dwc2,g_serial`
3. Reboot the Zero 2 W.
4. On the Pi Zero 2 W, verify:
   - `ls /dev/ttyGS*` shows a gadget serial device.

## Run

```bash
pip3 install -r requirements.txt
python3 drive.py
```

GUI monitor:

```bash
python3 run_drive_gui.py
```

Dry-run monitor:

```bash
python3 test_drive_gui.py
```

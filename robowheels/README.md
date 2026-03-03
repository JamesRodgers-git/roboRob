# RoboWheels - Raspberry Pi 5 CRSF Connection

This project implements CRSF (Crossfire) protocol communication for Raspberry Pi 5.

## Setup

### 1. Install Dependencies

```bash
pip3 install -r requirements.txt
```

### 2. Enable UART on Raspberry Pi 5

The Raspberry Pi 5 uses a different UART configuration than previous models. You may need to:

1. Enable UART in `raspi-config`:
   ```bash
   sudo raspi-config
   # Navigate to: Interface Options -> Serial Port -> Enable
   ```

2. For Raspberry Pi 5, the UART might be on `/dev/ttyAMA0` or `/dev/ttyAMA1`. Check available ports:
   ```bash
   ls -l /dev/ttyAMA*
   ```

3. Add your user to the dialout group (if needed):
   ```bash
   sudo usermod -a -G dialout $USER
   # Log out and back in for changes to take effect
   ```

### 3. Hardware Connection

Connect your CRSF receiver to the Raspberry Pi:
- **RX pin** of CRSF receiver → **TX pin** of Raspberry Pi (GPIO 14)
- **TX pin** of CRSF receiver → **RX pin** of Raspberry Pi (GPIO 15)
- **GND** → **GND**
- **5V** → **5V** (if needed)

**Note:** CRSF uses inverted serial logic. You may need a level shifter or inverter circuit depending on your receiver.

## Running the Test

### GUI Version (Recommended for Screen Sharing/VNC)

Run the GUI test script for a graphical interface:

```bash
python3 test_crsf_gui.py
```

Or specify a different serial port:

```bash
python3 test_crsf_gui.py /dev/ttyAMA1
```

The GUI will:
- Display a clean graphical interface with all channel values
- Show real-time link statistics (RSSI, link quality, SNR)
- Update connection status and runtime
- Work well with VNC/remote desktop screen sharing
- Provide Reconnect and Quit buttons

### CLI Version

Run the command-line test script:

```bash
python3 test_crsf.py
```

Or specify a different serial port:

```bash
python3 test_crsf.py /dev/ttyAMA1
```

The CLI test will:
- Attempt to connect to the CRSF receiver
- Display received channel values in real-time (updates in place)
- Show link statistics (RSSI, link quality, SNR)
- Provide periodic status summaries
- Output final statistics when stopped (Ctrl+C)

## Running the Wheelchair Drive Loop

The main drive loop reads CRSF channels, applies safety limits (acceleration, turn rate, lateral acceleration),
and drives the left/right motors with optional braking.

1. Update key parameters in `config.py`:
   - `WHEEL_BASE_METERS` (distance between wheels)
   - `MAX_SPEED`, `MAX_ACCELERATION`, `MAX_LATERAL_ACCELERATION`, `MAX_TURN_RATE`
   - `CRSF_LEFT_CHANNEL`, `CRSF_RIGHT_CHANNEL` (which channels control left/right)

2. Run:

```bash
python3 run_drive.py
```

Press Ctrl+C to stop.

## Drive Loop GUI

This version runs the live drive loop while showing CRSF channels, motor outputs, and brake states.

```bash
python3 run_drive_gui.py
```

## Drive Monitor GUI

This GUI shows CRSF inputs, computed motor outputs, and brake states.

Dry run (does not drive hardware):

```bash
python3 test_drive_gui.py
```

Apply outputs to motors/brakes:

```bash
python3 test_drive_gui.py --apply
```

## Expected Output

When working correctly, you should see:
- Channel values updating (16 channels, typically 988-2012 range)
- Link statistics showing signal strength and quality
- Frame count increasing over time

## Troubleshooting

### No frames received
- Verify transmitter is powered on and bound to receiver
- Check wiring connections
- Verify correct serial port (`/dev/ttyAMA0` vs `/dev/ttyAMA1`)
- Check if UART is enabled and not used by other services

### Permission denied
- Add user to dialout group: `sudo usermod -a -G dialout $USER`
- May need to run with `sudo` (not recommended for production)

### Connection fails
- Check if port exists: `ls -l /dev/ttyAMA*`
- Verify no other process is using the port: `lsof /dev/ttyAMA0`
- Check UART configuration in `/boot/config.txt`

## Files

- `crsf_connection.py` - CRSF protocol implementation and serial communication
- `test_crsf_gui.py` - GUI test script with graphical interface (recommended for screen sharing)
- `test_crsf.py` - CLI test script that outputs connection results
- `requirements.txt` - Python dependencies

**Note:** The GUI version uses tkinter, which comes pre-installed with Python on Raspberry Pi. No additional dependencies needed for the GUI.

#!/usr/bin/env python3
import argparse
import time
import tkinter as tk

import config
from src.crsf_connection import CRSFConnection
from src.movement_algorithms import LateralLimitedMovementAlgorithm


def normalize_crsf_channel(
    value: int,
    input_min: int,
    input_max: int,
    input_center: int,
    deadband: int,
    invert: bool = False,
) -> float:
    if value >= input_center + deadband:
        norm = (value - (input_center + deadband)) / max(1.0, (input_max - input_center - deadband))
        out = max(0.0, min(1.0, norm))
    elif value <= input_center - deadband:
        norm = (value - (input_center - deadband)) / max(1.0, (input_center - deadband - input_min))
        out = max(-1.0, min(0.0, norm))
    else:
        out = 0.0
    return -out if invert else out


class NullMotorController:
    def __init__(self, max_speed_mph: float):
        self._max_speed_mph = max_speed_mph
        self._speed_mph = 0.0

    def set_speed_mph(self, speed_mph: float):
        self._speed_mph = speed_mph

    def get_speed_mph(self):
        return self._speed_mph

    def get_speed_percentage(self):
        if self._max_speed_mph <= 0:
            return 0.0
        return (self._speed_mph / self._max_speed_mph) * 100


class NullBrakeController:
    def __init__(self):
        self._left = 0.0
        self._right = 0.0

    def set_brake(self, left_value: float, right_value: float):
        self._left = float(left_value)
        self._right = float(right_value)

    def get_brake(self):
        return self._left, self._right

    def cleanup(self):
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Drive loop GUI monitor")
    parser.add_argument("--port", default=config.CRSF_PORT)
    parser.add_argument("--apply", action="store_true", help="Apply outputs to motors/brakes")
    args = parser.parse_args()

    crsf = CRSFConnection(port=args.port, baudrate=config.CRSF_BAUD_RATE)
    if not crsf.connect():
        print("Failed to connect to CRSF receiver.")
        return

    if args.apply:
        from src.motor_controller import MotorController
        from src.brake_controller import BrakeController

        motor_left = MotorController(
            address=config.MOTOR_CONTROLLER1_ADDRESS,
            min_speed=config.MOTOR_CONTROLLER_MIN_SPEED,
            max_speed=config.MOTOR_CONTROLLER_MAX_SPEED,
            reset_speed=config.MOTOR_CONTROLLER_RESET_SPEED,
            max_speed_mph=config.MAX_SPEED,
        )
        motor_right = MotorController(
            address=config.MOTOR_CONTROLLER2_ADDRESS,
            min_speed=config.MOTOR_CONTROLLER_MIN_SPEED,
            max_speed=config.MOTOR_CONTROLLER_MAX_SPEED,
            reset_speed=config.MOTOR_CONTROLLER_RESET_SPEED,
            max_speed_mph=config.MAX_SPEED,
        )
        brakes = BrakeController(
            config.BRAKE_LEFT_PIN,
            config.BRAKE_RIGHT_PIN,
            brake_apply_rate_per_s=config.BRAKE_APPLY_RATE_PER_S,
            brake_release_rate_per_s=config.BRAKE_RELEASE_RATE_PER_S,
        )
    else:
        motor_left = NullMotorController(config.MAX_SPEED)
        motor_right = NullMotorController(config.MAX_SPEED)
        brakes = NullBrakeController()

    algorithm = LateralLimitedMovementAlgorithm(
        max_speed_mph=config.MAX_SPEED,
        max_acceleration=config.MAX_ACCELERATION,
        max_turn_rate=config.MAX_TURN_RATE,
        max_lateral_acceleration=config.MAX_LATERAL_ACCELERATION,
        wheel_base_meters=config.WHEEL_BASE_METERS,
        turn_gain_at_stop=config.TURN_GAIN_AT_STOP,
        turn_gain_at_max_speed=config.TURN_GAIN_AT_MAX_SPEED,
        turn_throttle_derate_at_full_turn=config.TURN_THROTTLE_DERATE_AT_FULL_TURN,
        pivot_turn_speed_mph=config.PIVOT_TURN_SPEED_MPH,
        turn_deadband=config.TURN_INPUT_DEADBAND,
        allow_reverse=config.ALLOW_REVERSE,
    )

    root = tk.Tk()
    root.title("RoboWheels Drive Monitor")

    status_var = tk.StringVar(value="Connecting...")
    status_label = tk.Label(root, textvariable=status_var, font=("Helvetica", 12))
    status_label.grid(row=0, column=0, sticky="w", padx=10, pady=5, columnspan=4)

    channel_vars = [tk.StringVar(value="1500") for _ in range(16)]
    tk.Label(root, text="Channels", font=("Helvetica", 12, "bold")).grid(row=1, column=0, sticky="w", padx=10)
    row = 2
    for i in range(16):
        tk.Label(root, text=f"CH{i+1:02d}:").grid(row=row, column=0, sticky="e", padx=10)
        tk.Label(root, textvariable=channel_vars[i], width=6).grid(row=row, column=1, sticky="w")
        if (i + 1) % 4 == 0:
            row += 1

    left_input_var = tk.StringVar(value="1500")
    right_input_var = tk.StringVar(value="1500")
    tk.Label(root, text="Inputs", font=("Helvetica", 12, "bold")).grid(row=2, column=2, sticky="w", padx=10)
    tk.Label(root, text="Throttle:").grid(row=3, column=2, sticky="e", padx=10)
    tk.Label(root, textvariable=left_input_var, width=6).grid(row=3, column=3, sticky="w")
    tk.Label(root, text="Turn:").grid(row=4, column=2, sticky="e", padx=10)
    tk.Label(root, textvariable=right_input_var, width=6).grid(row=4, column=3, sticky="w")

    motor_left_var = tk.StringVar(value="0.00 mph (0.0%)")
    motor_right_var = tk.StringVar(value="0.00 mph (0.0%)")
    brake_left_var = tk.StringVar(value="0.0%")
    brake_right_var = tk.StringVar(value="0.0%")
    yaw_rate_var = tk.StringVar(value="0.00 deg/s")
    lat_accel_var = tk.StringVar(value="0.00 m/s^2")

    tk.Label(root, text="Outputs", font=("Helvetica", 12, "bold")).grid(row=6, column=2, sticky="w", padx=10)
    tk.Label(root, text="Motor L:").grid(row=7, column=2, sticky="e", padx=10)
    tk.Label(root, textvariable=motor_left_var, width=18).grid(row=7, column=3, sticky="w")
    tk.Label(root, text="Motor R:").grid(row=8, column=2, sticky="e", padx=10)
    tk.Label(root, textvariable=motor_right_var, width=18).grid(row=8, column=3, sticky="w")
    tk.Label(root, text="Brake L:").grid(row=9, column=2, sticky="e", padx=10)
    tk.Label(root, textvariable=brake_left_var, width=18).grid(row=9, column=3, sticky="w")
    tk.Label(root, text="Brake R:").grid(row=10, column=2, sticky="e", padx=10)
    tk.Label(root, textvariable=brake_right_var, width=18).grid(row=10, column=3, sticky="w")
    tk.Label(root, text="Yaw rate:").grid(row=11, column=2, sticky="e", padx=10)
    tk.Label(root, textvariable=yaw_rate_var, width=18).grid(row=11, column=3, sticky="w")
    tk.Label(root, text="Lat accel:").grid(row=12, column=2, sticky="e", padx=10)
    tk.Label(root, textvariable=lat_accel_var, width=18).grid(row=12, column=3, sticky="w")

    last_channels = [1500] * 16
    last_update = time.time()
    mph_to_mps = 0.44704

    def refresh():
        nonlocal last_update
        frame = crsf.read_frame()
        if frame and frame.get("type") == CRSFConnection.FRAME_TYPE_CHANNELS:
            last_channels[:] = frame.get("channels", last_channels)
            last_update = time.time()

        age = time.time() - last_update
        status_var.set(f"Signal age: {age:0.2f}s | {'APPLYING OUTPUTS' if args.apply else 'DRY RUN'}")

        for idx, value in enumerate(last_channels):
            channel_vars[idx].set(f"{int(value)}")

        throttle_input = int(last_channels[config.CRSF_THROTTLE_CHANNEL - 1])
        turn_input = int(last_channels[config.CRSF_TURN_CHANNEL - 1])
        throttle_command = normalize_crsf_channel(
            throttle_input,
            config.CRSF_CHANNEL_MIN,
            config.CRSF_CHANNEL_MAX,
            1500,
            config.CRSF_CHANNEL_DEADBAND,
            invert=config.THROTTLE_INPUT_INVERT,
        )
        turn_command = normalize_crsf_channel(
            turn_input,
            config.CRSF_CHANNEL_MIN,
            config.CRSF_CHANNEL_MAX,
            1500,
            config.CRSF_CHANNEL_DEADBAND,
            invert=config.TURN_INPUT_INVERT,
        )
        left_input_var.set(f"{throttle_input}")
        right_input_var.set(f"{turn_input}")

        left_mph, right_mph, left_brake, right_brake = algorithm.compute(
            throttle_command,
            turn_command,
            motor_left.get_speed_mph(),
            motor_right.get_speed_mph(),
            *brakes.get_brake(),
        )

        motor_left.set_speed_mph(left_mph)
        motor_right.set_speed_mph(right_mph)
        brakes.set_brake(left_brake, right_brake)

        motor_left_var.set(f"{left_mph:0.2f} mph ({motor_left.get_speed_percentage():0.1f}%)")
        motor_right_var.set(f"{right_mph:0.2f} mph ({motor_right.get_speed_percentage():0.1f}%)")
        brake_left_var.set(f"{left_brake:0.1f}%")
        brake_right_var.set(f"{right_brake:0.1f}%")

        left_mps = left_mph * mph_to_mps
        right_mps = right_mph * mph_to_mps
        v_avg = 0.5 * (left_mps + right_mps)
        yaw_rate = (right_mps - left_mps) / max(0.01, config.WHEEL_BASE_METERS)
        lat_accel = v_avg * yaw_rate
        yaw_rate_var.set(f"{yaw_rate * 57.2958:0.2f} deg/s")
        lat_accel_var.set(f"{lat_accel:0.2f} m/s^2")

        root.after(int(1000 / max(5, config.CONTROL_LOOP_HZ)), refresh)

    def on_close():
        try:
            brakes.cleanup()
            crsf.disconnect()
        finally:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    refresh()
    root.mainloop()


if __name__ == "__main__":
    main()

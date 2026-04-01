#!/usr/bin/env python3
import time
import threading
from typing import List, Dict

import config
from src.brake_controller import BrakeController
from src.crsf_connection import CRSFConnection
from src.motor_controller import MotorController
from src.move_controller import MoveController
from src.movement_algorithms import LateralLimitedMovementAlgorithm


class Drive:
    def __init__(self):
        # Config (all from config module)
        self.port = config.CRSF_PORT
        self.baudrate = config.CRSF_BAUD_RATE
        self.crsf_left_channel = config.CRSF_LEFT_CHANNEL
        self.crsf_right_channel = config.CRSF_RIGHT_CHANNEL
        self.signal_stale_timeout_s = config.SIGNAL_STALE_TIMEOUT_S
        self.control_loop_hz = config.CONTROL_LOOP_HZ

        self.brake_left_pin = config.BRAKE_LEFT_PIN
        self.brake_right_pin = config.BRAKE_RIGHT_PIN

        self.motor1_address = config.MOTOR_CONTROLLER1_ADDRESS
        self.motor2_address = config.MOTOR_CONTROLLER2_ADDRESS
        self.motor_min_speed = config.MOTOR_CONTROLLER_MIN_SPEED
        self.motor_max_speed = config.MOTOR_CONTROLLER_MAX_SPEED
        self.motor_reset_speed = config.MOTOR_CONTROLLER_RESET_SPEED
        self.max_speed_mph = config.MAX_SPEED

        self.max_acceleration = config.MAX_ACCELERATION
        self.max_turn_rate = config.MAX_TURN_RATE
        self.max_lateral_acceleration = config.MAX_LATERAL_ACCELERATION
        self.wheel_base_meters = config.WHEEL_BASE_METERS
        self.crsf_channel_min = config.CRSF_CHANNEL_MIN
        self.crsf_channel_max = config.CRSF_CHANNEL_MAX
        self.crsf_channel_deadband = config.CRSF_CHANNEL_DEADBAND

        # State
        self.running = False
        self.control_thread = None
        self.data_lock = threading.Lock()
        self.channels: List[int] = [1500] * 16
        self.link_stats: Dict = {}
        self.last_rx_time = 0.0

        # CRSF (starts its own reader thread)
        self.crsf = CRSFConnection(port=self.port, baudrate=self.baudrate)
        try:
            self.crsf.start()
        except RuntimeError:
            raise RuntimeError("Failed to start CRSF receiver loop.")

        # Brakes and algorithm first (no dependencies)
        self.brakes = BrakeController(self.brake_left_pin, self.brake_right_pin)
        self.algorithm = LateralLimitedMovementAlgorithm(
            max_speed_mph=self.max_speed_mph,
            max_acceleration=self.max_acceleration,
            max_turn_rate=self.max_turn_rate,
            max_lateral_acceleration=self.max_lateral_acceleration,
            wheel_base_meters=self.wheel_base_meters,
            input_min=self.crsf_channel_min,
            input_max=self.crsf_channel_max,
            input_center=1500,
            input_deadband=self.crsf_channel_deadband,
        )

        # Motors
        self.motor_left = MotorController(
            address=self.motor1_address,
            min_speed=self.motor_min_speed,
            max_speed=self.motor_max_speed,
            reset_speed=self.motor_reset_speed,
            max_speed_mph=self.max_speed_mph,
        )
        self.motor_right = MotorController(
            address=self.motor2_address,
            min_speed=self.motor_min_speed,
            max_speed=self.motor_max_speed,
            reset_speed=self.motor_reset_speed,
            max_speed_mph=self.max_speed_mph,
        )

        # Move controller (uses crsf, motors, brakes, algorithm)
        self.move_controller = MoveController(
            crsf_connection=self.crsf,
            motor_controller_left=self.motor_left,
            motor_controller_right=self.motor_right,
            brake_controller=self.brakes,
            movement_algorithm=self.algorithm,
            left_channel_index=self.crsf_left_channel,
            right_channel_index=self.crsf_right_channel,
            signal_stale_timeout_s=self.signal_stale_timeout_s,
        )

    def start(self) -> None:
        self.running = True
        self.start_time = time.time()
        # Let CRSF reader receive at least one frame before control runs (avoids always hitting stale timeout)
        time.sleep(1.0)
        self.control_thread = threading.Thread(target=self._control_loop, daemon=True)
        self.control_thread.start()

    def stop(self) -> None:
        self.running = False
        if self.control_thread and self.control_thread.is_alive():
            self.control_thread.join(timeout=1.0)
        self.crsf.stop()
        self.brakes.cleanup()

    def _control_loop(self) -> None:
        loop_delay = 1.0 / max(1, self.control_loop_hz)
        debug = getattr(config, "DEBUG_DRIVE", False)
        last_debug = 0.0
        while self.running:
            channels, last_rx, _, _, _ = self.crsf.get_snapshot()

            if time.time() - last_rx > self.signal_stale_timeout_s:
                self.motor_left.set_speed_mph(0)
                self.motor_right.set_speed_mph(0)
                self.brakes.set_brake(100, 100)
                time.sleep(loop_delay)
                continue

            left_input = int(channels[self.crsf_left_channel - 1])
            right_input = int(channels[self.crsf_right_channel - 1])

            left_mph, right_mph, left_brake, right_brake = self.algorithm.compute(
                left_input,
                right_input,
                float(self.motor_left.get_speed_mph()),
                float(self.motor_right.get_speed_mph()),
                *self.brakes.get_brake(),
            )

            self.motor_left.set_speed_mph(left_mph)
            self.motor_right.set_speed_mph(right_mph)
            self.brakes.set_brake(left_brake, right_brake)

            if debug and (time.time() - last_debug) >= 2.0:
                last_debug = time.time()
                raw_l = self.motor_left.speed
                raw_r = self.motor_right.speed
                print(f"[drive] ch1={left_input} ch2={right_input} -> left_mph={left_mph:.2f} right_mph={right_mph:.2f} DAC L={raw_l} R={raw_r}")

            time.sleep(loop_delay)

def main() -> None:
    drive = Drive()
    drive.start()

    try:
        while True:
            time.sleep(1)
    finally:
        drive.stop()

if __name__ == "__main__":
    main()

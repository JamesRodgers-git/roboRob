#!/usr/bin/env python3
import time

import config
from src.brake_controller import BrakeController
from src.crsf_connection import CRSFConnection
from src.motor_controller import MotorController
from src.move_controller import MoveController
from src.movement_algorithms import LateralLimitedMovementAlgorithm


def main() -> None:
    crsf = CRSFConnection(port=config.CRSF_PORT, baudrate=config.CRSF_BAUD_RATE)
    if not crsf.connect():
        print("Failed to connect to CRSF receiver.")
        return

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

    brakes = BrakeController(config.BRAKE_LEFT_PIN, config.BRAKE_RIGHT_PIN)

    algorithm = LateralLimitedMovementAlgorithm(
        max_speed_mph=config.MAX_SPEED,
        max_acceleration=config.MAX_ACCELERATION,
        max_turn_rate=config.MAX_TURN_RATE,
        max_lateral_acceleration=config.MAX_LATERAL_ACCELERATION,
        wheel_base_meters=config.WHEEL_BASE_METERS,
        input_min=config.CRSF_CHANNEL_MIN,
        input_max=config.CRSF_CHANNEL_MAX,
        input_center=1500,
        input_deadband=config.CRSF_CHANNEL_DEADBAND,
    )

    controller = MoveController(
        crsf_connection=crsf,
        motor_controller_left=motor_left,
        motor_controller_right=motor_right,
        brake_controller=brakes,
        movement_algorithm=algorithm,
        left_channel_index=config.CRSF_LEFT_CHANNEL,
        right_channel_index=config.CRSF_RIGHT_CHANNEL,
        signal_stale_timeout_s=config.SIGNAL_STALE_TIMEOUT_S,
    )

    loop_delay = 1.0 / max(1, config.CONTROL_LOOP_HZ)
    try:
        while True:
            controller.tick()
            time.sleep(loop_delay)
    except KeyboardInterrupt:
        print("Stopping drive loop.")
    finally:
        brakes.cleanup()
        crsf.disconnect()


if __name__ == "__main__":
    main()

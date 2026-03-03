import argparse
import time

import config
from src.motor_controller import MotorController


def _make_controller(address: int) -> MotorController:
    return MotorController(
        address=address,
        min_speed=config.MOTOR_CONTROLLER_MIN_SPEED,
        max_speed=config.MOTOR_CONTROLLER_MAX_SPEED,
        reset_speed=config.MOTOR_CONTROLLER_RESET_SPEED,
        max_speed_mph=config.MAX_SPEED,
    )


def _runup(motor: MotorController, label: str) -> None:
    """Run speed ramp 0 -> 1000 -> 2000 -> 3000 -> 4095 -> 0 on a single motor."""
    print(f"[{label}] Setting speed to 0")
    motor.set_speed(0)
    time.sleep(1)

    print(f"[{label}] Setting speed to 1000 (raw)")
    motor.set_speed(1000)
    time.sleep(1)

    print(f"[{label}] Setting speed to 2000 (raw)")
    motor.set_speed(2000)
    time.sleep(1)

    print(f"[{label}] Setting speed to 3000 (raw)")
    motor.set_speed(3000)
    time.sleep(1)

    print(f"[{label}] Setting speed to 4095 (raw)")
    motor.set_speed(4095)
    time.sleep(1)

    print(f"[{label}] Setting speed to 0")
    motor.set_speed(0)
    time.sleep(1)
    print(f"[{label}] Done")


def _reset_test(motor: MotorController, label: str) -> None:
    """Set speed, i2c_reset, then 0 on a single motor."""
    print(f"[{label}] Reset test")
    motor.set_speed(1000)
    time.sleep(0.5)
    motor.i2c_reset()
    print(f"[{label}] Setting speed to 0")
    motor.set_speed(0)
    time.sleep(1)
    print(f"[{label}] Done")


def test_motor_1_runup():
    """Runup test for motor 1 only (address 0x60)."""
    motor = _make_controller(config.MOTOR_CONTROLLER1_ADDRESS)
    _runup(motor, "Motor 1")


def test_motor_2_runup():
    """Runup test for motor 2 only (address 0x61)."""
    motor = _make_controller(config.MOTOR_CONTROLLER2_ADDRESS)
    _runup(motor, "Motor 2")


def test_motor_1_reset():
    """Reset test for motor 1 only."""
    motor = _make_controller(config.MOTOR_CONTROLLER1_ADDRESS)
    _reset_test(motor, "Motor 1")


def test_motor_2_reset():
    """Reset test for motor 2 only."""
    motor = _make_controller(config.MOTOR_CONTROLLER2_ADDRESS)
    _reset_test(motor, "Motor 2")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Test motor controller(s). Use --motor 1 or 2 to isolate a single motor."
    )
    parser.add_argument(
        "--motor",
        type=int,
        choices=[1, 2],
        default=None,
        help="Test only motor 1 or 2 (default: run both)",
    )
    parser.add_argument(
        "--test",
        choices=["runup", "reset"],
        default="runup",
        help="Test to run: runup (speed ramp) or reset (default: runup)",
    )
    args = parser.parse_args()

    if args.motor == 1:
        if args.test == "runup":
            test_motor_1_runup()
        else:
            test_motor_1_reset()
    elif args.motor == 2:
        if args.test == "runup":
            test_motor_2_runup()
        else:
            test_motor_2_reset()
    else:
        # Run both motors, one after the other
        print("Running Motor 1, then Motor 2.\n")
        if args.test == "runup":
            test_motor_1_runup()
            print()
            test_motor_2_runup()
        else:
            test_motor_1_reset()
            print()
            test_motor_2_reset()

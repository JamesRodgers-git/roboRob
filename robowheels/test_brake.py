#!/usr/bin/env python3
"""
Tests for the brake controller.

Spring brake semantics: 100 = release (no brake), 0 = full brake.

- Unit tests run without RPi (BrakeController skips GPIO when unavailable).
- Hardware test (--hardware) cycles the brake on the Pi for manual verification.
"""

import argparse
import time
import sys

import config
from src.brake_controller import BrakeController


def test_get_brake_initial():
    """Initial brake state is 0 (full brake) on both sides."""
    ctrl = BrakeController(config.BRAKE_LEFT_PIN, config.BRAKE_RIGHT_PIN)
    try:
        left, right = ctrl.get_brake()
        assert left == 0.0 and right == 0.0
    finally:
        ctrl.cleanup()


def test_set_brake_release():
    """Setting 100 releases the brake (spring brake: 100 = no brake)."""
    ctrl = BrakeController(config.BRAKE_LEFT_PIN, config.BRAKE_RIGHT_PIN)
    try:
        ctrl.set_brake(100, 100)
        left, right = ctrl.get_brake()
        assert left == 100.0 and right == 100.0
    finally:
        ctrl.cleanup()


def test_set_brake_full():
    """Setting 0 applies full brake."""
    ctrl = BrakeController(config.BRAKE_LEFT_PIN, config.BRAKE_RIGHT_PIN)
    try:
        ctrl.set_brake(0, 0)
        left, right = ctrl.get_brake()
        assert left == 0.0 and right == 0.0
    finally:
        ctrl.cleanup()


def test_set_brake_clamping():
    """Values outside 0-100 are clamped."""
    ctrl = BrakeController(config.BRAKE_LEFT_PIN, config.BRAKE_RIGHT_PIN)
    try:
        ctrl.set_brake(-10, 150)
        left, right = ctrl.get_brake()
        assert left == 0.0 and right == 100.0
    finally:
        ctrl.cleanup()


def test_set_brake_independent():
    """Left and right brakes can be set independently."""
    ctrl = BrakeController(config.BRAKE_LEFT_PIN, config.BRAKE_RIGHT_PIN)
    try:
        ctrl.set_brake(100, 0)
        left, right = ctrl.get_brake()
        assert left == 100.0 and right == 0.0

        ctrl.set_brake(50, 75)
        left, right = ctrl.get_brake()
        assert left == 50.0 and right == 75.0
    finally:
        ctrl.cleanup()


def run_unit_tests():
    """Run all unit tests (no hardware required)."""
    tests = [
        test_get_brake_initial,
        test_set_brake_release,
        test_set_brake_full,
        test_set_brake_clamping,
        test_set_brake_independent,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  OK  {t.__name__}")
        except Exception as e:
            print(f"  FAIL {t.__name__}: {e}")
            failed += 1
    return failed == 0


def run_hardware_test(hold_seconds: float = 2.0, cycles: int = 3):
    """
    Cycle brake on hardware: release (100) then apply (0), for manual verification.
    Spring brake: 100 = released, 0 = full brake.
    """
    print("Brake hardware test (spring brake: 100=release, 0=full brake)")
    print(f"Cycles: {cycles}, hold time: {hold_seconds}s per state\n")

    ctrl = BrakeController(config.BRAKE_LEFT_PIN, config.BRAKE_RIGHT_PIN)
    try:
        for i in range(cycles):
            print(f"--- Cycle {i + 1}/{cycles} ---")
            print("  Releasing brake (100)...")
            ctrl.set_brake(100, 100)
            time.sleep(hold_seconds)
            print("  Applying full brake (0)...")
            ctrl.set_brake(0, 0)
            time.sleep(hold_seconds)
        print("  Releasing brake (100) before exit.")
        ctrl.set_brake(100, 100)
        print("Done.")
    finally:
        ctrl.cleanup()


def main():
    parser = argparse.ArgumentParser(description="Test brake controller")
    parser.add_argument(
        "--hardware",
        action="store_true",
        help="Run hardware test: cycle brake release/apply on the Pi",
    )
    parser.add_argument(
        "--hold",
        type=float,
        default=2.0,
        metavar="SECONDS",
        help="Seconds to hold each brake state in hardware test (default: 2)",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=3,
        metavar="N",
        help="Number of release/apply cycles in hardware test (default: 3)",
    )
    args = parser.parse_args()

    if args.hardware:
        run_hardware_test(hold_seconds=args.hold, cycles=args.cycles)
        return

    print("Running brake controller unit tests...")
    ok = run_unit_tests()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

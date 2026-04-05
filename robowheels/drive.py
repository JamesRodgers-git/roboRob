#!/usr/bin/env python3
import logging
import threading
import time
from typing import Dict, List

import config
from src.brake_controller import BrakeController
from src.crsf_connection import CRSFConnection
from src.motor_controller import MotorController
from src.movement_algorithms import LateralLimitedMovementAlgorithm, estimated_turn_power
from src.movement_protocol import MovementStatus
from src.serial_command_server import SerialCommandServer

LOGGER = logging.getLogger("robowheels.drive")


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


class Drive:
    def __init__(self):
        log_level_name = str(getattr(config, "DRIVE_LOG_LEVEL", "INFO")).upper()
        log_level = getattr(logging, log_level_name, logging.INFO)
        if not logging.getLogger().handlers:
            logging.basicConfig(
                level=log_level,
                format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            )
        LOGGER.setLevel(log_level)

        # Config (all from config module)
        self.port = config.CRSF_PORT
        self.baudrate = config.CRSF_BAUD_RATE
        self.crsf_throttle_channel = config.CRSF_THROTTLE_CHANNEL
        self.crsf_turn_channel = config.CRSF_TURN_CHANNEL
        self.signal_stale_timeout_s = config.SIGNAL_STALE_TIMEOUT_S
        self.control_loop_hz = config.CONTROL_LOOP_HZ

        self.brake_left_pin = config.BRAKE_LEFT_PIN
        self.brake_right_pin = config.BRAKE_RIGHT_PIN
        self.brake_apply_rate_per_s = config.BRAKE_APPLY_RATE_PER_S
        self.brake_release_rate_per_s = config.BRAKE_RELEASE_RATE_PER_S

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
        self.turn_gain_at_stop = config.TURN_GAIN_AT_STOP
        self.turn_gain_at_max_speed = config.TURN_GAIN_AT_MAX_SPEED
        self.pivot_turn_speed_mph = config.PIVOT_TURN_SPEED_MPH
        self.turn_input_deadband = config.TURN_INPUT_DEADBAND
        self.allow_reverse = config.ALLOW_REVERSE
        self.turn_input_invert = config.TURN_INPUT_INVERT
        self.throttle_input_invert = config.THROTTLE_INPUT_INVERT
        self.manual_override_threshold = config.MANUAL_OVERRIDE_THRESHOLD
        self.crsf_channel_min = config.CRSF_CHANNEL_MIN
        self.crsf_channel_max = config.CRSF_CHANNEL_MAX
        self.crsf_channel_deadband = config.CRSF_CHANNEL_DEADBAND

        self.usb_command_port = config.USB_COMMAND_PORT
        self.usb_command_baudrate = config.USB_COMMAND_BAUD_RATE
        self.usb_command_timeout_s = config.USB_COMMAND_TIMEOUT_S
        self.usb_status_rate_hz = config.USB_STATUS_RATE_HZ
        self.ai_failsafe_timeout_s = config.AI_FAILSAFE_TIMEOUT_S

        # State
        self.running = False
        self.control_thread = None
        self.data_lock = threading.Lock()
        self.channels: List[int] = [1500] * 16
        self.link_stats: Dict = {}
        self.last_rx_time = 0.0
        self.last_control_source = "boot"
        self.ai_command_seen = False
        self.last_ai_command_time = 0.0
        self.ai_timeout_latched = False

        # CRSF (starts its own reader thread)
        self.crsf = CRSFConnection(port=self.port, baudrate=self.baudrate)
        try:
            self.crsf.start()
        except RuntimeError as exc:
            raise RuntimeError("Failed to start CRSF receiver loop.") from exc

        # Brakes and algorithm
        self.brakes = BrakeController(
            self.brake_left_pin,
            self.brake_right_pin,
            brake_apply_rate_per_s=self.brake_apply_rate_per_s,
            brake_release_rate_per_s=self.brake_release_rate_per_s,
        )
        self.algorithm = LateralLimitedMovementAlgorithm(
            max_speed_mph=self.max_speed_mph,
            max_acceleration=self.max_acceleration,
            max_turn_rate=self.max_turn_rate,
            max_lateral_acceleration=self.max_lateral_acceleration,
            wheel_base_meters=self.wheel_base_meters,
            turn_gain_at_stop=self.turn_gain_at_stop,
            turn_gain_at_max_speed=self.turn_gain_at_max_speed,
            pivot_turn_speed_mph=self.pivot_turn_speed_mph,
            turn_deadband=self.turn_input_deadband,
            allow_reverse=self.allow_reverse,
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

        # AI command transport (Pi 5 -> Zero 2 W over USB serial)
        self.serial_server = SerialCommandServer(
            port=self.usb_command_port,
            baudrate=self.usb_command_baudrate,
        )
        LOGGER.info(
            "Drive configured: CRSF port=%s, USB command port=%s, AI timeout=%.2fs",
            self.port,
            self.usb_command_port,
            self.ai_failsafe_timeout_s,
        )

    def start(self) -> None:
        self.running = True
        self.start_time = time.time()
        self.serial_server.start()
        # Let CRSF reader receive at least one frame before control runs.
        time.sleep(1.0)
        self.control_thread = threading.Thread(target=self._control_loop, daemon=True)
        self.control_thread.start()

    def stop(self) -> None:
        self.running = False
        if self.control_thread and self.control_thread.is_alive():
            self.control_thread.join(timeout=1.0)
        self.serial_server.stop()
        self.crsf.stop()
        self.brakes.cleanup()

    def _control_loop(self) -> None:
        loop_delay = 1.0 / max(1, self.control_loop_hz)
        status_interval = 1.0 / max(1, self.usb_status_rate_hz)
        debug = getattr(config, "DEBUG_DRIVE", False)
        last_debug = 0.0
        last_status_tx = 0.0
        radio_stale_latched = False
        while self.running:
            channels, last_rx, _, _, _ = self.crsf.get_snapshot()
            now = time.time()

            radio_fresh = (now - last_rx) <= self.signal_stale_timeout_s
            if radio_fresh and radio_stale_latched:
                LOGGER.info("CRSF radio signal restored")
                radio_stale_latched = False
            if (not radio_fresh) and (not radio_stale_latched):
                LOGGER.warning("CRSF radio signal stale; entering radio failsafe")
                radio_stale_latched = True

            if radio_fresh:
                throttle_input = int(channels[self.crsf_throttle_channel - 1])
                turn_input = int(channels[self.crsf_turn_channel - 1])
                radio_throttle = normalize_crsf_channel(
                    throttle_input,
                    self.crsf_channel_min,
                    self.crsf_channel_max,
                    1500,
                    self.crsf_channel_deadband,
                    invert=self.throttle_input_invert,
                )
                radio_turn = normalize_crsf_channel(
                    turn_input,
                    self.crsf_channel_min,
                    self.crsf_channel_max,
                    1500,
                    self.crsf_channel_deadband,
                    invert=self.turn_input_invert,
                )
            else:
                throttle_input = 1500
                turn_input = 1500
                radio_throttle = 0.0
                radio_turn = 0.0

            manual_active = (
                abs(radio_throttle) >= self.manual_override_threshold
                or abs(radio_turn) >= self.manual_override_threshold
            )
            ai_command = self.serial_server.get_latest_command(self.usb_command_timeout_s)
            if ai_command is not None:
                self.ai_command_seen = True
                self.last_ai_command_time = now

            if manual_active:
                requested_throttle = radio_throttle
                requested_turn = radio_turn
                source = "radio"
            elif ai_command is not None:
                requested_throttle = ai_command.throttle
                requested_turn = ai_command.turn
                source = ai_command.source or "serial-ai"
            elif radio_fresh:
                requested_throttle = radio_throttle
                requested_turn = radio_turn
                source = "radio-idle"
            else:
                source = "failsafe-stop"
                self.motor_left.set_speed_mph(0.0)
                self.motor_right.set_speed_mph(0.0)
                self.brakes.set_brake(0, 0)
                if source != self.last_control_source:
                    LOGGER.warning("No valid control signal; hard stop applied")
                    self.last_control_source = source
                time.sleep(loop_delay)
                continue

            ai_signal_age = now - self.last_ai_command_time
            ai_link_timed_out = self.ai_command_seen and (ai_signal_age > self.ai_failsafe_timeout_s)
            if (not manual_active) and ai_link_timed_out:
                self.motor_left.set_speed_mph(0.0)
                self.motor_right.set_speed_mph(0.0)
                self.brakes.set_brake(0, 0)
                if not self.ai_timeout_latched:
                    LOGGER.warning(
                        "AI command timeout %.2fs exceeded (age=%.2fs); hard stop applied",
                        self.ai_failsafe_timeout_s,
                        ai_signal_age,
                    )
                    self.ai_timeout_latched = True
                self.last_control_source = "ai-timeout-stop"
                time.sleep(loop_delay)
                continue
            if self.ai_timeout_latched and ((manual_active and radio_fresh) or (not ai_link_timed_out)):
                LOGGER.info("AI timeout condition cleared")
                self.ai_timeout_latched = False

            left_mph, right_mph, left_brake, right_brake = self.algorithm.compute(
                requested_throttle,
                requested_turn,
                float(self.motor_left.get_speed_mph()),
                float(self.motor_right.get_speed_mph()),
                *self.brakes.get_brake(),
            )

            self.motor_left.set_speed_mph(left_mph)
            self.motor_right.set_speed_mph(right_mph)
            self.brakes.set_brake(left_brake, right_brake)

            avg_speed_mph = 0.5 * (left_mph + right_mph)
            est_throttle = 0.0 if self.max_speed_mph <= 0 else (avg_speed_mph / self.max_speed_mph)
            status = MovementStatus(
                source=source,
                requested_throttle=requested_throttle,
                requested_turn=requested_turn,
                estimated_speed_mph=avg_speed_mph,
                estimated_throttle=est_throttle,
                actual_turn_power=estimated_turn_power(left_mph, right_mph),
                left_speed_mph=left_mph,
                right_speed_mph=right_mph,
                left_brake=left_brake,
                right_brake=right_brake,
            )
            if (now - last_status_tx) >= status_interval:
                self.serial_server.send_status(status)
                last_status_tx = now
            if source != self.last_control_source:
                LOGGER.info(
                    "Control source=%s throttle=%+.2f turn=%+.2f speed=%.2f mph",
                    source,
                    requested_throttle,
                    requested_turn,
                    avg_speed_mph,
                )
                self.last_control_source = source

            if debug and (now - last_debug) >= 2.0:
                last_debug = now
                raw_l = self.motor_left.speed
                raw_r = self.motor_right.speed
                print(
                    "[drive] "
                    f"th={requested_throttle:+0.2f} turn={requested_turn:+0.2f} src={source} "
                    f"(ch_th={throttle_input} ch_turn={turn_input}) -> "
                    f"left_mph={left_mph:.2f} right_mph={right_mph:.2f} DAC L={raw_l} R={raw_r}"
                )

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

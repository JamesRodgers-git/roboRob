import time
from typing import Optional, Tuple

from src.crsf_connection import CRSFConnection
from src.motor_controller import MotorController
from src.brake_controller import BrakeController
from src.movement_algorithms import MovementAlgorithm


def _default_channel_to_unit(value: int) -> float:
    return max(-1.0, min(1.0, (float(value) - 1500.0) / 500.0))


class MoveController:
    def __init__(
        self,
        crsf_connection: CRSFConnection,
        motor_controller_left: MotorController,
        motor_controller_right: MotorController,
        brake_controller: BrakeController,
        movement_algorithm: MovementAlgorithm,
        throttle_channel_index: int = 1,
        turn_channel_index: int = 2,
        signal_stale_timeout_s: float = 0.5,
        channel_normalizer=None,
    ):
        self.crsf_connection = crsf_connection
        self.motor_controller_left = motor_controller_left
        self.motor_controller_right = motor_controller_right
        self.brake_controller = brake_controller
        self.movement_algorithm = movement_algorithm
        self.throttle_channel_index = throttle_channel_index
        self.turn_channel_index = turn_channel_index
        self.signal_stale_timeout_s = signal_stale_timeout_s
        self.channel_normalizer = channel_normalizer
        self._last_channels = [1500] * 16

    def move(self, speed: int):
        self.motor_controller_left.set_speed(speed)
        self.motor_controller_right.set_speed(speed)
        self.brake_controller.set_brake(speed, speed)

    def _apply_safe_stop(self):
        self.motor_controller_left.set_speed_mph(0)
        self.motor_controller_right.set_speed_mph(0)
        self.brake_controller.set_brake(0, 0)

    def tick(self, override_inputs: Optional[Tuple[float, float]] = None) -> None:
        frame = self.crsf_connection.read_frame()
        if frame and frame.get("type") == CRSFConnection.FRAME_TYPE_CHANNELS:
            self._last_channels = frame.get("channels", self._last_channels)

        time_since_update = time.time() - self.crsf_connection.get_last_update_time()
        if time_since_update > self.signal_stale_timeout_s:
            self._apply_safe_stop()
            return

        if override_inputs is not None:
            throttle_command, turn_command = override_inputs
        else:
            throttle_input = self._last_channels[self.throttle_channel_index - 1]
            turn_input = self._last_channels[self.turn_channel_index - 1]
            if self.channel_normalizer is None:
                throttle_command = _default_channel_to_unit(throttle_input)
                turn_command = _default_channel_to_unit(turn_input)
            else:
                throttle_command = float(self.channel_normalizer(throttle_input, "throttle"))
                turn_command = float(self.channel_normalizer(turn_input, "turn"))

        left_speed_mph, right_speed_mph, left_brake, right_brake = self.movement_algorithm.compute(
            throttle_command,
            turn_command,
            self.motor_controller_left.get_speed_mph(),
            self.motor_controller_right.get_speed_mph(),
            *self.brake_controller.get_brake(),
        )

        self.motor_controller_left.set_speed_mph(left_speed_mph)
        self.motor_controller_right.set_speed_mph(right_speed_mph)
        self.brake_controller.set_brake(left_brake, right_brake)

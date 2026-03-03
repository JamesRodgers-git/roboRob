import time
from typing import Optional, Tuple

from src.crsf_connection import CRSFConnection
from src.motor_controller import MotorController
from src.brake_controller import BrakeController
from src.movement_algorithms import MovementAlgorithm

class MoveController:
    def __init__(
        self,
        crsf_connection: CRSFConnection,
        motor_controller_left: MotorController,
        motor_controller_right: MotorController,
        brake_controller: BrakeController,
        movement_algorithm: MovementAlgorithm,
        left_channel_index: int = 1,
        right_channel_index: int = 2,
        signal_stale_timeout_s: float = 0.5,
    ):
        self.crsf_connection = crsf_connection
        self.motor_controller_left = motor_controller_left
        self.motor_controller_right = motor_controller_right
        self.brake_controller = brake_controller
        self.movement_algorithm = movement_algorithm
        self.left_channel_index = left_channel_index
        self.right_channel_index = right_channel_index
        self.signal_stale_timeout_s = signal_stale_timeout_s
        self._last_channels = [1500] * 16

    def move(self, speed: int):
        self.motor_controller_left.set_speed(speed)
        self.motor_controller_right.set_speed(speed)
        self.brake_controller.set_brake(speed, speed)

    def _apply_safe_stop(self):
        self.motor_controller_left.set_speed_mph(0)
        self.motor_controller_right.set_speed_mph(0)
        self.brake_controller.set_brake(100, 100)

    def tick(self, override_inputs: Optional[Tuple[int, int]] = None) -> None:
        frame = self.crsf_connection.read_frame()
        if frame and frame.get("type") == CRSFConnection.FRAME_TYPE_CHANNELS:
            self._last_channels = frame.get("channels", self._last_channels)

        time_since_update = time.time() - self.crsf_connection.get_last_update_time()
        if time_since_update > self.signal_stale_timeout_s:
            self._apply_safe_stop()
            return

        if override_inputs is not None:
            left_input, right_input = override_inputs
        else:
            left_input = self._last_channels[self.left_channel_index - 1]
            right_input = self._last_channels[self.right_channel_index - 1]

        left_speed_mph, right_speed_mph, left_brake, right_brake = self.movement_algorithm.compute(
            left_input,
            right_input,
            self.motor_controller_left.get_speed_mph(),
            self.motor_controller_right.get_speed_mph(),
            *self.brake_controller.get_brake(),
        )

        self.motor_controller_left.set_speed_mph(left_speed_mph)
        self.motor_controller_right.set_speed_mph(right_speed_mph)
        self.brake_controller.set_brake(left_brake, right_brake)

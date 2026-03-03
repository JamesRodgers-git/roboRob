from typing import Tuple
import time

_MPH_TO_MPS = 0.44704

class MovementAlgorithm:
    def __init__(self, 
    max_speed_mph: int,
    max_acceleration: int,
    max_turn_rate: int,
    max_lateral_acceleration: int):
        self.max_speed_mph = max_speed_mph
        self.max_acceleration = max_acceleration
        self.max_turn_rate = max_turn_rate
        self.max_lateral_acceleration = max_lateral_acceleration
    '''
    Compute the new speed and brake for the left and right motors.
    Parameters:
    left_channel_input: int - the input from the left channel
    right_channel_input: int - the input from the right channel
    current_left_motor_speed: int - the current speed of the left motor
    current_right_motor_speed: int - the current speed of the right motor
    current_left_brake: int - the current brake of the left motor
    current_right_brake: int - the current brake of the right motor
    Returns: Tuple[int, int, int, int] - returns speed left, speed right, brake left, brake right
    '''
    def compute(self, 
    left_channel_input: int, 
    right_channel_input: int, 
    current_left_motor_speed_mph: int, 
    current_right_motor_speed_mph: int,  
    current_left_brake: int,
    current_right_brake: int,
    ) -> Tuple[int, int, int, int]:
        raise NotImplementedError("Subclasses must implement this method")

class SimpleMovementAlgorithm(MovementAlgorithm):
    def compute(self, 
    left_channel_input: int, 
    right_channel_input: int, 
    current_left_motor_speed_mph: int, 
    current_right_motor_speed_mph: int,  
    current_left_brake: int,
    current_right_brake: int,
    ) -> Tuple[int, int, int, int]:
        left_motor_speed_mph = current_left_motor_speed_mph + (left_channel_input - 1500) * self.max_speed_mph / 1000
        right_motor_speed_mph = current_right_motor_speed_mph + (right_channel_input - 1500) * self.max_speed_mph / 1000
        
        return left_motor_speed_mph, right_motor_speed_mph, 0, 0


class LateralLimitedMovementAlgorithm(MovementAlgorithm):
    def __init__(
        self,
        max_speed_mph: int,
        max_acceleration: int,
        max_turn_rate: int,
        max_lateral_acceleration: int,
        wheel_base_meters: float,
        input_min: int = 988,
        input_max: int = 2012,
        input_center: int = 1500,
        input_deadband: int = 30,
        min_speed_mps_for_lateral_limit: float = 0.15,
    ):
        super().__init__(max_speed_mph, max_acceleration, max_turn_rate, max_lateral_acceleration)
        self.wheel_base_meters = max(0.01, wheel_base_meters)
        self.input_min = input_min
        self.input_max = input_max
        self.input_center = input_center
        self.input_deadband = max(0, input_deadband)
        self.min_speed_mps_for_lateral_limit = max(0.01, min_speed_mps_for_lateral_limit)
        self._last_update_time = time.monotonic()

    def _clamp(self, value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))

    def _normalize_channel(self, value: int) -> float:
        if value >= self.input_center + self.input_deadband:
            return self._clamp(
                (value - (self.input_center + self.input_deadband))
                / (self.input_max - self.input_center - self.input_deadband),
                0.0,
                1.0,
            )
        if value <= self.input_center - self.input_deadband:
            return self._clamp(
                (value - (self.input_center - self.input_deadband))
                / (self.input_center - self.input_deadband - self.input_min),
                -1.0,
                0.0,
            )
        return 0.0

    def _limit_rate(self, target: float, current: float, max_rate_per_s: float, dt: float) -> float:
        if dt <= 0:
            return current
        max_delta = max_rate_per_s * dt
        return self._clamp(target, current - max_delta, current + max_delta)

    def compute(self, 
    left_channel_input: int, 
    right_channel_input: int, 
    current_left_motor_speed_mph: int, 
    current_right_motor_speed_mph: int,  
    current_left_brake: int,
    current_right_brake: int,
    ) -> Tuple[int, int, int, int]:

        # todo remove this and adjust brakes once reverse is implemented
        left_channel_input = max(1500, min(2012, left_channel_input))
        right_channel_input = max(1500, min(2012, right_channel_input))

        now = time.monotonic()
        dt = self._clamp(now - self._last_update_time, 0.005, 0.2)
        self._last_update_time = now

        left_cmd = self._normalize_channel(left_channel_input)
        right_cmd = self._normalize_channel(right_channel_input)

        desired_left_mph = left_cmd * self.max_speed_mph
        desired_right_mph = right_cmd * self.max_speed_mph

        limited_left_mph = self._limit_rate(desired_left_mph, current_left_motor_speed_mph, self.max_acceleration, dt)
        limited_right_mph = self._limit_rate(desired_right_mph, current_right_motor_speed_mph, self.max_acceleration, dt)

        left_mps = limited_left_mph * _MPH_TO_MPS
        right_mps = limited_right_mph * _MPH_TO_MPS
        v_avg = 0.5 * (left_mps + right_mps)
        yaw_rate = (right_mps - left_mps) / self.wheel_base_meters

        max_turn_rate_rad = (self.max_turn_rate * 3.1415926535) / 180.0
        allowed_yaw_rate = max_turn_rate_rad

        speed_for_limit = max(abs(v_avg), self.min_speed_mps_for_lateral_limit)
        max_lat_mps2 = self.max_lateral_acceleration * _MPH_TO_MPS
        allowed_from_lateral = max_lat_mps2 / speed_for_limit
        allowed_yaw_rate = min(allowed_yaw_rate, allowed_from_lateral)

        if abs(yaw_rate) > allowed_yaw_rate:
            limited_delta = self._clamp(
                right_mps - left_mps,
                -allowed_yaw_rate * self.wheel_base_meters,
                allowed_yaw_rate * self.wheel_base_meters,
            )
            right_mps = v_avg + 0.5 * limited_delta
            left_mps = v_avg - 0.5 * limited_delta

        final_left_mph = self._clamp(left_mps / _MPH_TO_MPS, -self.max_speed_mph, self.max_speed_mph)
        final_right_mph = self._clamp(right_mps / _MPH_TO_MPS, -self.max_speed_mph, self.max_speed_mph)

        left_brake = current_left_brake
        right_brake = current_right_brake

        if final_left_mph < 0.1 and final_right_mph < 0.1:
            left_brake = 0
            right_brake = 0
        else:
            left_brake = 100
            right_brake = 100

        return final_left_mph, final_right_mph, left_brake, right_brake

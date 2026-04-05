from typing import Tuple
import time

_MPH_TO_MPS = 0.44704


def estimated_turn_power(left_speed_mph: float, right_speed_mph: float) -> float:
    denom = max(0.01, abs(left_speed_mph) + abs(right_speed_mph))
    return max(-1.0, min(1.0, (left_speed_mph - right_speed_mph) / denom))


class MovementAlgorithm:
    def __init__(
        self,
        max_speed_mph: float,
        max_acceleration: float,
        max_turn_rate: float,
        max_lateral_acceleration: float,
    ):
        self.max_speed_mph = max_speed_mph
        self.max_acceleration = max_acceleration
        self.max_turn_rate = max_turn_rate
        self.max_lateral_acceleration = max_lateral_acceleration

    def compute(
        self,
        throttle_command: float,
        turn_command: float,
        current_left_motor_speed_mph: float,
        current_right_motor_speed_mph: float,
        current_left_brake: float,
        current_right_brake: float,
    ) -> Tuple[float, float, float, float]:
        raise NotImplementedError("Subclasses must implement this method")


class SimpleMovementAlgorithm(MovementAlgorithm):
    def compute(
        self,
        throttle_command: float,
        turn_command: float,
        current_left_motor_speed_mph: float,
        current_right_motor_speed_mph: float,
        current_left_brake: float,
        current_right_brake: float,
    ) -> Tuple[float, float, float, float]:
        throttle = max(0.0, min(1.0, float(throttle_command)))
        turn = max(-1.0, min(1.0, float(turn_command)))
        base = throttle * self.max_speed_mph
        delta = turn * base
        left = max(0.0, min(self.max_speed_mph, base + delta))
        right = max(0.0, min(self.max_speed_mph, base - delta))
        return left, right, 100.0, 100.0


class LateralLimitedMovementAlgorithm(MovementAlgorithm):
    def __init__(
        self,
        max_speed_mph: float,
        max_acceleration: float,
        max_turn_rate: float,
        max_lateral_acceleration: float,
        wheel_base_meters: float,
        min_speed_mps_for_lateral_limit: float = 0.15,
        turn_gain_at_stop: float = 1.0,
        turn_gain_at_max_speed: float = 0.35,
        pivot_turn_speed_mph: float = 1.6,
        turn_deadband: float = 0.02,
        allow_reverse: bool = False,
    ):
        super().__init__(max_speed_mph, max_acceleration, max_turn_rate, max_lateral_acceleration)
        self.wheel_base_meters = max(0.01, wheel_base_meters)
        self.min_speed_mps_for_lateral_limit = max(0.01, min_speed_mps_for_lateral_limit)
        self.turn_gain_at_stop = max(0.0, float(turn_gain_at_stop))
        self.turn_gain_at_max_speed = max(0.0, float(turn_gain_at_max_speed))
        self.pivot_turn_speed_mph = max(0.0, float(pivot_turn_speed_mph))
        self.turn_deadband = max(0.0, float(turn_deadband))
        self.allow_reverse = bool(allow_reverse)
        self._last_update_time = time.monotonic()

    def _clamp(self, value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))

    def _limit_rate(self, target: float, current: float, max_rate_per_s: float, dt: float) -> float:
        if dt <= 0:
            return current
        max_delta = max_rate_per_s * dt
        return self._clamp(target, current - max_delta, current + max_delta)

    def _turn_gain_for_speed(self, base_speed_mph: float) -> float:
        if self.max_speed_mph <= 0:
            return self.turn_gain_at_max_speed
        speed_ratio = self._clamp(abs(base_speed_mph) / self.max_speed_mph, 0.0, 1.0)
        # sqrt drops turn gain sooner at low speeds while still preserving full softening at top speed.
        t = speed_ratio ** 0.5
        return self.turn_gain_at_stop + ((self.turn_gain_at_max_speed - self.turn_gain_at_stop) * t)

    def _target_wheel_speeds(self, throttle: float, turn: float) -> Tuple[float, float]:
        base_speed = throttle * self.max_speed_mph
        if abs(throttle) <= self.turn_deadband and abs(turn) > self.turn_deadband:
            # When starting from stationary, prioritize maximum turning sharpness.
            pivot = self._clamp(abs(turn) * self.pivot_turn_speed_mph, 0.0, self.max_speed_mph)
            if turn > 0:
                return pivot, 0.0
            return 0.0, pivot

        effective_turn = turn * self._turn_gain_for_speed(base_speed)
        turn_delta = effective_turn * abs(base_speed)
        left_target = base_speed + turn_delta
        right_target = base_speed - turn_delta

        if self.allow_reverse:
            lo = -self.max_speed_mph
            hi = self.max_speed_mph
        else:
            lo = 0.0
            hi = self.max_speed_mph
        return self._clamp(left_target, lo, hi), self._clamp(right_target, lo, hi)

    def compute(
        self,
        throttle_command: float,
        turn_command: float,
        current_left_motor_speed_mph: float,
        current_right_motor_speed_mph: float,
        current_left_brake: float,
        current_right_brake: float,
    ) -> Tuple[float, float, float, float]:
        throttle = self._clamp(float(throttle_command), -1.0, 1.0)
        turn = self._clamp(float(turn_command), -1.0, 1.0)
        if not self.allow_reverse:
            throttle = max(0.0, throttle)

        now = time.monotonic()
        dt = self._clamp(now - self._last_update_time, 0.005, 0.2)
        self._last_update_time = now

        desired_left_mph, desired_right_mph = self._target_wheel_speeds(throttle, turn)
        limited_left_mph = self._limit_rate(
            desired_left_mph,
            current_left_motor_speed_mph,
            self.max_acceleration,
            dt,
        )
        limited_right_mph = self._limit_rate(
            desired_right_mph,
            current_right_motor_speed_mph,
            self.max_acceleration,
            dt,
        )

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
            right_mps = v_avg + (0.5 * limited_delta)
            left_mps = v_avg - (0.5 * limited_delta)

        if self.allow_reverse:
            lo = -self.max_speed_mph
            hi = self.max_speed_mph
        else:
            lo = 0.0
            hi = self.max_speed_mph
        final_left_mph = self._clamp(left_mps / _MPH_TO_MPS, lo, hi)
        final_right_mph = self._clamp(right_mps / _MPH_TO_MPS, lo, hi)

        if abs(final_left_mph) < 0.1 and abs(final_right_mph) < 0.1:
            return final_left_mph, final_right_mph, 0.0, 0.0
        return final_left_mph, final_right_mph, 100.0, 100.0

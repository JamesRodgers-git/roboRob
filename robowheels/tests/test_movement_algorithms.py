from src.movement_algorithms import LateralLimitedMovementAlgorithm, estimated_turn_power


def _make_algorithm() -> LateralLimitedMovementAlgorithm:
    return LateralLimitedMovementAlgorithm(
        max_speed_mph=5.0,
        max_acceleration=1000.0,
        max_turn_rate=999.0,
        max_lateral_acceleration=999.0,
        wheel_base_meters=0.6,
        turn_gain_at_stop=1.0,
        turn_gain_at_max_speed=0.3,
        turn_throttle_derate_at_full_turn=0.2,
        pivot_turn_speed_mph=2.0,
        turn_deadband=0.02,
        allow_reverse=False,
    )


def test_stationary_turn_uses_sharp_mode():
    algo = _make_algorithm()
    left, right, _, _ = algo.compute(0.0, 1.0, 0.0, 0.0, 0.0, 0.0)
    assert left > 0.1
    assert right == 0.0


def test_turn_is_softer_at_high_speed_than_low_speed():
    algo = _make_algorithm()
    low_left, low_right, _, _ = algo.compute(0.25, 1.0, 1.25, 1.25, 100.0, 100.0)
    high_left, high_right, _, _ = algo.compute(1.0, 1.0, 5.0, 5.0, 100.0, 100.0)

    low_turn_power = abs(estimated_turn_power(low_left, low_right))
    high_turn_power = abs(estimated_turn_power(high_left, high_right))
    assert high_turn_power < low_turn_power


def test_outputs_stay_within_speed_bounds():
    algo = _make_algorithm()
    left, right, _, _ = algo.compute(1.0, 1.0, 5.0, 5.0, 100.0, 100.0)
    assert 0.0 <= left <= 5.0
    assert 0.0 <= right <= 5.0


def test_straight_full_throttle_is_not_derated():
    algo = _make_algorithm()
    left, right, _, _ = algo.compute(1.0, 0.0, 5.0, 5.0, 100.0, 100.0)
    assert left == 5.0
    assert right == 5.0


def test_full_throttle_turn_reserves_speed_headroom():
    algo = _make_algorithm()
    straight_left, straight_right, _, _ = algo.compute(
        1.0,
        0.0,
        5.0,
        5.0,
        100.0,
        100.0,
    )
    turning_left, turning_right, _, _ = algo.compute(
        1.0,
        1.0,
        5.0,
        5.0,
        100.0,
        100.0,
    )

    straight_avg = 0.5 * (straight_left + straight_right)
    turning_avg = 0.5 * (turning_left + turning_right)
    assert turning_avg < straight_avg

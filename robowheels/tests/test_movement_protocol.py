from src.movement_protocol import MovementCommand, encode_json_line, parse_command_message


def test_parse_command_message_accepts_valid_json():
    cmd = parse_command_message('{"type":"command","throttle":0.5,"turn":-0.3,"source":"ai"}')
    assert cmd is not None
    assert cmd.throttle == 0.5
    assert cmd.turn == -0.3
    assert cmd.source == "ai"


def test_parse_command_message_rejects_wrong_type():
    cmd = parse_command_message('{"type":"status","throttle":0.1,"turn":0.2}')
    assert cmd is None


def test_command_serialization_is_line_delimited():
    raw = encode_json_line(MovementCommand(throttle=2.0, turn=-2.0, source="test").to_dict())
    assert raw.endswith(b"\n")
    parsed = parse_command_message(raw.decode("utf-8").strip())
    assert parsed is not None
    assert parsed.throttle == 1.0
    assert parsed.turn == -1.0

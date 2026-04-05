import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


def _clamp_unit(value: float) -> float:
    return max(-1.0, min(1.0, float(value)))


@dataclass
class MovementCommand:
    throttle: float
    turn: float
    source: str = "unknown"
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        self.throttle = _clamp_unit(self.throttle)
        self.turn = _clamp_unit(self.turn)
        if self.timestamp <= 0:
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "command",
            "throttle": self.throttle,
            "turn": self.turn,
            "source": self.source,
            "timestamp": self.timestamp,
        }


@dataclass
class MovementStatus:
    source: str
    requested_throttle: float
    requested_turn: float
    estimated_speed_mph: float
    estimated_throttle: float
    actual_turn_power: float
    left_speed_mph: float
    right_speed_mph: float
    left_brake: float
    right_brake: float
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        self.requested_throttle = _clamp_unit(self.requested_throttle)
        self.requested_turn = _clamp_unit(self.requested_turn)
        self.estimated_throttle = _clamp_unit(self.estimated_throttle)
        self.actual_turn_power = _clamp_unit(self.actual_turn_power)
        if self.timestamp <= 0:
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "status",
            "source": self.source,
            "requested_throttle": self.requested_throttle,
            "requested_turn": self.requested_turn,
            "estimated_speed_mph": self.estimated_speed_mph,
            "estimated_throttle": self.estimated_throttle,
            "actual_turn_power": self.actual_turn_power,
            "left_speed_mph": self.left_speed_mph,
            "right_speed_mph": self.right_speed_mph,
            "left_brake": self.left_brake,
            "right_brake": self.right_brake,
            "timestamp": self.timestamp,
        }


def parse_command_message(raw_line: str, default_source: str = "serial-ai") -> Optional[MovementCommand]:
    try:
        payload = json.loads(raw_line)
    except json.JSONDecodeError:
        return None

    if payload.get("type", "command") != "command":
        return None
    if "throttle" not in payload or "turn" not in payload:
        return None

    return MovementCommand(
        throttle=float(payload["throttle"]),
        turn=float(payload["turn"]),
        source=str(payload.get("source", default_source)),
        timestamp=float(payload.get("timestamp", 0.0)),
    )


def encode_json_line(payload: Dict[str, Any]) -> bytes:
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")

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
    source: str = "robobrain"
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
    timestamp: float

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> Optional["MovementStatus"]:
        if payload.get("type") != "status":
            return None
        required = (
            "source",
            "requested_throttle",
            "requested_turn",
            "estimated_speed_mph",
            "estimated_throttle",
            "actual_turn_power",
            "left_speed_mph",
            "right_speed_mph",
            "left_brake",
            "right_brake",
            "timestamp",
        )
        if any(key not in payload for key in required):
            return None
        return cls(
            source=str(payload["source"]),
            requested_throttle=float(payload["requested_throttle"]),
            requested_turn=float(payload["requested_turn"]),
            estimated_speed_mph=float(payload["estimated_speed_mph"]),
            estimated_throttle=float(payload["estimated_throttle"]),
            actual_turn_power=float(payload["actual_turn_power"]),
            left_speed_mph=float(payload["left_speed_mph"]),
            right_speed_mph=float(payload["right_speed_mph"]),
            left_brake=float(payload["left_brake"]),
            right_brake=float(payload["right_brake"]),
            timestamp=float(payload["timestamp"]),
        )


def parse_status_message(raw_line: str) -> Optional[MovementStatus]:
    try:
        payload = json.loads(raw_line)
    except json.JSONDecodeError:
        return None
    return MovementStatus.from_dict(payload)


def encode_json_line(payload: Dict[str, Any]) -> bytes:
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")

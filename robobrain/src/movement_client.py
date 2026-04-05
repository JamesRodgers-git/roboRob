import glob
import logging
import threading
import time
from typing import Optional

import serial
from serial.tools import list_ports

from src.movement_protocol import MovementCommand, MovementStatus, encode_json_line, parse_status_message
LOGGER = logging.getLogger("robobrain.serial")


class MovementClient:
    """
    Sends movement commands to RoboWheels and tracks the latest returned status.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        read_timeout_s: float = 0.02,
        reconnect_interval_s: float = 0.5,
    ):
        self.port = port
        self.baudrate = baudrate
        self.read_timeout_s = read_timeout_s
        self.reconnect_interval_s = reconnect_interval_s
        self.serial_conn: Optional[serial.Serial] = None
        self.reader_thread: Optional[threading.Thread] = None
        self.running = False
        self.data_lock = threading.Lock()
        self.conn_lock = threading.Lock()
        self._latest_status: Optional[MovementStatus] = None
        self._active_port: Optional[str] = None
        self._connect_error_logged = False
        self._read_error_logged = False
        self._write_error_logged = False

    def start(self) -> None:
        self.running = True
        self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.reader_thread.start()

    def stop(self) -> None:
        self.running = False
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=1.0)
        self.reader_thread = None
        self._close_connection()

    def _close_connection(self) -> None:
        with self.conn_lock:
            if self.serial_conn and self.serial_conn.is_open:
                try:
                    self.serial_conn.close()
                except Exception:
                    pass
            self.serial_conn = None
            self._active_port = None

    def _candidate_ports(self):
        if self.port and self.port.lower() != "auto":
            return [self.port]

        preferred = []
        for path in sorted(glob.glob("/dev/ttyACM*")):
            preferred.append(path)
        for path in sorted(glob.glob("/dev/ttyUSB*")):
            if path not in preferred:
                preferred.append(path)

        scored = []
        for info in list_ports.comports():
            dev = info.device
            text = f"{info.description} {info.manufacturer} {info.product}".lower()
            score = 0
            if dev.startswith("/dev/ttyACM"):
                score += 100
            if "gadget" in text:
                score += 60
            if "raspberry" in text:
                score += 50
            if "usb serial" in text or "cdc" in text or "acm" in text:
                score += 20
            if score > 0:
                scored.append((score, dev))
        for _, dev in sorted(scored, key=lambda x: (-x[0], x[1])):
            if dev not in preferred:
                preferred.append(dev)
        return preferred

    def _ensure_connection(self) -> Optional[serial.Serial]:
        with self.conn_lock:
            if self.serial_conn and self.serial_conn.is_open:
                return self.serial_conn

        for candidate in self._candidate_ports():
            try:
                conn = serial.Serial(
                    port=candidate,
                    baudrate=self.baudrate,
                    timeout=self.read_timeout_s,
                )
                with self.conn_lock:
                    self.serial_conn = conn
                    self._active_port = candidate
                self._connect_error_logged = False
                LOGGER.info("Connected to %s", candidate)
                return conn
            except Exception as exc:
                if not self._connect_error_logged:
                    self._connect_error_logged = True
                    LOGGER.info("Waiting for RoboWheels USB serial device: %s", exc)
        return None

    def _read_loop(self) -> None:
        while self.running:
            conn = self._ensure_connection()
            if conn is None:
                time.sleep(self.reconnect_interval_s)
                continue
            try:
                raw = conn.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                status = parse_status_message(line)
                if status is None:
                    continue
                with self.data_lock:
                    self._latest_status = status
            except (serial.SerialException, OSError):
                self._close_connection()
                time.sleep(self.reconnect_interval_s)
            except Exception as exc:
                if not self._read_error_logged:
                    self._read_error_logged = True
                    LOGGER.warning("Read/decode error: %s", exc)
                time.sleep(0.05)

    def send_command(self, throttle: float, turn: float, source: str = "robobrain") -> bool:
        conn = self._ensure_connection()
        if conn is None or not conn.is_open:
            return False
        command = MovementCommand(throttle=throttle, turn=turn, source=source)
        try:
            conn.write(encode_json_line(command.to_dict()))
            return True
        except (serial.SerialException, OSError):
            self._close_connection()
            return False
        except Exception as exc:
            if not self._write_error_logged:
                self._write_error_logged = True
                LOGGER.warning("Write error: %s", exc)
            return False

    def get_latest_status(self) -> Optional[MovementStatus]:
        with self.data_lock:
            return self._latest_status

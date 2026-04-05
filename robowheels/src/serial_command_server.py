import glob
import logging
import threading
import time
from typing import Optional

import serial

from src.movement_protocol import MovementCommand, MovementStatus, encode_json_line, parse_command_message
LOGGER = logging.getLogger("robowheels.serial")


class SerialCommandServer:
    """
    Reads movement commands from a serial line (newline-delimited JSON) and
    provides the most recent command to the drive loop.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        read_timeout_s: float = 0.02,
        reconnect_interval_s: float = 0.5,
        auto_device_glob: str = "/dev/ttyGS*",
    ):
        self.port = port
        self.baudrate = baudrate
        self.read_timeout_s = read_timeout_s
        self.reconnect_interval_s = reconnect_interval_s
        self.auto_device_glob = auto_device_glob
        self.serial_conn: Optional[serial.Serial] = None
        self.reader_thread: Optional[threading.Thread] = None
        self.running = False
        self.data_lock = threading.Lock()
        self.conn_lock = threading.Lock()
        self._latest_command: Optional[MovementCommand] = None
        self._latest_command_rx_time = 0.0
        self._active_port: Optional[str] = None
        self._connect_error_logged = False
        self._decode_error_logged = False
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

    def _candidate_ports(self):
        if self.port and self.port.lower() != "auto":
            return [self.port]
        return sorted(glob.glob(self.auto_device_glob))

    def _close_connection(self) -> None:
        with self.conn_lock:
            if self.serial_conn and self.serial_conn.is_open:
                try:
                    self.serial_conn.close()
                except Exception:
                    pass
            self.serial_conn = None
            self._active_port = None

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
                LOGGER.info("Listening on %s", candidate)
                return conn
            except Exception as exc:
                if not self._connect_error_logged:
                    self._connect_error_logged = True
                    LOGGER.info("Waiting for USB gadget serial: %s", exc)
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
                command = parse_command_message(line)
                if command is None:
                    continue
                with self.data_lock:
                    self._latest_command = command
                    self._latest_command_rx_time = time.time()
            except (serial.SerialException, OSError):
                self._close_connection()
                time.sleep(self.reconnect_interval_s)
            except Exception as exc:
                if not self._decode_error_logged:
                    self._decode_error_logged = True
                    LOGGER.warning("Read/decode error: %s", exc)
                time.sleep(0.05)

    def get_latest_command(self, max_age_s: float) -> Optional[MovementCommand]:
        now = time.time()
        with self.data_lock:
            command = self._latest_command
            rx_time = self._latest_command_rx_time
        if command is None:
            return None
        if rx_time <= 0 or (now - rx_time) > max_age_s:
            return None
        return command

    def send_status(self, status: MovementStatus) -> None:
        conn = self._ensure_connection()
        if conn is None or not conn.is_open:
            return
        try:
            conn.write(encode_json_line(status.to_dict()))
        except (serial.SerialException, OSError):
            self._close_connection()
        except Exception as exc:
            if not self._write_error_logged:
                self._write_error_logged = True
                LOGGER.warning("Write error: %s", exc)

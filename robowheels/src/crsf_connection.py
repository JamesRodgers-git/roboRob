"""
CRSF (Crossfire) connection module for Raspberry Pi 5
Handles serial communication and CRSF protocol parsing
Starts a reader thread that reads the latest frame and updates the channels and link statistics.
"""

import serial
import struct
import time
from typing import Optional, List, Dict, Tuple
import threading


class CRSFConnection:
    """Handles CRSF connection and data parsing"""
    
    # CRSF frame types
    FRAME_TYPE_CHANNELS = 0x16
    FRAME_TYPE_LINK_STATISTICS = 0x14
    FRAME_TYPE_BATTERY_SENSOR = 0x08
    FRAME_TYPE_ATTITUDE = 0x1E
    FRAME_TYPE_FLIGHT_MODE = 0x21
    
    def __init__(self, port: str = '/dev/ttyAMA0', baudrate: int = 420000):
        """
        Initialize CRSF connection
        
        Args:
            port: Serial port path (default: /dev/ttyAMA0 for Raspberry Pi)
            baudrate: Serial baudrate (default: 420000 for CRSF)
        """
        self.port = port
        self.baudrate = baudrate
        self.serial_conn: Optional[serial.Serial] = None
        self.channels = [1500] * 16  # 16 channels, default to 1500 (center)
        self.link_statistics = {}
        self.last_update = time.time()
        self.link_stats = {}
        self.latest_frame = None
        self.reader_thread = None
        self.data_lock = threading.Lock()
        self.running = False
        self.channel_updates = 0
        self.stats_updates = 0
        
    def connect(self) -> bool:
        """
        Open serial connection
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1  # Reduced timeout for lower latency
            )
            try:
                self.serial_conn.reset_input_buffer()
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"Failed to connect to {self.port}: {e}")
            return False
    
    def disconnect(self):
        """Close serial connection"""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            self.serial_conn = None

    def start(self) -> None:
        if not self.connect():
            raise RuntimeError("Failed to connect to CRSF receiver.")

        if self.is_connected():
            self.running = True
            self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.reader_thread.start()
        else:
            raise RuntimeError("Need to connect to CRSF receiver before starting.")
    
    def stop(self) -> None:
        self.running = False
        if self.reader_thread:
            self.reader_thread.join(timeout=1.0)
        self.reader_thread = None
        self.disconnect()

    def _read_loop(self) -> None:
        while self.running:
            if not self.is_connected():
                time.sleep(0.05)
                continue

            frame = self.read_latest_frame()
            if frame:
                with self.data_lock:
                    frame_type = frame.get("type", 0)
                    if frame_type == CRSFConnection.FRAME_TYPE_CHANNELS:
                        self.channels = frame.get("channels", self.channels)
                        self.channel_updates += 1
                        self.last_update = time.time()
                    elif frame_type == CRSFConnection.FRAME_TYPE_LINK_STATISTICS:
                        self.link_stats = frame.get("link_statistics", self.link_stats)
                        self.stats_updates += 1
            else:
                time.sleep(0.002)
    
    def _parse_channels(self, data: bytes) -> List[int]:
        """
        Parse channel data from CRSF frame
        
        Args:
            data: Frame payload data
            
        Returns:
            List of 16 channel values (988-2012 range)
        """
        if len(data) < 22:  # 16 channels * 11 bits = 22 bytes
            return self.channels
        
        # CRSF channels are 11-bit values packed into bytes
        channels = []
        for i in range(16):
            byte_index = (i * 11) // 8
            bit_index = (i * 11) % 8
            
            if byte_index + 1 < len(data):
                # Extract 11-bit value
                if bit_index <= 5:
                    # Value fits within 2 bytes
                    value = (data[byte_index] >> bit_index) | (data[byte_index + 1] << (8 - bit_index))
                    value &= 0x7FF  # Mask to 11 bits
                else:
                    # Value spans 3 bytes
                    value = (data[byte_index] >> bit_index) | (data[byte_index + 1] << (8 - bit_index))
                    value |= (data[byte_index + 2] << (16 - bit_index))
                    value &= 0x7FF
                
                # Convert to PWM value (988-2012)
                channels.append((value - 992) * 5 / 8 + 1500)
            else:
                channels.append(1500)  # Default center value
        
        return channels
    
    def _parse_link_statistics(self, data: bytes) -> Dict:
        """
        Parse link statistics from CRSF frame
        
        Args:
            data: Frame payload data
            
        Returns:
            Dictionary with link statistics
        """
        if len(data) < 6:
            return {}
        
        return {
            'uplink_rssi_ant1': data[0],
            'uplink_rssi_ant2': data[1],
            'uplink_link_quality': data[2],
            'uplink_snr': data[3],
            'active_antenna': data[4],
            'rf_mode': data[5],
            'uplink_power': data[6] if len(data) > 6 else 0,
            'downlink_rssi': data[7] if len(data) > 7 else 0,
            'downlink_link_quality': data[8] if len(data) > 8 else 0,
            'downlink_snr': data[9] if len(data) > 9 else 0,
        }
    
    def read_frame(self) -> Optional[Dict]:
        """
        Read and parse a CRSF frame from serial
        
        Returns:
            Dictionary with frame data or None if no valid frame
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            return None
        
        try:
            # Wait for frame start (0xC8 or 0xEE)
            start_byte = self.serial_conn.read(1)
            if not start_byte:
                return None
            
            # Check for valid start byte
            if start_byte[0] not in [0xC8, 0xEE]:
                return None
            
            # Read frame length
            length_byte = self.serial_conn.read(1)
            if not length_byte:
                return None
            
            frame_length = length_byte[0]
            if frame_length < 2 or frame_length > 64:
                return None
            
            # Read frame type and payload
            payload_length = frame_length - 2  # Exclude type and CRC
            frame_data = self.serial_conn.read(payload_length + 1)  # +1 for CRC
            if len(frame_data) < payload_length:
                return None
            
            frame_type = frame_data[0]
            payload = frame_data[1:payload_length+1]
            crc = frame_data[payload_length] if len(frame_data) > payload_length else 0
            
            # Parse based on frame type
            result = {
                'type': frame_type,
                'length': frame_length,
                'raw_payload': payload,
                'crc': crc
            }
            
            if frame_type == self.FRAME_TYPE_CHANNELS:
                self.channels = self._parse_channels(payload)
                result['channels'] = self.channels
                self.last_update = time.time()
            elif frame_type == self.FRAME_TYPE_LINK_STATISTICS:
                self.link_statistics = self._parse_link_statistics(payload)
                result['link_statistics'] = self.link_statistics
                self.last_update = time.time()
            
            return result
            
        except serial.SerialTimeoutException:
            return None
        except Exception as e:
            print(f"Error reading frame: {e}")
            return None

    def read_latest_frame(self, max_frames: int = 10, max_time_s: float = 0.02) -> Optional[Dict]:
        """Read and return the most recent frame by draining buffered data."""
        if not self.serial_conn or not self.serial_conn.is_open:
            return None

        latest = None
        start = time.monotonic()
        frames_read = 0
        while frames_read < max_frames and (time.monotonic() - start) < max_time_s:
            if self.serial_conn.in_waiting == 0:
                break
            frame = self.read_frame()
            if frame:
                latest = frame
                frames_read += 1
            else:
                break
        return latest
    
    def get_channels(self) -> List[int]:
        """Get current channel values (copy). For a consistent multi-field snapshot, use get_snapshot()."""
        with self.data_lock:
            return list(self.channels)

    def get_snapshot(self) -> Tuple[List[int], float, int, int, Dict]:
        """
        Return a consistent snapshot under one lock. Use this whenever you need
        multiple fields from CRSF so they don't change mid-read.
        Returns:
            (channels_copy, last_update_timestamp, channel_updates, stats_updates, link_stats_copy)
        """
        with self.data_lock:
            return (
                list(self.channels),
                self.last_update,
                self.channel_updates,
                self.stats_updates,
                dict(self.link_stats),
            )
    
    def get_link_statistics(self) -> Dict:
        """Get current link statistics (from reader thread state). For a consistent snapshot with channels, use get_snapshot()."""
        with self.data_lock:
            return dict(self.link_stats)
    
    def is_connected(self) -> bool:
        """Check if connection is active"""
        return self.serial_conn is not None and self.serial_conn.is_open
    
    def get_last_update_time(self) -> float:
        """Get timestamp of last successful data update"""
        return self.last_update

    def send_frame(self, frame_type: int, payload: bytes):
        """Send a CRSF frame to the serial port"""
        if not self.serial_conn or not self.serial_conn.is_open:
            return False
        
        frame = struct.pack('BB', frame_type, len(payload)) + payload
        self.serial_conn.write(frame)
        return True
    

import smbus2

# MCP4725 fast-mode write: first byte = 0x00 | (value >> 8), second byte = value & 0xFF
MCP4725_FAST_WRITE = 0x00


class MotorController:
    def __init__(self, address: int, min_speed: int, max_speed: int, reset_speed: int, max_speed_mph: int):
        self.bus = smbus2.SMBus(1)
        self.address = address
        self.speed = 0
        self.min_speed = min_speed
        self.max_speed = max_speed
        self.reset_speed = reset_speed
        self.max_speed_mph = max_speed_mph
        self._i2c_error_logged = False
        self._write_dac(0)

    def _write_dac(self, value: int) -> None:
        """Write 12-bit value to MCP4725 (0-4095). Sends 2 bytes: upper 4 bits, lower 8 bits."""
        value = max(self.min_speed, min(self.max_speed, value))
        first_byte = MCP4725_FAST_WRITE | (value >> 8)
        second_byte = value & 0xFF
        try:
            self.bus.write_i2c_block_data(self.address, first_byte, [second_byte])
        except OSError as e:
            if not self._i2c_error_logged:
                self._i2c_error_logged = True
                print(f"[MotorController 0x{self.address:02x}] I2C error (will keep running): {e}")
                print(f"  Last value attempted: {value} (0=stop, 4095=full). Check: I2C enabled, wiring, DAC address, permissions.")

    def set_speed(self, speed: int):
        """Set speed as percentage (0-100) or raw 12-bit value (0-4095)."""
        if speed > 100:
            self.speed = max(self.min_speed, min(self.max_speed, int(speed)))
            self._write_dac(self.speed)
            return

        self.set_speed_percent(speed)

    def set_speed_percent(self, speed_percent: float):
        """Set speed as a percentage of the max speed (0-100)."""
        speed = int(speed_percent * self.max_speed / 100)
        self.speed = max(self.min_speed, min(self.max_speed, int(speed)))
        self._write_dac(self.speed)

    def set_speed_mph(self, speed_mph: float):
        """Set speed using mph and the configured max speed."""
        if self.max_speed_mph <= 0:
            self.set_speed_percent(0)
            return
        speed_percent = (speed_mph / self.max_speed_mph) * 100
        self.set_speed_percent(speed_percent)

    def i2c_reset(self):
        self._write_dac(self.reset_speed)
        self.speed = self.reset_speed

    def get_speed_percentage(self):
        """Get speed as a percentage of the max speed"""
        return self.speed / self.max_speed * 100
    
    def get_speed_mph(self):
        """Get speed in miles per hour"""
        return self.speed / self.max_speed * self.max_speed_mph

try:
    from gpiozero import PWMOutputDevice
except ImportError:
    PWMOutputDevice = None

try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None


"""
Brake controller for the RoboWheels.
PWM output for the left and right brake independently.
Brake values are 0-100: 0 = full brake, 100 = release (spring brake).
"""
class BrakeController:
    def __init__(self, left_brake_pin: int, right_brake_pin: int, pwm_hz: int = 1000):
        self.left_brake_pin = left_brake_pin
        self.right_brake_pin = right_brake_pin
        self.pwm_hz = pwm_hz
        self.left_pwm = None
        self.right_pwm = None
        self._gpio_backend = None  # "gpiozero" or "rpi"
        self._left_value = 0.0
        self._right_value = 0.0

        # Prefer gpiozero (works on Pi 5; RPi.GPIO raises RuntimeError on Pi 5)
        if PWMOutputDevice is not None:
            self._init_gpiozero()
        elif GPIO is not None:
            self._init_rpi_gpio()
        # else: no backend (e.g. dev machine)

    def _init_gpiozero(self):
        self.left_pwm = PWMOutputDevice(
            self.left_brake_pin, frequency=self.pwm_hz, initial_value=0.0
        )
        self.right_pwm = PWMOutputDevice(
            self.right_brake_pin, frequency=self.pwm_hz, initial_value=0.0
        )
        self._gpio_backend = "gpiozero"

    def _init_rpi_gpio(self):
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(self.left_brake_pin, GPIO.OUT)
            GPIO.setup(self.right_brake_pin, GPIO.OUT)
            self.left_pwm = GPIO.PWM(self.left_brake_pin, self.pwm_hz)
            self.right_pwm = GPIO.PWM(self.right_brake_pin, self.pwm_hz)
            self.left_pwm.start(0)
            self.right_pwm.start(0)
            self._gpio_backend = "rpi"
        except RuntimeError as e:
            # Pi 5: "Cannot determine SOC peripheral base address"
            if PWMOutputDevice is not None:
                self._init_gpiozero()
            else:
                raise RuntimeError(
                    "RPi.GPIO does not support this board (e.g. Raspberry Pi 5). "
                    "Install gpiozero: pip install gpiozero"
                ) from e

    def is_active(self) -> bool:
        """True if PWM is actually driving pins."""
        return self.left_pwm is not None and self.right_pwm is not None

    def _apply(self, pwm, value):
        if pwm is None:
            return
        v = max(0.0, min(100.0, float(value)))
        if self._gpio_backend == "gpiozero":
            pwm.value = v / 100.0
        else:
            pwm.ChangeDutyCycle(v)

    def set_brake(self, left_value: float, right_value: float):
        self._left_value = max(0.0, min(100.0, float(left_value)))
        self._right_value = max(0.0, min(100.0, float(right_value)))
        self._apply(self.left_pwm, self._left_value)
        self._apply(self.right_pwm, self._right_value)

    def get_brake(self):
        return self._left_value, self._right_value

    def cleanup(self):
        if self.left_pwm is None and self.right_pwm is None:
            return
        if self._gpio_backend == "gpiozero":
            if self.left_pwm:
                self.left_pwm.close()
            if self.right_pwm:
                self.right_pwm.close()
        elif self._gpio_backend == "rpi" and GPIO is not None:
            if self.left_pwm:
                self.left_pwm.stop()
            if self.right_pwm:
                self.right_pwm.stop()
            GPIO.cleanup()
        self.left_pwm = None
        self.right_pwm = None
        self._gpio_backend = None

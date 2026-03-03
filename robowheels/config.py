BRAKE_LEFT_PIN = 17
BRAKE_RIGHT_PIN = 27

CRSF_PORT = '/dev/ttyAMA0'
CRSF_BAUD_RATE = 420000
CRSF_LEFT_CHANNEL = 1
CRSF_RIGHT_CHANNEL = 2
CRSF_CHANNEL_DEADBAND = 30
CRSF_CHANNEL_MIN = 988
CRSF_CHANNEL_MAX = 2012
SIGNAL_STALE_TIMEOUT_S = 0.5

MOTOR_CONTROLLER1_ADDRESS = 0x61
MOTOR_CONTROLLER2_ADDRESS = 0x60

MOTOR_CONTROLLER_MIN_SPEED = 0
MOTOR_CONTROLLER_MAX_SPEED = 4095
MOTOR_CONTROLLER_RESET_SPEED = 0

MAX_SPEED = 5 # estimated top speed in miles per hour
MAX_ACCELERATION = 4 # maximum acceleration limit in miles per hour per second
MAX_LATERAL_ACCELERATION = 1 # maximum lateral acceleration limit in miles per hour per second
MAX_TURN_RATE = 100 # maximum turn rate limit in degrees per second
WHEEL_BASE_METERS = 0.6 # distance between wheels, update to match your chair
CONTROL_LOOP_HZ = 50

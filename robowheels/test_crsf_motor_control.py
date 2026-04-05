import time
import config
from src import motor_controller, crsf_connection

def test_crsf_motor_control():
    crsf_controller = crsf_connection.CRSFConnection()
    crsf_controller.connect()

    channels = crsf_controller.get_channels()

    motor_controller1 = motor_controller.MotorController(
        address=config.MOTOR_CONTROLLER1_ADDRESS,
        min_speed=config.MOTOR_CONTROLLER_MIN_SPEED,
        max_speed=config.MOTOR_CONTROLLER_MAX_SPEED,
        reset_speed=config.MOTOR_CONTROLLER_RESET_SPEED,
        max_speed_mph=config.MAX_SPEED,
    )
    motor_controller2 = motor_controller.MotorController(
        address=config.MOTOR_CONTROLLER2_ADDRESS,
        min_speed=config.MOTOR_CONTROLLER_MIN_SPEED,
        max_speed=config.MOTOR_CONTROLLER_MAX_SPEED,
        reset_speed=config.MOTOR_CONTROLLER_RESET_SPEED,
        max_speed_mph=config.MAX_SPEED,
    )

    motor_controller1.set_speed(1000)
    motor_controller2.set_speed(1000)
    time.sleep(1)

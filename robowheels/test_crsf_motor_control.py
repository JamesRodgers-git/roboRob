import time
from src import motor_controller, crsf_connection

def test_crsf_motor_control():
    crsf_controller = crsf_connection.CRSFConnection()
    crsf_controller.connect()

    channels = crsf_controller.get_channels()

    motor_controller1 = motor_controller.MotorController(0x60)
    motor_controller2 = motor_controller.MotorController(0x61)

    motor_controller1.set_speed(1000)
    motor_controller2.set_speed(1000)
    time.sleep(1)
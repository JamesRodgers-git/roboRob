from src import crsf_connection

def test_crsf_connection():
    crsf_controller = crsf_connection.CRSFConnection()
    crsf_controller.connect()
    print("CRSF connection successful")
    crsf_controller.disconnect()
    print("CRSF connection disconnected")



if __name__ == "__main__":
    test_crsf_connection()
from src.hrd_control import ct_controller

def _get_settings() -> dict:
    return {
        "serial_baud_rate": 9600,
        "serial_timeout": 1,
        "valve_filling_position": "A",
        "valve_injection_position": "B",
        "sample_loop_flush_time": 30,
        "valve_switching_timeout": 10,
        "lcms_response_timeout": 20,
        "lcms_sample_prep_timeout": 300,
        "sample_detection_timeout": 1200,
    }

def test_start_call():
    controller = ct_controller.Controller(hardware_settings=_get_settings())
    controller._send_start_request()
    controller._wait_on_lcms_start()
    print("SUCCESS")
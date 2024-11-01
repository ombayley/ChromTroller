# mock_lcms_device.py

class MockLCMSDevice:
    """
    A mock version of the LCMSDevice class for testing without hardware.
    """
    standard_acknowledge = 'ACK'
    valve_state = "A"

    def get_id(self) -> str:
        return 'MockLCMSDevice'

    def get_valve_pos(self) -> str:
        # Return a default valve position
        return self.valve_state

    def get_lcms_power(self) -> str:
        # Simulate LCMS device being powered on
        return '1'

    def send_start_request(self) -> str:
        # Simulate sending a start request
        return self.standard_acknowledge

    def get_lcms_start_request(self) -> str:
        # Simulate LCMS acknowledging the start request
        return '0'  # '0' indicates acknowledgement in your script

    def get_lcms_start(self) -> str:
        # Simulate LCMS sending the 'start' signal
        return '0'

    def set_valve_pos(self, desired_position: str) -> None:
        # Simulate setting the valve position
        self.valve_state = desired_position
        pass

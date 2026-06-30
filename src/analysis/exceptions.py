
class ParsingError(Exception):
    """Exception thrown when file parsing fails"""

class FailedToConverge(Exception):
    """This exception indicates that a routine failed to converge"""

    def __init__(self, *args):
        super().__init__(*args)
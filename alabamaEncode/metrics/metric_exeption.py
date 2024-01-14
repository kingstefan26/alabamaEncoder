class MetricException(Exception):
    """Base class for exceptions in this module."""

    pass


class VmafException(MetricException):
    """Exception raised for errors in the VMAF metric.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

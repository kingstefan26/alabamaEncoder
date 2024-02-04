class MetricException(Exception):
    """Base class for exceptions in this module."""

    pass


class VmafException(MetricException):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class Ssimu2Exception(MetricException):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

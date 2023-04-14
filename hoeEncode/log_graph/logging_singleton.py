

class LoggingSingleton:
    __instance = None

    @staticmethod
    def get_instance():
        """ Static access method. """
        if LoggingSingleton.__instance is None:
            LoggingSingleton()
        return LoggingSingleton.__instance

    def __init__(self):
        """ Virtually private constructor. """
        if LoggingSingleton.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            LoggingSingleton.__instance = self

    def set_logger(self, logger):
        self.logger = logger

    def get_logger(self):
        return self.logger
from abc import abstractmethod
from typing import Any


class BaseCommandObject(object):
    @abstractmethod
    def run(self) -> Any:
        pass


def run_command(command: BaseCommandObject):
    """
    Wrapper around object.run() because its easier to run_command(object) than object.run() in certain situations
    """
    return command.run()

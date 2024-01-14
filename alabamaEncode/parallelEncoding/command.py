from abc import abstractmethod
from typing import Any


class BaseCommandObject(object):
    @abstractmethod
    def run(self) -> Any:
        pass

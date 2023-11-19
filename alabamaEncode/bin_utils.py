import os
from shutil import which

__all__ = ["get_binary"]


def _check_bin(path) -> bool:
    if path is None:
        return False
    _which = which(path) is not None
    if _which:
        return True
    else:
        if os.path.exists(path):
            return True
        else:
            return False


class BinaryNotFound(Exception):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return f"Binary {self.name} not found"


def get_binary(name):
    _bin = os.getenv(f"{name.upper()}_CLI_PATH", name)
    if _check_bin(_bin):
        return _bin
    else:
        raise BinaryNotFound(name)

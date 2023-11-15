import os
from shutil import which


def doesBinaryExist(pathOrLocation):
    if pathOrLocation is None:
        return False
    _which = which(pathOrLocation) is not None
    if _which:
        return True
    else:
        if os.path.exists(pathOrLocation):
            return True
        else:
            return False

from shutil import which


def doesBinaryExist(pathOrLocation):
    return which(pathOrLocation) is not None

"""
Provides a central place to get the path to the binaries, and checks if they exist.
Also includes checks if the binaries are what we need (e.g., ffmpeg has been compiled with certain flags)
"""

import os
from shutil import which

__all__ = ["get_binary", "register_bin", "verify_ffmpeg_library", "check_bin"]

from typing import List

from alabamaEncode.core.util.cli_executor import run_cli

bins = []


def check_bin(path) -> bool:
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


class FFmpegNotCompiledWithLibrary(Exception):
    def __init__(self, lib_name):
        self.lib_name = lib_name

    def __str__(self):
        return f"ffmpeg is not compiled with {self.lib_name}"


ffmpeg_build_conf = ""


def check_ffmpeg_libraries(lib_name: str) -> bool:
    """
    Checks if the ffmpeg libraries are compiled with the given library
    :param lib_name: name of the library
    :return: True if the library is compiled, False otherwise
    """
    global ffmpeg_build_conf
    if ffmpeg_build_conf == "":
        ffmpeg_build_conf = (
            run_cli(f"{get_binary('ffmpeg')} -v error -buildconf").verify().get_output()
        )
    return ffmpeg_build_conf.find(lib_name) != -1


def verify_ffmpeg_library(lib_name: [str | List[str]]) -> None:
    """
    Checks if the ffmpeg libraries are compiled with the given library, and raises an exception if it is not
    :param lib_name: name of the library
    """
    if isinstance(lib_name, str):
        lib_name = [lib_name]
    for lib in lib_name:
        if not check_ffmpeg_libraries(lib):
            raise FFmpegNotCompiledWithLibrary(lib)


def check_for_ffmpeg_libraries(lib_name: [str | List[str]]) -> bool:
    """
    Checks if the ffmpeg libraries are compiled with the given library, and returns True if it is, False otherwise
    :param lib_name: name of the library(s)
    :return: True if the library is compiled, False otherwise
    """
    if isinstance(lib_name, str):
        lib_name = [lib_name]
    for lib in lib_name:
        if not check_ffmpeg_libraries(lib):
            return False
    return True


class BinaryNotFound(Exception):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return (
            f"Binary {self.name} not found,"
            f" set the {self.name.upper()}_CLI_PATH environment variable to the path of the binary."
        )


def register_bin(name, cli):
    bins.append((name, cli))


def get_binary(name):
    _bin = os.getenv(f"{name.upper()}_CLI_PATH", name)
    if _bin == name:
        for _name, _cli in bins:
            if _name == name:
                _bin = _cli
                break
    if _bin is None:
        _bin = os.path.expanduser(f"~/.alabamaEncoder/bin/{name}")
    if check_bin(_bin):
        return _bin
    else:
        raise BinaryNotFound(name)

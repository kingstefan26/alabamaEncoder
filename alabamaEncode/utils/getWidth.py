import os

from alabamaEncode.utils.execute import syscmd


def get_width(in_path):
    if not os.path.exists(in_path):
        raise FileNotFoundError(f"File {in_path} does not exist")
    argv_ = f'ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "{in_path}"'
    result = syscmd(argv_)
    result = result.strip()
    result = result.replace(",", "")
    return int(result)

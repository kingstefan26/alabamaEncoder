from alabamaEncode.utils.execute import syscmd


def is_hdr(vid_path: str):
    """Check if a video is HDR"""
    command = f'ffprobe -v quiet -show_entries stream=color_transfer -of csv=p=0 -select_streams v:0 "{vid_path}"'

    out = syscmd(command)

    out = out.strip()

    return True if out != "bt709" else False

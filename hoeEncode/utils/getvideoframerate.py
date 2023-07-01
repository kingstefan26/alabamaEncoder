import subprocess


def get_video_frame_rate(filename) -> float:
    result = subprocess.run([
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        "-show_entries",
        "stream=r_frame_rate",
        filename,
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    result_string = result.stdout.decode('utf-8').split()[0].split('/')
    if result_string == '':
        raise Exception('Could not get frame rate')
    fps = float(result_string[0]) / float(result_string[1])
    return fps

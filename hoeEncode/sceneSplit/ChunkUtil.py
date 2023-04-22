from hoeEncode.utils.resolutionLadder import get_quality_preset
from hoeEncode.utils.getvideoframerate import get_video_frame_rate


def create_chunk_ffmpeg_pipe_command(resolution_canon_name="source", start_clip_time=0, end_clip_time=0, in_path="./no",
                                     framerate=-1):
    if framerate == -1:
        framerate = get_video_frame_rate(in_path)

    end_thingy = (float(end_clip_time) / framerate)
    start_time = (float(start_clip_time) / framerate)
    duration = (end_thingy - start_time)

    end_command = "ffmpeg -v error -nostdin "

    if start_clip_time != -1:
        end_command += f"-ss {str(start_time)} "

    end_command += f"-i {in_path} "

    if end_clip_time != -1:
        end_command += f"-t {str(duration)} "

    end_command += f"-an -sn -strict -1 {get_quality_preset(resolution_canon_name)} -f yuv4mpegpipe - "

    return end_command


def create_chunk_ffmpeg_pipe_command_using_chunk(in_chunk=None, resolution_canon_name="source", crop_string='',
                                                 bit_depth: (8 | 10) = 8):
    end_command = "ffmpeg -v error -nostdin "
    end_command += in_chunk.get_ss_ffmpeg_command_pair()
    if bit_depth == 10:
        end_command += f"-pix_fmt yuv420p10le "
    else:
        end_command += f"-pix_fmt yuv420p "
    if not '-vf' in crop_string and not crop_string == '':
        crop_string = f'-vf {crop_string}'
    end_command += f" -an -sn -strict -1 {get_quality_preset(resolution_canon_name)} {crop_string} -f yuv4mpegpipe - "

    return end_command

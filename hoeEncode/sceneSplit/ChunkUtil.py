from hoeEncode.utils.getvideoframerate import get_video_frame_rate


def create_chunk_ffmpeg_pipe_command(filter_graph="", start_frame=0, end_frame=0, in_path=None,
                                     framerate=-1):
    """
    :param filter_graph: ffmpeg -vf or -fiter_graph, used for scaling cropping hdr tone mapping etc.
    :param start_frame: start of the chunk in frames
    :param end_frame:  end of the chunk in frames
    :param in_path: path to the video file
    :param framerate: framerate of the file, not necessary
    :return: ffmpeg cli that will pipe the chunk to stdout
    """
    if framerate == -1:
        framerate = get_video_frame_rate(in_path)

    end_thingy = (float(end_frame) / framerate)
    start_time = (float(start_frame) / framerate)
    duration = (end_thingy - start_time)

    return f"ffmpeg -v error -nostdin -ss {start_time} -i {in_path} -t {duration} -an -sn" \
           f" -strict -1 {filter_graph} -f yuv4mpegpipe - "


def create_chunk_ffmpeg_pipe_command_using_chunk(in_chunk=None, crop_string='',
                                                 bit_depth: (8 | 10) = 8):
    end_command = f"ffmpeg -v error -nostdin {in_chunk.get_ss_ffmpeg_command_pair()}"

    if bit_depth == 10:
        end_command += f"-pix_fmt yuv420p10le "
    else:
        end_command += f"-pix_fmt yuv420p "

    if not '-vf' in crop_string and not crop_string == '':
        crop_string = f'-vf {crop_string}'

    end_command += f" -an -sn -strict -1 {crop_string} -f yuv4mpegpipe - "

    return end_command

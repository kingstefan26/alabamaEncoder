from alabamaEncode.utils.getFramerate import get_video_frame_rate
from alabamaEncode.utils.getHeight import get_height
from alabamaEncode.utils.getWidth import get_width


class ChunkObject:
    """
    Ffmpeg based video chunk object
    example:
    If we want to extract a chunk that starts at frame 100 and ends at frame 200:
    obj = ChunkObject(100,200,"infile.mkv")
    f'ffmpeg {obj.get_ss_ffmpeg_command_pair()} outfile.mkv'
    """

    def __init__(
        self,
        first_frame_index=-1,
        last_frame_index=-1,
        path="",
        framerate=-1,
        chunk_index=-1,
        height=-1,
        width=-1,
        complexity=-1.0,
    ):
        self.path = path  # path to the source video file
        self.last_frame_index = last_frame_index
        self.first_frame_index = first_frame_index
        self.framerate = framerate
        self.width = width
        self.height = height
        self.complexity = complexity
        self.length = self.last_frame_index - self.first_frame_index
        self.end_override = -1  # ends the chunk after `end_override` frames if set
        self.chunk_index = chunk_index
        self.chunk_path = ""  # path to the encoded (or not yet) chunk file
        self.chunk_done = False
        self.ideal_bitrate = -1

    def __str__(self):
        return f"ChunkObject({self.first_frame_index}, {self.last_frame_index}, {self.path}, {self.framerate})"

    def get_frame_count(self):
        return self.last_frame_index - self.first_frame_index

    def get_lenght(self) -> float:
        # get framerate
        if self.framerate == -1:
            self.framerate = get_video_frame_rate(self.path)

        local_overriden_end = self.last_frame_index
        if self.end_override != -1 and self.length > self.end_override:
            local_overriden_end = self.first_frame_index + self.end_override

        end_thingy = float(local_overriden_end) / self.framerate
        start_time = float(self.first_frame_index) / self.framerate
        return end_thingy - start_time

    def get_ss_ffmpeg_command_pair(self) -> str:
        """
        :return: an '-ss 12 clip.mp4 -t 2' ffmpeg command from start frame index and end frame index
        """

        if self.first_frame_index == -1 or self.last_frame_index == -1:
            return f" -i {self.path} "

        if self.framerate == -1:
            self.framerate = get_video_frame_rate(self.path)

        # if we override the end, we end at "start frame # + override"
        local_overriden_end = self.last_frame_index
        if self.end_override != -1 and self.length > self.end_override:
            local_overriden_end = self.first_frame_index + self.end_override

        end_thingy = float(local_overriden_end) / self.framerate
        start_time = float(self.first_frame_index) / self.framerate
        duration = end_thingy - start_time

        return f' -ss {str(start_time)} -i "{self.path}" -t {str(duration)} '

    def get_width(self) -> int:
        if self.width == -1:
            self.width = get_width(self.path)
        return self.width

    def get_height(self) -> int:
        if self.height == -1:
            self.height = get_height(self.path)
        return self.height

    def create_chunk_ffmpeg_pipe_command(self, video_filters="", bit_depth=10) -> str:
        """
        :param video_filters: ffmpeg vf filters, e.g., scaling tonemapping
        :param bit_depth: bit depth of the output stream 8 or 10
        :return: a 'ffmpeg ... |' command string that pipes a y4m stream into stdout
        """
        end_command = f"ffmpeg -v error -nostdin {self.get_ss_ffmpeg_command_pair()} -pix_fmt yuv420p10le "

        if bit_depth == 8:
            end_command = end_command.replace("10le", "")

        if not "-vf" in video_filters and not video_filters == "":
            video_filters = f"-vf {video_filters}"

        end_command += f" -an -sn -strict -1 {video_filters} -f yuv4mpegpipe - "

        return end_command

    def log_prefix(self):
        return f"[{self.chunk_index}] "


def test_1():
    chunk = ChunkObject(
        path="video.mkv", first_frame_index=100, last_frame_index=200, framerate=24
    )
    expected_1 = " -ss 4.166666666666667 -i video.mkv -t 4.166666666666667 "
    result_1 = chunk.get_ss_ffmpeg_command_pair()
    print(result_1)
    if expected_1 == result_1:
        print("Test 1 passed")

    expected_2 = " -ss 4.166666666666667 -i video.mkv -t 4.166666666666667 "
    chunk.end_override = 150
    result_2 = chunk.get_ss_ffmpeg_command_pair()
    print(result_2)
    if result_2 == expected_2:
        print("Test 2 passed")

    expected_3 = " -ss 4.166666666666667 -i video.mkv -t 2.083333333333333 "
    chunk.end_override = 50
    result_3 = chunk.get_ss_ffmpeg_command_pair()
    print(result_3)
    if result_3 == expected_3:
        print("Test 3 passed")


def test_2():
    chunk = ChunkObject(path="video.mkv")
    expected_1 = " -i video.mkv "
    result_1 = chunk.get_ss_ffmpeg_command_pair()
    print(result_1)
    if expected_1 == result_1:
        print("Test 1 passed")

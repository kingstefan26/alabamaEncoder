import os
from multiprocessing.pool import ThreadPool
from typing import List

from tqdm import tqdm

from alabamaEncode.ffmpeg import Ffmpeg
from alabamaEncode.path import PathAlabama


class WrongFrameCountError(Exception):
    def __init__(self):
        super().__init__("The frame count of the chunk is not equal to the expected")


class FfmpegDecodeFailException(Exception):
    def __init__(self):
        super().__init__("Ffmpeg failed to decode the video")


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

    def get_frame_count(self) -> int:
        return self.last_frame_index - self.first_frame_index

    def get_lenght(self) -> float:
        # get framerate
        if self.framerate == -1:
            self.framerate = Ffmpeg.get_video_frame_rate(PathAlabama(self.path))

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

        # case where we don't have a start or end frame index so include the whole video
        if self.first_frame_index == -1 or self.last_frame_index == -1:
            return f' -i "{self.path}" '

        # get framerate
        if self.framerate == -1:
            self.framerate = Ffmpeg.get_video_frame_rate(PathAlabama(self.path))

        # if we override the end, we end at "start frame # + override"
        local_overriden_end = self.last_frame_index
        if self.end_override != -1 and self.length > self.end_override:
            local_overriden_end = self.first_frame_index + self.end_override

        # get the start time and duration
        end_thingy = float(local_overriden_end) / self.framerate
        start_time = float(self.first_frame_index) / self.framerate
        duration = end_thingy - start_time

        return f' -ss {str(start_time)} -i "{self.path}" -t {str(duration)} '

    def get_width(self) -> int:
        if self.width == -1:
            self.width = Ffmpeg.get_width(PathAlabama(self.path))
        return self.width

    def get_height(self) -> int:
        if self.height == -1:
            self.height = Ffmpeg.get_height(PathAlabama(self.path))
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

    def verify_integrity(self) -> bool:
        """
        checks the integrity of a chunk
        :return: True if invalid
        """
        self.chunk_done = False

        try:
            path = PathAlabama(self.chunk_path)
            if Ffmpeg.check_for_invalid(path):
                raise FfmpegDecodeFailException()

            actual_frame_count = Ffmpeg.get_frame_count(path)
            expected_frame_count = self.last_frame_index - self.first_frame_index

            if actual_frame_count != expected_frame_count:
                raise WrongFrameCountError()
        except Exception as e:
            if isinstance(e, WrongFrameCountError) or isinstance(
                e, FfmpegDecodeFailException
            ):
                tqdm.write(f"{self.log_prefix()} failed the integrity because: {e} 🤕")
            return True

        self.chunk_done = True
        return False


def process_chunk(args) -> ChunkObject or None:
    """
    if chunk is invalid return it, else return None
    :param args:
    :return:
    """
    chunk, pbar = args
    result: bool = chunk.verify_integrity()
    pbar.update()
    return chunk if result else None


class ChunkSequence:
    """
    A sequence of chunks.
    """

    def __init__(self, chunks: List[ChunkObject]):
        self.chunks = chunks
        self.input_file = ""

    def get_specific_chunk(self, index: int) -> ChunkObject:
        return self.chunks[index]

    def __len__(self):
        return len(self.chunks)

    def __getitem__(self, index):
        return self.chunks[index]

    def setup_paths(self, temp_folder: str, extension: str):
        """
        sets up the paths for the chunks, in the appropriate temp folder, and with the appropriate extension
        :param extension: .ivf .mkv etc.
        :param temp_folder: the temp folder to put the chunks in
        :return: Void
        """
        for c in self.chunks:
            # /home/user/encode/show/temp/1.ivf
            # or
            # /home/user/encode/show/temp/1.mkv
            c.chunk_path = f"{temp_folder}{c.chunk_index}{extension}"

    def sequence_integrity_check(self, check_workers: int = 5) -> bool:
        """
        checks the integrity of the chunks, and removes any that are invalid, and see if all are done
        :param check_workers: number of workers to use for the check
        :return: true if there are broken chunks / not all chunks are done
        """

        print("Preforming integrity check 🥰")
        seq_chunks = list(self.chunks)
        total_chunks = len(seq_chunks)

        with tqdm(total=total_chunks, desc="Checking files", unit="file") as pbar:
            with ThreadPool(check_workers) as pool:
                process_args = [(c, pbar) for c in seq_chunks]
                invalid_chunks: List[ChunkObject or None] = list(
                    pool.imap(process_chunk, process_args)
                )

        invalid_chunks: List[ChunkObject] = [
            chunk for chunk in invalid_chunks if chunk is not None
        ]

        del_count = 0

        if len(invalid_chunks) > 0:
            for c in invalid_chunks:
                if os.path.exists(c.chunk_path):
                    os.remove(c.chunk_path)
                    del_count = +1
            return True
        print(f"Deleted {del_count} invalid files 😂")

        undone_chunks_count = len([c for c in self.chunks if not c.chunk_done])

        if undone_chunks_count > 0:
            print(
                f"Only {len(self.chunks) - undone_chunks_count}/{len(self.chunks)} chunks are done 😏"
            )
            return True

        print("All chunks passed integrity checks 🤓")
        return False


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

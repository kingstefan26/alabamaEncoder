import os

from alabamaEncode.alabamaPath import PathAlabama
from alabamaEncode.utils.execute import syscmd


class Ffmpeg:
    @staticmethod
    def check_for_invalid(path: PathAlabama) -> bool:
        """
        Checks if the file is not a valid video file
        :param path: PathAlabama instance
        :return: True if the video is invalid, False if the video is valid
        """
        path.check_video()
        out = syscmd(f"ffmpeg -v error -i {path.get_safe()} -c copy -f null -")
        # if there is no output and syscmd returns status code 0, then the file is valid
        if isinstance(out, int) and out == 0:
            return False
        else:
            return True

    @staticmethod
    def get_frame_count(path: PathAlabama) -> int:
        """
        Returns the frame count of the video
        :param path: path to the video
        :return: int
        """
        path.check_video()
        arg = (
            f"ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets "
            f"-of csv=p=0 {path.get_safe()}"
        )
        result = syscmd(arg)
        result = result.replace("\n", "").replace(",", "")
        return int(result)

    @staticmethod
    def get_video_length(path: PathAlabama, sexagesimal=False) -> float | str:
        """
        Returns the video length in seconds
        :param sexagesimal: If True, returns the length in sexagesimal format
        :param path: Path to the video
        :return: float
        """
        path.check_video()
        sex = ""
        if sexagesimal:
            sex = "-sexagesimal"
        cli = (
            f"ffprobe -v error -show_entries format=duration {sex} -of default=noprint_wrappers=1:nokey=1 "
            f"{path.get_safe()}"
        )
        result = syscmd(cli)

        if isinstance(result, str):
            if "N/A" in result or "Invalid data found" in result:
                raise ValueError(f"File {path} is invalid, (encoded with aomenc?)")

        if sex:
            return result
        return float(result)

    @staticmethod
    def get_total_bitrate(path: PathAlabama) -> float:
        path.check_video()
        return os.path.getsize(path.get()) * 8 / Ffmpeg.get_video_length(path)

    @staticmethod
    def get_height(path: PathAlabama) -> int:
        path.check_video()
        argv_ = f"ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 {path.get_safe()}"
        result = syscmd(argv_)
        result = result.strip()
        result = result.replace(",", "")
        return int(result)

    @staticmethod
    def get_width(path: PathAlabama) -> int:
        path.check_video()
        argv_ = f"ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 {path.get_safe()}"
        result = syscmd(argv_)
        result = result.strip()
        result = result.replace(",", "")
        return int(result)

    @staticmethod
    def is_hdr(path: PathAlabama) -> bool:
        """Check if a video is HDR"""
        path.check_video()
        command = (
            f"ffprobe -v quiet -show_entries stream=color_transfer "
            f"-of csv=p=0 -select_streams v:0 {path.get_safe()}"
        )

        out = syscmd(command)

        out = out.strip()

        return True if out != "bt709" else False

    @staticmethod
    def get_video_frame_rate(file: PathAlabama) -> float:
        file.check_video()
        cli = (
            f"ffprobe -v error -select_streams v -of default=noprint_wrappers=1:nokey=1"
            f" -show_entries stream=r_frame_rate {file.get_safe()}"
        )
        result = syscmd(cli)
        if result == "":
            raise Exception("Could not get frame rate")
        return float(result[0]) / float(result[1])

    @staticmethod
    def get_source_bitrates(path: PathAlabama, shutit=False) -> tuple[float, float]:
        """
        stolen from the one and only autocompressor.com's source code 🤑
        Returns tuple of bitrates (firstVideoStream, firstAudioStream)
        Works via demux-to-null (container stats are considered false)
        """
        common = "-show_entries packet=size -of default=nokey=1:noprint_wrappers=1"
    
        command_v = f"ffprobe -v error -select_streams V:0 {common} {path.get_safe()}"
        command_a = f"ffprobe -v error -select_streams a:0 {common} {path.get_safe()}"
    
        v_out = syscmd(command_v)
        if isinstance(v_out, int):
            print("Failed getting video bitrate")
            return 0, 0
        packets_v_arr = v_out.split("\n")
    
        a_out = syscmd(command_a)
        if isinstance(a_out, int):
            print("Failed getting video bitrate")
            return 0, 0
        packets_a_arr = a_out.split("\n")
    
        packets_v_bits = 0
        packets_a_bits = 0
    
        for i in packets_v_arr:
            if i.isdigit():
                packets_v_bits += int(i) * 8
    
        for j in packets_a_arr:
            if j.isdigit():
                packets_a_bits += int(j) * 8
    
        real_duration = Ffmpeg.get_video_length(path)

        vid_bps = round(packets_v_bits / real_duration)
        aud_bps = round(packets_a_bits / real_duration)
        if shutit is False:
            print(f"Video is {vid_bps} bps")
            print(f"Audio is {aud_bps} bps")
    
        return vid_bps, aud_bps

import json
import os

from alabamaEncode.cli_executor import run_cli
from alabamaEncode.path import PathAlabama


class Ffmpeg:
    @staticmethod
    def check_for_invalid(path: PathAlabama) -> bool:
        """
        Checks if the file is not a valid video file
        :param path: PathAlabama instance
        :return: True if the video is invalid, False if the video is valid
        """
        path.check_video()

        return not run_cli(
            f"ffmpeg -v error -i {path.get_safe()} -c copy -f null /dev/null"
        ).success()

    @staticmethod
    def get_frame_count(path: PathAlabama) -> int:
        """
        Returns the frame count of the video
        :param path: path to the video
        :return: int
        """
        path.check_video()
        return (
            run_cli(
                f"ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of csv=p=0 {path.get_safe()}"
            )
            .verify()
            .get_as_int()
        )

    @staticmethod
    def get_video_length(path: PathAlabama, sexagesimal=False) -> float | str:
        """
        Returns the video length in seconds
        :param sexagesimal: If True, returns the length in sexagesimal format
        :param path: Path to the video
        :return: float
        """
        path.check_video()
        do_hexadecimal = "-sexagesimal" if sexagesimal else ""
        out = (
            run_cli(
                f"ffprobe -v error -show_entries format=duration {do_hexadecimal} -of default=noprint_wrappers=1"
                f":nokey=1 {path.get_safe()}"
            )
            .verify(bad_output_hints=["N/A", "Invalid data found"])
            .get_output()
        )

        return out if sexagesimal else float(out)

    @staticmethod
    def get_total_bitrate(path: PathAlabama) -> float:
        path.check_video()
        return os.path.getsize(path.get()) * 8 / Ffmpeg.get_video_length(path)

    @staticmethod
    def get_height(path: PathAlabama) -> int:
        path.check_video()
        return (
            run_cli(
                f"ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 {path.get_safe()}"
            )
            .verify()
            .filter_output(",")
            .get_as_int()
        )

    @staticmethod
    def get_width(path: PathAlabama) -> int:
        path.check_video()
        return (
            run_cli(
                f"ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 {path.get_safe()}"
            )
            .verify()
            .filter_output(",")
            .get_as_int()
        )

    @staticmethod
    def is_hdr(path: PathAlabama) -> bool:
        """Check if a video is HDR"""
        path.check_video()
        out = (
            run_cli(
                (
                    f"ffprobe -v quiet -show_entries stream=color_transfer "
                    f"-of csv=p=0 -select_streams v:0 {path.get_safe()}"
                )
            )
            .get_output()
            .strip()
        )

        if "bt709" in out or "unknown" in out:
            return False
        return True

    @staticmethod
    def get_video_frame_rate(file: PathAlabama) -> float:
        file.check_video()
        result = (
            run_cli(
                (
                    f"ffprobe -v error -select_streams v -of default=noprint_wrappers=1:nokey=1"
                    f" -show_entries stream=r_frame_rate {file.get_safe()}"
                )
            )
            .verify(bad_output_hints=[""])
            .get_output()
            .split("/")
        )
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

        v_out = run_cli(command_v).get_output()
        if isinstance(v_out, int):
            print("Failed getting video bitrate")
            return 0, 0
        packets_v_arr = v_out.split("\n")

        a_out = run_cli(command_a).get_output()
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

    @staticmethod
    def get_tonemap_vf() -> str:
        # tonemap_string = 'zscale=t=linear:npl=(>100),format=gbrpf32le,tonemap=tonemap=reinhard:desat=0,zscale=p=bt709:t=bt709:m=bt709:r=tv:d=error_diffusion,format=yuv420p10le'
        tonemap_string = "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=mobius:desat=0,zscale=t=bt709:m=bt709:r=tv:d=error_diffusion"
        return tonemap_string

    @staticmethod
    def get_first_frame_data(path: PathAlabama):
        # ffprobe -v error -select_streams v:0 -show_frames 'path' -of json -read_intervals "%+0.3"
        path.check_video()
        return json.loads(
            run_cli(
                f'ffprobe -v error -select_streams v:0 -show_frames -of json -read_intervals "1%+#1" {path.get_safe()}'
            )
            .verify()
            .get_output()
        )["frames"][0]

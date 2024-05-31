import json
import os
import re
from typing import Any

from alabamaEncode.core.util.bin_utils import get_binary, verify_ffmpeg_library
from alabamaEncode.core.util.cli_executor import run_cli
from alabamaEncode.core.util.path import PathAlabama


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
                f"ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets "
                f"-of default=noprint_wrappers=1:nokey=1 {path.get_safe()}"
            )
            .verify()
            .strip_mp4_warning()
            .get_as_int()
        )

    @staticmethod
    def get_frame_count_fast(path: PathAlabama):
        length_in_secs = Ffmpeg.get_video_length(path)
        fps = Ffmpeg.get_video_frame_rate(path)
        return int(length_in_secs * fps)

    @staticmethod
    def get_tracks(path: PathAlabama):
        path.check_video()
        out = (
            run_cli(
                f'{get_binary("ffprobe")} -v error -show_entries stream -of json {path.get_safe()}'
            )
            .verify()
            .strip_mp4_warning()
            .get_output()
        )
        return json.loads(out)["streams"]

    @staticmethod
    def get_video_length(path: PathAlabama, sexagesimal=False) -> float | str:
        """
        Returns the video length in seconds
        :param sexagesimal: If True, returns the length in sexagesimal format
        :param path: Path to the video
        :return: float
        """
        path.check_video()
        cli_command = (
            f"ffprobe -v error -show_entries format=duration {'-sexagesimal' if sexagesimal else ''}"
            f" -of default=noprint_wrappers=1:nokey=1 {path.get_safe()}"
        )
        try:
            out = (
                run_cli(cli_command)
                .verify(
                    bad_output_hints=["N/A", "Invalid data found"],
                    fail_message=f"ffprobe failed, {cli_command}",
                )
                .strip_mp4_warning()
                .get_output()
            )
        except RuntimeError:
            frame_count = Ffmpeg.get_frame_count(path)
            fps = Ffmpeg.get_video_frame_rate(path)
            return frame_count / fps

        return out if sexagesimal else float(out)

    @staticmethod
    def get_total_bitrate(path: PathAlabama) -> float:
        path.check_video()
        return (os.path.getsize(path.get()) * 8) / Ffmpeg.get_video_length(path)

    @staticmethod
    def get_height(path: PathAlabama) -> int:
        path.check_video()
        return (
            run_cli(
                f"ffprobe -v error -select_streams v:0 -show_entries stream=height "
                f"-of default=noprint_wrappers=1:nokey=1 {path.get_safe()}"
            )
            .verify()
            .strip_mp4_warning()
            .get_as_int()
        )

    @staticmethod
    def get_width(path: PathAlabama) -> int:
        path.check_video()
        return (
            run_cli(
                f"ffprobe -v error -select_streams v:0 -show_entries stream=width "
                f"-of default=noprint_wrappers=1:nokey=1 {path.get_safe()}"
            )
            .verify()
            .strip_mp4_warning()
            .get_as_int()
        )

    @staticmethod
    def get_pix_fmt(path: PathAlabama) -> str:
        path.check_video()
        return (
            run_cli(
                f"ffprobe -v error -select_streams v:0 -show_entries stream=pix_fmt "
                f"-of default=noprint_wrappers=1:nokey=1 {path.get_safe()}"
            )
            .verify()
            .strip_mp4_warning()
            .get_output()
        )

    @staticmethod
    def get_bit_depth(path: PathAlabama) -> int:
        pix_fmt = Ffmpeg.get_pix_fmt(path)
        if pix_fmt == "yuv420p":
            return 8
        elif pix_fmt == "yuv420p10le":
            return 10
        else:
            raise NotImplemented(f"could not parse bitdepth out of: {pix_fmt}; please report it")

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
            .strip_mp4_warning()
            .get_output()
            .split("/")
        )
        return float(result[0]) / float(result[1])

    @staticmethod
    def get_fps_fraction(file: PathAlabama) -> str:
        file.check_video()
        return (
            run_cli(
                (
                    f"ffprobe -v error -select_streams v -of default=noprint_wrappers=1:nokey=1"
                    f" -show_entries stream=r_frame_rate {file.get_safe()}"
                )
            )
            .verify(bad_output_hints=[""])
            .strip_mp4_warning()
            .get_output()
        )

    @staticmethod
    def get_source_bitrates(
        path: PathAlabama, calculate_video=True, calculate_audio=True
    ) -> tuple[float, float]:
        """
        stolen from the one and only autocompressor.com's source code 🤑
        Returns tuple of bitrates (firstVideoStream, firstAudioStream)
        Works via demux-to-null (container stats are considered false)
        """
        common = "-show_entries packet=size -of default=nokey=1:noprint_wrappers=1"
        command_v = f"ffprobe -v error -select_streams V:0 {common} {path.get_safe()}"
        command_a = f"ffprobe -v error -select_streams a:0 {common} {path.get_safe()}"
        vid_bps = 0
        aud_bps = 0

        real_duration = Ffmpeg.get_video_length(path)

        if calculate_video:
            packets_v_arr = (
                run_cli(command_v).verify().strip_mp4_warning().get_output().split("\n")
            )
            packets_v_bits = sum([int(i) * 8 for i in packets_v_arr if i.isdigit()])
            vid_bps = round(packets_v_bits / real_duration)

        if calculate_audio:
            packets_a_arr = (
                run_cli(command_a).verify().strip_mp4_warning().get_output().split("\n")
            )
            packets_a_bits = sum([int(j) * 8 for j in packets_a_arr if j.isdigit()])
            aud_bps = round(packets_a_bits / real_duration)

        return vid_bps, aud_bps

    @staticmethod
    def get_tonemap_vf() -> str:
        # https://ffmpeg.org/ffmpeg-filters.html#tonemap
        verify_ffmpeg_library("libzimg")
        return "zscale=t=linear,tonemap=mobius,zscale=p=bt709:t=bt709:m=bt709:r=tv:d=error_diffusion"

    @staticmethod
    def get_first_frame_data(path: PathAlabama) -> dict:
        # ffprobe -v error -select_streams v:0 -show_frames 'path' -of json -read_intervals "%+0.3"
        path.check_video()
        return json.loads(
            run_cli(
                f'ffprobe -v error -select_streams v:0 -show_frames -of json -read_intervals "1%+#1" {path.get_safe()}'
            )
            .verify()
            .get_output()
        )["frames"][0]

    @staticmethod
    def get_codec(path: PathAlabama) -> str:
        path.check_video()
        return (
            run_cli(
                f"ffprobe -v error -select_streams v:0 -show_entries stream=codec_name "
                f"-of default=noprint_wrappers=1:nokey=1 {path.get_safe()}"
            )
            .verify()
            .strip_mp4_warning()
            .get_output()
        )

    @staticmethod
    def get_vmaf_motion(chunk) -> float:
        verify_ffmpeg_library("libvmaf")
        # [Parsed_vmafmotion_0 @ 0x558626bfa300] VMAF Motion avg: 8.732
        out = (
            run_cli(
                f"{get_binary('ffmpeg')} {chunk.get_ss_ffmpeg_command_pair()} -lavfi vmafmotion -f null /dev/null "
            )
            .verify()
            .strip_mp4_warning()
            .get_output()
        )
        return float(re.findall(r"VMAF Motion avg: ([0-9.]+)", out)[0])

    @staticmethod
    def get_ffprobe_content_features(chunk, vf) -> dict[Any, Any]:
        # ffmpeg -v error -nostdin -hwaccel auto -i
        # '/home/kokoniara/howlscastle_test.mkv'  -pix_fmt yuv420p10le -an -sn -strict -1 -f yuv4mpegpipe - | ffprobe
        # -v error -select_streams v:0 -f lavfi -i 'movie=/dev/stdin,entropy,scdet,signalstats' -show_frames -of json

        out = (
            run_cli(
                f"{chunk.create_chunk_ffmpeg_pipe_command(video_filters=vf)} | {get_binary('ffprobe')} -v error "
                f"-select_streams v:0 -f lavfi -i 'movie=/dev/stdin,entropy,scdet,signalstats' -show_frames -of json"
            )
            .verify()
            .get_output()
        )

        parsed_json = json.loads(out)
        filtered = {}

        for frame in parsed_json["frames"]:
            tags = frame["tags"]

            tags = {
                "entropy.entropy.normal.Y": tags["lavfi.entropy.entropy.normal.Y"],
                "entropy.normalized_entropy.normal.Y": tags[
                    "lavfi.entropy.normalized_entropy.normal.Y"
                ],
                "entropy.entropy.normal.U": tags["lavfi.entropy.entropy.normal.U"],
                "entropy.normalized_entropy.normal.U": tags[
                    "lavfi.entropy.normalized_entropy.normal.U"
                ],
                "entropy.entropy.normal.V": tags["lavfi.entropy.entropy.normal.V"],
                "entropy.normalized_entropy.normal.V": tags[
                    "lavfi.entropy.normalized_entropy.normal.V"
                ],
                "scd.mafd": tags["lavfi.scd.mafd"],
                "scd.score": tags["lavfi.scd.score"],
                "signalstats.YMIN": tags["lavfi.signalstats.YMIN"],
                "signalstats.YLOW": tags["lavfi.signalstats.YLOW"],
                "signalstats.YAVG": tags["lavfi.signalstats.YAVG"],
                "signalstats.YHIGH": tags["lavfi.signalstats.YHIGH"],
                "signalstats.YMAX": tags["lavfi.signalstats.YMAX"],
                "signalstats.UMIN": tags["lavfi.signalstats.UMIN"],
                "signalstats.ULOW": tags["lavfi.signalstats.ULOW"],
                "signalstats.UAVG": tags["lavfi.signalstats.UAVG"],
                "signalstats.UHIGH": tags["lavfi.signalstats.UHIGH"],
                "signalstats.UMAX": tags["lavfi.signalstats.UMAX"],
                "signalstats.VMIN": tags["lavfi.signalstats.VMIN"],
                "signalstats.VLOW": tags["lavfi.signalstats.VLOW"],
                "signalstats.VAVG": tags["lavfi.signalstats.VAVG"],
                "signalstats.VHIGH": tags["lavfi.signalstats.VHIGH"],
                "signalstats.VMAX": tags["lavfi.signalstats.VMAX"],
                "signalstats.SATMIN": tags["lavfi.signalstats.SATMIN"],
                "signalstats.SATLOW": tags["lavfi.signalstats.SATLOW"],
                "signalstats.SATAVG": tags["lavfi.signalstats.SATAVG"],
            }

            filtered[frame["pts"]] = tags
        return filtered

    @staticmethod
    def get_siti_tools_data(chunk, vf) -> dict[Any, Any]:
        out = (
            run_cli(
                f"{chunk.create_chunk_ffmpeg_pipe_command(video_filters=vf)} |"
                f" {get_binary('siti-tools')} -f json -b 10 -r full -q /dev/stdin"
            )
            .verify()
            .get_output()
        )

        parsed_json = json.loads(out)
        # remove "settings" and "input_file" keys
        parsed_json.pop("settings", None)
        parsed_json.pop("input_file", None)

        # {
        #     "si": [
        #       1,
        #       1,
        #       for every frame...
        #     ],
        #      "ti": [
        #       1,
        #       1,
        #       for every frame except the first...
        #     ]
        # }
        # convert to:
        # {
        #     "frame #": [
        #         si score
        #         ti score # 0 if first frame
        #     ]
        #   ... for every frame
        # }
        new = []
        for i in range(len(parsed_json["si"])):
            si_ti_pair = [parsed_json["si"][i], 0]
            if i != 0:
                si_ti_pair[1] = parsed_json["ti"][i - 1]
            new.append(si_ti_pair)

        return_dict = {}
        for i, frame in enumerate(new):
            return_dict[i] = frame

        return return_dict

    @staticmethod
    def get_content_features(chunk, vf=""):
        siti = Ffmpeg.get_siti_tools_data(chunk, vf)
        ffprobe = Ffmpeg.get_ffprobe_content_features(chunk, vf)
        # since ffprobe and siti are both dicts that use frame # as the key, we can just merge them
        # and return the result
        new = {}
        for key in ffprobe.keys():
            new[key] = {
                **ffprobe[key],
                "siti.si": siti[key][0],
                "siti.ti": siti[key][1],
            }
        return new


def track_test():
    tracks = Ffmpeg.get_tracks(PathAlabama("/home/kokoniara/owoStreamCopy_ffv1.mkv"))
    for track in tracks:
        match track["codec_type"]:
            case "video":
                print("video track")
            case "audio":
                print("audio track")
            case "subtitle":
                print("subtitle track")
        print(track)


if __name__ == "__main__":
    track_test()



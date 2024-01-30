import os
import tempfile
import time
from typing import List

from alabamaEncode.core.bin_utils import get_binary
from alabamaEncode.core.cli_executor import run_cli
from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.path import PathAlabama


class VideoConcatenator:
    def __init__(
        self,
        files: List[str] = None,
        output: str = None,
        file_with_audio: str = None,
        audio_param_override="-c:a libopus -af aformat=channel_layouts=7.1|5.1|stereo -mapping_family 1",
        start_offset=-1,
        end_offset=-1,
        title="",
        encoder_name="TestHoeEncode",
        mux_audio=True,
        subs_file=None,
        audio_only=False,
    ):
        self.files = files
        self.output = output
        self.file_with_audio = file_with_audio
        self.audio_param_override = audio_param_override
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.title = title
        self.encoder_name = encoder_name
        self.mux_audio = mux_audio
        self.subs_file = subs_file
        self.audio_only = audio_only

    def find_files_in_dir(self, folder_path, extension):
        """
        Finds all numbered files in a folder with a given extension
        :param folder_path:  The folder to search
        :param extension: The extension to search for
        :return: self for chaining
        """
        files = []
        for file in os.listdir(folder_path):
            if file.endswith(extension) and "temp.mkv" not in file:
                files.append(os.path.join(folder_path, file))

        files.sort(key=lambda x: int(os.path.splitext(os.path.basename(x))[0]))

        self.files = files
        return self

    def concat_videos(self):
        start = time.time()
        self._concat_videos()
        end = time.time()
        print(f"Concat took {end - start} seconds")

    def _concat_videos(self):
        if not self.output:
            print("If muxing please provide an output path")
            return

        if os.path.exists(self.output):
            print(f"File {self.output} already exists")
            return

        concat_file_path = "lovelyconcat"

        with open(concat_file_path, "w") as f:
            for file in self.files:
                f.write(f"file '{file}'\n")

        vid_output = self.output + ".videoonly.mkv"
        print("Concating Video")
        os.system(
            f'{get_binary("ffmpeg")} -y -stats -v error -f concat '
            f'-safe 0 -i "{concat_file_path}" -c:v copy -map_metadata -1 -vsync cfr "{vid_output}"'
        )
        if Ffmpeg.check_for_invalid(PathAlabama(vid_output)):
            print("Invalid file found, exiting")
            return

        has_audio_track = False
        tracks = Ffmpeg.get_tracks(PathAlabama(self.file_with_audio))
        for track in tracks:
            if track["codec_type"] == "audio":
                has_audio_track = True
                break

        if self.audio_only:
            print("Encoding a audio track only")

            if not has_audio_track:
                print("No audio track found, not encoding")
                return

            print("Encoding a audio track")

            vec = [
                get_binary("ffmpeg"),
                "-y",
                "-stats",
                "-v error",
            ]

            if self.start_offset != -1:
                vec += [f"-ss {self.start_offset}"]

            vec += ["-i", f'"{self.file_with_audio}"']

            if self.end_offset != -1:
                vec += [f"-t {Ffmpeg.get_video_length(PathAlabama(vid_output))}"]

            vec += [
                "-map",
                "0:a:0",
                self.audio_param_override,
                "-map_metadata -1",
                f'"{self.output}"',
            ]

            encode_audio = " ".join(vec)
            os.system(encode_audio)
            if Ffmpeg.check_for_invalid(PathAlabama(self.output)):
                print("Invalid file found, exiting")
                return
            os.remove(vid_output)
            return

        if self.mux_audio and has_audio_track:
            print("Encoding a audio track")
            audio_output = self.output + ".audioonly.mkv"

            start_offset_command = ""
            if self.start_offset != -1:
                start_offset_command = f"-ss {self.start_offset}"

            end_offset_command = ""
            if self.end_offset != -1:
                end_offset_command = (
                    f"-t {Ffmpeg.get_video_length(PathAlabama(vid_output))}"
                )

            vec = [
                get_binary("ffmpeg"),
                "-y",
                "-stats",
                "-v error",
            ]

            if self.start_offset != -1:
                vec += [start_offset_command]

            vec += [f'-i "{self.file_with_audio}"']

            if self.end_offset != -1:
                vec += [end_offset_command]

            vec += [
                "-map",
                "0:a:0",
                self.audio_param_override,
                "-map_metadata -1",
                f'"{audio_output}"',
            ]

            encode_audio = " ".join(vec)

            os.system(encode_audio)
            if Ffmpeg.check_for_invalid(PathAlabama(audio_output)):
                print("Invalid file found, exiting")
                return

            print("Muxing audio into the output")

            title_bit = f' -metadata description="encoded by {self.encoder_name}" '
            if self.title:
                title_bit += f' -metadata title="{self.title}"'

            if self.subs_file is None:
                vec = [
                    get_binary("ffmpeg"),
                    "-y",
                    "-stats",
                    "-v error",
                    f'-i "{vid_output}"',
                    f'-i "{audio_output}"',
                    start_offset_command,
                    f'-i "{self.file_with_audio}"',
                    end_offset_command,
                ]

                vec += [f' -metadata description="encoded by {self.encoder_name}"']

                if self.title:
                    vec += [f' -metadata title="{self.title}"']

                vec += ["-map 0:v", "-map 1:a"]

                if "mp4" in self.output:
                    vec += ["-c:s mov_text"]

                vec += [
                    "-map 2:s?",
                    "-movflags +faststart",
                    "-map_chapters -1",
                    "-c:v copy",
                    "-c:a copy",
                    "-vsync cfr",
                    f'"{self.output}"',
                ]

                final_command = " ".join(vec)
                # print(f"running: {final_command}")
                out = run_cli(final_command).verify().get_output()
                if (
                    "Subtitle encoding currently only possible from text to text or bitmap to bitmap"
                    in str(out)
                ):
                    print("Subtitle encoding failed, trying again")
                    for a in vec:
                        if "mov_text" in a or "map 2:s?" in a:
                            vec.remove(a)
                    final_command = " ".join(vec)
                    # print(f"running: {final_command}")
                    run_cli(final_command).verify()
            else:
                subs_i = ""
                subs_map = ""
                if len(self.subs_file) > 0 and self.subs_file[0] != "":
                    if start_offset_command != "":
                        # offset each track using -itsoffset {offset} -ss {offset}
                        print("Offseting subs")
                        for sub in self.subs_file:
                            temp_sub = f"{sub}.temp.vtt"
                            encode_sub = (
                                f'{get_binary("ffmpeg")} -y -v error -itsoffset {self.start_offset} '
                                f'-ss {self.start_offset} -i "{sub}" "{temp_sub}"'
                            )
                            # print(f"running: {encode_sub}")

                    for i, sub in enumerate(self.subs_file):
                        if start_offset_command != "":
                            subs_i += f' -i "{sub}.temp.vtt" '
                        else:
                            subs_i += f' -i "{sub}" '
                        subs_map += f"-map {i+2} "

                final_command = (
                    f'{get_binary("ffmpeg")} -y -stats -v error -i "{vid_output}" -i "{audio_output}" '
                    f'{subs_i} {start_offset_command} -i "{self.file_with_audio}" {end_offset_command} '
                    f"{title_bit} -map 0:v -map 1:a {subs_map} -movflags +faststart -map_chapters -1 "
                    f'-c:v copy -c:a copy -vsync cfr "{self.output}"'
                )
                # print(f"running: {final_command}")
                os.system(final_command)

            os.system(f'rm "{concat_file_path}" "{vid_output}" "{audio_output}"')
        else:
            if not has_audio_track:
                print("No audio track found, not encoding")
            print("Not muxing audio")
            os.system(
                f"{get_binary('ffmpeg')} -y -stats -v error -i {vid_output} -c copy {self.output}"
            )
            os.system(
                f"rm {concat_file_path} {vid_output}",
            )

        if not os.path.exists(self.output) or os.path.getsize(self.output) < 1000:
            if os.path.exists(self.output):
                os.remove(self.output)
            raise Exception("VIDEO CONCAT FAILED")


def test():
    def create_fake_ivf_and_test(_temp):
        for i in range(20):
            with open(os.path.join(_temp, f"{i}.ivf"), "w") as f:
                f.write(" ")
        # test the file discovery
        vc = VideoConcatenator()
        vc.find_files_in_dir(_temp, ".ivf")
        assert len(vc.files) == 20
        print("Test passed")

    # make temp dir and put 20 empty .ivf files
    temp_dir = tempfile.mkdtemp()
    create_fake_ivf_and_test(temp_dir)

    # make a helpers dir and put 20 empty .ivf files
    sub_dir = os.path.join(temp_dir, "helpers")
    os.mkdir(sub_dir)
    create_fake_ivf_and_test(temp_dir)

    # remove temp dir
    os.system(f"rm -rf {temp_dir}")


if __name__ == "__main__":
    test()

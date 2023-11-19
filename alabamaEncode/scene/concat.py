import os
import tempfile
import time
from typing import List

from alabamaEncode.bin_utils import get_binary
from alabamaEncode.cli_executor import run_cli
from alabamaEncode.ffmpeg import Ffmpeg
from alabamaEncode.path import PathAlabama
from alabamaEncode.utils.binary import doesBinaryExist


class VideoConcatenator:
    nessesary = ["ffmpeg"]

    def __init__(
        self,
        files: List[str] = None,
        output: str = None,
        file_with_audio: str = None,
        audio_param_override="-c:a libopus -ac 2 -b:v 96k -vbr on",
        start_offset=-1,
        end_offset=-1,
        title="",
        encoder_name="TestHoeEncode",
        mux_audio=True,
        subs_file=None,
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
        for n in self.nessesary:
            if not doesBinaryExist(n):
                print(f"Could not find {n} in PATH")
                exit(1)

    def find_files_in_dir(self, folder_path, extension):
        files = []
        for file in os.listdir(folder_path):
            if file.endswith(extension):
                files.append(os.path.join(folder_path, file))
        f_2 = []
        for f in files:
            try:
                a = int(os.path.splitext(os.path.basename(f))[0])
                f_2.append(f)
            except ValueError:
                pass
        files = f_2

        # print(f"Found {len(files)} files")
        # print("Sorting files")
        # sort files by name by interpreting their name as an integer
        files.sort(key=lambda x: int(os.path.splitext(os.path.basename(x))[0]))

        self.files = files

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
        concat_command = f'{get_binary("ffmpeg")} -y -stats -v error -f concat -safe 0 -i "{concat_file_path}" -c:v copy -map_metadata -1 "{vid_output}"'

        print("Concating Video")
        print(f"running: {concat_command}")
        os.system(concat_command)
        if Ffmpeg.check_for_invalid(PathAlabama(vid_output)):
            print("Invalid file found, exiting")
            return

        if self.mux_audio:
            print("Getting video length")
            start_offset_command = (
                f"-ss {self.start_offset}" if self.start_offset != -1 else ""
            )
            end_offset_command = (
                f"-t {Ffmpeg.get_video_length(PathAlabama(vid_output))}"
                if self.end_offset != -1
                else ""
            )

            print("Encoding a audio track")
            audio_output = self.output + ".audioonly.mkv"
            encode_audio = f'{get_binary("ffmpeg")} -y -stats -v error {start_offset_command} -i "{self.file_with_audio}" {end_offset_command} -map 0:a:0 {self.audio_param_override} -map_metadata -1 "{audio_output}"'
            print(f"running: {encode_audio}")
            os.system(encode_audio)
            if Ffmpeg.check_for_invalid(PathAlabama(audio_output)):
                print("Invalid file found, exiting")
                return

            print("Muxing audio into the output")

            title_bit = f' -metadata description="encoded by {self.encoder_name}" '
            if self.title:
                title_bit += f' -metadata title="{self.title}"'

            if self.subs_file is None:
                sub_hack = ""
                if "mp4" in self.output:
                    sub_hack = " -c:s mov_text "
                final_command = f'{get_binary("ffmpeg")} -y -stats -v error -i "{vid_output}" -i "{audio_output}" {start_offset_command} -i "{self.file_with_audio}" {end_offset_command} {title_bit} -map 0:v -map 1:a {sub_hack} -map "2:s?" -movflags +faststart -c:v copy -c:a copy "{self.output}"'
                print(f"running: {final_command}")
                out = run_cli(final_command).get_output()
                if (
                    "Subtitle encoding currently only possible from text to text or bitmap to bitmap"
                    in str(out)
                ):
                    print("Subtitle encoding failed, trying again")
                    print(f"running: {final_command}")
                    final_command = f'{get_binary("ffmpeg")} -y -stats -v error -i "{vid_output}" -i "{audio_output}" {start_offset_command} -i "{self.file_with_audio}" {end_offset_command} {title_bit} -map 0:v -map 1:a -movflags +faststart -c:v copy -c:a copy "{self.output}"'
                    run_cli(final_command)
            else:
                subs_i = ""
                subs_map = ""
                if len(self.subs_file) > 0 and self.subs_file[0] != "":
                    if start_offset_command != "":
                        # offset each track using -itsoffset {offset} -ss {offset}
                        print("Offseting subs")
                        for sub in self.subs_file:
                            temp_sub = f"{sub}.temp.vtt"
                            encode_sub = f'{get_binary("ffmpeg")} -y -v error -itsoffset {self.start_offset} -ss {self.start_offset} -i "{sub}" "{temp_sub}"'
                            print(f"running: {encode_sub}")

                    for i, sub in enumerate(self.subs_file):
                        if start_offset_command != "":
                            subs_i += f' -i "{sub}.temp.vtt" '
                        else:
                            subs_i += f' -i "{sub}" '
                        subs_map += f"-map {i+2} "

                final_command = f'{get_binary("ffmpeg")} -y -stats -v error -i "{vid_output}" -i "{audio_output}" {subs_i} {start_offset_command} -i "{self.file_with_audio}" {end_offset_command} {title_bit} -map 0:v -map 1:a {subs_map} -movflags +faststart -c:v copy -c:a copy "{self.output}"'
                print(f"running: {final_command}")
                run_cli(final_command)

            if not os.path.exists(self.output) or os.path.getsize(self.output) < 100:
                if os.path.exists(self.output):
                    os.remove(self.output)
                raise Exception("VIDEO CONCAT FAILED")

            remove_command = f'rm "{concat_file_path}" "{vid_output}" "{audio_output}"'
            print(f"running: {remove_command}")
            os.system(remove_command)

            return
        else:
            print("Not muxing audio")
            commands = [
                f"mv {vid_output} {self.output}",
                f"rm {concat_file_path} {vid_output}",
            ]

        for command in commands:
            print("Running: " + command)

            os.system(command)
        if not os.path.exists(self.output) or os.path.getsize(self.output) < 100:
            raise Exception("VIDEO CONCAT FAILED")


def test():
    # make temp dir and put 20 empty .ivf files
    temp_dir = tempfile.mkdtemp()
    for i in range(20):
        with open(os.path.join(temp_dir, f"{i}.ivf"), "w") as f:
            f.write(" ")

    # test the file discovery
    vc = VideoConcatenator()
    vc.find_files_in_dir(temp_dir, ".ivf")
    assert len(vc.files) == 20
    print("Test passed")

    # make a sub dir and put 20 empty .ivf files
    sub_dir = os.path.join(temp_dir, "sub")
    os.mkdir(sub_dir)
    for i in range(20):
        with open(os.path.join(sub_dir, f"{i}.ivf"), "w") as f:
            f.write(" ")

    # there still should be 20 files
    vc = VideoConcatenator()
    vc.find_files_in_dir(temp_dir, ".ivf")
    assert len(vc.files) == 20
    print("Test passed")

    # remove temp dir
    os.system(f"rm -rf {temp_dir}")


if __name__ == "__main__":
    test()

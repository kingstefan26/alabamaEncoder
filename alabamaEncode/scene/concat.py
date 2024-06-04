import os
import tempfile
import time
from typing import List

from tqdm import tqdm

from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.util.bin_utils import get_binary
from alabamaEncode.core.util.cli_executor import run_cli
from alabamaEncode.core.util.path import PathAlabama


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
        temp_dir="",
        copy_included_subs=True,
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
        self.temp_dir = temp_dir
        self.copy_included_subs = copy_included_subs

        if not self.output:
            print("If muxing please provide an output path")
            raise Exception("No output path not provided")

        if self.temp_dir == "":
            self.temp_dir = os.path.dirname(self.output) + "/"

        self.final_files = []

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

    def extract_subs(self, start_offset="", end_offset=""):
        og_file = PathAlabama(self.file_with_audio)
        tracks = Ffmpeg.get_tracks(og_file)
        extracted_subs = []
        sub_counter = 0
        for track in tqdm(
            [track for track in tracks if track["codec_type"] == "subtitle"],
            desc="Extracting Subs",
        ):
            tag_lang = ""
            if "language" in track["tags"]:
                tag_lang = track["tags"]["language"]
            tag_title = ""
            if "title" in track["tags"]:
                tag_title = track["tags"]["title"]

            out_path = f"{self.temp_dir}{tag_lang}.vtt"
            counter = 1
            while os.path.exists(out_path):
                out_path = f"{self.temp_dir}{tag_lang}_{counter}.vtt"
                counter += 1
            try:
                a = (
                    f'{get_binary("ffmpeg")} -v error -y -stats {start_offset} -i {og_file.get_safe()} {end_offset} '
                    f'-map 0:s:{sub_counter} "{out_path}"'
                )
                run_cli(a)
            except Exception as e:
                # print(e)
                pass

            if os.path.exists(out_path):
                extracted_subs.append((out_path, tag_lang, tag_title, sub_counter))
            # else:
            #     print(f"Failed extracing {tag_lang}_{counter} sub")
            #     pass

            sub_counter += 1

        return extracted_subs

    def concat_video_track(self):
        concat_file_path = self.temp_dir + "concat.txt"

        with open(concat_file_path, "w") as f:
            for file in self.files:
                f.write(f"file '{file}'\n")

        concat_vid_ext = ".mkv"

        if Ffmpeg.get_codec(PathAlabama(self.files[0])) == "av1":
            concat_vid_ext = ".ivf"

        self.vid_output = f"{self.temp_dir}vid{concat_vid_ext}"
        print("Concating Video")
        if not os.path.exists(self.vid_output):
            os.system(
                f'{get_binary("ffmpeg")} -y -stats -v error -f concat '
                f'-safe 0 -i "{concat_file_path}" -c:v copy -map_metadata -1 -vsync cfr "{self.vid_output}"'
            )
        if Ffmpeg.check_for_invalid(PathAlabama(self.vid_output)):
            raise Exception("Concating chunks failed")

        os.remove(concat_file_path)

        self.final_files += [f'-i "{self.vid_output}"']

    def encode_audio_tracks(self):
        print("Encoding a audio track")
        self.audio_output = f"{self.temp_dir}audio.mkv"

        vec = [
            get_binary("ffmpeg"),
            "-y",
            "-stats",
            "-v error",
        ]

        if self.start_offset != -1:
            vec += [f"-ss {self.start_offset}"]

        vec += [f'-i "{self.file_with_audio}"']

        if self.end_offset != -1:
            vec += [f"-t {Ffmpeg.get_video_length(PathAlabama(self.vid_output))}"]

        vec += [
            "-map",
            "0:a:0",
            self.audio_param_override,
            "-map_metadata -1",
            f'"{self.audio_output}"',
        ]

        encode_audio = " ".join(vec)
        if not os.path.exists(self.audio_output):
            os.system(encode_audio)
        if Ffmpeg.check_for_invalid(PathAlabama(self.audio_output)):
            raise Exception("Audio Track encoding Failed")

        self.final_files += [f'-i "{self.audio_output}"']

    def has_audio_track(self) -> bool:
        has_audio_track = False
        tracks = Ffmpeg.get_tracks(PathAlabama(self.file_with_audio))
        for track in tracks:
            if track["codec_type"] == "audio":
                has_audio_track = True
                break

        return has_audio_track

    def has_sub_track(self) -> bool:
        has_sub_track = False
        tracks = Ffmpeg.get_tracks(PathAlabama(self.file_with_audio))
        for track in tracks:
            if track["codec_type"] == "subtitle":
                has_sub_track = True
                break

        return has_sub_track

    def _concat_videos(self):
        if os.path.exists(self.output):
            print(f"File {self.output} already exists")
            return

        self.concat_video_track()

        has_audio_track = self.has_audio_track()
        has_sub_track = self.has_sub_track()

        if self.audio_only:
            if not has_audio_track:
                print("No audio track found, not encoding")
                return

            print("Encoding a audio track only")

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
                vec += [f"-t {Ffmpeg.get_video_length(PathAlabama(self.vid_output))}"]

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
            os.remove(self.vid_output)
            return

        start_offset_command = ""
        if self.start_offset != -1:
            start_offset_command = f"-ss {self.start_offset}"

        end_offset_command = ""
        if self.end_offset != -1:
            end_offset_command = (
                f"-t {Ffmpeg.get_video_length(PathAlabama(self.vid_output))}"
            )

        if not self.mux_audio or not has_audio_track:
            if not has_audio_track:
                print("No audio track found, not encoding")
            print("Skipping audio")
            os.system(
                f"{get_binary('ffmpeg')} -y -stats -v error -i {self.vid_output} -c copy {self.output}"
            )
            os.remove(self.vid_output)
            if Ffmpeg.check_for_invalid(PathAlabama(self.output)):
                os.remove(self.output)
                raise Exception("VIDEO CONCAT FAILED")
            return

        self.encode_audio_tracks()
        print("Muxing audio into the output")

        title_bit = f' -metadata description="encoded by {self.encoder_name}" '
        if self.title:
            title_bit += f' -metadata title="{self.title}"'

        if self.subs_file is None or self.subs_file[0] == "":
            vec = [
                get_binary("ffmpeg"),
                "-y",
                "-stats",
                "-v error",
                f'-i "{self.vid_output}"',
                f'-i "{self.audio_output}"',
            ]

            sub_tracks = []
            if self.copy_included_subs and has_sub_track:
                sub_tracks = self.extract_subs(
                    start_offset=start_offset_command, end_offset=end_offset_command
                )

                for out_path, tag_lang, tag_title, track_index in sub_tracks:
                    vec += [
                        f'-i "{out_path}"',
                    ]

            if self.encoder_name:
                vec += [f' -metadata description="encoded by {self.encoder_name}"']

            if self.title:
                vec += [f' -metadata title="{self.title}"']

            if self.copy_included_subs and len(sub_tracks) > 0:
                stream_index = 2
                for out_path, tag_lang, tag_title, track_index in sub_tracks:
                    vec += [
                        f"-map {stream_index}:s",
                        f'-metadata:s:s:{track_index} language="{tag_lang}"',
                        f'-metadata:s:s:{track_index} title="{tag_title}"',
                    ]
                    stream_index += 1

            vec += ["-map 0:v", "-map 1:a"]

            if "mp4" in self.output:
                vec += ["-c:s mov_text", "-movflags +faststart"]

            vec += [
                "-map_chapters -1",
                "-c:v copy",
                "-c:a copy",
                "-flags:v +bitexact",
                "-flags:a +bitexact",
                "-avoid_negative_ts make_non_negative",
                "-strict strict",
                "-err_detect compliant",
                "-fflags +genpts+bitexact",
                f'"{self.output}"',
            ]

            final_command = " ".join(vec)
            out = run_cli(final_command).verify().get_output()
            if (
                "Subtitle encoding currently only possible from text to text or bitmap to bitmap"
                in str(out)
            ):
                print("Subtitle encoding failed, trying again")
                for a in vec:
                    if "mov_text" in a or "map 2:s" in a:
                        vec.remove(a)
                final_command = " ".join(vec)
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

                for track_index, sub in enumerate(self.subs_file):
                    if start_offset_command != "":
                        subs_i += f' -i "{sub}.temp.vtt" '
                    else:
                        subs_i += f' -i "{sub}" '
                    subs_map += f"-map {track_index+2} "

            final_command = (
                f'{get_binary("ffmpeg")} -y -stats -v error -i "{self.vid_output}" -i "{self.audio_output}" '
                f'{subs_i} {start_offset_command} -i "{self.file_with_audio}" {end_offset_command} '
                f"{title_bit} -map 0:v -map 1:a {subs_map} -movflags +faststart -map_chapters -1 "
                f'-c:v copy -c:a copy -vsync cfr "{self.output}"'
            )
            os.system(final_command)

        os.remove(self.vid_output)
        os.remove(self.audio_output)

        if Ffmpeg.check_for_invalid(PathAlabama(self.output)):
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

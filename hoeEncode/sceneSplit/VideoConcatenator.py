import os
from typing import List

from hoeEncode.ffmpegUtil import doesBinaryExist, get_frame_count, get_video_frame_rate


class VideoConcatenator:
    mux_audio = True
    nessesary = ['ffmpeg', 'mkvmerge']

    def __init__(self, files: List[str] = None, output: str = None, file_with_audio: str = None,
                 audio_param_override='-c:a libopus -ac 2 -b:v 96k -vbr on'):
        self.files = files
        self.output = output
        self.file_with_audio = file_with_audio
        self.audio_param_override = audio_param_override
        for n in self.nessesary:
            if not doesBinaryExist(n):
                print(f'Could not find {n} in PATH')
                exit(1)

    def find_files_in_dir(self, folder_path, extension):
        files = []
        for file in os.listdir(folder_path):
            if file.endswith(extension):
                files.append(os.path.join(folder_path, file))

        self.files = files

    def concat_videos(self):
        if not self.output:
            print('If muxing please provide an output path')
            return

        if os.path.exists(self.output):
            print(f'File {self.output} already exists')
            return

        concat_file_path = 'lovelyconcat'

        with open(concat_file_path, 'w') as f:
            for file in self.files:
                f.write(f'file \'{file}\'\n')

        total_duration = 0
        for file in self.files:
            total_duration += get_frame_count(file)

        cuttoff = total_duration / get_video_frame_rate(self.files[0])
        print(f'Cuttoff is {cuttoff}')
        print(f'Frame rate is {get_video_frame_rate(self.files[0])}')
        print(f'Total duration is {total_duration} frames')

        if self.mux_audio:
            print('Muxing audio into the output')
            commands = [
                f'ffmpeg -v error -f concat -safe 0 -i {concat_file_path} -i "{self.file_with_audio}" -t {cuttoff} -map 0:v -map 1:a {self.audio_param_override} -movflags +faststart -c:v copy temp_{self.output}',
                f'mkvmerge -o {self.output} temp_{self.output}',
                f'rm temp_{self.output} {concat_file_path}'
            ]
        else:
            print('Not muxing audio')
            commands = [
                f'ffmpeg -v error -f concat -safe 0 -i {concat_file_path} -c copy -movflags +faststart temp_{self.output}',
                f'mkvmerge -o {self.output} temp_{self.output}',
                f'rm temp_{self.output} {concat_file_path}'
            ]

        for command in commands:
            print('Running: ' + command)
            os.system(command)

        print(f'Removing {concat_file_path}')
        os.system(f'rm {concat_file_path}')

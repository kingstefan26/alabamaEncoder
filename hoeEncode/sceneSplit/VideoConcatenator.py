import os
import tempfile
from typing import List

from hoeEncode.ffmpegUtil import doesBinaryExist, get_frame_count
from hoeEncode.utils.getvideoframerate import get_video_frame_rate


class VideoConcatenator:
    mux_audio = True
    nessesary = ['ffmpeg']

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

        print(f'Found {len(files)} files')
        print('Sorting files')
        # sort files by name by interpreting their name as an integer
        files.sort(key=lambda x: int(os.path.splitext(os.path.basename(x))[0]))

        self.files = files

    def concat_videos(self, do_cuttoff=False):
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

        cuttoff = ''
        if do_cuttoff:
            cuttoff = total_duration / get_video_frame_rate(self.files[0])
            print(f'Cuttoff is {cuttoff}')
            print(f'Frame rate is {get_video_frame_rate(self.files[0])}')
            print(f'Total duration is {total_duration} frames')
            cuttoff = f'-t {cuttoff}'

        if self.mux_audio:
            print('Muxing audio into the output')
            commands = [
                f'ffmpeg -v error -f concat -safe 0 -i {concat_file_path} -i "{self.file_with_audio}" {cuttoff} -map 0:v -map 1:a -map 1:s {self.audio_param_override} -movflags +faststart -c:v copy {self.output}',
                f'rm {concat_file_path}'
            ]
        else:
            print('Not muxing audio')
            commands = [
                f'ffmpeg -v error -f concat -safe 0 -i {concat_file_path} -c copy -movflags +faststart {self.output}',
                f'rm {self.output} {concat_file_path}'
            ]

        for command in commands:
            print('Running: ' + command)
            os.system(command)


def test():
    # make temp dir and put 20 empty .ivf files
    temp_dir = tempfile.mkdtemp()
    for i in range(20):
        with open(os.path.join(temp_dir, f'{i}.ivf'), 'w') as f:
            f.write(' ')

    # test the file discovery
    vc = VideoConcatenator()
    vc.find_files_in_dir(temp_dir, '.ivf')
    assert len(vc.files) == 20
    print('Test passed')

    # make a sub dir and put 20 empty .ivf files
    sub_dir = os.path.join(temp_dir, 'sub')
    os.mkdir(sub_dir)
    for i in range(20):
        with open(os.path.join(sub_dir, f'{i}.ivf'), 'w') as f:
            f.write(' ')

    # there still should be 20 files
    vc = VideoConcatenator()
    vc.find_files_in_dir(temp_dir, '.ivf')
    assert len(vc.files) == 20
    print('Test passed')

    # remove temp dir
    os.system(f'rm -rf {temp_dir}')


if __name__ == '__main__':
    test()

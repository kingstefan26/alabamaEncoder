import copy
import shutil

from tqdm.contrib.concurrent import process_map

from hoeEncode.ConvexHullEncoding.ConvexHull import ConvexEncoder
from hoeEncode.ConvexHullEncoding.tests.TestUtil import path_setup, get_test_scenes
from hoeEncode.encode.ffmpeg.ChunkOffset import ChunkObject
from hoeEncode.encode.ffmpeg.FfmpegUtil import EncoderConfigObject, EncoderJob, VideoConcatenator, get_video_vmeth
from paraliezeMeHoe.ThaVaidioEncoda import run_kummand

if __name__ == '__main__':
    bias_pct = 8
    print(f'Test 24: test 24 but on a sequence of scenes')

    test_env = './tst/'
    control_env = './control/'
    # shutil.rmtree(test_env, ignore_errors=True)
    # shutil.rmtree(control_env, ignore_errors=True)
    # path_setup(test_env)
    # path_setup(control_env)

    input_file = '/mnt/sda1/Animation.mkv'
    print('Preparing scenes for test file and using one')
    scenes = get_test_scenes(input_file, '/home/kokoniara/dev/VideoSplit/hoeEncode/ConvexHullEncoding/animation.json')

    # reduction = (control_stats.filesize - test_stats.filesize) / control_stats.filesize * 100
    #
    # reduction = reduction * -1
    #
    # vmaf_improvement = (test_stats.vmaf_score - control_stats.vmaf_score) / control_stats.vmaf_score * 100
    #
    # print(f'\nFile size change compared to control: {reduction:.2f}%')
    # print(f'VMAF change to control: {vmaf_improvement:.2f}%')

    sequence_lenght = 5
    sequence_start = 0

    # new scene list
    new_scene_list = scenes if sequence_lenght == -1 else \
        scenes[sequence_start:sequence_start + min(sequence_lenght, len(scenes) - sequence_start)]


    # test
    jobs = [EncoderJob(ChunkObject(path=input_file, first_frame_index=scene[0], last_frame_index=scene[1]), i,
                       f'{test_env}{i}.ivf') for i, scene in enumerate(new_scene_list)]

    config_test = EncoderConfigObject(temp_folder=test_env, two_pass=True, bitrate=1000, grain_synth=0)
    cvmands = [ConvexEncoder(job, copy.deepcopy(config_test)) for job in jobs]
    for conx in cvmands:
        conx.flag_21 = (True, bias_pct)
        conx.flag_19 = True

    print('\nStarting test')
    process_map(run_kummand,
                cvmands,
                max_workers=5,
                chunksize=1,
                desc='Encoding Complexity Seq TEST',
                unit="scene")

    print('\n\nDone with test, starting control')

    # control
    jobs = [EncoderJob(ChunkObject(path=input_file, first_frame_index=scene[0], last_frame_index=scene[1]), i,
                       f'{control_env}{i}.ivf') for i, scene in enumerate(new_scene_list)]

    config_control = EncoderConfigObject(temp_folder=control_env, two_pass=True, bitrate=1000, grain_synth=0)
    process_map(run_kummand,
                [ConvexEncoder(job, copy.deepcopy(config_control)) for job in jobs],
                max_workers=5,
                chunksize=1,
                desc='Encoding Complexity Seq CONTROL',
                unit="scene")

    c_test = VideoConcatenator(output='test.webm', file_with_audio=input_file)
    c_test.find_files_in_dir(test_env, 'ivf')
    c_test.concat_videos()

    c_control = VideoConcatenator(output='control.webm', file_with_audio=input_file)
    c_control.find_files_in_dir(control_env, 'ivf')
    c_control.concat_videos()


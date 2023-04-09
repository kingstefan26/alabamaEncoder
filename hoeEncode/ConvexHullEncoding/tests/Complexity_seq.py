import copy
import shutil

from hoeEncode.ConvexHullEncoding.ConvexHull import ConvexEncoder
from hoeEncode.ConvexHullEncoding.tests.TestUtil import path_setup, get_test_scenes, get_a_chunk
from hoeEncode.encode.ffmpeg.ChunkOffset import ChunkObject
from hoeEncode.encode.ffmpeg.FfmpegUtil import EncoderConfigObject, EncoderJob
from paraliezeMeHoe.ThaVaidioEncoda import run_kummand

if __name__ == '__main__':
    # setup
    test_env = './seq_complexity_test/'
    shutil.rmtree('./complexity_test/', ignore_errors=True)
    path_setup(test_env)

    input_file = '/mnt/sda1/movies/Tetris (2023)/Tetris.2023.1080p.WEB.H264-NAISU[rarbg].mkv'
    scenes = get_test_scenes(input_file, '/home/kokoniara/dev/VideoSplit/hoeEncode/ConvexHullEncoding/scenecache.json')

    chunk = get_a_chunk(53, scenes, input_file)

    job = EncoderJob(chunk, 0, test_env + 'chunk.ivf')
    config = EncoderConfigObject()
    config.temp_folder = test_env
    config.two_pass = True
    config.bitrate = '1000k'

    # test
    sequence_lenght = 20
    sequence_start = 1564

    # new scene list
    new_scene_list = []
    if sequence_lenght != -1:
        for i in range(sequence_start, sequence_start + sequence_lenght):
            new_scene_list.append(scenes[i])
    elif sequence_lenght == -1:
        new_scene_list = scenes

    jobs = []
    for i, scene in enumerate(new_scene_list):
        jobs.append(EncoderJob(ChunkObject(
            path=input_file,
            first_frame_index=scene[0],
            last_frame_index=scene[1]
        ), i, f'{test_env}{i}.ivf'))

    config = EncoderConfigObject()
    config.temp_folder = test_env
    config.two_pass = True
    config.bitrate = "1000k"

    from hoeEncode.ConvexHullEncoding.AutoGrain import get_best_avg_grainsynth

    config.grain_synth = get_best_avg_grainsynth(scenes=scenes,
                                                 input_file=input_file,
                                                 random_pick=3,
                                                 cache_filename='grainsynthcache.json',
                                                 temp_folder=test_env)

    print("AutoGrainSynth: " + str(config.grain_synth))

    if config.grain_synth == -1:
        raise Exception("AutoGrainSynth failed")

    cvmands = []

    for job in jobs:  # 😀
        conx = ConvexEncoder(job, copy.deepcopy(config))
        conx.flag_14 = True
        conx.flag_11 = False
        # conx.flag_15 = True
        conx.encode_speed = 5
        cvmands.append(conx)

    from tqdm.contrib.concurrent import process_map

    process_map(run_kummand,
                cvmands,
                max_workers=5,
                chunksize=1,
                desc='Encoding Complexity Seq',
                unit="scene")

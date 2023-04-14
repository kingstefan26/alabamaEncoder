import copy
import os
import shutil

from hoeEncode.ConvexHullEncoding.ConvexHull import ConvexEncoder
from hoeEncode.ConvexHullEncoding.tests.TestUtil import path_setup, get_test_scenes, get_a_chunk
from hoeEncode.encode.encoderImpl.Svtenc import AbstractEncoderSvtenc
from hoeEncode.encode.ffmpeg.ChunkOffset import ChunkObject
from hoeEncode.encode.ffmpeg.FfmpegUtil import EncoderConfigObject, EncoderJob
from paraliezeMeHoe.ThaVaidioEncoda import run_kummand, CliKummand

if __name__ == '__main__':
    # setup
    test_env = './seq_complexity_test/'
    test_env_nor = './seq_complexity_test_nor/'
    shutil.rmtree('./complexity_test/', ignore_errors=True)
    path_setup(test_env)
    path_setup(test_env_nor)

    input_file = '/mnt/sda1/shows/The Chilling Adventures of Sabrina/Season 1/[TorrentCouch.net].The.Chilling.Adventures.Of.Sabrina.S01E04.720p.WEBRip.x264.mp4'
    scenes = get_test_scenes(input_file, '/home/kokoniara/dev/VideoSplit/hoeEncode/ConvexHullEncoding/scenecache.json')

    # test
    sequence_lenght = 20
    sequence_start = 584

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
    config.bitrate = "500k"

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

    do_normal = True

    if do_normal is False:
        quit()


    jobs = []

    for i, scene in enumerate(new_scene_list):
        jobs.append(EncoderJob(ChunkObject(
            path=input_file,
            first_frame_index=scene[0],
            last_frame_index=scene[1]
        ), i, f'{test_env_nor}{i}.ivf'))

    cvmands = []


    for job in jobs:  # 😀
        if not os.path.exists(job.encoded_scene_path):
            svt = AbstractEncoderSvtenc()
            svt.eat_job_config(job, config)
            cli_cvmd = CliKummand()
            cli_cvmd.add_infile_dependency(job.encoded_scene_path)
            cli_cvmd.kummands = svt.get_encode_commands()
            cvmands.append(cli_cvmd)

    process_map(run_kummand,
                cvmands,
                max_workers=7,
                chunksize=1,
                desc='Encoding Complexity Seq Normal',
                unit="scene")

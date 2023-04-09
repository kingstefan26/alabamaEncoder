import copy
import os
import shutil

from hoeEncode.ConvexHullEncoding import ConvexHull
from hoeEncode.ConvexHullEncoding.ConvexHull import ConvexEncoder, ConvexKummand
from hoeEncode.ConvexHullEncoding.tests.TestUtil import path_setup, get_test_scenes, get_a_chunk
from hoeEncode.encode.ffmpeg.ChunkOffset import ChunkObject
from hoeEncode.encode.ffmpeg.FfmpegUtil import EncoderConfigObject, EncoderJob
from paraliezeMeHoe.ThaVaidioEncoda import run_kummand

if __name__ == '__main__':
    # setup
    test_env = './complexity_test/'
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
    print("Calculating complexity")

    convex = ConvexEncoder(job, config)

    print(convex.calculate_complexity())
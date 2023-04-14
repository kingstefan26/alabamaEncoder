import shutil

from hoeEncode.ConvexHullEncoding.ConvexHull import ConvexEncoder
from hoeEncode.ConvexHullEncoding.tests.TestUtil import path_setup, get_test_scenes, get_a_chunk
from hoeEncode.encode.ffmpeg.FfmpegUtil import EncoderConfigObject, EncoderJob

if __name__ == '__main__':
    print("Test 18: Testing if doing CQ-VBV instead of CQ for complexity estimation does something?")

    # setup
    test_env = './tst/'
    shutil.rmtree(test_env, ignore_errors=True)
    path_setup(test_env)

    input_file = '/mnt/sda1/shows/The Chilling Adventures of Sabrina/Season 1/[TorrentCouch.net].The.Chilling.Adventures.Of.Sabrina.S01E04.720p.WEBRip.x264.mp4'
    print('Preparing scenes for test file and using one')
    scenes = get_test_scenes(input_file, '/home/kokoniara/dev/VideoSplit/hoeEncode/ConvexHullEncoding/scenecache.json')

    chunk = get_a_chunk(152, scenes, input_file)

    job = EncoderJob(chunk, 0, '')
    config = EncoderConfigObject(temp_folder=test_env, two_pass=True, bitrate=500, grain_synth=0)



    job.encoded_scene_path = 'control.ivf'
    print("Running control")
    enc_control = ConvexEncoder(job, config)
    enc_control.run()

    job.encoded_scene_path = 'test.ivf'
    print("Running test")
    enc_test = ConvexEncoder(job, config)
    enc_test.flag_18 = True
    shutil.rmtree(test_env, ignore_errors=True)
    path_setup(test_env)
    enc_test.run()

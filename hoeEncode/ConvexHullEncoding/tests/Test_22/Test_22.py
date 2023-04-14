import shutil

from hoeEncode.ConvexHullEncoding.ConvexHull import ConvexEncoder
from hoeEncode.ConvexHullEncoding.tests.TestUtil import path_setup, get_test_scenes, get_a_chunk
from hoeEncode.encode.ffmpeg.FfmpegUtil import EncoderConfigObject, EncoderJob

if __name__ == '__main__':
    bias_pct = 8
    print(f'Test 22: use low bias-pct ({bias_pct}) value for final encode AND use VBR target to calculate complexity factor')

    test_env = './tst/'
    shutil.rmtree(test_env, ignore_errors=True)
    path_setup(test_env)

    input_file = '/mnt/sda1/shows/The Chilling Adventures of Sabrina/Season 1/[TorrentCouch.net].The.Chilling.Adventures.Of.Sabrina.S01E04.720p.WEBRip.x264.mp4'
    print('Preparing scenes for test file and using one')
    scenes = get_test_scenes(input_file,
                             '/home/kokoniara/dev/VideoSplit/hoeEncode/ConvexHullEncoding/scenecache.json')

    chunk = get_a_chunk(152, scenes, input_file)

    config = EncoderConfigObject(temp_folder=test_env, two_pass=True, bitrate=500, grain_synth=0)

    print('\nRunning control')
    enc_control = ConvexEncoder(EncoderJob(chunk, 0, 'control.ivf'), config)
    control_stats = enc_control.run()

    print('\nRunning test')
    enc_test = ConvexEncoder(EncoderJob(chunk, 0, 'test.ivf'), config)
    enc_test.flag_21 = (True, bias_pct)
    enc_test.flag_19 = True
    test_stats = enc_test.run()

    reduction = (control_stats.filesize - test_stats.filesize) / control_stats.filesize * 100

    vmaf_improvement = (test_stats.vmaf_score - control_stats.vmaf_score) / control_stats.vmaf_score * 100

    print(f'\nFile size reduction compared to control: {reduction:.2f}%')
    print(f'VMAF improvement compared to control: {vmaf_improvement:.2f}%')

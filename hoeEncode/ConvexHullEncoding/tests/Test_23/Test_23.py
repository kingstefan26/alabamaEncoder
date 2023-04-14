import shutil

from hoeEncode.ConvexHullEncoding.ConvexHull import ConvexEncoder
from hoeEncode.ConvexHullEncoding.tests.TestUtil import path_setup, get_test_scenes, get_a_chunk
from hoeEncode.encode.ffmpeg.FfmpegUtil import EncoderConfigObject, EncoderJob

bias_pct = 8


def do_test(path, index):
    test_env = f'./tst{index}/'
    shutil.rmtree(test_env, ignore_errors=True)
    path_setup(test_env)

    scenes = get_test_scenes(path, f'/home/kokoniara/dev/VideoSplit/hoeEncode/ConvexHullEncoding/scenecache{index}.json')

    chunk = get_a_chunk(4, scenes, path)

    config = EncoderConfigObject(temp_folder=test_env, two_pass=True, bitrate=1000, grain_synth=0)

    enc_control = ConvexEncoder(EncoderJob(chunk, 0, f'control{index}.ivf'), config)
    control_stats = enc_control.run()

    enc_test = ConvexEncoder(EncoderJob(chunk, 0, f'test{index}.ivf'), config)
    enc_test.flag_21 = (True, bias_pct)
    enc_test.flag_19 = True
    test_stats = enc_test.run()

    reduction = (control_stats.filesize - test_stats.filesize) / control_stats.filesize * 100

    vmaf_improvement = (test_stats.vmaf_score - control_stats.vmaf_score) / control_stats.vmaf_score * 100

    return (reduction, vmaf_improvement)


if __name__ == '__main__':
    print('Test 23: test 22 but few different chunks')

    paths = {
        "Stop motion": "/mnt/sda1/stopmotion.mkv",
        "2d animation": "/mnt/sda1/Animation.mkv",
        "live action": "/mnt/sda1/liveAction.mkv"
    }

    rslts = []

    for i, (name, path) in enumerate(paths.items()):
        reduction, vmaf_improvement = do_test(path, i)
        rslts.append((reduction, vmaf_improvement, name))

    print('\nResults:')
    for reduction, vmaf_improvement, name in rslts:
        print(f'{name}: {reduction:.2f}% reduction, {vmaf_improvement:.2f}% VMAF improvement')
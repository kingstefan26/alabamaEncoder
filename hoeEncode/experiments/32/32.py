"""
Testing chroma offest in svtenc
"""
import os

from hoeEncode.encoders.RateDiss import RateDistribution
from hoeEncode.encoders.encoderImpl.Svtenc import AbstractEncoderSvtenc
from hoeEncode.experiments.TestUtil import path_setup
from hoeEncode.ffmpegUtil import get_total_bitrate, get_video_vmeth, get_video_ssim
from hoeEncode.sceneSplit.ChunkOffset import ChunkObject


def do_runs():
    print("| _xyz_ |  size  | kpbs | vmaf  | DB Change % | \n |----------|:------:|:----:|:-----:|:-----------:|")
    zero_dbrate = -1
    for chroma_thing in [0, -2, -1]:
        print(f'\nRunning chroma thing {chroma_thing}')
        svtenc.chroma_thing = chroma_thing
        svtenc.update(output_path=f'{test_env}chrm{chroma_thing}.ivf')
        if svtenc.rate_distribution != RateDistribution.VBR:
            return
        print(svtenc.get_encode_commands())
        quit()
        svtenc.run(override_if_exists=False)
        size = os.path.getsize(svtenc.output_path) / 1000
        bps = int(get_total_bitrate(svtenc.output_path) / 1000)
        vmaf = get_video_vmeth(distorted_path=svtenc.output_path,
                               in_chunk=chunk,
                               crop_string=crope_stringe,
                               phone_model=False,
                               uhd_model=True)
        ssim = get_video_ssim(distorted_path=svtenc.output_path,
                              in_chunk=chunk,
                              crop_string=crope_stringe)
        curr_db_rate = size / vmaf
        if chroma_thing == 0:
            zero_dbrate = curr_db_rate

        print(f'size: {size}k, {bps}kbps, {vmaf}vmaf, {ssim}ssim')
        change_from_zero = (curr_db_rate - zero_dbrate) / zero_dbrate * 100
        print(f'| {chroma_thing} | {size}kb | {bps} | {vmaf} |  {change_from_zero}% |')


if __name__ == '__main__':
    paths = ['/mnt/data/liveAction_normal.mp4', '/mnt/data/liveAction_highMotion.mkv', '/mnt/data/Animation.mkv',
             '/mnt/data/stopmotion.mkv', '/mnt/data/liveAction_4k.mp4', '/mnt/data/liveaction_bright.mkv']
    # paths = ['/mnt/data/liveAction_4k.mp4']

    for path in paths:
        print(f'\n\nDoing: {path}')
        chunk = ChunkObject(path=path, first_frame_index=0, last_frame_index=200)

        crope_stringe = ''

        if 'liveAction_normal' in path:
            # clip is 4k but we only want to encode 1080p, also map from hdr
            crope_stringe = 'crop=3808:1744:28:208,scale=-2:1080:flags=lanczos,zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=reinhard:desat=0,zscale=t=bt709:m=bt709:r=tv'
        elif 'liveAction_highMotion' in path:
            # crop black borders
            crope_stringe = 'crop=1920:800:0:140'
        elif 'liveAction_4k' in path:
            # the same clip as liveAction_normal but in we dont scale down to 1080p
            crope_stringe = 'crop=3808:1744:28:208,zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=reinhard:desat=0,zscale=t=bt709:m=bt709:r=tv'
        elif 'liveaction_bright' in path:
            crope_stringe = 'crop=1920:960:0:60'

        svtenc = AbstractEncoderSvtenc()

        test_env = './tstCRF' + path.split('/')[-1].split('.')[0] + '/'
        # shutil.rmtree(test_env, ignore_errors=True)
        path_setup(test_env)
        svtenc.update(crf=18, speed=4, passes=1, chunk=chunk, current_scene_index=0, threads=8,
                      crop_string=crope_stringe, svt_grain_synth=3)
        svtenc.keyint = -2
        svtenc.chroma_thing = 0
        svtenc.open_gop = False

        print('\nCrf 18:')
        do_runs()

        test_env = './tstVBR' + path.split('/')[-1].split('.')[0] + '/'
        # shutil.rmtree(test_env, ignore_errors=True)
        path_setup(test_env)

        svtenc.update(rate_distribution=RateDistribution.VBR, bitrate=1500, passes=3)
        if 'liveAction_normal' in path:
            svtenc.update(bitrate=1000)
        elif 'liveAction_highMotion' in path:
            svtenc.update(bitrate=2000)
        elif 'Animation' in path:
            svtenc.update(bitrate=1500)
        elif 'stopmotion' in path:
            svtenc.update(bitrate=3000)
        elif 'liveAction_4k' in path:
            svtenc.update(bitrate=4000)
        elif 'liveaction_bright' in path:
            svtenc.update(bitrate=1000)

        svtenc.update(rate_distribution=RateDistribution.VBR, bitrate=2000, passes=3)
        print(f'\nVbr {svtenc.bitrate}:')
        svtenc.keyint = 999
        svtenc.bias_pct = 50
        do_runs()

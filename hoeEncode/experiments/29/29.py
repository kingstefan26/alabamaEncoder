import os.path
import shutil

from hoeEncode.encoders.RateDiss import RateDistribution
from hoeEncode.encoders.encoderImpl.Svtenc import AbstractEncoderSvtenc
from hoeEncode.experiments.TestUtil import path_setup
from hoeEncode.ffmpegUtil import get_video_vmeth, get_video_ssim, get_total_bitrate
from hoeEncode.sceneSplit.ChunkOffset import ChunkObject


def do_runs():
    svtenc.qm_enabled = True
    for mqm, mxqm in [(8, 15), (0, 15)]:
        print(f'\nRunning with min {mqm} and max {mxqm}')
        svtenc.qm_min = mqm
        svtenc.qm_max = mxqm
        svtenc.update(output_path=f'{test_env}liveaction_min{mqm}_max{mxqm}.ivf')
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
        print(f'size: {size}k, {bps}kbps, {vmaf}vmaf, {ssim}ssim')

    print('\nRunning without quantisation matrices')
    svtenc.qm_enabled = False
    svtenc.update(output_path=f'{test_env}liveaction_no_qm.ivf')
    svtenc.run()
    size = os.path.getsize(svtenc.output_path) / 1000
    bps = int(get_total_bitrate(svtenc.output_path) / 1000)
    vmaf = get_video_vmeth(distorted_path=svtenc.output_path, in_chunk=chunk, crop_string=crope_stringe,
                           phone_model=False,
                           uhd_model=True)
    ssim = get_video_ssim(distorted_path=svtenc.output_path, in_chunk=chunk, crop_string=crope_stringe)
    print(f'size: {size}k, {bps}kbps, {vmaf}vmaf, {ssim}ssim')

if __name__ == '__main__':
    print('Test 29: experimenting with quantisation matrices')


    # live_action = '/mnt/data/liveAction_normal.mp4'
    # live_action = '/mnt/data/liveAction_highMotion.mkv'
    # live_action = '/mnt/data/Animation.mkv'
    live_action = '/mnt/data/stopmotion.mkv'

    chunk = ChunkObject(path=live_action, first_frame_index=0, last_frame_index=200)

    # crope_stringe = 'crop=3808:1744:28:208,scale=-2:1080:flags=lanczos,zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv'
    crope_stringe = ''
    # crope_stringe = 'crop=1920:800:0:140'

    svtenc = AbstractEncoderSvtenc()

    test_env = './tstCRF/'
    shutil.rmtree(test_env, ignore_errors=True)
    path_setup(test_env)
    svtenc.update(crf=18, speed=4, passes=1, chunk=chunk, current_scene_index=0, threads=8,
                  crop_string=crope_stringe, svt_grain_synth=3)
    svtenc.keyint = -2
    svtenc.chroma_thing = False
    svtenc.open_gop = False


    print('Crf 18:')
    do_runs()

    test_env = './tstVBR/'
    shutil.rmtree(test_env, ignore_errors=True)
    path_setup(test_env)

    svtenc.update(rate_distribution=RateDistribution.VBR, bitrate=3000, passes=3)
    print(f'Vbr {svtenc.bitrate}:')
    svtenc.keyint = 240
    svtenc.bias_pct = 90
    do_runs()


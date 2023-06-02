"""
Experimenting with svtav1 super resolution
"""
import os

"""
From SVT-AV1 git:

SuperresMode
--superres-mode [0-4] 0 Enable super-resolution mode, 
refer to the super-resolution section below for more info


SuperresDenom
--superres-denom [8-16] default:8 Super-resolution denominator, 
only applicable for mode == 1 [8: no scaling, 16: half-scaling]


SuperresKfDenom
--superres-kf-denom [8-16] default:8 
Super-resolution denominator for key frames, only applicable for mode == 1 [8: no scaling, 16: half-scaling]


SuperresQthres
--superres-qthres [0-63] default:43 
Super-resolution q-threshold, only applicable for mode == 3


SuperresKfQthres
--superres-kf-qthres [0-63] default:43 Super-resolution q-threshold for key frames, only applicable for mode == 3


Super resolution is better described in the Super-Resolution documentation,
but this basically allows the input to be encoded at a lower resolution,
horizontally, but then later upscaled back to the original resolution by the
decoder.
SuperresMode
0: None, no frame super-resolution allowed
1: All frames are encoded at the specified scale of 8/denom, thus a denom of 8 means no scaling, and 16 means half-scaling
2: All frames are coded at a random scale
3: Super-resolution scale for a frame is determined based on the q_index, a qthreshold of 63 means no scaling
4: Automatically select the super-resolution mode for appropriate frames

The performance of the encoder will be affected for all modes other than mode
0. And for mode 4, it should be noted that the encoder will run at least twice,
one for down scaling, and another with no scaling, and then it will choose the
best one for each of the appropriate frames.
"""

from hoeEncode.encoders.RateDiss import RateDistribution
from hoeEncode.encoders.encoderImpl.Svtenc import AbstractEncoderSvtenc
from hoeEncode.sceneSplit.ChunkOffset import ChunkObject

if __name__ == '__main__':
    # paths = ['/mnt/data/liveAction_normal.mp4', '/mnt/data/liveAction_highMotion.mkv', '/mnt/data/Animation.mkv',
    #          '/mnt/data/stopmotion.mkv', '/mnt/data/liveAction_4k.mp4', '/mnt/data/liveaction_bright.mkv']
    paths = [
        '/mnt/data/liveAction_normal.mp4',
        '/mnt/data/liveAction_highMotion.mkv',
        '/mnt/data/liveaction_bright.mkv'
    ]

    for path in paths:
        print(f'\n\n## Doing: {path}')
        chunk = ChunkObject(path=path, first_frame_index=0, last_frame_index=200)

        test_env = './tstCRF' + path.split('/')[-1].split('.')[0] + '/'
        # shutil.rmtree(test_env, ignore_errors=True)
        if not os.path.exists(test_env):
            os.mkdir(test_env)

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

        svtenc.update()
        svtenc.svt_chroma_thing = 0
        svtenc.keyint = -2
        svtenc.svt_bias_pct = 50
        svtenc.svt_open_gop = False

        svtenc.update(
            rate_distribution=RateDistribution.CQ,
            crf=18,
            passes=1,
            chunk=chunk,
            current_scene_index=0,
            threads=12,
            crop_string=crope_stringe,
            svt_grain_synth=3
        )

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

        print(f'CRF {svtenc.bitrate}\n')
        print(
            f"| _super res mode_ |  time taken  | kpbs | vmaf  | BD Change % | time Change % |\n"
            "|----------|:------:|:----:|:-----:|:-----------:|:---:|"
        )
        no_sres_dbrate = -1
        nosres_time = -1
        for superres in [0, 1, 3]:
            svtenc.update(output_path=f'{test_env}superres{superres}.ivf')
            svtenc.svt_supperres_mode = superres
            stats = svtenc.run(override_if_exists=False, calculate_vmaf=True)
            stats.time_encoding = round(stats.time_encoding, 2)

            curr_db_rate = stats.size / stats.vmaf
            if superres == 0:
                nosres_time = stats.time_encoding
                no_sres_dbrate = curr_db_rate

            change_from_zero = (curr_db_rate - no_sres_dbrate) / no_sres_dbrate * 100
            change_from_zero = round(change_from_zero, 2)
            change_from_zero_time = (stats.time_encoding - nosres_time) / nosres_time * 100
            change_from_zero_time = round(change_from_zero_time, 2)
            print(
                f'| {superres} |'
                f' {stats.time_encoding}s |'
                f' {stats.bitrate} '
                f'| {round(stats.vmaf, 2)} | '
                f' {change_from_zero}% |'
                f' {change_from_zero_time}% |')

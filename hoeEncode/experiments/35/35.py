"""
Experimenting with s frames with high gops for VBR in SVT-AV1
"""
import os

from hoeEncode.encoders.RateDiss import RateDistribution
from hoeEncode.encoders.encoderImpl.Svtenc import AbstractEncoderSvtenc
from hoeEncode.sceneSplit.ChunkOffset import ChunkObject

if __name__ == '__main__':
    # paths = ['/mnt/data/liveAction_normal.mp4', '/mnt/data/liveAction_highMotion.mkv', '/mnt/data/Animation.mkv',
    #          '/mnt/data/stopmotion.mkv', '/mnt/data/liveAction_4k.mp4', '/mnt/data/liveaction_bright.mkv']
    paths = [
        '/mnt/data/liveAction_normal.mp4',
        '/mnt/data/liveAction_highMotion.mkv',
        '/mnt/data/liveaction_bright.mkv',
        '/mnt/data/liveAction_4k.mp4'
    ]

    for path in paths:
        print(f'\n\n## Doing: {path}')
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

        svtenc.update()
        svtenc.svt_chroma_thing = 0
        svtenc.keyint = 9999
        svtenc.svt_bias_pct = 50
        svtenc.svt_open_gop = False

        test_env = './tstVBR' + path.split('/')[-1].split('.')[0] + '/'
        # shutil.rmtree(test_env, ignore_errors=True)
        if not os.path.exists(test_env):
            os.mkdir(test_env)

        svtenc.update(
            rate_distribution=RateDistribution.VBR,
            passes=3,
            chunk=chunk,
            current_scene_index=0,
            threads=12,
            crop_string=crope_stringe,
            svt_grain_synth=3,
            speed=4
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

        print(f'Vbr {svtenc.bitrate}\n')
        print(
            f"| _sframe dist_ |  time taken  | kpbs | vmaf  | BD Change % | time Change % |\n"
            "|----------|:------:|:----:|:-----:|:-----------:|:---:|"
        )
        no_sres_dbrate = -1
        nosres_time = -1
        for sframe_dist in [0, 240]:
            svtenc.update(output_path=f'{test_env}sframe_dist{sframe_dist}.ivf')
            svtenc.svt_sframe_interval = sframe_dist
            stats = svtenc.run(override_if_exists=False, calculate_vmaf=True)

            curr_db_rate = stats.size / stats.vmaf
            if sframe_dist == 0:
                nosres_time = stats.time_encoding
                no_sres_dbrate = curr_db_rate

            change_from_zero = (curr_db_rate - no_sres_dbrate) / no_sres_dbrate * 100
            change_from_zero_time = (stats.time_encoding - nosres_time) / nosres_time * 100
            print(
                f'| {sframe_dist} |'
                f' {stats.time_encoding}s |'
                f' {stats.bitrate} '
                f'| {stats.vmaf} | '
                f' {change_from_zero}% |'
                f' {change_from_zero_time}% |')